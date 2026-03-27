"""
orca.py — Cliente Orca Whirlpools (Solana) para o OpenClaw API Gateway.
"""
from .._base_dex import BaseDEXClient


class OrcaClient(BaseDEXClient):

    NAME          = "orca"
    BASE_URL      = "https://api.orca.so"
    CALLS_PER_MIN = 30
    CACHE_TTL     = 900
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["pools", "tvl", "volume", "apr"]

    def _health_check(self):
        self.session.get(self.BASE_URL + "/v1/whirlpool/list", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type in ("pools", "pools_solana"):
            return self._top_pools(kwargs.get("min_tvl", 100_000))
        raise ValueError(f"OrcaClient não suporta: {data_type}")

    def _top_pools(self, min_tvl: float = 100_000) -> dict:
        data  = self.get("/v1/whirlpool/list")
        whirlpools = data.get("whirlpools", []) if isinstance(data, dict) else []
        pools = []
        for p in whirlpools:
            tvl = float(p.get("tvl", 0))
            if tvl < min_tvl:
                continue
            apy = float(p.get("apy", {}).get("day", {}).get("feeApy", 0)) * 100 if isinstance(p.get("apy"), dict) else 0
            pools.append({
                "pool_id":    p.get("address", ""),
                "protocol":   "orca",
                "chain":      "Solana",
                "token0":     p.get("tokenA", {}).get("symbol", "") if isinstance(p.get("tokenA"), dict) else "",
                "token1":     p.get("tokenB", {}).get("symbol", "") if isinstance(p.get("tokenB"), dict) else "",
                "symbol":     p.get("name", ""),
                "fee_tier":   float(p.get("feeRate", 0)) / 10000,
                "tvl_usd":    tvl,
                "volume_24h": float(p.get("volume", {}).get("day", 0)) if isinstance(p.get("volume"), dict) else 0,
                "apr_base":   apy,
                "apr_total":  apy,
                "source":     "orca",
            })
        pools.sort(key=lambda x: x["tvl_usd"], reverse=True)
        return {"pools": pools[:50], "total": len(pools), "chain": "Solana", "source": "orca"}
