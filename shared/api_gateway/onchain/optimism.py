from .._base_rpc import BaseRPCClient


class OptimismRPCClient(BaseRPCClient):
    NAME     = "optimism_rpc"
    CHAIN_ID = 10
    BASE_URL = "https://mainnet.optimism.io"
    CALLS_PER_MIN = 30
    CACHE_TTL     = 30
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["block_number", "balance", "contract_call", "logs"]

    RPC_URLS = {
        "official":   "https://mainnet.optimism.io",
        "ankr":       "https://rpc.ankr.com/optimism",
        "llamarpc":   "https://optimism.llamarpc.com",
        "publicnode": "https://optimism-rpc.publicnode.com",
    }

    def _health_check(self):
        block = self.get_block_number()
        if not block:
            raise Exception("Optimism RPC indisponível")
