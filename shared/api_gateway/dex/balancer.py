"""
balancer.py — Cliente Balancer V2 para o OpenClaw API Gateway.
"""
from .._base_dex import BaseDEXClient


SUBGRAPH_URLS = {
    "Ethereum": "https://api.thegraph.com/subgraphs/name/balancer-labs/balancer-v2",
    "Arbitrum": "https://api.thegraph.com/subgraphs/name/balancer-labs/balancer-arbitrum-v2",
    "Polygon":  "https://api.thegraph.com/subgraphs/name/balancer-labs/balancer-polygon-v2",
}

TOP_POOLS_QUERY = """
{
  pools(first: 50, orderBy: totalLiquidity, orderDirection: desc,
        where: {totalLiquidity_gt: "100000"}) {
    id
    name
    tokens { symbol balance }
    totalLiquidity
    totalSwapVolume
    swapFee
  }
}
"""


class BalancerClient(BaseDEXClient):

    NAME          = "balancer"
    BASE_URL      = SUBGRAPH_URLS["Ethereum"]
    CALLS_PER_MIN = 30
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
            return self._top_pools(
                chain=kwargs.get("chain", "Ethereum"),
                min_tvl=kwargs.get("min_tvl", 500_000),
            )
        raise ValueError(f"BalancerClient não suporta: {data_type}")

    def _top_pools(self, chain: str = "Ethereum", min_tvl: float = 500_000) -> dict:
        url  = SUBGRAPH_URLS.get(chain, SUBGRAPH_URLS["Ethereum"])
        body = {"query": TOP_POOLS_QUERY}
        resp = self.session.post(url, json=body, timeout=20)
        resp.raise_for_status()
        pools_raw = resp.json().get("data", {}).get("pools", [])
        pools = []
        for p in pools_raw:
            tvl = float(p.get("totalLiquidity", 0))
            if tvl < min_tvl:
                continue
            tokens  = p.get("tokens", [])
            symbols = [t.get("symbol", "") for t in tokens]
            fee     = float(p.get("swapFee", 0)) * 100
            pools.append({
                "pool_id":    p.get("id", ""),
                "protocol":   "balancer",
                "chain":      chain,
                "token0":     symbols[0] if symbols else "",
                "token1":     symbols[1] if len(symbols) > 1 else "",
                "symbol":     "/".join(symbols[:4]),
                "fee_tier":   fee,
                "tvl_usd":    tvl,
                "volume_24h": float(p.get("totalSwapVolume", 0)),
                "apr_base":   0.0,
                "apr_total":  0.0,
                "source":     "balancer",
            })
        pools.sort(key=lambda x: x["tvl_usd"], reverse=True)
        return {"pools": pools, "total": len(pools), "chain": chain, "source": "balancer"}
