---
name: funding-rate-monitor
version: 1.0.0
description: Monitors crypto perpetual futures funding rates, runs backtests of the "Extreme Reversal" strategy, and validates data quality via automated tests.
author: Latrel
created: 2026-03-26
python: ">=3.8"
dependencies:
  - requests
  - pandas
  - numpy
  - tabulate
platforms:
  - win32
  - linux
  - darwin
---

# Funding Rate Monitor Skill

A unified Python skill for monitoring, backtesting, and testing cryptocurrency perpetual futures funding rates using Binance and Bybit APIs.

## Overview

Perpetual futures contracts use a funding rate mechanism to keep contract prices aligned with spot prices. When the funding rate is extremely high, it signals overbought market sentiment — a SHORT reversal opportunity. When extremely low, it signals oversold conditions — a LONG opportunity.

This skill automates:
1. **Live monitoring** — Current funding rates for selected symbols
2. **Backtesting** — Historical strategy performance with real price data
3. **Automated testing** — Data quality and logic validation

## Strategy

**Funding Rate Extreme Reversal**
- SHORT when funding rate > +0.08% (overbought — longs paying heavily)
- LONG  when funding rate < -0.03% (oversold — shorts paying heavily)
- FLAT  otherwise (no position)
- Stop Loss: 2% | Take Profit: 3% | Leverage: 1x
- Additional exit: when funding normalizes back to neutral zone

## Quick Start

```bash
# Install dependencies
py -m pip install requests pandas numpy tabulate

# Run full mode (live + backtest + tests)
bash ~/skills/funding-rate-monitor/scripts/run_skill.sh

# Or run directly
py ~/skills/funding-rate-monitor/scripts/funding_monitor.py --mode full
```

## Usage

```bash
py funding_monitor.py [OPTIONS]

Options:
  --mode       {live,backtest,full,test}   Default: full
  --symbols    SYMBOL [SYMBOL ...]         Default: BTCUSDT ETHUSDT
  --exchange   {binance,bybit}             Default: binance
  --limit      INT                         History records to fetch (default: 500)
  --output     {terminal,file,both}        Default: both
```

### Examples

```bash
# Live funding rates only
py funding_monitor.py --mode live --symbols BTCUSDT ETHUSDT SOLUSDT

# Backtest BTC on Binance, save reports
py funding_monitor.py --mode backtest --symbols BTCUSDT --output both

# Run automated test suite
py funding_monitor.py --mode test

# Use Bybit exchange
py funding_monitor.py --mode live --exchange bybit --symbols BTCUSDT

# Full analysis on multiple symbols
py funding_monitor.py --mode full --symbols BTCUSDT ETHUSDT --limit 1000
```

## Output Files

| File | Description |
|------|-------------|
| `~/funding_backtest/data/{symbol}_funding_history.csv` | Historical funding rates |
| `~/funding_backtest/data/equity_curve_{symbol}.csv` | Backtest equity curve |
| `~/funding_backtest/reports/backtest_{symbol}.txt` | Full backtest report |
| `~/funding_backtest/reports/backtest_results.txt` | Latest report (generic name) |

## Adaptive Thresholds

When the historical dataset does not contain rates exceeding the absolute thresholds (+0.08% / -0.03%), the script automatically switches to **adaptive thresholds** using the top/bottom 15th percentile of the dataset. This ensures backtests always produce signals even in low-volatility periods.

## Test Suite

The `--mode test` runs 4 test groups:
1. **API Connectivity** — Verifies Binance endpoints respond correctly
2. **CSV Data Quality** — Checks files exist, ≥100 rows, no gaps >9h, rates in range
3. **Backtest Logic** — Validates equity curve, trade count, sharpe, drawdown
4. **Signal Classification** — 8 unit tests using absolute thresholds

## Architecture

```
funding_monitor.py
├── SECTION 1: CONFIG     — constants, imports, directory setup
├── SECTION 2: FETCH      — API calls, data collection, CSV saving
├── SECTION 3: BACKTEST   — strategy engine, metrics computation
├── SECTION 4: TESTS      — automated validation suite
├── SECTION 5: REPORT     — formatting and file output
└── SECTION 6: MAIN       — CLI entrypoint, orchestration
```

## Data Sources

- **Binance Futures**: `https://fapi.binance.com/fapi/v1`
  - `/premiumIndex` — current funding rate
  - `/fundingRate` — historical rates
  - `/klines` — OHLCV price data
- **Bybit**: `https://api.bybit.com/v5/market`
  - `/tickers` — current rates
  - `/funding/history` — historical rates

## Notes

- No API keys required (public endpoints only)
- Windows UTF-8 encoding handled automatically
- Python 3.8+ compatible (no 3.10+ syntax)
- All dependencies are standard data science libraries
