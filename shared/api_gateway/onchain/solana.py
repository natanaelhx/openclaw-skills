"""
solana.py — Cliente RPC Solana para o OpenClaw API Gateway.
"""
from ..base_client import BaseAPIClient


class SolanaRPCClient(BaseAPIClient):

    NAME     = "solana_rpc"
    BASE_URL = "https://api.mainnet-beta.solana.com"
    CALLS_PER_MIN = 60
    CACHE_TTL     = 30
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["slot", "balance", "transaction", "account_info"]

    RPC_URLS = {
        "mainnet":    "https://api.mainnet-beta.solana.com",
        "ankr":       "https://rpc.ankr.com/solana",
        "publicnode": "https://solana-rpc.publicnode.com",
    }

    def _rpc_call(self, method: str, params: list = None) -> dict:
        import time
        urls = list(self.RPC_URLS.values())
        payload = {"jsonrpc": "2.0", "method": method, "params": params or [], "id": 1}
        for url in urls:
            try:
                resp = self.session.post(url, json=payload, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if "error" in data:
                    raise Exception(data["error"].get("message", "Solana RPC error"))
                return data.get("result")
            except Exception:
                continue
        raise Exception("Todos os RPCs Solana falharam")

    def get_slot(self) -> int:
        return self._rpc_call("getSlot") or 0

    def get_balance(self, pubkey: str) -> float:
        result = self._rpc_call("getBalance", [pubkey])
        return result.get("value", 0) / 1e9 if isinstance(result, dict) else 0.0

    def is_available(self) -> bool:
        try:
            return self.get_slot() > 0
        except Exception:
            return False

    def _health_check(self):
        if not self.is_available():
            raise Exception("Solana RPC indisponível")

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type == "slot":
            return {"slot": self.get_slot(), "source": self.NAME}
        if data_type == "balance":
            addr = kwargs.get("address", "")
            return {"address": addr, "balance_sol": self.get_balance(addr), "source": self.NAME}
        raise ValueError(f"SolanaRPCClient não suporta: {data_type}")
