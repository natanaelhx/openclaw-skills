from .._base_rpc import BaseRPCClient


class BSCRPCClient(BaseRPCClient):
    NAME     = "bsc_rpc"
    CHAIN_ID = 56
    BASE_URL = "https://bsc-dataseed.binance.org"
    CALLS_PER_MIN = 30
    CACHE_TTL     = 30
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["block_number", "balance", "contract_call", "logs"]

    RPC_URLS = {
        "official":   "https://bsc-dataseed.binance.org",
        "ankr":       "https://rpc.ankr.com/bsc",
        "publicnode": "https://bsc-rpc.publicnode.com",
        "drpc":       "https://bsc.drpc.org",
    }

    def _health_check(self):
        block = self.get_block_number()
        if not block:
            raise Exception("BSC RPC indisponível")
