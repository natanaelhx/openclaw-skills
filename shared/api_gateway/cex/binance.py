"""
binance.py — Cliente Binance (Spot + Futures) para o OpenClaw API Gateway.
Dados públicos: funding rate, OI, L/S ratio, preço, OHLCV.
"""
from .._base_cex import BaseCEXClient


class BinanceClient(BaseCEXClient):

    NAME          = "binance"
    CALLS_PER_MIN = 1200
    CACHE_TTL     = 300  # 5min — dados de mercado mudam rápido
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["price", "ohlcv", "funding_rate", "open_interest",
                     "long_short_ratio", "liquidations"]

    BASE_FUTURES      = "https://fapi.binance.com/fapi/v1"
    BASE_FUTURES_DATA = "https://fapi.binance.com/futures/data"
    BASE_SPOT         = "https://api.binance.com/api/v3"
    BASE_URL          = BASE_FUTURES  # default para health check

    def _health_check(self):
        self.session.get(self.BASE_SPOT + "/ping", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type == "funding_rate":
            return self._funding_rate(kwargs.get("symbol", "BTCUSDT"))
        if data_type == "open_interest":
            return self._open_interest(kwargs.get("symbol", "BTCUSDT"))
        if data_type == "long_short_ratio":
            return self._ls_ratio(kwargs.get("symbol", "BTCUSDT"),
                                  kwargs.get("period", "5m"))
        if data_type == "price":
            return self._price(kwargs.get("symbol", "BTCUSDT"))
        if data_type == "ohlcv":
            return self._ohlcv(kwargs.get("symbol", "BTCUSDT"),
                               kwargs.get("interval", "1h"),
                               kwargs.get("limit", 100))
        raise ValueError(f"BinanceClient não suporta: {data_type}")

    def _funding_rate(self, symbol: str) -> dict:
        from ..normalizer import DataNormalizer
        url  = self.BASE_FUTURES + "/premiumIndex"
        data = self.get(url, params={"symbol": symbol}, use_cache=True)
        return DataNormalizer.funding_rate(data, "binance")

    def _open_interest(self, symbol: str) -> dict:
        from ..normalizer import DataNormalizer
        url  = self.BASE_FUTURES + "/openInterest"
        data = self.get(url, params={"symbol": symbol}, use_cache=True)
        return DataNormalizer.open_interest(data, "binance")

    def _ls_ratio(self, symbol: str, period: str = "5m") -> dict:
        from ..normalizer import DataNormalizer
        url  = self.BASE_FUTURES_DATA + "/topLongShortAccountRatio"
        data = self.get(url, params={"symbol": symbol, "period": period, "limit": 1},
                        use_cache=True)
        if isinstance(data, list) and data:
            return DataNormalizer.long_short_ratio(data[0], "binance")
        return DataNormalizer.long_short_ratio(data, "binance")

    def _price(self, symbol: str) -> dict:
        from ..normalizer import DataNormalizer
        url  = self.BASE_SPOT + "/ticker/24hr"
        data = self.get(url, params={"symbol": symbol}, use_cache=True)
        return DataNormalizer.price(data, "binance")

    def _ohlcv(self, symbol: str, interval: str, limit: int) -> dict:
        url  = self.BASE_FUTURES + "/klines"
        data = self.get(url, params={"symbol": symbol, "interval": interval, "limit": limit},
                        use_cache=True)
        return {"symbol": symbol, "interval": interval, "klines": data, "source": "binance"}

    def get_funding_history(self, symbol: str, limit: int = 100) -> list:
        url = self.BASE_FUTURES + "/fundingRate"
        return self.get(url, params={"symbol": symbol, "limit": limit})

    def get_all_funding_rates(self) -> list:
        url = self.BASE_FUTURES + "/premiumIndex"
        return self.get(url)

    def get(self, url_or_endpoint: str, params: dict = None,
            use_cache: bool = True, cache_key: str = None) -> dict:
        """Override para aceitar URL completa ou endpoint relativo."""
        import json
        if url_or_endpoint.startswith("http"):
            import requests as _req
            import time
            key = cache_key or f"{url_or_endpoint}:{json.dumps(params or {}, sort_keys=True)}"
            if use_cache:
                cached = self.cache.get(key)
                if cached is not None:
                    return cached
            self.rate_limiter.wait_if_needed()
            for attempt in range(3):
                try:
                    resp = self.session.get(url_or_endpoint, params=params, timeout=10)
                    resp.raise_for_status()
                    data = resp.json()
                    if use_cache:
                        self.cache.set(key, data)
                    return data
                except _req.exceptions.HTTPError as e:
                    if e.response.status_code == 429:
                        time.sleep((2 ** attempt) * 5)
                    elif e.response.status_code in [502, 503, 504]:
                        time.sleep(2 ** attempt)
                    else:
                        raise
                except (_req.exceptions.ConnectionError, _req.exceptions.Timeout):
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                    else:
                        raise
            raise Exception(f"Falha após 3 tentativas: {url_or_endpoint}")
        return super().get(url_or_endpoint, params, use_cache, cache_key)
