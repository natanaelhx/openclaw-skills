"""
normalizer.py — Normaliza dados de diferentes APIs para formato padrão único.
As skills nunca lidam com o formato raw de cada API.
"""
from datetime import datetime, timezone
from typing import Optional


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_float(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


class DataNormalizer:
    """
    Normaliza dados de diferentes APIs para um formato padrão único.
    Métodos estáticos — sem estado.
    """

    @staticmethod
    def funding_rate(raw: dict, source: str) -> dict:
        """
        Formato padrão:
        {
            symbol, rate (float), rate_pct (str),
            next_funding_ts (int), next_funding_dt (str),
            mark_price (float), index_price (float),
            source (str), fetched_at (str)
        }
        """
        normalizers = {
            "binance": DataNormalizer._funding_from_binance,
            "bybit":   DataNormalizer._funding_from_bybit,
            "okx":     DataNormalizer._funding_from_okx,
            "bitget":  DataNormalizer._funding_from_bitget,
            "gate":    DataNormalizer._funding_from_gate,
            "mexc":    DataNormalizer._funding_from_mexc,
            "htx":     DataNormalizer._funding_from_htx,
        }
        fn = normalizers.get(source, DataNormalizer._funding_generic)
        return fn(raw)

    @staticmethod
    def _funding_from_binance(raw: dict) -> dict:
        rate = _safe_float(raw.get("lastFundingRate"))
        ts   = _safe_int(raw.get("nextFundingTime", 0)) // 1000
        return {
            "symbol":          raw.get("symbol", ""),
            "rate":            rate,
            "rate_pct":        f"{rate * 100:.4f}%",
            "next_funding_ts": ts,
            "next_funding_dt": _ts_to_str(ts),
            "mark_price":      _safe_float(raw.get("markPrice")),
            "index_price":     _safe_float(raw.get("indexPrice")),
            "source":          "binance",
            "fetched_at":      _now_utc(),
        }

    @staticmethod
    def _funding_from_bybit(raw: dict) -> dict:
        item = raw.get("result", {})
        if isinstance(item, dict) and "list" in item:
            item = item["list"][0] if item["list"] else {}
        rate = _safe_float(item.get("fundingRate"))
        ts   = _safe_int(item.get("nextFundingTime", 0)) // 1000
        return {
            "symbol":          item.get("symbol", ""),
            "rate":            rate,
            "rate_pct":        f"{rate * 100:.4f}%",
            "next_funding_ts": ts,
            "next_funding_dt": _ts_to_str(ts),
            "mark_price":      _safe_float(item.get("markPrice")),
            "index_price":     _safe_float(item.get("indexPrice")),
            "source":          "bybit",
            "fetched_at":      _now_utc(),
        }

    @staticmethod
    def _funding_from_okx(raw: dict) -> dict:
        item = raw.get("data", [{}])[0] if raw.get("data") else {}
        rate = _safe_float(item.get("fundingRate"))
        ts   = _safe_int(item.get("nextFundingTime", 0)) // 1000
        return {
            "symbol":          item.get("instId", "").replace("-SWAP", "").replace("-", ""),
            "rate":            rate,
            "rate_pct":        f"{rate * 100:.4f}%",
            "next_funding_ts": ts,
            "next_funding_dt": _ts_to_str(ts),
            "mark_price":      _safe_float(item.get("markPx")),
            "index_price":     _safe_float(item.get("idxPx")),
            "source":          "okx",
            "fetched_at":      _now_utc(),
        }

    @staticmethod
    def _funding_from_bitget(raw: dict) -> dict:
        item = raw.get("data", {}) if raw.get("data") else {}
        rate = _safe_float(item.get("fundingRate"))
        ts   = _safe_int(item.get("nextFundingTime", 0)) // 1000
        return {
            "symbol":          item.get("symbol", ""),
            "rate":            rate,
            "rate_pct":        f"{rate * 100:.4f}%",
            "next_funding_ts": ts,
            "next_funding_dt": _ts_to_str(ts),
            "mark_price":      _safe_float(item.get("markPrice")),
            "index_price":     0.0,
            "source":          "bitget",
            "fetched_at":      _now_utc(),
        }

    @staticmethod
    def _funding_from_gate(raw: dict) -> dict:
        # Gate retorna lista quando sem symbol, ou dict
        if isinstance(raw, list):
            item = raw[0] if raw else {}
        else:
            item = raw
        rate = _safe_float(item.get("funding_rate"))
        ts   = _safe_int(item.get("funding_next_apply", 0))
        return {
            "symbol":          item.get("name", ""),
            "rate":            rate,
            "rate_pct":        f"{rate * 100:.4f}%",
            "next_funding_ts": ts,
            "next_funding_dt": _ts_to_str(ts),
            "mark_price":      _safe_float(item.get("mark_price")),
            "index_price":     _safe_float(item.get("index_price")),
            "source":          "gate",
            "fetched_at":      _now_utc(),
        }

    @staticmethod
    def _funding_from_mexc(raw: dict) -> dict:
        item = raw.get("data", {}) if isinstance(raw.get("data"), dict) else {}
        rate = _safe_float(item.get("fundingRate"))
        ts   = _safe_int(item.get("nextSettleTime", 0)) // 1000
        return {
            "symbol":          item.get("symbol", ""),
            "rate":            rate,
            "rate_pct":        f"{rate * 100:.4f}%",
            "next_funding_ts": ts,
            "next_funding_dt": _ts_to_str(ts),
            "mark_price":      _safe_float(item.get("fairPrice")),
            "index_price":     _safe_float(item.get("indexPrice")),
            "source":          "mexc",
            "fetched_at":      _now_utc(),
        }

    @staticmethod
    def _funding_from_htx(raw: dict) -> dict:
        item = raw.get("data", [{}])[0] if raw.get("data") else {}
        rate = _safe_float(item.get("funding_rate"))
        ts   = _safe_int(item.get("next_funding_time", 0)) // 1000
        return {
            "symbol":          item.get("contract_code", ""),
            "rate":            rate,
            "rate_pct":        f"{rate * 100:.4f}%",
            "next_funding_ts": ts,
            "next_funding_dt": _ts_to_str(ts),
            "mark_price":      0.0,
            "index_price":     0.0,
            "source":          "htx",
            "fetched_at":      _now_utc(),
        }

    @staticmethod
    def _funding_generic(raw: dict) -> dict:
        rate = _safe_float(
            raw.get("fundingRate") or raw.get("funding_rate") or raw.get("rate", 0)
        )
        return {
            "symbol":          raw.get("symbol", ""),
            "rate":            rate,
            "rate_pct":        f"{rate * 100:.4f}%",
            "next_funding_ts": 0,
            "next_funding_dt": "",
            "mark_price":      0.0,
            "index_price":     0.0,
            "source":          "unknown",
            "fetched_at":      _now_utc(),
        }

    @staticmethod
    def pool(raw: dict, source: str) -> dict:
        """
        Formato padrão de pool de liquidez.
        """
        normalizers = {
            "defillama":  DataNormalizer._pool_from_defillama,
            "uniswap_v3": DataNormalizer._pool_from_uniswap_v3,
            "aerodrome":  DataNormalizer._pool_from_aerodrome,
            "curve":      DataNormalizer._pool_from_curve,
        }
        fn = normalizers.get(source, DataNormalizer._pool_generic)
        return fn(raw)

    @staticmethod
    def _pool_from_defillama(raw: dict) -> dict:
        apr_base    = _safe_float(raw.get("apyBase"))
        apr_reward  = _safe_float(raw.get("apyReward"))
        apr_total   = _safe_float(raw.get("apy"))
        yield_24h   = _safe_float(raw.get("apyBase24h", apr_total / 365 if apr_total else 0))
        tokens      = raw.get("underlyingTokens", [])
        symbol      = raw.get("symbol", "")
        return {
            "pool_id":    raw.get("pool", ""),
            "protocol":   raw.get("project", ""),
            "chain":      raw.get("chain", ""),
            "token0":     symbol.split("-")[0] if "-" in symbol else symbol.split("/")[0] if "/" in symbol else "",
            "token1":     symbol.split("-")[1] if "-" in symbol else symbol.split("/")[1] if "/" in symbol else "",
            "symbol":     symbol,
            "fee_tier":   0.0,
            "tvl_usd":    _safe_float(raw.get("tvlUsd")),
            "volume_24h": _safe_float(raw.get("volumeUsd24h")),
            "apr_base":   apr_base,
            "apr_reward": apr_reward,
            "apr_total":  apr_total,
            "il_7d":      _safe_float(raw.get("il7d")),
            "yield_24h":  yield_24h,
            "risk_score": _risk_score(apr_total, _safe_float(raw.get("tvlUsd")), raw.get("project", "")),
            "source":     "defillama",
            "fetched_at": _now_utc(),
        }

    @staticmethod
    def _pool_from_uniswap_v3(raw: dict) -> dict:
        tvl     = _safe_float(raw.get("totalValueLockedUSD"))
        vol_24h = _safe_float(raw.get("volumeUSD"))
        fee_tier = _safe_float(raw.get("feeTier", 0)) / 10000  # bps -> %
        apr_base = (vol_24h * fee_tier / 100 / tvl * 365 * 100) if tvl > 0 else 0
        t0 = raw.get("token0", {})
        t1 = raw.get("token1", {})
        return {
            "pool_id":    raw.get("id", ""),
            "protocol":   "uniswap-v3",
            "chain":      raw.get("_chain", "Ethereum"),
            "token0":     t0.get("symbol", ""),
            "token1":     t1.get("symbol", ""),
            "symbol":     f"{t0.get('symbol','')}/{t1.get('symbol','')}",
            "fee_tier":   fee_tier,
            "tvl_usd":    tvl,
            "volume_24h": vol_24h,
            "apr_base":   apr_base,
            "apr_reward": 0.0,
            "apr_total":  apr_base,
            "il_7d":      0.0,
            "yield_24h":  apr_base / 365,
            "risk_score": _risk_score(apr_base, tvl, "uniswap-v3"),
            "source":     "uniswap_v3",
            "fetched_at": _now_utc(),
        }

    @staticmethod
    def _pool_from_aerodrome(raw: dict) -> dict:
        tvl     = _safe_float(raw.get("tvl") or raw.get("reserveUSD"))
        apr_total = _safe_float(raw.get("apr") or raw.get("gaugeApr"))
        return {
            "pool_id":    raw.get("address", raw.get("lp", "")),
            "protocol":   "aerodrome",
            "chain":      "Base",
            "token0":     raw.get("token0", {}).get("symbol", ""),
            "token1":     raw.get("token1", {}).get("symbol", ""),
            "symbol":     raw.get("symbol", ""),
            "fee_tier":   _safe_float(raw.get("fee", 0)) / 100,
            "tvl_usd":    tvl,
            "volume_24h": _safe_float(raw.get("volume24h") or raw.get("volumeUSD")),
            "apr_base":   _safe_float(raw.get("baseApr")),
            "apr_reward": _safe_float(raw.get("gaugeApr")),
            "apr_total":  apr_total,
            "il_7d":      0.0,
            "yield_24h":  apr_total / 365,
            "risk_score": _risk_score(apr_total, tvl, "aerodrome"),
            "source":     "aerodrome",
            "fetched_at": _now_utc(),
        }

    @staticmethod
    def _pool_from_curve(raw: dict) -> dict:
        apr_base   = _safe_float(raw.get("latestDailyApy", 0)) * 365
        apr_reward = _safe_float(raw.get("crvApy", 0))
        apr_total  = apr_base + apr_reward
        tvl        = _safe_float(raw.get("usdTotal"))
        return {
            "pool_id":    raw.get("address", ""),
            "protocol":   "curve",
            "chain":      raw.get("_chain", "Ethereum"),
            "token0":     "",
            "token1":     "",
            "symbol":     raw.get("name", ""),
            "fee_tier":   _safe_float(raw.get("fee", 0)) * 100,
            "tvl_usd":    tvl,
            "volume_24h": _safe_float(raw.get("volumeUSD")),
            "apr_base":   apr_base,
            "apr_reward": apr_reward,
            "apr_total":  apr_total,
            "il_7d":      0.0,
            "yield_24h":  apr_total / 365,
            "risk_score": _risk_score(apr_total, tvl, "curve"),
            "source":     "curve",
            "fetched_at": _now_utc(),
        }

    @staticmethod
    def _pool_generic(raw: dict) -> dict:
        return {
            "pool_id":    raw.get("id", raw.get("address", "")),
            "protocol":   raw.get("protocol", ""),
            "chain":      raw.get("chain", ""),
            "token0":     "",
            "token1":     "",
            "symbol":     raw.get("symbol", ""),
            "fee_tier":   0.0,
            "tvl_usd":    _safe_float(raw.get("tvlUsd") or raw.get("tvl")),
            "volume_24h": _safe_float(raw.get("volumeUsd24h") or raw.get("volume24h")),
            "apr_base":   _safe_float(raw.get("apyBase") or raw.get("apr")),
            "apr_reward": _safe_float(raw.get("apyReward")),
            "apr_total":  _safe_float(raw.get("apy") or raw.get("apr_total")),
            "il_7d":      0.0,
            "yield_24h":  0.0,
            "risk_score": "N/A",
            "source":     "unknown",
            "fetched_at": _now_utc(),
        }

    @staticmethod
    def open_interest(raw: dict, source: str) -> dict:
        """Formato padrão de open interest."""
        normalizers = {
            "binance": DataNormalizer._oi_from_binance,
            "bybit":   DataNormalizer._oi_from_bybit,
            "okx":     DataNormalizer._oi_from_okx,
        }
        fn = normalizers.get(source, DataNormalizer._oi_generic)
        return fn(raw)

    @staticmethod
    def _oi_from_binance(raw: dict) -> dict:
        return {
            "symbol":        raw.get("symbol", ""),
            "oi_contracts":  _safe_float(raw.get("openInterest")),
            "oi_usd":        0.0,
            "oi_change_1h":  0.0,
            "oi_change_24h": 0.0,
            "source":        "binance",
            "fetched_at":    _now_utc(),
        }

    @staticmethod
    def _oi_from_bybit(raw: dict) -> dict:
        item = raw.get("result", {})
        lst  = item.get("list", [{}]) if isinstance(item, dict) else [{}]
        d    = lst[0] if lst else {}
        return {
            "symbol":        d.get("symbol", ""),
            "oi_contracts":  _safe_float(d.get("openInterest")),
            "oi_usd":        0.0,
            "oi_change_1h":  0.0,
            "oi_change_24h": 0.0,
            "source":        "bybit",
            "fetched_at":    _now_utc(),
        }

    @staticmethod
    def _oi_from_okx(raw: dict) -> dict:
        item = raw.get("data", [{}])[0] if raw.get("data") else {}
        return {
            "symbol":        item.get("instId", "").replace("-SWAP", "").replace("-", ""),
            "oi_contracts":  _safe_float(item.get("oi")),
            "oi_usd":        _safe_float(item.get("oiCcy")),
            "oi_change_1h":  0.0,
            "oi_change_24h": 0.0,
            "source":        "okx",
            "fetched_at":    _now_utc(),
        }

    @staticmethod
    def _oi_generic(raw: dict) -> dict:
        return {
            "symbol":        raw.get("symbol", ""),
            "oi_contracts":  _safe_float(raw.get("openInterest") or raw.get("oi")),
            "oi_usd":        0.0,
            "oi_change_1h":  0.0,
            "oi_change_24h": 0.0,
            "source":        "unknown",
            "fetched_at":    _now_utc(),
        }

    @staticmethod
    def price(raw: dict, source: str) -> dict:
        """Formato padrão de preço."""
        normalizers = {
            "binance":    DataNormalizer._price_from_binance,
            "coingecko":  DataNormalizer._price_from_coingecko,
            "dexscreener": DataNormalizer._price_from_dexscreener,
        }
        fn = normalizers.get(source, DataNormalizer._price_generic)
        return fn(raw)

    @staticmethod
    def _price_from_binance(raw: dict) -> dict:
        return {
            "symbol":     raw.get("symbol", ""),
            "price_usd":  _safe_float(raw.get("price")),
            "change_1h":  0.0,
            "change_24h": _safe_float(raw.get("priceChangePercent")),
            "change_7d":  0.0,
            "volume_24h": _safe_float(raw.get("volume")),
            "market_cap": 0.0,
            "source":     "binance",
            "fetched_at": _now_utc(),
        }

    @staticmethod
    def _price_from_coingecko(raw: dict) -> dict:
        # raw pode ser {coin_id: {usd: price, ...}}
        if raw and not raw.get("price_usd"):
            coin_id = next(iter(raw), "")
            data    = raw.get(coin_id, {})
            return {
                "symbol":     coin_id.upper(),
                "price_usd":  _safe_float(data.get("usd")),
                "change_1h":  _safe_float(data.get("usd_1h_change")),
                "change_24h": _safe_float(data.get("usd_24h_change")),
                "change_7d":  0.0,
                "volume_24h": _safe_float(data.get("usd_24h_vol")),
                "market_cap": _safe_float(data.get("usd_market_cap")),
                "source":     "coingecko",
                "fetched_at": _now_utc(),
            }
        return DataNormalizer._price_generic(raw)

    @staticmethod
    def _price_from_dexscreener(raw: dict) -> dict:
        pair = raw.get("pairs", [{}])[0] if raw.get("pairs") else {}
        return {
            "symbol":     pair.get("baseToken", {}).get("symbol", ""),
            "price_usd":  _safe_float(pair.get("priceUsd")),
            "change_1h":  _safe_float(pair.get("priceChange", {}).get("h1")),
            "change_24h": _safe_float(pair.get("priceChange", {}).get("h24")),
            "change_7d":  0.0,
            "volume_24h": _safe_float(pair.get("volume", {}).get("h24")),
            "market_cap": _safe_float(pair.get("marketCap")),
            "source":     "dexscreener",
            "fetched_at": _now_utc(),
        }

    @staticmethod
    def _price_generic(raw: dict) -> dict:
        return {
            "symbol":     raw.get("symbol", ""),
            "price_usd":  _safe_float(raw.get("price_usd") or raw.get("price") or raw.get("lastPrice")),
            "change_1h":  0.0,
            "change_24h": _safe_float(raw.get("change_24h") or raw.get("priceChangePercent")),
            "change_7d":  0.0,
            "volume_24h": _safe_float(raw.get("volume_24h") or raw.get("volume")),
            "market_cap": 0.0,
            "source":     "unknown",
            "fetched_at": _now_utc(),
        }

    @staticmethod
    def long_short_ratio(raw: dict, source: str) -> dict:
        """Formato padrão de long/short ratio."""
        normalizers = {
            "binance": DataNormalizer._ls_from_binance,
            "bybit":   DataNormalizer._ls_from_bybit,
        }
        fn = normalizers.get(source, DataNormalizer._ls_generic)
        return fn(raw)

    @staticmethod
    def _ls_from_binance(raw: dict) -> dict:
        if isinstance(raw, list):
            item = raw[0] if raw else {}
        else:
            item = raw
        long_pct = _safe_float(item.get("longAccount") or item.get("longPosition", 0)) * 100
        short_pct = _safe_float(item.get("shortAccount") or item.get("shortPosition", 0)) * 100
        ratio = long_pct / short_pct if short_pct > 0 else 0
        return {
            "symbol":     item.get("symbol", ""),
            "ratio":      ratio,
            "long_pct":   long_pct,
            "short_pct":  short_pct,
            "type":       "account",
            "change_24h": 0.0,
            "source":     "binance",
            "fetched_at": _now_utc(),
        }

    @staticmethod
    def _ls_from_bybit(raw: dict) -> dict:
        lst  = raw.get("result", {}).get("list", [{}]) if isinstance(raw.get("result"), dict) else [{}]
        item = lst[0] if lst else {}
        buy  = _safe_float(item.get("buyRatio", 0.5))
        sell = _safe_float(item.get("sellRatio", 0.5))
        ratio = buy / sell if sell > 0 else 0
        return {
            "symbol":     item.get("symbol", ""),
            "ratio":      ratio,
            "long_pct":   buy * 100,
            "short_pct":  sell * 100,
            "type":       "account",
            "change_24h": 0.0,
            "source":     "bybit",
            "fetched_at": _now_utc(),
        }

    @staticmethod
    def _ls_generic(raw: dict) -> dict:
        long_pct  = _safe_float(raw.get("long_pct") or raw.get("longAccount", 0)) * 100
        short_pct = _safe_float(raw.get("short_pct") or raw.get("shortAccount", 0)) * 100
        ratio     = long_pct / short_pct if short_pct > 0 else 0
        return {
            "symbol":     raw.get("symbol", ""),
            "ratio":      ratio,
            "long_pct":   long_pct,
            "short_pct":  short_pct,
            "type":       "account",
            "change_24h": 0.0,
            "source":     "unknown",
            "fetched_at": _now_utc(),
        }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ts_to_str(ts: int) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ""


def _risk_score(apr: float, tvl: float, protocol: str) -> str:
    safe_protocols = {"uniswap-v3", "curve", "balancer", "aerodrome", "velodrome"}
    if tvl < 100_000:
        return "ALTO"
    if apr > 100 and protocol not in safe_protocols:
        return "ALTO"
    if apr > 50:
        return "MÉDIO"
    if protocol in safe_protocols and tvl > 1_000_000:
        return "BAIXO"
    return "MÉDIO"
