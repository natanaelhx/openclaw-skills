from .._base_rpc import BaseRPCClient as _BaseRPCClient


class BaseChainRPCClient(_BaseRPCClient):
    NAME     = "base_rpc"
    CHAIN_ID = 8453
    BASE_URL = "https://mainnet.base.org"
    CALLS_PER_MIN = 30
    CACHE_TTL     = 30
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["block_number", "balance", "contract_call", "logs"]

    RPC_URLS = {
        "official":   "https://mainnet.base.org",
        "ankr":       "https://rpc.ankr.com/base",
        "llamarpc":   "https://base.llamarpc.com",
        "publicnode": "https://base-rpc.publicnode.com",
        "drpc":       "https://base.drpc.org",
    }

    def _health_check(self):
        block = self.get_block_number()
        if not block:
            raise Exception("Base Chain RPC indisponível")


# Alias para compatibilidade com o registry
BaseRPCClient = BaseChainRPCClient
