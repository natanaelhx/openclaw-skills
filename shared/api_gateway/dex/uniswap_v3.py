"""
uniswap_v3.py — Cliente Uniswap V3 (via The Graph) para o OpenClaw API Gateway.
"""
from .._base_dex import BaseDEXClient
from ..normalizer import DataNormalizer


SUBGRAPH_URLS = {
    "Ethereum": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3",
    "Arbitrum": "https://api.thegraph.com/subgraphs/name/ianlapham/arbitrum-minimal",
    "Optimism": "https://api.thegraph.com/subgraphs/name/ianlapham/optimism-post-regenesis",
    "Base":     "https://api.studio.thegraph.com/query/48211/uniswap-v3-base/version/latest",
    "Polygon":  "https://api.thegraph.com/subgraphs/name/ianlapham/uniswap-v3-polygon",
}

TOP_POOLS_QUERY = """
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


class UniswapV3Client(BaseDEXClient):

    NAME          = "uniswap_v3"
    BASE_URL      = SUBGRAPH_URLS["Ethereum"]
    CALLS_PER_MIN = 30
    CACHE_TTL     = 900
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["pools", "tvl", "volume", "fees", "apr"]

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
        raise ValueError(f"UniswapV3Client não suporta: {data_type}")

    def _top_pools(self, chain: str = "Ethereum", min_tvl: float = 500_000) -> dict:
        url  = SUBGRAPH_URLS.get(chain, SUBGRAPH_URLS["Ethereum"])
        data = self._gql_post(url, TOP_POOLS_QUERY)
        pools_raw = data.get("data", {}).get("pools", [])
        normalized = []
        for p in pools_raw:
            tvl = float(p.get("totalValueLockedUSD", 0))
            if tvl < min_tvl:
                continue
            p["_chain"] = chain
            normalized.append(DataNormalizer._pool_from_uniswap_v3(p))
        normalized.sort(key=lambda x: x["tvl_usd"], reverse=True)
        return {"pools": normalized, "total": len(normalized), "chain": chain, "source": "uniswap_v3"}

    def _gql_post(self, url: str, query: str, variables: dict = None) -> dict:
        import json, time, requests as _req
        body = {"query": query, "variables": variables or {}}
        key  = f"gql:{url}:{json.dumps(body, sort_keys=True)[:200]}"
        cached = self.cache.get(key)
        if cached:
            return cached
        self.rate_limiter.wait_if_needed()
        for attempt in range(3):
            try:
                resp = self.session.post(url, json=body, timeout=20)
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
        raise Exception(f"Falha GraphQL Uniswap V3: {url}")
