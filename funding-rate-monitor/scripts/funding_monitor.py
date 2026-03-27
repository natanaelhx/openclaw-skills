#!/usr/bin/env python3
"""
funding_monitor.py — Unified Funding Rate Monitor & Backtest Skill
Combines: fetch, backtest, tests, and reporting in a single script.

Strategy: "Funding Rate Extreme Reversal"
  SHORT when funding > +0.08%  (overbought)
  LONG  when funding < -0.03%  (oversold)
  FLAT  otherwise
  Risk: SL 2%, TP 3%, normalize exit, 1 position at a time.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

import os, sys, json, csv, math, bisect, argparse, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    import pandas as pd
    import numpy as np
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

BASE_BINANCE = "https://fapi.binance.com/fapi/v1"
BASE_BYBIT   = "https://api.bybit.com/v5/market"
SYMBOLS_DEFAULT = ["BTCUSDT", "ETHUSDT"]

# ── API Gateway (opcional — fallback automático para chamadas diretas) ──────
_SHARED_DIR = Path(__file__).parent.parent.parent / "shared"
if _SHARED_DIR.exists():
    sys.path.insert(0, str(_SHARED_DIR))
    try:
        from api_gateway.router import APIRouter as _APIRouter
        _ROUTER = _APIRouter()
        _GATEWAY_AVAILABLE = True
    except ImportError:
        _ROUTER = None
        _GATEWAY_AVAILABLE = False
else:
    _ROUTER = None
    _GATEWAY_AVAILABLE = False
FUNDING_HIGH     = 0.08    # % threshold SHORT signal
FUNDING_LOW      = -0.03   # % threshold LONG signal
ADAPTIVE_PCT     = 0.15
INITIAL_CAPITAL  = 10_000.0
STOP_LOSS        = 0.02
TAKE_PROFIT      = 0.03
DATA_DIR  = Path(os.path.expanduser("~/funding_backtest/data"))
REPORT_DIR = Path(os.path.expanduser("~/funding_backtest/reports"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: FETCH
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_json(url):
    """Fetch URL with timeout=15, raises RuntimeError on failure."""
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {url}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")
    except Exception as e:
        raise RuntimeError(f"Fetch error: {e}")


def minutes_until(iso_time):
    """Return human-readable string like '5h 23min' until the given ISO time."""
    try:
        if iso_time.endswith("Z"):
            iso_time = iso_time[:-1] + "+00:00"
        target = datetime.fromisoformat(iso_time)
        now = datetime.now(timezone.utc)
        diff_secs = (target - now).total_seconds()
        if diff_secs <= 0:
            return "now"
        hours = int(diff_secs // 3600)
        mins = int((diff_secs % 3600) // 60)
        if hours > 0:
            return f"{hours}h {mins}min"
        return f"{mins}min"
    except Exception:
        return iso_time


def get_current_funding(symbol, exchange="binance"):
    """Return dict: {symbol, rate_pct, next_funding_time_iso, time_until_next, exchange}.
    Usa APIRouter quando disponível (fallback automático entre exchanges).
    """
    # Tenta via APIRouter primeiro (tem fallback automático)
    if _GATEWAY_AVAILABLE and _ROUTER:
        try:
            data = _ROUTER.fetch("funding_rate", symbol=symbol)
            return {
                "symbol":               symbol,
                "rate_pct":             data["rate"] * 100,
                "next_funding_time_iso": data.get("next_funding_dt", ""),
                "time_until_next":      "via router",
                "exchange":             data.get("_source", exchange),
            }
        except Exception:
            pass  # Fallback para chamada direta

    if exchange == "binance":
        url = f"{BASE_BINANCE}/premiumIndex?symbol={symbol}"
        data = fetch_json(url)
        rate_pct = float(data["lastFundingRate"]) * 100
        nft_ms = int(data["nextFundingTime"])
        nft_iso = datetime.fromtimestamp(nft_ms / 1000, tz=timezone.utc).isoformat()
        return {
            "symbol": symbol,
            "rate_pct": rate_pct,
            "next_funding_time_iso": nft_iso,
            "time_until_next": minutes_until(nft_iso),
            "exchange": exchange,
        }
    elif exchange == "bybit":
        url = f"{BASE_BYBIT}/tickers?category=linear&symbol={symbol}"
        data = fetch_json(url)
        item = data["result"]["list"][0]
        rate_pct = float(item.get("fundingRate", 0)) * 100
        nft_iso = ""
        nft_ts = item.get("nextFundingTime", "")
        if nft_ts:
            try:
                nft_iso = datetime.fromtimestamp(int(nft_ts) / 1000, tz=timezone.utc).isoformat()
            except Exception:
                nft_iso = str(nft_ts)
        return {
            "symbol": symbol,
            "rate_pct": rate_pct,
            "next_funding_time_iso": nft_iso,
            "time_until_next": minutes_until(nft_iso) if nft_iso else "N/A",
            "exchange": exchange,
        }
    else:
        raise ValueError(f"Unknown exchange: {exchange}")


def get_funding_history(symbol, limit=500, exchange="binance"):
    """Return list of dicts: {ts, iso, rate, symbol}."""
    if exchange == "binance":
        url = f"{BASE_BINANCE}/fundingRate?symbol={symbol}&limit={limit}"
        raw = fetch_json(url)
        result = []
        for row in raw:
            ts = int(row["fundingTime"])
            iso = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
            rate = float(row["fundingRate"]) * 100
            result.append({"ts": ts, "iso": iso, "rate": rate, "symbol": symbol})
        return sorted(result, key=lambda x: x["ts"])
    elif exchange == "bybit":
        url = f"{BASE_BYBIT}/funding/history?category=linear&symbol={symbol}&limit={limit}"
        data = fetch_json(url)
        result = []
        for row in data["result"]["list"]:
            ts = int(row["fundingRateTimestamp"])
            iso = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
            rate = float(row["fundingRate"]) * 100
            result.append({"ts": ts, "iso": iso, "rate": rate, "symbol": symbol})
        return sorted(result, key=lambda x: x["ts"])
    else:
        raise ValueError(f"Unknown exchange: {exchange}")


def get_top_funding(n=10, exchange="binance"):
    """Fetch all pairs from premiumIndex, return dict {top_positive: [...], top_negative: [...]}."""
    if exchange == "binance":
        url = f"{BASE_BINANCE}/premiumIndex"
        raw = fetch_json(url)
        parsed = []
        for item in raw:
            try:
                rate = float(item["lastFundingRate"]) * 100
                parsed.append({"symbol": item["symbol"], "rate": rate})
            except (KeyError, ValueError):
                continue
        sorted_pairs = sorted(parsed, key=lambda x: x["rate"])
        top_negative = sorted_pairs[:n]
        top_positive = list(reversed(sorted_pairs[-n:]))
        return {"top_positive": top_positive, "top_negative": top_negative}
    elif exchange == "bybit":
        url = f"{BASE_BYBIT}/tickers?category=linear"
        data = fetch_json(url)
        parsed = []
        for item in data["result"]["list"]:
            try:
                rate = float(item.get("fundingRate", 0)) * 100
                parsed.append({"symbol": item["symbol"], "rate": rate})
            except (KeyError, ValueError):
                continue
        sorted_pairs = sorted(parsed, key=lambda x: x["rate"])
        top_negative = sorted_pairs[:n]
        top_positive = list(reversed(sorted_pairs[-n:]))
        return {"top_positive": top_positive, "top_negative": top_negative}
    else:
        raise ValueError(f"Unknown exchange: {exchange}")


def save_history_csv(data, filepath):
    """Save list of funding dicts to CSV."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "fundingTime", "fundingTime_iso", "fundingRate_pct"])
        for row in data:
            writer.writerow([
                row.get("symbol", ""),
                row["ts"],
                row["iso"],
                f"{row['rate']:.6f}",
            ])


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: BACKTEST
# ═══════════════════════════════════════════════════════════════════════════════

