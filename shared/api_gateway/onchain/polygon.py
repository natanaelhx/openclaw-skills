from .._base_rpc import BaseRPCClient


class PolygonRPCClient(BaseRPCClient):
    NAME     = "polygon_rpc"
    CHAIN_ID = 137
    BASE_URL = "https://polygon-rpc.com"
    CALLS_PER_MIN = 30
    CACHE_TTL     = 30
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["block_number", "balance", "contract_call", "logs"]

    RPC_URLS = {
        "official":   "https://polygon-rpc.com",
        "ankr":       "https://rpc.ankr.com/polygon",
        "llamarpc":   "https://polygon.llamarpc.com",
        "publicnode": "https://polygon-bor-rpc.publicnode.com",
        "drpc":       "https://polygon.drpc.org",
    }

    def _health_check(self):
        block = self.get_block_number()
        if not block:
            raise Exception("Polygon RPC indisponível")
