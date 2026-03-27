"""
curve.py — Cliente Curve Finance para o OpenClaw API Gateway.
"""
from .._base_dex import BaseDEXClient
from ..normalizer import DataNormalizer


CHAIN_MAP = {
    "Ethereum": "ethereum",
    "Arbitrum": "arbitrum",
    "Optimism": "optimism",
    "Base":     "base",
    "Polygon":  "polygon",
    "Avalanche":"avalanche",
    "BSC":      "bsc",
}


class CurveClient(BaseDEXClient):

    NAME          = "curve"
    BASE_URL      = "https://api.curve.fi/api"
    CALLS_PER_MIN = 60
    CACHE_TTL     = 900
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["pools", "tvl", "volume", "apr"]

    def _health_check(self):
        self.session.get(self.BASE_URL + "/getPools/ethereum/main", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type in ("pools", "pools_evm"):
            chains = kwargs.get("chains", ["Ethereum"])
            if chains is None:
                chains = ["Ethereum"]
            return self._pools(chains=chains, min_tvl=kwargs.get("min_tvl", 500_000))
        raise ValueError(f"CurveClient não suporta: {data_type}")

    def _pools(self, chains: list = None, min_tvl: float = 500_000) -> dict:
        if chains is None:
            chains = ["Ethereum"]
        all_pools = []
        for chain in chains:
            slug = CHAIN_MAP.get(chain, chain.lower())
            try:
                data = self.get(f"/getPools/{slug}/main")
                raw  = data.get("data", {}).get("poolData", [])
                for p in raw:
                    tvl = float(p.get("usdTotal", 0))
                    if tvl < min_tvl:
                        continue
                    p["_chain"] = chain
                    all_pools.append(DataNormalizer._pool_from_curve(p))
                # factory pools também
                data2 = self.get(f"/getPools/{slug}/factory")
                raw2  = data2.get("data", {}).get("poolData", [])
                for p in raw2:
                    tvl = float(p.get("usdTotal", 0))
                    if tvl < min_tvl:
                        continue
                    p["_chain"] = chain
                    all_pools.append(DataNormalizer._pool_from_curve(p))
            except Exception:
                continue

        all_pools.sort(key=lambda x: x["tvl_usd"], reverse=True)
        return {"pools": all_pools, "total": len(all_pools), "source": "curve"}