def classify_signal(rate_pct, short_thr, long_thr):
    """Return 'SHORT', 'LONG', or 'FLAT'."""
    if rate_pct > short_thr:
        return "SHORT"
    elif rate_pct < long_thr:
        return "LONG"
    return "FLAT"


def compute_adaptive_thresholds(rates):
    """Return (long_thr, short_thr) using ADAPTIVE_PCT percentiles."""
    sorted_rates = sorted(rates)
    n = len(sorted_rates)
    low_idx = max(0, int(n * ADAPTIVE_PCT) - 1)
    high_idx = min(n - 1, int(n * (1 - ADAPTIVE_PCT)))
    long_threshold = sorted_rates[low_idx]
    short_threshold = sorted_rates[high_idx]
    return long_threshold, short_threshold


def fetch_klines_8h(symbol, limit=500):
    """Fetch from Binance /klines?symbol=X&interval=8h&limit=N.
    Returns list of {open_time, open, high, low, close}."""
    url = f"{BASE_BINANCE}/klines?symbol={symbol}&interval=8h&limit={limit}"
    raw = fetch_json(url)
    result = []
    for k in raw:
        result.append({
            "open_time": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
        })
    return result


def run_backtest(funding_data, price_data, short_thr, long_thr):
    """
    Merges funding data with price data using bisect.
    Runs strategy with SL/TP/normalize exits.
    Returns dict with: trades, metrics, equity_curve, threshold_mode, short_thr, long_thr.
    """
    # Determine threshold mode
    use_adaptive = (short_thr != FUNDING_HIGH) or (long_thr != FUNDING_LOW)
    threshold_mode = "ADAPTIVE (15th percentile)" if use_adaptive else "ABSOLUTE"

    # Neutral zone for normalize exit
    mid = (short_thr + long_thr) / 2
    band = (short_thr - long_thr) * 0.2

    def is_neutral(rate):
        return abs(rate - mid) < band

    # Build price lookup
    price_map = {p["open_time"]: p for p in price_data}
    price_times = sorted(price_map.keys())

    def nearest_price(ts_ms):
        idx = bisect.bisect_left(price_times, ts_ms)
        best = None
        best_diff = 4 * 3600 * 1000  # 4h in ms
        for i in [idx - 1, idx, idx + 1]:
            if 0 <= i < len(price_times):
                diff = abs(price_times[i] - ts_ms)
                if diff < best_diff:
                    best_diff = diff
                    best = price_map[price_times[i]]
        return best

    trades = []
    equity = INITIAL_CAPITAL
    equity_curve = [{"ts": funding_data[0]["iso"], "equity": equity}]
    position = None
    long_count = short_count = 0

    for row in funding_data:
        rate = row["rate"]
        candle = nearest_price(row["ts"])
        if candle is None:
            continue

        entry_price = candle["open"]
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]

        # Manage open position
        if position is not None:
            direction = position["direction"]
            ep = position["entry_price"]
            size = position["size"]
            pnl = None
            exit_price = None
            exit_reason = None

            if direction == "LONG":
                sl_price = ep * (1 - STOP_LOSS)
                tp_price = ep * (1 + TAKE_PROFIT)
                if low <= sl_price:
                    pnl = size * (sl_price - ep) / ep
                    exit_price = sl_price
                    exit_reason = "SL"
                elif high >= tp_price:
                    pnl = size * (tp_price - ep) / ep
                    exit_price = tp_price
                    exit_reason = "TP"
                elif is_neutral(rate):
                    pnl = size * (close - ep) / ep
                    exit_price = close
                    exit_reason = "NORMALIZE"
            else:  # SHORT
                sl_price = ep * (1 + STOP_LOSS)
                tp_price = ep * (1 - TAKE_PROFIT)
                if high >= sl_price:
                    pnl = size * (ep - sl_price) / ep
                    exit_price = sl_price
                    exit_reason = "SL"
                elif low <= tp_price:
                    pnl = size * (ep - tp_price) / ep
                    exit_price = tp_price
                    exit_reason = "TP"
                elif is_neutral(rate):
                    pnl = size * (ep - close) / ep
                    exit_price = close
                    exit_reason = "NORMALIZE"

            if pnl is not None:
                equity += pnl
                trades.append({
                    "entry_ts": position["entry_ts"],
                    "exit_ts": row["iso"],
                    "direction": direction,
                    "entry_price": ep,
                    "exit_price": exit_price,
                    "size": size,
                    "pnl": pnl,
                    "pnl_pct": pnl / size * 100,
                    "exit_reason": exit_reason,
                    "entry_rate": position["entry_rate"],
                })
                position = None

        # Check for new entry
        if position is None:
            sig = classify_signal(rate, short_thr, long_thr)
            if sig != "FLAT":
                size = equity  # leverage = 1x
                position = {
                    "direction": sig,
                    "entry_price": entry_price,
                    "entry_ts": row["iso"],
                    "entry_rate": rate,
                    "size": size,
                }
                if sig == "LONG":
                    long_count += 1
                else:
                    short_count += 1

        equity_curve.append({"ts": row["iso"], "equity": round(equity, 4)})

    # Close any open position at end
    if position and price_times:
        last_candle = price_map[price_times[-1]]
        ep = position["entry_price"]
        size = position["size"]
        close = last_candle["close"]
        if position["direction"] == "LONG":
            pnl = size * (close - ep) / ep
        else:
            pnl = size * (ep - close) / ep
        equity += pnl
        trades.append({
            "entry_ts": position["entry_ts"],
            "exit_ts": "END",
            "direction": position["direction"],
            "entry_price": ep,
            "exit_price": close,
            "size": size,
            "pnl": pnl,
            "pnl_pct": pnl / size * 100,
            "exit_reason": "END",
            "entry_rate": position["entry_rate"],
        })

    n = len(trades)
    if n == 0:
        return {
            "trades": [],
            "equity_curve": equity_curve,
            "metrics": {
                "n_trades": 0, "long_trades": 0, "short_trades": 0,
                "win_rate": 0, "profit_factor": 0, "total_return_pct": 0,
                "annualized_return_pct": 0, "max_drawdown_pct": 0,
                "sharpe_ratio": 0, "final_equity": equity,
                "best_trade_pct": 0, "worst_trade_pct": 0, "days_tested": 0,
            },
            "threshold_mode": threshold_mode,
            "short_thr": short_thr,
            "long_thr": long_thr,
            "error": "No trades executed. Check thresholds.",
        }

    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    win_rate = len(wins) / n * 100
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    total_return = (equity - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100

    first_ts = funding_data[0]["ts"]
    last_ts = funding_data[-1]["ts"]
    days = (last_ts - first_ts) / (1000 * 86400)
    ann_return = ((1 + total_return / 100) ** (365 / days) - 1) * 100 if days > 0 else 0

    peak = INITIAL_CAPITAL
    max_dd = 0.0
    running_eq = INITIAL_CAPITAL
    for t in trades:
        running_eq += t["pnl"]
        if running_eq > peak:
            peak = running_eq
        dd = (peak - running_eq) / peak * 100
        if dd > max_dd:
            max_dd = dd

    if n > 1:
        pnl_pcts = [t["pnl_pct"] for t in trades]
        mean_r = sum(pnl_pcts) / n
        variance = sum((r - mean_r) ** 2 for r in pnl_pcts) / (n - 1)
        std_r = math.sqrt(variance) if variance > 0 else 0
        sharpe = (mean_r / std_r) * math.sqrt(365 * 3) if std_r > 0 else 0
    else:
        sharpe = 0

    best = max(trades, key=lambda t: t["pnl_pct"])
    worst = min(trades, key=lambda t: t["pnl_pct"])

    return {
        "trades": trades,
        "equity_curve": equity_curve,
        "metrics": {
            "n_trades": n,
            "long_trades": long_count,
            "short_trades": short_count,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_return_pct": total_return,
            "annualized_return_pct": ann_return,
            "max_drawdown_pct": max_dd,
            "sharpe_ratio": sharpe,
            "final_equity": equity,
            "best_trade_pct": best["pnl_pct"],
            "worst_trade_pct": worst["pnl_pct"],
            "days_tested": days,
        },
        "threshold_mode": threshold_mode,
        "short_thr": short_thr,
        "long_thr": long_thr,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    """Run 4 test groups. Returns {passed, failed, total, details}."""
    passed = 0
    failed = 0
    details = []

    def check(name, ok, detail=""):
        nonlocal passed, failed
        status = "PASS" if ok else "FAIL"
        icon = "✅" if ok else "❌"
        line = f"  {icon} {status}  {name}"
        if detail:
            line += f"  ({detail})"
        print(line)
        if ok:
            passed += 1
        else:
            failed += 1
        details.append({"name": name, "passed": ok, "detail": detail})

    # ── TEST GROUP 1: API Connectivity ─────────────────────────────────────────
    print()
    print("━" * 55)
    print("  TEST 1 — API Connectivity")
    print("━" * 55)

    try:
        btc_data = fetch_json(f"{BASE_BINANCE}/premiumIndex?symbol=BTCUSDT")
        check("Binance API responds (BTC)", True, "status 200")
        check("Field 'symbol' present", "symbol" in btc_data, btc_data.get("symbol", "MISSING"))
        check("Field 'lastFundingRate' present", "lastFundingRate" in btc_data,
              btc_data.get("lastFundingRate", "MISSING"))
        check("Field 'nextFundingTime' present", "nextFundingTime" in btc_data)
        rate_val = float(btc_data["lastFundingRate"]) * 100
        check("Funding rate is valid number (not NaN)", not math.isnan(rate_val), f"{rate_val:.4f}%")
    except Exception as e:
        for name in ["Binance API responds (BTC)", "Field 'symbol' present",
                     "Field 'lastFundingRate' present", "Field 'nextFundingTime' present",
                     "Funding rate is valid number (not NaN)"]:
            check(name, False, str(e))

    try:
        eth_data = fetch_json(f"{BASE_BINANCE}/premiumIndex?symbol=ETHUSDT")
        check("Binance API responds (ETH)", True, "status 200")
        eth_rate = float(eth_data["lastFundingRate"]) * 100
        check("ETH funding rate valid", not math.isnan(eth_rate), f"{eth_rate:.4f}%")
    except Exception as e:
        check("Binance API responds (ETH)", False, str(e))
        check("ETH funding rate valid", False, "API unavailable")

    # ── TEST GROUP 2: CSV Data Quality ─────────────────────────────────────────
    print()
    print("━" * 55)
    print("  TEST 2 — CSV Data Quality")
    print("━" * 55)

    for symbol, filename in [("BTC", "btc_funding_history.csv"), ("ETH", "eth_funding_history.csv")]:
        filepath = DATA_DIR / filename
        if not filepath.exists():
            check(f"{symbol} CSV exists", False, f"{filename} not found")
            check(f"{symbol} has >= 100 rows", False, "file missing")
            check(f"{symbol} timestamps in order", False, "file missing")
            check(f"{symbol} no gaps > 9h", False, "file missing")
            check(f"{symbol} rates in range", False, "file missing")
            continue

        rows = []
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        check(f"{symbol} CSV exists", True, filename)
        check(f"{symbol} has >= 100 rows", len(rows) >= 100, f"{len(rows)} rows")

        timestamps = [int(r["fundingTime"]) for r in rows]
        in_order = all(timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1))
        check(f"{symbol} timestamps in chronological order", in_order)

        max_gap_h = 0.0
        gap_ok = True
        for i in range(1, len(timestamps)):
            gap_h = (timestamps[i] - timestamps[i - 1]) / (3600 * 1000)
            if gap_h > max_gap_h:
                max_gap_h = gap_h
            if gap_h > 9:
                gap_ok = False
        check(f"{symbol} no gaps > 9h", gap_ok, f"max gap: {max_gap_h:.1f}h")

        rates = [float(r["fundingRate_pct"]) for r in rows]
        in_range = all(-2.0 <= r <= 2.0 for r in rates)
        out_of_range = [r for r in rates if not (-2.0 <= r <= 2.0)]
        check(f"{symbol} rates in range (-2% to +2%)", in_range,
              f"{len(out_of_range)} out of range" if not in_range else "all OK")

    # ── TEST GROUP 3: Backtest Logic ────────────────────────────────────────────
    print()
    print("━" * 55)
    print("  TEST 3 — Backtest Logic")
    print("━" * 55)

    eq_path = DATA_DIR / "equity_curve.csv"
    report_path = REPORT_DIR / "backtest_results.txt"

    if not eq_path.exists():
        check("Equity curve CSV exists", False, "run backtest first")
        check("Equity always > 0", False, "file missing")
    else:
        eq_rows = []
        with open(eq_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                eq_rows.append(float(row["equity_usd"]))
        check("Equity curve CSV exists", True, f"{len(eq_rows)} points")
        check("Equity always > 0", all(e > 0 for e in eq_rows),
              f"min: ${min(eq_rows):,.2f}" if eq_rows else "empty")

    if not report_path.exists():
        check("Backtest report exists", False, "run backtest first")
        check("Number of trades > 10", False, "report missing")
        check("Sharpe ratio valid (not Inf/NaN)", False, "report missing")
        check("Drawdown between 0% and 100%", False, "report missing")
    else:
        report_text = report_path.read_text(encoding="utf-8")
        check("Backtest report exists", True)

        def extract_metric(text, label):
            for line in text.split("\n"):
                if label in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        return parts[-1].strip()
            return None

        n_trades_str = extract_metric(report_text, "Total trades:")
        n_trades = 0
        if n_trades_str:
            try:
                n_trades = int(n_trades_str)
            except ValueError:
                pass
        check("Number of trades > 10", n_trades > 10, f"{n_trades} trades")

        sharpe_str = extract_metric(report_text, "Sharpe ratio:")
        if sharpe_str:
            try:
                sharpe = float(sharpe_str)
                sharpe_ok = not math.isnan(sharpe) and not math.isinf(sharpe)
                check("Sharpe ratio valid (not Inf/NaN)", sharpe_ok, f"{sharpe:.2f}")
            except ValueError:
                check("Sharpe ratio valid (not Inf/NaN)", False, f"not parseable: {sharpe_str}")
        else:
            check("Sharpe ratio valid (not Inf/NaN)", False, "not found in report")

        dd_str = extract_metric(report_text, "Max drawdown:")
        if dd_str:
            try:
                dd = float(dd_str.replace("%", ""))
                check("Drawdown between 0% and 100%", 0 <= dd <= 100, f"{dd:.2f}%")
            except ValueError:
                check("Drawdown between 0% and 100%", False, f"not parseable: {dd_str}")
        else:
            check("Drawdown between 0% and 100%", False, "not found in report")

    # ── TEST GROUP 4: Signal Classification ────────────────────────────────────
    print()
    print("━" * 55)
    print("  TEST 4 — Signal Classification")
    print("━" * 55)

    # Always use ABSOLUTE thresholds for these unit tests
    ABS_HIGH = FUNDING_HIGH   # 0.08
    ABS_LOW  = FUNDING_LOW    # -0.03

    test_cases = [
        (0.10,  "SHORT", "funding +0.10% -> SHORT"),
        (0.08,  "FLAT",  "funding +0.08% = threshold -> FLAT (not strictly >)"),
        (0.09,  "SHORT", "funding +0.09% -> SHORT"),
        (-0.05, "LONG",  "funding -0.05% -> LONG"),
        (-0.03, "FLAT",  "funding -0.03% = threshold -> FLAT (not strictly <)"),
        (-0.04, "LONG",  "funding -0.04% -> LONG"),
        (0.00,  "FLAT",  "funding 0.00% -> FLAT"),
        (0.05,  "FLAT",  "funding +0.05% -> FLAT (below threshold)"),
    ]

    for rate, expected, desc in test_cases:
        got = classify_signal(rate, ABS_HIGH, ABS_LOW)
        check(desc, got == expected, f"expected={expected} got={got}")

    total = passed + failed
    return {"passed": passed, "failed": failed, "total": total, "details": details}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def _status_emoji(rate_pct):
    """Return status string with emoji based on rate."""
    if rate_pct > FUNDING_HIGH:
        return "EXTREME HIGH 🔴"
    elif rate_pct > 0.05:
        return "HIGH 🟠"
    elif rate_pct > 0.01:
        return "MODERATE"
    elif rate_pct > -0.01:
        return "NEUTRAL 🟢"
    elif rate_pct > FUNDING_LOW:
        return "MODERATE NEG"
    elif rate_pct > -0.05:
        return "LOW 🔵"
    else:
        return "EXTREME LOW 🔵"


def print_live_summary(current_list):
    """Print table: symbol, rate%, status emoji, next funding."""
    print()
    print("=" * 65)
    print("  LIVE FUNDING RATES")
    print("=" * 65)
    print(f"  {'Symbol':<14} {'Rate %':>10}  {'Status':<20}  {'Next Funding'}")
    print("  " + "-" * 61)
    for item in current_list:
        sym = item.get("symbol", "?")
        rate = item.get("rate_pct", 0)
        status = _status_emoji(rate)
        nxt = item.get("time_until_next", "?")
        print(f"  {sym:<14} {rate:>+10.4f}%  {status:<20}  in {nxt}")
    print("=" * 65)


def print_top_funding(top_data, n=5):
    """Print top positives and negatives table."""
    print()
    print("  TOP FUNDING RATES")
    print("  " + "-" * 45)
    print(f"  {'Rank':<6} {'Symbol':<16} {'Rate %':>10}")
    print("  " + "-" * 45)
    print("  [TOP POSITIVE — Longs paying Shorts]")
    for i, item in enumerate(top_data.get("top_positive", [])[:n], 1):
        print(f"  {i:<6} {item['symbol']:<16} {item['rate']:>+10.4f}%")
    print("  [TOP NEGATIVE — Shorts paying Longs]")
    for i, item in enumerate(top_data.get("top_negative", [])[:n], 1):
        print(f"  {i:<6} {item['symbol']:<16} {item['rate']:>+10.4f}%")
    print("  " + "-" * 45)


def print_backtest_summary(result):
    """Print all metrics formatted, including threshold mode note."""
    m = result.get("metrics", {})
    trades = result.get("trades", [])
    threshold_mode = result.get("threshold_mode", "UNKNOWN")
    short_thr = result.get("short_thr", FUNDING_HIGH)
    long_thr = result.get("long_thr", FUNDING_LOW)

    if result.get("error") and m.get("n_trades", 0) == 0:
        print(f"\n  ERROR: {result['error']}")
        return

    # Period from funding data if available
    print()
    print("=" * 55)
    print("  BACKTEST RESULTS — Funding Rate Extreme Reversal")
    print("  Capital: $10,000 | Leverage: 1x")
    print("=" * 55)
    print(f"  Days tested:           {m.get('days_tested', 0):.0f} days")
    print(f"  Threshold mode:        {threshold_mode}")
    print(f"  SHORT when rate >      {short_thr:+.4f}%")
    print(f"  LONG  when rate <      {long_thr:+.4f}%")
    print()
    print("  PERFORMANCE")
    print(f"  Total trades:          {m.get('n_trades', 0)}")
    print(f"    -> LONG:             {m.get('long_trades', 0)}")
    print(f"    -> SHORT:            {m.get('short_trades', 0)}")
    print(f"  Win rate:              {m.get('win_rate', 0):.1f}%")
    pf = m.get("profit_factor", 0)
    pf_str = f"{pf:.2f}" if pf != float("inf") else "inf"
    print(f"  Profit factor:         {pf_str}")
    print(f"  Total return:          {m.get('total_return_pct', 0):+.2f}%")
    print(f"  Annualized return:     {m.get('annualized_return_pct', 0):+.2f}%")
    print(f"  Max drawdown:          {m.get('max_drawdown_pct', 0):.2f}%")
    print(f"  Sharpe ratio:          {m.get('sharpe_ratio', 0):.2f}")
    print(f"  Final equity:          ${m.get('final_equity', 0):,.2f}")
    print()
    print("  EXTREMES")
    print(f"  Best trade:            {m.get('best_trade_pct', 0):+.2f}%")
    print(f"  Worst trade:           {m.get('worst_trade_pct', 0):+.2f}%")
    print()
    print("  EXIT REASON DISTRIBUTION")
    exit_counts = {}
    for t in trades:
        exit_counts[t["exit_reason"]] = exit_counts.get(t["exit_reason"], 0) + 1
    for reason, count in sorted(exit_counts.items()):
        print(f"    {reason:<12} {count} trades")
    print("=" * 55)


def save_backtest_report(result, filepath):
    """Save text report to file."""
    m = result.get("metrics", {})
    trades = result.get("trades", [])
    threshold_mode = result.get("threshold_mode", "UNKNOWN")
    short_thr = result.get("short_thr", FUNDING_HIGH)
    long_thr = result.get("long_thr", FUNDING_LOW)

    lines = [
        "=" * 55,
        "  BACKTEST RESULTS — Funding Rate Extreme Reversal",
        "  Capital: $10,000 | Leverage: 1x",
        "=" * 55,
        f"  Days tested:           {m.get('days_tested', 0):.0f} days",
        f"  Threshold mode:        {threshold_mode}",
        f"  SHORT when rate >      {short_thr:+.4f}%",
        f"  LONG  when rate <      {long_thr:+.4f}%",
        "",
        "  PERFORMANCE",
        f"  Total trades:          {m.get('n_trades', 0)}",
        f"    -> LONG:             {m.get('long_trades', 0)}",
        f"    -> SHORT:            {m.get('short_trades', 0)}",
        f"  Win rate:              {m.get('win_rate', 0):.1f}%",
    ]
    pf = m.get("profit_factor", 0)
    pf_str = f"{pf:.2f}" if pf != float("inf") else "inf"
    lines += [
        f"  Profit factor:         {pf_str}",
        f"  Total return:          {m.get('total_return_pct', 0):+.2f}%",
        f"  Annualized return:     {m.get('annualized_return_pct', 0):+.2f}%",
        f"  Max drawdown:          {m.get('max_drawdown_pct', 0):.2f}%",
        f"  Sharpe ratio:          {m.get('sharpe_ratio', 0):.2f}",
        f"  Final equity:          ${m.get('final_equity', 0):,.2f}",
        "",
        "  EXTREMES",
        f"  Best trade:            {m.get('best_trade_pct', 0):+.2f}%",
        f"  Worst trade:           {m.get('worst_trade_pct', 0):+.2f}%",
        "",
        "  EXIT REASON DISTRIBUTION",
    ]
    exit_counts = {}
    for t in trades:
        exit_counts[t["exit_reason"]] = exit_counts.get(t["exit_reason"], 0) + 1
    for reason, count in sorted(exit_counts.items()):
        lines.append(f"    {reason:<12} {count} trades")
    lines += ["", "=" * 55]

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def save_equity_csv(equity_curve, filepath):
    """Save equity curve to CSV."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "equity_usd"])
        for row in equity_curve:
            writer.writerow([row["ts"], row["equity"]])


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Funding Rate Monitor")
    parser.add_argument("--mode", choices=["live", "backtest", "full", "test"], default="full")
    parser.add_argument("--symbols", nargs="+", default=SYMBOLS_DEFAULT)
    parser.add_argument("--exchange", choices=["binance", "bybit"], default="binance")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", choices=["terminal", "file", "both"], default="both")
    args = parser.parse_args()

    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║         FUNDING RATE MONITOR — Unified Skill         ║")
    print(f"║  Mode: {args.mode:<10} Exchange: {args.exchange:<10} Symbols: {len(args.symbols):<3}  ║")
    print("╚══════════════════════════════════════════════════════╝")

    # ── LIVE ───────────────────────────────────────────────────────────────────
    if args.mode in ("live", "full"):
        print("\n[LIVE] Fetching current funding rates...")
        current_list = []
        for sym in args.symbols:
            try:
                info = get_current_funding(sym, exchange=args.exchange)
                current_list.append(info)
                print(f"  {sym}: {info['rate_pct']:+.4f}% (next in {info['time_until_next']})")
            except Exception as e:
                print(f"  {sym}: ERROR — {e}")

        print("\n[LIVE] Fetching top funding rates...")
        try:
            top_data = get_top_funding(n=10, exchange=args.exchange)
            print_live_summary(current_list)
            print_top_funding(top_data, n=5)
        except Exception as e:
            print(f"  ERROR fetching top funding: {e}")
            print_live_summary(current_list)

    # ── BACKTEST ───────────────────────────────────────────────────────────────
    if args.mode in ("backtest", "full"):
        print("\n[BACKTEST] Starting...")

        generic_files_written = False
        for sym in args.symbols:
            sym_lower = sym.lower()
            print(f"\n  Symbol: {sym}")

            # Fetch or load funding history
            csv_path = DATA_DIR / f"{sym_lower}_funding_history.csv"
            print(f"  Fetching funding history ({args.limit} records)...")
            try:
                funding_data = get_funding_history(sym, limit=args.limit, exchange=args.exchange)
                print(f"  {len(funding_data)} records ({funding_data[0]['iso'][:10]} -> {funding_data[-1]['iso'][:10]})")
                if args.output in ("file", "both"):
                    save_history_csv(funding_data, csv_path)
                    print(f"  Saved: {csv_path}")
            except Exception as e:
                print(f"  ERROR fetching funding history: {e}")
                continue

            # Fetch price data
            print(f"  Fetching 8h klines...")
            try:
                price_data = fetch_klines_8h(sym, limit=args.limit)
                print(f"  {len(price_data)} candles loaded")
            except Exception as e:
                print(f"  ERROR fetching klines: {e}")
                continue

            # Determine thresholds
            all_rates = [r["rate"] for r in funding_data]
            max_rate = max(all_rates)
            min_rate = min(all_rates)
            use_adaptive = (max_rate < FUNDING_HIGH) and (min_rate > FUNDING_LOW)

            if use_adaptive:
                long_thr, short_thr = compute_adaptive_thresholds(all_rates)
                print(f"  NOTICE: Using ADAPTIVE thresholds (max={max_rate:.4f}%, min={min_rate:.4f}%)")
                print(f"    SHORT when rate > {short_thr:+.4f}%")
                print(f"    LONG  when rate < {long_thr:+.4f}%")
            else:
                short_thr = FUNDING_HIGH
                long_thr = FUNDING_LOW
                print(f"  Using ABSOLUTE thresholds:")
                print(f"    SHORT when rate > {short_thr:+.4f}%")
                print(f"    LONG  when rate < {long_thr:+.4f}%")

            print(f"  Running backtest...")
            result = run_backtest(funding_data, price_data, short_thr, long_thr)

            if result.get("error") and result["metrics"]["n_trades"] == 0:
                print(f"  ERROR: {result['error']}")
                continue

            print_backtest_summary(result)

            if args.output in ("file", "both"):
                rpt_path = REPORT_DIR / f"backtest_{sym_lower}.txt"
                eq_path = DATA_DIR / f"equity_curve_{sym_lower}.csv"
                save_backtest_report(result, rpt_path)
                save_equity_csv(result["equity_curve"], eq_path)
                print(f"  Report saved: {rpt_path}")
                print(f"  Equity curve saved: {eq_path}")
                # Save generic names for test compatibility — only for first symbol
                # (or if the result has more trades than previously saved)
                if not generic_files_written:
                    generic_rpt = REPORT_DIR / "backtest_results.txt"
                    generic_eq = DATA_DIR / "equity_curve.csv"
                    save_backtest_report(result, generic_rpt)
                    save_equity_csv(result["equity_curve"], generic_eq)
                    generic_files_written = True

    # ── TEST ───────────────────────────────────────────────────────────────────
    if args.mode in ("test", "full"):
        print("\n[TEST] Running automated test suite...")
        test_result = run_tests()
        print()
        print("━" * 55)
        total = test_result["total"]
        passed = test_result["passed"]
        failed = test_result["failed"]
        print(f"  FINAL RESULT: {passed}/{total} tests passed")
        if failed > 0:
            print(f"  {failed} test(s) FAILED.")
        else:
            print("  All tests passed!")
        print("━" * 55)
        print()

    print("\nDone.")


if __name__ == "__main__":
    main()
