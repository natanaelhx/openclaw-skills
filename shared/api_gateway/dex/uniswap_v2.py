"""
uniswap_v2.py — Cliente Uniswap V2 para o OpenClaw API Gateway.
"""
from .._base_dex import BaseDEXClient


class UniswapV2Client(BaseDEXClient):

    NAME          = "uniswap_v2"
    BASE_URL      = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"
    CALLS_PER_MIN = 30
    CACHE_TTL     = 900
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["pools", "tvl", "volume"]

    def _health_check(self):
        body = {"query": "{ pairs(first: 1) { id } }"}
        resp = self.session.post(self.BASE_URL, json=body, timeout=8)
        resp.raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type in ("pools", "pools_evm"):
            return self._top_pairs(kwargs.get("min_tvl", 500_000))
        raise ValueError(f"UniswapV2Client não suporta: {data_type}")

    def _top_pairs(self, min_tvl: float = 500_000) -> dict:
        import json, time, requests as _req
        query = """
        {
          pairs(first: 50, orderBy: reserveUSD, orderDirection: desc) {
            id
            token0 { symbol }
            token1 { symbol }
            reserveUSD
            volumeUSD
          }
        }
        """
        body = {"query": query}
        resp = self.session.post(self.BASE_URL, json=body, timeout=20)
        resp.raise_for_status()
        pairs = resp.json().get("data", {}).get("pairs", [])
        pools = []
        for p in pairs:
            tvl = float(p.get("reserveUSD", 0))
            if tvl < min_tvl:
                continue
            pools.append({
                "pool_id":    p.get("id", ""),
                "protocol":   "uniswap-v2",
                "chain":      "Ethereum",
                "token0":     p.get("token0", {}).get("symbol", ""),
                "token1":     p.get("token1", {}).get("symbol", ""),
                "symbol":     f"{p.get('token0',{}).get('symbol','')}/{p.get('token1',{}).get('symbol','')}",
                "fee_tier":   0.3,
                "tvl_usd":    tvl,
                "volume_24h": float(p.get("volumeUSD", 0)),
                "apr_base":   0.0,
                "apr_total":  0.0,
                "source":     "uniswap_v2",
            })
        return {"pools": pools, "total": len(pools), "source": "uniswap_v2"}
