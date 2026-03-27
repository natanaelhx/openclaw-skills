# Exchange API Reference

## Binance Futures Endpoints

Base URL: `https://fapi.binance.com/fapi/v1`

### 1. `/premiumIndex` — Current Funding Rate (single symbol)

**Request:**
```
GET https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT
```

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "markPrice": "65432.10000000",
  "indexPrice": "65430.55000000",
  "estimatedSettlePrice": "65431.00000000",
  "lastFundingRate": "0.00010000",
  "nextFundingTime": 1711497600000,
  "interestRate": "0.00010000",
  "time": 1711494321456
}
```

**Key fields:**
- `lastFundingRate` — raw rate as decimal (multiply × 100 for percentage)
- `nextFundingTime` — Unix timestamp in milliseconds for next funding
- `markPrice` — current mark price used for funding calculations

**Rate limit:** 20 requests/second per IP

---

### 2. `/premiumIndex` — All Symbols (no symbol param)

**Request:**
```
GET https://fapi.binance.com/fapi/v1/premiumIndex
```

**Response:** Array of objects with same structure as single-symbol response.

Used by `get_top_funding()` to rank all perpetual pairs.

---

### 3. `/fundingRate` — Historical Funding Rates

**Request:**
```
GET https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=500
```

**Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| symbol | STRING | Required. e.g. BTCUSDT |
| startTime | LONG | Optional. Unix ms |
| endTime | LONG | Optional. Unix ms |
| limit | INT | Default 100, max 1000 |

**Response:**
```json
[
  {
    "symbol": "BTCUSDT",
    "fundingRate": "0.00010000",
    "fundingTime": 1711468800000,
    "markPrice": "65200.00000000"
  },
  ...
]
```

**Key fields:**
- `fundingRate` — raw rate (multiply × 100 for %)
- `fundingTime` — settlement timestamp in milliseconds

**Rate limit:** 20 requests/second

---

### 4. `/klines` — OHLCV Candlestick Data

**Request:**
```
GET https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=8h&limit=500
```

**Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| symbol | STRING | Required |
| interval | ENUM | 1m, 5m, 1h, 4h, 8h, 1d, etc. |
| limit | INT | Default 500, max 1500 |

**Response:** Array of arrays:
```json
[
  [
    1711468800000,    // [0] Open time (ms)
    "65200.00",       // [1] Open
    "65800.00",       // [2] High
    "64900.00",       // [3] Low
    "65500.00",       // [4] Close
    "12345.678",      // [5] Volume
    1711497599999,    // [6] Close time (ms)
    "808345678.90",   // [7] Quote asset volume
    4532,             // [8] Number of trades
    "6543.210",       // [9] Taker buy base asset volume
    "428765432.10",   // [10] Taker buy quote asset volume
    "0"               // [11] Unused
  ],
  ...
]
```

Used to get real OHLCV data for backtesting SL/TP hit detection.

---

## Bybit Endpoints

Base URL: `https://api.bybit.com/v5/market`

### 1. `/tickers` — Current Funding Rate (linear perpetuals)

**Request:**
```
GET https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT
```

**Response:**
```json
{
  "retCode": 0,
  "retMsg": "OK",
  "result": {
    "category": "linear",
    "list": [
      {
        "symbol": "BTCUSDT",
        "lastPrice": "65432.10",
        "fundingRate": "0.0001",
        "nextFundingTime": "1711497600000",
        "markPrice": "65430.00",
        "indexPrice": "65428.55"
      }
    ]
  }
}
```

### 2. `/funding/history` — Historical Funding Rates

**Request:**
```
GET https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=200
```

**Response:**
```json
{
  "retCode": 0,
  "result": {
    "category": "linear",
    "list": [
      {
        "symbol": "BTCUSDT",
        "fundingRate": "0.0001",
        "fundingRateTimestamp": "1711468800000"
      }
    ]
  }
}
```

**Note:** Bybit max limit is 200 per request.

---

## Rate Limits Summary

| Exchange | Endpoint Type | Limit |
|----------|--------------|-------|
| Binance | Public market data | 1200 weight/min |
| Binance | /premiumIndex (all) | weight: 10 |
| Binance | /fundingRate | weight: 1 |
| Binance | /klines | weight: 5 |
| Bybit | Public endpoints | 120 req/s |

---

## Timestamp Conversion Examples

```python
from datetime import datetime, timezone

# Milliseconds to ISO string
ts_ms = 1711468800000
iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
# Result: "2024-03-26T16:00:00+00:00"

# ISO string to milliseconds
dt = datetime.fromisoformat("2024-03-26T16:00:00+00:00")
ts_ms = int(dt.timestamp() * 1000)
# Result: 1711468800000

# Human-readable difference
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
target = datetime.fromtimestamp(1711497600000 / 1000, tz=timezone.utc)
diff_secs = (target - now).total_seconds()
hours = int(diff_secs // 3600)
mins = int((diff_secs % 3600) // 60)
# Result: "8h 0min"
```

---

## Funding Rate Conversion

Binance returns funding rates as raw decimals. Conversion:
```
raw = 0.00010000
percentage = raw * 100 = 0.01%
```

Standard perpetual funding settlement: every 8 hours at 00:00, 08:00, 16:00 UTC.

Positive rate = longs pay shorts (bullish sentiment, longs are dominant)
Negative rate = shorts pay longs (bearish sentiment, shorts are dominant)
