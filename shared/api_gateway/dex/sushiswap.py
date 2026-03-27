"""
sushiswap.py — Cliente SushiSwap para o OpenClaw API Gateway.
"""
from .._base_dex import BaseDEXClient


CHAIN_IDS = {
    "Ethereum": 1, "Arbitrum": 42161, "Polygon": 137,
    "Optimism": 10, "Base": 8453, "Avalanche": 43114, "BSC": 56,
}


class SushiSwapClient(BaseDEXClient):

    NAME          = "sushiswap"
    BASE_URL      = "https://api.sushi.com/pool/v2"
    CALLS_PER_MIN = 30
    CACHE_TTL     = 900
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["pools", "tvl", "volume", "apr"]

    def _health_check(self):
        self.session.get(self.BASE_URL + "?chainIds=1&take=1", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type in ("pools", "pools_evm"):
            chains = kwargs.get("chains", ["Ethereum"])
            return self._top_pools(chains=chains, min_tvl=kwargs.get("min_tvl", 500_000))
        raise ValueError(f"SushiSwapClient não suporta: {data_type}")

    def _top_pools(self, chains: list = None, min_tvl: float = 500_000) -> dict:
        if chains is None:
            chains = ["Ethereum"]
        chain_ids = [str(CHAIN_IDS[c]) for c in chains if c in CHAIN_IDS]
        params = {
            "chainIds": ",".join(chain_ids),
            "orderBy":  "liquidityUSD",
            "orderDir": "desc",
            "take":     50,
        }
        data  = self.get("", params=params)
        pools_raw = data if isinstance(data, list) else data.get("data", [])
        pools = []
        for p in pools_raw:
            tvl = float(p.get("liquidityUSD", 0))
            if tvl < min_tvl:
                continue
            pools.append({
                "pool_id":    p.get("id", p.get("address", "")),
                "protocol":   "sushiswap",
                "chain":      p.get("chainId", ""),
                "token0":     p.get("token0", {}).get("symbol", ""),
                "token1":     p.get("token1", {}).get("symbol", ""),
                "symbol":     p.get("name", ""),
                "fee_tier":   float(p.get("swapFee", 0)) * 100,
                "tvl_usd":    tvl,
                "volume_24h": float(p.get("volume1d", 0)),
                "apr_base":   float(p.get("feeApr1d", 0)) * 100,
                "apr_total":  float(p.get("totalApr1d", 0)) * 100,
                "source":     "sushiswap",
            })
        return {"pools": pools, "total": len(pools), "source": "sushiswap"}
