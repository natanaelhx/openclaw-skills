"""
aerodrome.py — Cliente Aerodrome Finance (Base) para o OpenClaw API Gateway.
"""
from .._base_dex import BaseDEXClient
from ..normalizer import DataNormalizer


class AerodromeClient(BaseDEXClient):

    NAME          = "aerodrome"
    BASE_URL      = "https://api.aerodrome.finance/api/v1"
    CALLS_PER_MIN = 60
    CACHE_TTL     = 900
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["pools", "tvl", "volume", "apr", "emissions", "gauges"]

    def _health_check(self):
        self.session.get(self.BASE_URL + "/pools", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type in ("pools", "pools_evm"):
            return self._pools(
                min_tvl=kwargs.get("min_tvl", 500_000),
                min_apr=kwargs.get("min_apr", 3.0),
            )
        raise ValueError(f"AerodromeClient não suporta: {data_type}")

    def _pools(self, min_tvl: float = 500_000, min_apr: float = 3.0) -> dict:
        data = self.get("/pools")
        pools_raw = data if isinstance(data, list) else data.get("data", [])
        normalized = []
        for p in pools_raw:
            tvl = float(p.get("tvl") or p.get("reserveUSD", 0))
            apr = float(p.get("apr") or p.get("gaugeApr", 0))
            if tvl < min_tvl or apr < min_apr:
                continue
            normalized.append(DataNormalizer._pool_from_aerodrome(p))
        normalized.sort(key=lambda x: x["tvl_usd"], reverse=True)
        return {"pools": normalized, "total": len(normalized), "chain": "Base", "source": "aerodrome"}
