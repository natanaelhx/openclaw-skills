"""
bybit.py — Cliente Bybit V5 para o OpenClaw API Gateway.
"""
from .._base_cex import BaseCEXClient


class BybitClient(BaseCEXClient):

    NAME          = "bybit"
    BASE_URL      = "https://api.bybit.com/v5"
    CALLS_PER_MIN = 120
    CACHE_TTL     = 300
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["price", "ohlcv", "funding_rate", "open_interest", "long_short_ratio"]

    def _health_check(self):
        self.session.get(self.BASE_URL + "/market/time", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type == "funding_rate":
            return self._funding_rate(kwargs.get("symbol", "BTCUSDT"))
        if data_type == "open_interest":
            return self._open_interest(kwargs.get("symbol", "BTCUSDT"))
        if data_type == "long_short_ratio":
            return self._ls_ratio(kwargs.get("symbol", "BTCUSDT"))
        if data_type == "price":
            return self._price(kwargs.get("symbol", "BTCUSDT"))
        raise ValueError(f"BybitClient não suporta: {data_type}")

    def _funding_rate(self, symbol: str) -> dict:
        from ..normalizer import DataNormalizer
        data = self.get("/market/tickers", params={"category": "linear", "symbol": symbol})
        # Bybit tickers inclui fundingRate no campo da lista
        lst = data.get("result", {}).get("list", [{}])
        item = lst[0] if lst else {}
        return DataNormalizer.funding_rate({"result": {"list": [item]}}, "bybit")

    def _open_interest(self, symbol: str) -> dict:
        from ..normalizer import DataNormalizer
        data = self.get("/market/open-interest",
                        params={"category": "linear", "symbol": symbol, "intervalTime": "5min", "limit": 1})
        return DataNormalizer.open_interest(data, "bybit")

    def _ls_ratio(self, symbol: str) -> dict:
        from ..normalizer import DataNormalizer
        data = self.get("/market/account-ratio",
                        params={"category": "linear", "symbol": symbol, "period": "5min", "limit": 1})
        return DataNormalizer.long_short_ratio(data, "bybit")

    def _price(self, symbol: str) -> dict:
        from ..normalizer import DataNormalizer
        data = self.get("/market/tickers", params={"category": "spot", "symbol": symbol})
        lst  = data.get("result", {}).get("list", [{}])
        item = lst[0] if lst else {}
        return {
            "symbol":     item.get("symbol", symbol),
            "price_usd":  float(item.get("lastPrice", 0)),
            "change_24h": float(item.get("price24hPcnt", 0)) * 100,
            "volume_24h": float(item.get("volume24h", 0)),
            "source":     "bybit",
        }

    def get_funding_history(self, symbol: str, limit: int = 200) -> list:
        data = self.get("/market/funding/history",
                        params={"category": "linear", "symbol": symbol, "limit": limit})
        return data.get("result", {}).get("list", [])
