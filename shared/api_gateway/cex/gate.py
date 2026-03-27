"""
gate.py — Cliente Gate.io para o OpenClaw API Gateway.
"""
from .._base_cex import BaseCEXClient


class GateClient(BaseCEXClient):

    NAME          = "gate"
    BASE_URL      = "https://api.gateio.ws/api/v4/futures/usdt"
    BASE_SPOT     = "https://api.gateio.ws/api/v4/spot"
    CALLS_PER_MIN = 900
    CACHE_TTL     = 300
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["price", "ohlcv", "funding_rate", "open_interest"]

    def _health_check(self):
        self.session.get(self.BASE_SPOT + "/tickers?currency_pair=BTC_USDT", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type == "funding_rate":
            return self._funding_rate(kwargs.get("symbol", "BTC_USDT"))
        if data_type == "price":
            return self._price(kwargs.get("symbol", "BTC_USDT"))
        raise ValueError(f"GateClient não suporta: {data_type}")

    def _norm_symbol(self, symbol: str) -> str:
        """BTCUSDT → BTC_USDT"""
        if "_" in symbol:
            return symbol
        if symbol.endswith("USDT"):
            return symbol[:-4] + "_USDT"
        return symbol

    def _funding_rate(self, symbol: str) -> dict:
        from ..normalizer import DataNormalizer
        sym  = self._norm_symbol(symbol)
        data = self.get("/contracts/" + sym)
        return DataNormalizer.funding_rate(data, "gate")

    def _price(self, symbol: str) -> dict:
        sym  = self._norm_symbol(symbol)
        data = self.get(self.BASE_SPOT + "/tickers", params={"currency_pair": sym})
        item = data[0] if isinstance(data, list) and data else {}
        return {
            "symbol":     sym,
            "price_usd":  float(item.get("last", 0)),
            "change_24h": float(item.get("change_percentage", 0)),
            "volume_24h": float(item.get("base_volume", 0)),
            "source":     "gate",
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
                    if e.response.status_code in [429, 502, 503, 504]:
                        time.sleep(2 ** attempt)
                    else:
                        raise
                except (_req.exceptions.ConnectionError, _req.exceptions.Timeout):
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                    else:
                        raise
            raise Exception(f"Falha: {url_or_endpoint}")
        return super().get(url_or_endpoint, params, use_cache, cache_key)
