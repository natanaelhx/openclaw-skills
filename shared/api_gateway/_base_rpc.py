"""
_base_rpc.py — Base para clientes RPC EVM e Solana.
"""
from .base_client import BaseAPIClient


class BaseRPCClient(BaseAPIClient):
    """Base para clientes JSON-RPC (EVM chains)."""

    RPC_URLS = {}  # {provider_name: url}
    CHAIN_ID = 0

    def __init__(self, api_key: str = None, cache_ttl: int = None):
        super().__init__(api_key, cache_ttl)
        urls = list(self.RPC_URLS.values())
        self._active_url = urls[0] if urls else ""
        self._url_index  = 0

    def _rpc_call(self, method: str, params: list = None) -> dict:
        """Executa chamada JSON-RPC com fallback entre providers."""
        import json, time, requests as _req
        urls = list(self.RPC_URLS.values())
        payload = {
            "jsonrpc": "2.0",
            "method":  method,
            "params":  params or [],
            "id":      1,
        }
        for i, url in enumerate(urls):
            try:
                resp = self.session.post(url, json=payload, timeout=8)
                resp.raise_for_status()
                data = resp.json()
                if "error" in data:
                    raise Exception(data["error"].get("message", "RPC error"))
                return data.get("result")
            except Exception:
                if i < len(urls) - 1:
                    continue
                raise

    def get_block_number(self) -> int:
        result = self._rpc_call("eth_blockNumber")
        return int(result, 16) if result else 0

    def get_balance(self, address: str) -> float:
        result = self._rpc_call("eth_getBalance", [address, "latest"])
        return int(result, 16) / 1e18 if result else 0.0

    def get_gas_price(self) -> int:
        result = self._rpc_call("eth_gasPrice")
        return int(result, 16) if result else 0

    def is_available(self) -> bool:
        try:
            block = self.get_block_number()
            return block > 0
        except Exception:
            return False

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type == "block_number":
            return {"block": self.get_block_number(), "source": self.NAME}
        if data_type == "balance":
            addr = kwargs.get("address", "")
            return {"address": addr, "balance_eth": self.get_balance(addr), "source": self.NAME}
        raise ValueError(f"{self.__class__.__name__} não suporta: {data_type}")
