from .._base_rpc import BaseRPCClient


class AvalancheRPCClient(BaseRPCClient):
    NAME     = "avalanche_rpc"
    CHAIN_ID = 43114
    BASE_URL = "https://api.avax.network/ext/bc/C/rpc"
    CALLS_PER_MIN = 30
    CACHE_TTL     = 30
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["block_number", "balance", "contract_call", "logs"]

    RPC_URLS = {
        "official":   "https://api.avax.network/ext/bc/C/rpc",
        "ankr":       "https://rpc.ankr.com/avalanche",
        "publicnode": "https://avalanche-c-chain-rpc.publicnode.com",
        "drpc":       "https://avalanche.drpc.org",
    }

    def _health_check(self):
        block = self.get_block_number()
        if not block:
            raise Exception("Avalanche RPC indisponível")
