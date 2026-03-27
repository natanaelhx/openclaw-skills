"""
dexscreener.py — Cliente DexScreener para o OpenClaw API Gateway.
"""
from ..base_client import BaseAPIClient
from ..normalizer import DataNormalizer


class DexScreenerClient(BaseAPIClient):

    NAME          = "dexscreener"
    BASE_URL      = "https://api.dexscreener.com/latest/dex"
    CALLS_PER_MIN = 300
    CACHE_TTL     = 120  # 2min — pares DEX mudam rápido
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["pairs", "token_pairs", "search_pairs", "price", "volume"]

    def _health_check(self):
        self.session.get("https://api.dexscreener.com/latest/dex/pairs/ethereum/0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
                         timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type == "price":
            return self._price_by_token(kwargs.get("address", ""))
        if data_type == "token_pairs_dex":
            return self._token_pairs(kwargs.get("address", ""))
        raise ValueError(f"DexScreenerClient não suporta: {data_type}")

    def _price_by_token(self, address: str) -> dict:
        data = self.get(f"/tokens/{address}")
        return DataNormalizer._price_from_dexscreener(data)

    def _token_pairs(self, address: str) -> dict:
        data = self.get(f"/tokens/{address}")
        pairs = data.get("pairs", [])
        return {
            "pairs":  pairs,
            "count":  len(pairs),
            "source": "dexscreener",
        }

    def search(self, query: str) -> dict:
        data = self.get("/search/", params={"q": query})
        return {"pairs": data.get("pairs", []), "source": "dexscreener"}

    def get_pairs(self, chain: str, pair_address: str) -> dict:
        return self.get(f"/pairs/{chain}/{pair_address}")

    def get_new_pairs(self, chain: str) -> dict:
        return self.get(f"/pairs/{chain}/new")
