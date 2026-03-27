"""
coinglass.py — Cliente CoinGlass para o OpenClaw API Gateway.
"""
from ..base_client import BaseAPIClient


class CoinGlassClient(BaseAPIClient):

    NAME          = "coinglass"
    BASE_URL      = "https://open-api.coinglass.com/public/futures"
    CALLS_PER_MIN = 30
    CACHE_TTL     = 300
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["open_interest", "liquidations", "long_short_ratio",
                     "funding_rate", "fear_greed"]

    def _set_auth_header(self, key: str):
        self.session.headers["coinglassSecret"] = key

    def _health_check(self):
        self.session.get(self.BASE_URL + "/v2/open-interest", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type == "open_interest":
            return self._open_interest(kwargs.get("symbol", "BTC"))
        if data_type == "long_short_ratio":
            return self._ls_ratio(kwargs.get("symbol", "BTC"))
        if data_type == "liquidations":
            return self._liquidations(kwargs.get("symbol", "BTC"))
        if data_type == "funding_rate":
            return self._funding_rate(kwargs.get("symbol", "BTC"))
        raise ValueError(f"CoinGlassClient não suporta: {data_type}")

    def _open_interest(self, symbol: str) -> dict:
        data = self.get("/v2/open-interest", params={"symbol": symbol})
        item = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
        return {
            "symbol":        symbol,
            "oi_usd":        float(item.get("oiUSD", 0)),
            "oi_contracts":  float(item.get("oiAmount", 0)),
            "oi_change_24h": float(item.get("h24Change", 0)),
            "source":        "coinglass",
        }

    def _ls_ratio(self, symbol: str) -> dict:
        data = self.get("/v2/longShortRatio",
                        params={"symbol": symbol, "exchange": "Binance", "period": "4h", "limit": 1})
        lst  = data.get("data", [{}])
        item = lst[-1] if lst else {}
        long_pct  = float(item.get("longRatio", 0.5)) * 100
        short_pct = float(item.get("shortRatio", 0.5)) * 100
        return {
            "symbol":    symbol,
            "ratio":     long_pct / short_pct if short_pct else 0,
            "long_pct":  long_pct,
            "short_pct": short_pct,
            "type":      "account",
            "source":    "coinglass",
        }

    def _liquidations(self, symbol: str) -> dict:
        data = self.get("/v2/liquidation/info", params={"symbol": symbol})
        return {"symbol": symbol, "data": data.get("data", {}), "source": "coinglass"}

    def _funding_rate(self, symbol: str) -> dict:
        data = self.get("/v2/fundingRate", params={"symbol": symbol})
        lst  = data.get("data", [])
        rates = []
        for exchange in lst:
            rate = float(exchange.get("fundingRate", 0))
            rates.append({
                "exchange": exchange.get("exchangeName", ""),
                "rate":     rate,
                "rate_pct": f"{rate * 100:.4f}%",
            })
        return {"symbol": symbol, "rates": rates, "source": "coinglass"}
