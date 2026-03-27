"""
the_graph.py — Cliente The Graph para o OpenClaw API Gateway.
"""
from ..base_client import BaseAPIClient


SUBGRAPHS = {
    "uniswap_v3_eth": "uniswap/uniswap-v3",
    "uniswap_v3_arb": "ianlapham/arbitrum-minimal",
    "aave_v3_eth":    "aave/protocol-v3",
    "compound_v3":    "messari/compound-v3-ethereum",
    "balancer_eth":   "balancer-labs/balancer-v2",
    "curve_eth":      "messari/curve-finance-ethereum",
    "gmx_arb":        "gmx-io/gmx-stats",
}

HOSTED_BASE = "https://api.thegraph.com/subgraphs/name"


class TheGraphClient(BaseAPIClient):

    NAME          = "the_graph"
    BASE_URL      = HOSTED_BASE
    CALLS_PER_MIN = 30
    CACHE_TTL     = 600
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["any_subgraph", "custom_queries"]

    def _health_check(self):
        self.session.get("https://api.thegraph.com/index-node/graphql", timeout=5)

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type == "pools":
            return self._top_pools(kwargs.get("subgraph", "uniswap_v3_eth"))
        raise ValueError(f"TheGraphClient não suporta: {data_type}")

    def query_subgraph(self, subgraph_name: str, gql_query: str,
                       variables: dict = None) -> dict:
        """Query qualquer subgraph pelo nome (ex: 'uniswap/uniswap-v3')."""
        url  = f"{HOSTED_BASE}/{subgraph_name}"
        body = {"query": gql_query, "variables": variables or {}}
        resp = self.session.post(url, json=body, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def query_known(self, subgraph_key: str, gql_query: str,
                    variables: dict = None) -> dict:
        """Query usando chave conhecida do SUBGRAPHS dict."""
        name = SUBGRAPHS.get(subgraph_key)
        if not name:
            raise ValueError(f"Subgraph desconhecido: {subgraph_key}")
        return self.query_subgraph(name, gql_query, variables)

    def _top_pools(self, subgraph_key: str) -> dict:
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
        data = self.query_known(subgraph_key, query)
        return {
            "pools":  data.get("data", {}).get("pools", []),
            "source": "the_graph",
        }
