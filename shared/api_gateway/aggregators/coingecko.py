"""
coingecko.py — Cliente CoinGecko para o OpenClaw API Gateway.
"""
from ..base_client import BaseAPIClient
from ..normalizer import DataNormalizer


class CoinGeckoClient(BaseAPIClient):

    NAME          = "coingecko"
    BASE_URL      = "https://api.coingecko.com/api/v3"
    CALLS_PER_MIN = 30  # plano gratuito
    CACHE_TTL     = 300
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["price", "market_cap", "volume", "ohlcv", "global_market",
                     "trending", "token_info"]

    def _set_auth_header(self, key: str):
        self.session.headers["x-cg-demo-api-key"] = key
        self.BASE_URL = "https://pro-api.coingecko.com/api/v3"
        self.rate_limiter.calls_per_minute = 500

    def _health_check(self):
        self.session.get(self.BASE_URL + "/ping", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type == "price":
            return self._price(kwargs.get("symbol", "bitcoin"))
        if data_type == "global_market":
            return self._global()
        if data_type == "trending":
            return self._trending()
        raise ValueError(f"CoinGeckoClient não suporta: {data_type}")

    def _price(self, symbol: str) -> dict:
        """symbol pode ser coin_id (bitcoin) ou ticker (BTC)."""
        coin_id = symbol.lower()
        data = self.get("/simple/price", params={
            "ids":            coin_id,
            "vs_currencies":  "usd",
            "include_market_cap": "true",
            "include_24hr_vol":   "true",
            "include_24hr_change":"true",
            "include_1h_change":  "true",
        })
        return DataNormalizer._price_from_coingecko(data)

    def _global(self) -> dict:
        data = self.get("/global")
        gdata = data.get("data", {})
        return {
            "total_market_cap_usd":   gdata.get("total_market_cap", {}).get("usd", 0),
            "total_volume_24h_usd":   gdata.get("total_volume", {}).get("usd", 0),
            "btc_dominance":          gdata.get("market_cap_percentage", {}).get("btc", 0),
            "eth_dominance":          gdata.get("market_cap_percentage", {}).get("eth", 0),
            "active_cryptocurrencies": gdata.get("active_cryptocurrencies", 0),
            "market_cap_change_24h":  gdata.get("market_cap_change_percentage_24h_usd", 0),
            "source":                 "coingecko",
        }

    def _trending(self) -> dict:
        data = self.get("/search/trending")
        coins = [
            {
                "rank":       i + 1,
                "name":       c.get("item", {}).get("name", ""),
                "symbol":     c.get("item", {}).get("symbol", ""),
                "market_cap_rank": c.get("item", {}).get("market_cap_rank", 0),
            }
            for i, c in enumerate(data.get("coins", []))
        ]
        return {"trending": coins, "source": "coingecko"}

    def get_markets(self, vs_currency: str = "usd", per_page: int = 100,
                    page: int = 1, category: str = None) -> list:
        params = {
            "vs_currency": vs_currency,
            "order":       "market_cap_desc",
            "per_page":    per_page,
            "page":        page,
            "sparkline":   "false",
        }
        if category:
            params["category"] = category
        return self.get("/coins/markets", params=params)
