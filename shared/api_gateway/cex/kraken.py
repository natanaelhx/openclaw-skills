"""
kraken.py — Cliente Kraken para o OpenClaw API Gateway.
"""
from .._base_cex import BaseCEXClient


class KrakenClient(BaseCEXClient):

    NAME          = "kraken"
    BASE_URL      = "https://api.kraken.com/0/public"
    BASE_FUTURES  = "https://futures.kraken.com/derivatives/api/v3"
    CALLS_PER_MIN = 60
    CACHE_TTL     = 300
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["price", "ohlcv", "orderbook", "funding_rate", "open_interest"]

    def _health_check(self):
        self.session.get(self.BASE_URL + "/Time", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type == "price":
            return self._price(kwargs.get("symbol", "XBTUSD"))
        if data_type == "funding_rate":
            return self._funding_rate(kwargs.get("symbol", "PF_XBTUSD"))
        raise ValueError(f"KrakenClient não suporta: {data_type}")

    def _price(self, symbol: str) -> dict:
        data = self.get("/Ticker", params={"pair": symbol})
        result = data.get("result", {})
        pair   = next(iter(result), symbol)
        item   = result.get(pair, {})
        price  = float(item.get("c", [0])[0]) if item.get("c") else 0
        return {
            "symbol":     symbol,
            "price_usd":  price,
            "change_24h": 0.0,
            "volume_24h": float(item.get("v", [0, 0])[1]) if item.get("v") else 0,
            "source":     "kraken",
        }

    def _funding_rate(self, symbol: str) -> dict:
        from ..normalizer import DataNormalizer, _safe_float
        data  = self.get(self.BASE_FUTURES + "/tickers", use_cache=True)
        ticks = data.get("tickers", [])
        item  = next((t for t in ticks if t.get("symbol") == symbol), {})
        rate  = _safe_float(item.get("fundingRate", 0))
        return {
            "symbol":          symbol,
            "rate":            rate,
            "rate_pct":        f"{rate * 100:.4f}%",
            "next_funding_ts": 0,
            "next_funding_dt": "",
            "mark_price":      _safe_float(item.get("markPrice")),
            "index_price":     _safe_float(item.get("indexPrice")),
            "source":          "kraken",
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
