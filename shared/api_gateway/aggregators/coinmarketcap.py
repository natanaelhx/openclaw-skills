"""
coinmarketcap.py — Cliente CoinMarketCap para o OpenClaw API Gateway.
Requer API key gratuita: https://pro.coinmarketcap.com/signup
"""
from ..base_client import BaseAPIClient


class CoinMarketCapClient(BaseAPIClient):

    NAME          = "coinmarketcap"
    BASE_URL      = "https://pro-api.coinmarketcap.com/v1"
    CALLS_PER_MIN = 30
    CACHE_TTL     = 300
    REQUIRES_KEY  = True
    FREE_TIER     = True
    SUPPORTS      = ["price", "market_cap", "volume", "rankings", "global_metrics", "fear_greed"]

    def _set_auth_header(self, key: str):
        self.session.headers["X-CMC_PRO_API_KEY"] = key

    def _health_check(self):
        if not self.api_key:
            raise Exception("CoinMarketCap requer API key (gratuita em https://pro.coinmarketcap.com/signup)")
        resp = self.session.get(self.BASE_URL + "/key/info", timeout=5)
        resp.raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if not self.api_key:
            raise Exception("CoinMarketCap requer API key")
        if data_type == "price":
            return self._price(kwargs.get("symbol", "BTC"))
        if data_type == "global_market":
            return self._global()
        if data_type == "fear_greed":
            return self._fear_greed()
        raise ValueError(f"CoinMarketCapClient não suporta: {data_type}")

    def _price(self, symbol: str) -> dict:
        data = self.get("/cryptocurrency/quotes/latest",
                        params={"symbol": symbol.upper(), "convert": "USD"})
        item = data.get("data", {}).get(symbol.upper(), {})
        quote = item.get("quote", {}).get("USD", {})
        return {
            "symbol":     symbol.upper(),
            "price_usd":  float(quote.get("price", 0)),
            "change_1h":  float(quote.get("percent_change_1h", 0)),
            "change_24h": float(quote.get("percent_change_24h", 0)),
            "change_7d":  float(quote.get("percent_change_7d", 0)),
            "volume_24h": float(quote.get("volume_24h", 0)),
            "market_cap": float(quote.get("market_cap", 0)),
            "source":     "coinmarketcap",
        }

    def _global(self) -> dict:
        data = self.get("/global-metrics/quotes/latest")
        item = data.get("data", {})
        quote = item.get("quote", {}).get("USD", {})
        return {
            "total_market_cap_usd":  float(quote.get("total_market_cap", 0)),
            "total_volume_24h_usd":  float(quote.get("total_volume_24h", 0)),
            "btc_dominance":         float(item.get("btc_dominance", 0)),
            "eth_dominance":         float(item.get("eth_dominance", 0)),
            "active_cryptocurrencies": int(item.get("active_cryptocurrencies", 0)),
            "source":                "coinmarketcap",
        }

    def _fear_greed(self) -> dict:
        data = self.get("/fear-and-greed/latest")
        item = data.get("data", {})
        return {
            "value":       item.get("value", 0),
            "label":       item.get("value_classification", ""),
            "last_updated": item.get("timestamp", ""),
            "source":      "coinmarketcap",
        }
