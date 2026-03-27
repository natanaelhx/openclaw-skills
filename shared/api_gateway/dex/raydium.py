"""
raydium.py — Cliente Raydium (Solana) para o OpenClaw API Gateway.
"""
from .._base_dex import BaseDEXClient


class RaydiumClient(BaseDEXClient):

    NAME          = "raydium"
    BASE_URL      = "https://api.raydium.io/v2"
    CALLS_PER_MIN = 60
    CACHE_TTL     = 900
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["pools", "tvl", "volume", "apr"]

    def _health_check(self):
        self.session.get(self.BASE_URL + "/main/info", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type in ("pools", "pools_solana"):
            return self._top_pools(kwargs.get("min_tvl", 100_000))
        raise ValueError(f"RaydiumClient não suporta: {data_type}")

    def _top_pools(self, min_tvl: float = 100_000) -> dict:
        data  = self.get("/main/pairs")
        pairs = data if isinstance(data, list) else []
        pools = []
        for p in pairs:
            tvl = float(p.get("liquidity", 0))
            if tvl < min_tvl:
                continue
            pools.append({
                "pool_id":    p.get("ammId", p.get("id", "")),
                "protocol":   "raydium",
                "chain":      "Solana",
                "token0":     p.get("name", "").split("-")[0] if "-" in p.get("name", "") else "",
                "token1":     p.get("name", "").split("-")[1] if "-" in p.get("name", "") else "",
                "symbol":     p.get("name", ""),
                "fee_tier":   0.25,
                "tvl_usd":    tvl,
                "volume_24h": float(p.get("volume24h", 0)),
                "apr_base":   float(p.get("apr24h", 0)),
                "apr_total":  float(p.get("apr24h", 0)),
                "source":     "raydium",
            })
        pools.sort(key=lambda x: x["tvl_usd"], reverse=True)
        return {"pools": pools[:50], "total": len(pools), "chain": "Solana", "source": "raydium"}
