"""
user_config.py — Configuração centralizada do OpenClaw.
Gerencia: tokens monitorados, alertas, API keys, preferências.
"""
import os
import json
from pathlib import Path

CONFIG_PATH = Path(os.path.expanduser("~/.moltbot/user_config.json"))
CONFIG_DIR  = CONFIG_PATH.parent

DEFAULT_CONFIG = {
    "tokens":   ["BTC", "ETH", "SOL"],
    "chains":   ["Ethereum", "Arbitrum", "Base", "Optimism", "Polygon"],
    "alerts": {
        "funding_high":  0.08,
        "funding_low":  -0.03,
        "min_apr":       3.0,
        "max_apr":      80.0,
        "min_tvl":   500000,
    },
    "api_keys": {
        "coinmarketcap": None,
        "dextools":      None,
        "coinglass":     None,
        "defillama_pro": None,
        "coingecko_pro": None,
    },
    "preferences": {
        "currency":    "USD",
        "language":    "pt-BR",
        "report_dir":  "~/liquidity_monitor/reports",
    },
}


class UserConfig:
    """Gerencia a configuração persistente do usuário."""

    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.config = self._load()

    def _load(self) -> dict:
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH) as f:
                    data = json.load(f)
                # Garante que api_keys existe
                if "api_keys" not in data:
                    data["api_keys"] = DEFAULT_CONFIG["api_keys"].copy()
                return data
            except (json.JSONDecodeError, OSError):
                pass
        # Cria config padrão
        self._save(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()

    def _save(self, config: dict = None):
        data = config or self.config
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ── Tokens ───────────────────────────────────────────────────────────────

    def get_tokens(self) -> list:
        return self.config.get("tokens", ["BTC", "ETH"])

    def add_token(self, symbol: str) -> dict:
        sym = symbol.upper()
        tokens = self.config.setdefault("tokens", [])
        if sym in tokens:
            return {"success": False, "message": f"{sym} já está na lista"}
        tokens.append(sym)
        self._save()
        return {"success": True, "message": f"{sym} adicionado", "tokens": tokens}

    def remove_token(self, symbol: str) -> dict:
        sym    = symbol.upper()
        tokens = self.config.get("tokens", [])
        if sym not in tokens:
            return {"success": False, "message": f"{sym} não encontrado"}
        tokens.remove(sym)
        self._save()
        return {"success": True, "message": f"{sym} removido", "tokens": tokens}

    # ── API Keys ─────────────────────────────────────────────────────────────

    def set_api_key(self, api_name: str, key: str) -> dict:
        """Salva API key após validação básica."""
        import importlib
        API_REGISTRY = importlib.import_module("api_gateway.registry").API_REGISTRY
        if api_name not in API_REGISTRY:
            return {"success": False, "message": f"API '{api_name}' não existe no registry"}
        if not key or len(key) < 8:
            return {"success": False, "message": "Key inválida (muito curta)"}
        api_keys = self.config.setdefault("api_keys", {})
        api_keys[api_name] = key
        self._save()
        return {"success": True, "message": f"Key de '{api_name}' salva com sucesso"}

    def remove_api_key(self, api_name: str) -> dict:
        """Remove API key (volta para endpoints públicos sem autenticação)."""
        api_keys = self.config.get("api_keys", {})
        if api_name not in api_keys or api_keys[api_name] is None:
            return {"success": False, "message": f"Sem key configurada para '{api_name}'"}
        api_keys[api_name] = None
        self._save()
        return {"success": True, "message": f"Key de '{api_name}' removida"}

    def list_api_keys(self) -> dict:
        """Lista APIs que têm key configurada (oculta o valor)."""
        api_keys = self.config.get("api_keys", {})
        result   = {}
        for name, key in api_keys.items():
            if key:
                result[name] = f"****{key[-4:]}" if len(key) >= 8 else "****"
            else:
                result[name] = None
        return result

    def get_api_key(self, api_name: str):
        """Retorna key de uma API (None se não configurada)."""
        return self.config.get("api_keys", {}).get(api_name)

    def get_all_api_keys(self) -> dict:
        """Retorna todas as keys (valores completos para uso interno)."""
        return {k: v for k, v in self.config.get("api_keys", {}).items() if v}

    # ── Alertas ──────────────────────────────────────────────────────────────

    def get_alerts(self) -> dict:
        return self.config.get("alerts", DEFAULT_CONFIG["alerts"].copy())

    def set_alert(self, key: str, value: float) -> dict:
        alerts = self.config.setdefault("alerts", {})
        if key not in DEFAULT_CONFIG["alerts"]:
            return {"success": False, "message": f"Alerta '{key}' desconhecido"}
        alerts[key] = value
        self._save()
        return {"success": True, "message": f"Alerta {key} = {value}"}

    # ── Chains ───────────────────────────────────────────────────────────────

    def get_chains(self) -> list:
        return self.config.get("chains", ["Ethereum", "Arbitrum", "Base"])

    def add_chain(self, chain: str) -> dict:
        chains = self.config.setdefault("chains", [])
        if chain in chains:
            return {"success": False, "message": f"{chain} já está na lista"}
        chains.append(chain)
        self._save()
        return {"success": True, "message": f"{chain} adicionada", "chains": chains}

    # ── Router ───────────────────────────────────────────────────────────────

    def get_router(self):
        """Retorna APIRouter configurado com as keys do usuário."""
        import importlib
        APIRouter = importlib.import_module("api_gateway.router").APIRouter
        return APIRouter(api_keys=self.get_all_api_keys())
