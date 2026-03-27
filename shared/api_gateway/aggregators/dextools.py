"""
dextools.py — Cliente DexTools para o OpenClaw API Gateway.
Requer API key (trial gratuita): https://developer.dextools.io/
"""
from ..base_client import BaseAPIClient


class DexToolsClient(BaseAPIClient):

    NAME          = "dextools"
    BASE_URL      = "https://public-api.dextools.io/trial/v2"
    CALLS_PER_MIN = 30
    CACHE_TTL     = 300
    REQUIRES_KEY  = True
    FREE_TIER     = True
    SUPPORTS      = ["pool_info", "price", "ohlcv", "liquidity", "token_audit"]

    def _set_auth_header(self, key: str):
        self.session.headers["X-API-Key"] = key

    def _health_check(self):
        if not self.api_key:
            raise Exception("DexTools requer API key (trial gratuita em https://developer.dextools.io/)")
        self.session.get(self.BASE_URL + "/blockchain", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if not self.api_key:
            raise Exception("DexTools requer API key")
        if data_type == "pool_info":
            return self._pool_info(kwargs["chain"], kwargs["address"])
        if data_type == "price":
            return self._price(kwargs["chain"], kwargs["address"])
        if data_type == "token_audit":
            return self._audit(kwargs["chain"], kwargs["address"])
        raise ValueError(f"DexToolsClient não suporta: {data_type}")

    def _pool_info(self, chain: str, address: str) -> dict:
        data = self.get(f"/pool/{chain}/{address}")
        return {"chain": chain, "address": address, "data": data, "source": "dextools"}

    def _price(self, chain: str, address: str) -> dict:
        data = self.get(f"/token/{chain}/{address}/price")
        return {"chain": chain, "address": address, "price_data": data, "source": "dextools"}

    def _audit(self, chain: str, address: str) -> dict:
        data = self.get(f"/token/{chain}/{address}/audit")
        return {"chain": chain, "address": address, "audit": data, "source": "dextools"}
