"""
pancakeswap.py — Cliente PancakeSwap V3 para o OpenClaw API Gateway.
"""
from .._base_dex import BaseDEXClient


class PancakeSwapClient(BaseDEXClient):

    NAME          = "pancakeswap"
    BASE_URL      = "https://api.thegraph.com/subgraphs/name/pancakeswap/exchange-v3-bsc"
    CALLS_PER_MIN = 60
    CACHE_TTL     = 900
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["pools", "tvl", "volume", "apr"]

    def _health_check(self):
        body = {"query": "{ pools(first: 1) { id } }"}
        resp = self.session.post(self.BASE_URL, json=body, timeout=8)
        resp.raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type in ("pools", "pools_evm"):
            return self._top_pools(kwargs.get("min_tvl", 500_000))
        raise ValueError(f"PancakeSwapClient não suporta: {data_type}")

    def _top_pools(self, min_tvl: float = 500_000) -> dict:
        query = """
        {
          pools(first: 50, orderBy: totalValueLockedUSD, orderDirection: desc) {
            id
            token0 { symbol }
            token1 { symbol }
            feeTier
            totalValueLockedUSD
            volumeUSD
          }
        }
        """
        body = {"query": query}
        resp = self.session.post(self.BASE_URL, json=body, timeout=20)
        resp.raise_for_status()
        pools_raw = resp.json().get("data", {}).get("pools", [])
        pools = []
        for p in pools_raw:
            tvl = float(p.get("totalValueLockedUSD", 0))
            if tvl < min_tvl:
                continue
            fee = float(p.get("feeTier", 0)) / 10000
            pools.append({
                "pool_id":    p.get("id", ""),
                "protocol":   "pancakeswap-v3",
                "chain":      "BSC",
                "token0":     p.get("token0", {}).get("symbol", ""),
                "token1":     p.get("token1", {}).get("symbol", ""),
                "symbol":     f"{p.get('token0',{}).get('symbol','')}/{p.get('token1',{}).get('symbol','')}",
                "fee_tier":   fee,
                "tvl_usd":    tvl,
                "volume_24h": float(p.get("volumeUSD", 0)),
                "apr_base":   0.0,
                "apr_total":  0.0,
                "source":     "pancakeswap",
            })
        return {"pools": pools, "total": len(pools), "source": "pancakeswap"}
