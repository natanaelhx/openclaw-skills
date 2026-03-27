"""
htx.py — Cliente HTX (ex-Huobi) para o OpenClaw API Gateway.
"""
from .._base_cex import BaseCEXClient


class HTXClient(BaseCEXClient):

    NAME          = "htx"
    BASE_URL      = "https://api.hbdm.com/linear-swap-ex/market"
    CALLS_PER_MIN = 100
    CACHE_TTL     = 300
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["price", "funding_rate", "open_interest"]

    def _health_check(self):
        self.session.get("https://api.huobi.pro/v1/common/timestamp", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type == "funding_rate":
            return self._funding_rate(kwargs.get("symbol", "BTC-USDT"))
        if data_type == "price":
            return self._price(kwargs.get("symbol", "btcusdt"))
        raise ValueError(f"HTXClient não suporta: {data_type}")

    def _norm_symbol(self, symbol: str) -> str:
        """BTCUSDT → BTC-USDT"""
        if "-" in symbol:
            return symbol
        if symbol.endswith("USDT"):
            return symbol[:-4] + "-USDT"
        return symbol

    def _funding_rate(self, symbol: str) -> dict:
        from ..normalizer import DataNormalizer
        sym  = self._norm_symbol(symbol)
        data = self.get("/swap-funding-rate", params={"contract_code": sym})
        return DataNormalizer.funding_rate(data, "htx")

    def _price(self, symbol: str) -> dict:
        sym  = symbol.lower().replace("-", "").replace("_", "")
        data = self.get("https://api.huobi.pro/market/detail/merged",
                        params={"symbol": sym})
        tick = data.get("tick", {})
        return {
            "symbol":     symbol,
            "price_usd":  float(tick.get("close", 0)),
            "change_24h": 0.0,
            "volume_24h": float(tick.get("amount", 0)),
            "source":     "htx",
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
