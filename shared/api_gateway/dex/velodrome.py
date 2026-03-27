"""
velodrome.py — Cliente Velodrome Finance (Optimism) para o OpenClaw API Gateway.
"""
from .._base_dex import BaseDEXClient
from ..normalizer import DataNormalizer


class VelodromeClient(BaseDEXClient):

    NAME          = "velodrome"
    BASE_URL      = "https://api.velodrome.finance/api/v1"
    CALLS_PER_MIN = 60
    CACHE_TTL     = 900
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["pools", "tvl", "volume", "apr", "emissions"]

    def _health_check(self):
        self.session.get(self.BASE_URL + "/pairs", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type in ("pools", "pools_evm"):
            return self._pools(
                min_tvl=kwargs.get("min_tvl", 500_000),
                min_apr=kwargs.get("min_apr", 3.0),
            )
        raise ValueError(f"VelodromeClient não suporta: {data_type}")

    def _pools(self, min_tvl: float = 500_000, min_apr: float = 3.0) -> dict:
        data = self.get("/pairs")
        pairs = data.get("data", []) if isinstance(data, dict) else data
        normalized = []
        for p in pairs:
            tvl = float(p.get("tvl") or p.get("reserve0", 0))
            apr = float(p.get("apr") or p.get("gauge", {}).get("apr", 0) if isinstance(p.get("gauge"), dict) else 0)
            if tvl < min_tvl or apr < min_apr:
                continue
            item = {
                "pool_id":    p.get("address", ""),
                "protocol":   "velodrome",
                "chain":      "Optimism",
                "token0":     p.get("token0", {}).get("symbol", "") if isinstance(p.get("token0"), dict) else "",
                "token1":     p.get("token1", {}).get("symbol", "") if isinstance(p.get("token1"), dict) else "",
                "symbol":     p.get("symbol", ""),
                "fee_tier":   float(p.get("fee", 0)) / 100,
                "tvl_usd":    tvl,
                "volume_24h": float(p.get("volume24h", 0)),
                "apr_base":   float(p.get("baseApr", 0)),
                "apr_reward": apr,
                "apr_total":  apr,
                "il_7d":      0.0,
                "yield_24h":  apr / 365,
                "risk_score": "MÉDIO",
                "source":     "velodrome",
            }
            normalized.append(item)
        normalized.sort(key=lambda x: x["tvl_usd"], reverse=True)
        return {"pools": normalized, "total": len(normalized), "chain": "Optimism", "source": "velodrome"}
