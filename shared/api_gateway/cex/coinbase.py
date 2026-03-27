"""
coinbase.py — Cliente Coinbase Advanced Trade para o OpenClaw API Gateway.
"""
from .._base_cex import BaseCEXClient


class CoinbaseClient(BaseCEXClient):

    NAME          = "coinbase"
    BASE_URL      = "https://api.exchange.coinbase.com"
    CALLS_PER_MIN = 30
    CACHE_TTL     = 300
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["price", "ohlcv", "orderbook", "trades"]

    def _health_check(self):
        self.session.get(self.BASE_URL + "/products/BTC-USD", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type == "price":
            return self._price(kwargs.get("symbol", "BTC-USD"))
        if data_type == "ohlcv":
            return self._ohlcv(kwargs.get("symbol", "BTC-USD"),
                               kwargs.get("granularity", 3600))
        raise ValueError(f"CoinbaseClient não suporta: {data_type}")

    def _price(self, symbol: str) -> dict:
        if "USDT" in symbol and "-" not in symbol:
            symbol = symbol.replace("USDT", "-USD")
        data = self.get(f"/products/{symbol}/ticker")
        return {
            "symbol":     symbol,
            "price_usd":  float(data.get("price", 0)),
            "change_24h": 0.0,
            "volume_24h": float(data.get("volume", 0)),
            "source":     "coinbase",
        }

    def _ohlcv(self, symbol: str, granularity: int) -> dict:
        data = self.get(f"/products/{symbol}/candles",
                        params={"granularity": granularity})
        return {"symbol": symbol, "granularity": granularity, "candles": data, "source": "coinbase"}
