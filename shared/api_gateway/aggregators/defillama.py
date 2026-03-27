"""
defillama.py — Cliente DefiLlama para o OpenClaw API Gateway.
Fonte primária para: TVL, pools, yields, APY multi-chain.
"""
from ..base_client import BaseAPIClient
from ..normalizer import DataNormalizer


class DefiLlamaClient(BaseAPIClient):

    NAME          = "defillama"
    BASE_URL      = "https://yields.llama.fi"
    BASE_TVL      = "https://api.llama.fi"
    BASE_COINS    = "https://coins.llama.fi"
    CALLS_PER_MIN = 300
    CACHE_TTL     = 1800  # 30min — dados de yield mudam devagar
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["tvl", "pools", "yields", "apr", "apy", "protocol_tvl",
                     "chain_tvl", "token_price"]

    def _health_check(self):
        self.session.get(self.BASE_TVL + "/chains", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type in ("pools_evm", "pools_solana", "pools"):
            return self._pools(
                chains=kwargs.get("chains"),
                min_tvl=kwargs.get("min_tvl", 500_000),
                min_apr=kwargs.get("min_apr", 3.0),
                protocols=kwargs.get("protocols"),
            )
        if data_type == "tvl":
            return self._protocol_tvl(kwargs.get("protocol", ""))
        if data_type == "token_price":
            return self._token_price(kwargs.get("coins", ""))
        raise ValueError(f"DefiLlamaClient não suporta: {data_type}")

    def _pools(self, chains=None, min_tvl=500_000, min_apr=3.0,
               protocols=None) -> dict:
        raw = self._get_abs(self.BASE_URL + "/pools")
        all_pools = raw.get("data", [])

        filtered = []
        for p in all_pools:
            if chains and p.get("chain") not in chains:
                continue
            if protocols and p.get("project") not in protocols:
                continue
            tvl = float(p.get("tvlUsd", 0))
            apr = float(p.get("apy") or 0)
            if tvl < min_tvl:
                continue
            if apr < min_apr:
                continue
            normalized = DataNormalizer._pool_from_defillama(p)
            filtered.append(normalized)

        filtered.sort(key=lambda x: x["tvl_usd"], reverse=True)
        return {
            "pools":   filtered,
            "total":   len(filtered),
            "source":  "defillama",
        }

    def _protocol_tvl(self, protocol: str) -> dict:
        data = self._get_abs(self.BASE_TVL + f"/protocol/{protocol}")
        return {
            "protocol": protocol,
            "tvl_usd":  float(data.get("tvl", [{}])[-1].get("totalLiquidityUSD", 0)) if data.get("tvl") else 0,
            "source":   "defillama",
        }

    def _token_price(self, coins: str) -> dict:
        data = self._get_abs(self.BASE_COINS + f"/prices/current/{coins}")
        return {"coins": data.get("coins", {}), "source": "defillama"}

    def get_pools_raw(self) -> list:
        """Retorna todos os pools sem filtro."""
        raw = self._get_abs(self.BASE_URL + "/pools")
        return raw.get("data", [])

    def get_chain_tvl(self) -> list:
        return self._get_abs(self.BASE_TVL + "/chains")

    def _get_abs(self, url: str, params: dict = None) -> dict:
        """GET com URL absoluta."""
        import json, time, requests as _req
        key = f"{url}:{json.dumps(params or {}, sort_keys=True)}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        self.rate_limiter.wait_if_needed()
        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                self.cache.set(key, data)
                return data
            except _req.exceptions.HTTPError as e:
                if e.response.status_code in [429, 502, 503, 504]:
                    time.sleep((2 ** attempt) * 2)
                else:
                    raise
            except (_req.exceptions.ConnectionError, _req.exceptions.Timeout):
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    raise
        raise Exception(f"Falha DefiLlama: {url}")
