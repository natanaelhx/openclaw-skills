"""
okx.py — Cliente OKX para o OpenClaw API Gateway.
"""
from .._base_cex import BaseCEXClient


class OKXClient(BaseCEXClient):

    NAME          = "okx"
    BASE_URL      = "https://www.okx.com/api/v5/public"
    BASE_MARKET   = "https://www.okx.com/api/v5/market"
    CALLS_PER_MIN = 60
    CACHE_TTL     = 300
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["price", "ohlcv", "funding_rate", "open_interest"]

    def _health_check(self):
        self.session.get(self.BASE_URL + "/instruments?instType=SPOT", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type == "funding_rate":
            return self._funding_rate(kwargs.get("symbol", "BTC-USDT"))
        if data_type == "open_interest":
            return self._open_interest(kwargs.get("symbol", "BTC-USDT"))
        if data_type == "price":
            return self._price(kwargs.get("symbol", "BTC-USDT"))
        raise ValueError(f"OKXClient não suporta: {data_type}")

    def _norm_symbol(self, symbol: str) -> str:
        """BTCUSDT → BTC-USDT-SWAP"""
        if symbol.endswith("-SWAP"):
            return symbol
        if "USDT" in symbol and "-" not in symbol:
            base = symbol.replace("USDT", "")
            return f"{base}-USDT-SWAP"
        return symbol

    def _funding_rate(self, symbol: str) -> dict:
        from ..normalizer import DataNormalizer
        inst = self._norm_symbol(symbol)
        data = self.get(self.BASE_URL + "/funding-rate", params={"instId": inst})
        return DataNormalizer.funding_rate(data, "okx")

    def _open_interest(self, symbol: str) -> dict:
        from ..normalizer import DataNormalizer
        inst = self._norm_symbol(symbol)
        data = self.get(self.BASE_URL + "/open-interest", params={"instId": inst})
        return DataNormalizer.open_interest(data, "okx")

    def _price(self, symbol: str) -> dict:
        inst = symbol if "-" in symbol else f"{symbol.replace('USDT','')}-USDT"
        data = self.get(self.BASE_MARKET + "/ticker", params={"instId": inst})
        item = data.get("data", [{}])[0] if data.get("data") else {}
        return {
            "symbol":     item.get("instId", symbol),
            "price_usd":  float(item.get("last", 0)),
            "change_24h": 0.0,
            "volume_24h": float(item.get("vol24h", 0)),
            "source":     "okx",
        }

    def get(self, url_or_endpoint: str, params: dict = None,
            use_cache: bool = True, cache_key: str = None) -> dict:
        if url_or_endpoint.startswith("http"):
            import json, time, requests as _req
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
