from .._base_rpc import BaseRPCClient


class ArbitrumRPCClient(BaseRPCClient):
    NAME     = "arbitrum_rpc"
    CHAIN_ID = 42161
    BASE_URL = "https://arb1.arbitrum.io/rpc"
    CALLS_PER_MIN = 30
    CACHE_TTL     = 30
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["block_number", "balance", "contract_call", "logs"]

    RPC_URLS = {
        "official":   "https://arb1.arbitrum.io/rpc",
        "ankr":       "https://rpc.ankr.com/arbitrum",
        "llamarpc":   "https://arbitrum.llamarpc.com",
        "publicnode": "https://arbitrum-one-rpc.publicnode.com",
        "drpc":       "https://arbitrum.drpc.org",
    }

    def _health_check(self):
        block = self.get_block_number()
        if not block:
            raise Exception("Arbitrum RPC indisponível")
