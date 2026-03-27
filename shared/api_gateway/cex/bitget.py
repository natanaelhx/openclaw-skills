"""
bitget.py — Cliente Bitget para o OpenClaw API Gateway.
"""
from .._base_cex import BaseCEXClient


class BitgetClient(BaseCEXClient):

    NAME          = "bitget"
    BASE_URL      = "https://api.bitget.com/api/v2/mix/market"
    CALLS_PER_MIN = 120
    CACHE_TTL     = 300
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["price", "funding_rate", "open_interest", "long_short_ratio"]

    def _health_check(self):
        self.session.get("https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES",
                         timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type == "funding_rate":
            return self._funding_rate(kwargs.get("symbol", "BTCUSDT"))
        if data_type == "open_interest":
            return self._open_interest(kwargs.get("symbol", "BTCUSDT"))
        raise ValueError(f"BitgetClient não suporta: {data_type}")

    def _norm_symbol(self, symbol: str) -> str:
        if not symbol.endswith("USDT"):
            return symbol
        if "_" in symbol:
            return symbol
        return symbol  # Bitget aceita BTCUSDT diretamente

    def _funding_rate(self, symbol: str) -> dict:
        from ..normalizer import DataNormalizer
        data = self.get("/current-fund-rate",
                        params={"symbol": symbol, "productType": "USDT-FUTURES"})
        return DataNormalizer.funding_rate(data, "bitget")

    def _open_interest(self, symbol: str) -> dict:
        from ..normalizer import DataNormalizer
        data = self.get("/open-interest",
                        params={"symbol": symbol, "productType": "USDT-FUTURES"})
        oi = float(data.get("data", {}).get("size", 0)) if data.get("data") else 0
        return {
            "symbol":        symbol,
            "oi_contracts":  oi,
            "oi_usd":        0.0,
            "oi_change_1h":  0.0,
            "oi_change_24h": 0.0,
            "source":        "bitget",
        }
