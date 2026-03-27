"""
ethereum.py — Cliente RPC Ethereum para o OpenClaw API Gateway.
"""
from .._base_rpc import BaseRPCClient


class EthereumRPCClient(BaseRPCClient):

    NAME     = "ethereum_rpc"
    CHAIN_ID = 1
    BASE_URL = "https://cloudflare-eth.com"
    CALLS_PER_MIN = 30
    CACHE_TTL     = 30
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["block_number", "balance", "contract_call", "logs", "gas_price"]

    RPC_URLS = {
        "cloudflare": "https://cloudflare-eth.com",
        "ankr":       "https://rpc.ankr.com/eth",
        "llamarpc":   "https://eth.llamarpc.com",
        "publicnode": "https://ethereum-rpc.publicnode.com",
        "drpc":       "https://eth.drpc.org",
    }

    def _health_check(self):
        block = self.get_block_number()
        if not block:
            raise Exception("Ethereum RPC indisponível")
