"""
router.py — Roteador inteligente entre APIs do OpenClaw.
Roteia automaticamente cada tipo de dado para a melhor API disponível,
com fallback automático em caso de falha.
"""
import time
import importlib
from typing import Optional, List

from .registry import API_REGISTRY
from .normalizer import DataNormalizer


class APIRouter:
    """
    Roteia automaticamente cada tipo de dado para a melhor API disponível.
    Tenta automaticamente o próximo fallback em caso de erro.
    """

    PRIORITY_MAP = {
        "funding_rate": [
            "binance", "bybit", "okx", "bitget", "gate", "mexc", "htx",
        ],
        "open_interest": [
            "coinglass", "binance", "bybit", "okx", "bitget",
        ],
        "long_short_ratio": [
            "coinglass", "binance", "bybit", "bitget",
        ],
        "liquidations": [
            "coinglass", "binance", "bybit", "okx",
        ],
        "price": [
            "binance", "coingecko", "coinmarketcap",
            "dexscreener", "coinglass",
        ],
        "ohlcv": [
            "binance", "bybit", "okx", "kraken", "coinbase",
        ],
        "pools_evm": [
            "defillama", "uniswap_v3", "curve", "balancer",
            "aerodrome", "velodrome", "sushiswap", "pancakeswap",
        ],
        "pools_solana": [
            "defillama", "raydium", "orca",
        ],
        "tvl": [
            "defillama",
        ],
        "global_market": [
            "coingecko", "coinmarketcap", "coinglass",
        ],
        "token_pairs_dex": [
            "dexscreener", "dextools", "the_graph",
        ],
    }

    def __init__(self, api_keys: dict = None):
        """
        api_keys: dict opcional com {api_name: key_string}
        Pode vir do UserConfig.
        """
        self.api_keys  = api_keys or {}
        self._clients  = {}
        self._status   = {}  # {api_name: {"down_since": timestamp}}

    def get_client(self, api_name: str):
        """Retorna instância cacheada do cliente para a API solicitada."""
        if api_name not in self._clients:
            if api_name not in API_REGISTRY:
                raise ValueError(f"API desconhecida no registry: {api_name}")
            reg = API_REGISTRY[api_name]
            try:
                mod = importlib.import_module(reg["module"])
                cls = getattr(mod, reg["class"])
                key = self.api_keys.get(api_name)
                self._clients[api_name] = cls(api_key=key)
            except (ImportError, AttributeError) as e:
                raise ImportError(f"Não foi possível carregar {api_name}: {e}")
        return self._clients[api_name]

    def fetch(self, data_type: str, **kwargs) -> dict:
        """
        Busca um tipo de dado usando a melhor API disponível.
        Tenta automaticamente o próximo fallback em caso de erro.
        Retorna dados normalizados com campo '_source'.
        """
        apis = self.PRIORITY_MAP.get(data_type, [])
        if not apis:
            raise ValueError(f"Tipo de dado desconhecido: {data_type}")

        last_error = None
        tried = []
        for api_name in apis:
            if not self._is_up(api_name):
                continue
            try:
                client = self.get_client(api_name)
                result = client.fetch(data_type, **kwargs)
                result["_source"] = api_name
                result["_fallback_chain"] = tried
                return result
            except Exception as e:
                last_error = e
                tried.append(api_name)
                self._mark_down(api_name)
                print(f"  ⚠️ {api_name} falhou ({e}), tentando próxima...")
                continue

        raise Exception(
            f"Todas as APIs falharam para {data_type}: {last_error}"
        )

    def fetch_all_sources(self, data_type: str, **kwargs) -> list:
        """
        Busca o dado em TODAS as fontes e retorna lista para comparação cruzada.
        """
        results = []
        for api_name in self.PRIORITY_MAP.get(data_type, []):
            try:
                client = self.get_client(api_name)
                result = client.fetch(data_type, **kwargs)
                result["_source"] = api_name
                results.append(result)
            except Exception:
                continue
        return results

    def fetch_funding_rate(self, symbol: str) -> dict:
        """Atalho para funding rate com normalização automática."""
        return self.fetch("funding_rate", symbol=symbol)

    def fetch_pools(self, chains: list = None, min_tvl: float = 500_000,
                    min_apr: float = 3.0) -> list:
        """Atalho para pools EVM com normalização automática."""
        return self.fetch("pools_evm", chains=chains, min_tvl=min_tvl, min_apr=min_apr)

    def _is_up(self, api_name: str) -> bool:
        """Verifica status cacheado da API (5min cooldown após falha)."""
        status = self._status.get(api_name, {})
        if status.get("down_since"):
            if time.time() - status["down_since"] > 300:
                del self._status[api_name]
                return True
            return False
        return True

    def _mark_down(self, api_name: str):
        self._status[api_name] = {"down_since": time.time()}

    def reset_status(self, api_name: str = None):
        """Limpa status de down de uma ou todas as APIs."""
        if api_name:
            self._status.pop(api_name, None)
        else:
            self._status.clear()

    def list_available(self, data_type: str) -> List[str]:
        """Lista APIs disponíveis (online) para um tipo de dado."""
        return [a for a in self.PRIORITY_MAP.get(data_type, []) if self._is_up(a)]
