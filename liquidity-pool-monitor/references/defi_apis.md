# DeFi APIs — Reference Documentation

## 1. DefiLlama Yields API

### Endpoint
```
GET https://yields.llama.fi/pools
```

### Description
Returns yield data for thousands of DeFi liquidity pools across all major chains.
No API key required. Generally reliable with good uptime.

### Rate Limits
- No official rate limit documented
- Recommended: max 1 request/10s to be safe
- Large payload (~2-5 MB JSON)

### Response Format
```json
{
  "status": "success",
  "data": [
    {
      "pool": "747c1d2a-c668-4682-b9f9-296708a3dd90",
      "chain": "Ethereum",
      "project": "uniswap-v3",
      "symbol": "USDC-WETH",
      "tvlUsd": 123456789.0,
      "apy": 12.34,
      "apyBase": 10.0,
      "apyReward": 2.34,
      "rewardTokens": ["0xabcd..."],
      "underlyingTokens": ["0x...", "0x..."],
      "volumeUsd1d": 5000000.0,
      "volumeUsd7d": 30000000.0,
      "il7d": 0.5,
      "status": "active"
    }
  ]
}
```

### Key Fields
| Field            | Type   | Description                        |
|------------------|--------|------------------------------------|
| pool             | string | Unique pool UUID                   |
| chain            | string | Blockchain name (e.g. "Ethereum")  |
| project          | string | Protocol slug (e.g. "uniswap-v3") |
| symbol           | string | Token pair (e.g. "USDC-WETH")     |
| tvlUsd           | float  | Total Value Locked in USD          |
| apy              | float  | Total APY (base + reward)          |
| apyBase          | float  | Fee-based APY                      |
| apyReward        | float  | Token reward APY                   |
| volumeUsd1d      | float  | 24h trading volume in USD          |
| il7d             | float  | 7-day impermanent loss %           |
| status           | string | "active" or "inactive"             |

---

## 2. Uniswap V3 GraphQL (The Graph)

### Endpoints
```
# Ethereum Mainnet
POST https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3

# Arbitrum
POST https://api.thegraph.com/subgraphs/name/ianlapham/arbitrum-minimal
```

### Description
GraphQL subgraph for Uniswap V3 on-chain data. Hosted on The Graph's decentralized
network. May be rate-limited or unavailable on free tier.

### Rate Limits
- Free tier: ~1,000 queries/day per IP (unofficial)
- Returns HTTP 429 on rate limit
- Returns HTTP 503 when subgraph is syncing or down

### Query Used
```graphql
{
  pools(
    first: 50,
    orderBy: totalValueLockedUSD,
    orderDirection: desc,
    where: {totalValueLockedUSD_gt: "500000"}
  ) {
    id
    token0 { symbol }
    token1 { symbol }
    feeTier
    totalValueLockedUSD
    volumeUSD
    poolDayData(first: 1, orderBy: date, orderDirection: desc) {
      volumeUSD
    }
  }
}
```

### Response Format
```json
{
  "data": {
    "pools": [
      {
        "id": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
        "token0": { "symbol": "USDC" },
        "token1": { "symbol": "WETH" },
        "feeTier": "500",
        "totalValueLockedUSD": "123456789.0",
        "volumeUSD": "999888777.0",
        "poolDayData": [
          { "volumeUSD": "5000000.0" }
        ]
      }
    ]
  }
}
```

### APR Calculation
```
APR = (volume24h * feeTier/1_000_000 * 365) / TVL * 100
```
Where feeTier is in bps (e.g. 500 = 0.05%, 3000 = 0.3%, 10000 = 1%).

---

## 3. Aerodrome Finance REST API

### Endpoint
```
GET https://api.aerodrome.finance/api/v1/pools
```

### Description
Returns pool data for Aerodrome Finance (the leading DEX on Base chain).
Response format may vary between API versions.

### Rate Limits
- No official documentation
- Generally permissive, ~1 req/s recommended

### Response Format (typical)
```json
[
  {
    "address": "0xabc...",
    "symbol": "USDC/WETH",
    "token0": { "symbol": "USDC", "address": "0x..." },
    "token1": { "symbol": "WETH", "address": "0x..." },
    "tvl": 5000000.0,
    "volume24h": 250000.0,
    "apr": 18.5,
    "isStable": false
  }
]
```

### Notes
- API may return `{"data": [...]}` wrapper or direct array
- `apr` field = total APR including AERO token rewards
- Pools on Base chain only

---

## 4. CoinGecko API — Prices

### Endpoint
```
GET https://api.coingecko.com/api/v3/simple/price
```

### Parameters
```
ids=bitcoin,ethereum,usd-coin,tether,wrapped-bitcoin,arbitrum,optimism,matic-network
vs_currencies=usd
include_market_cap=true
include_24hr_change=true
```

### Rate Limits
- Free tier: 10-50 calls/minute (varies)
- Add 1s delay between consecutive CoinGecko calls
- Returns HTTP 429 on rate limit

### Response Format
```json
{
  "bitcoin": {
    "usd": 65000.0,
    "usd_market_cap": 1280000000000.0,
    "usd_24h_change": 1.23
  },
  "ethereum": {
    "usd": 3200.0,
    "usd_market_cap": 380000000000.0,
    "usd_24h_change": -0.5
  }
}
```

---

## 5. CoinGecko API — Global Market Data

### Endpoint
```
GET https://api.coingecko.com/api/v3/global
```

### Response Format
```json
{
  "data": {
    "active_cryptocurrencies": 13000,
    "markets": 850,
    "total_market_cap": {
      "usd": 2500000000000.0
    },
    "total_volume": {
      "usd": 95000000000.0
    },
    "market_cap_percentage": {
      "btc": 51.5,
      "eth": 17.2
    },
    "market_cap_change_percentage_24h_usd": -1.5,
    "btc_dominance": 51.5
  }
}
```

### Sentiment Logic
| Condition                                | Sentiment  |
|------------------------------------------|------------|
| BTC dominance < 50% AND mcap_change > 0  | RISK_ON    |
| BTC dominance > 55% OR mcap_change < -3% | RISK_OFF   |
| Otherwise                                | NEUTRAL    |

---

## Error Handling Summary

| Error Code | Meaning              | Action                         |
|------------|----------------------|--------------------------------|
| 429        | Rate Limited         | Wait 5s, retry once            |
| 503        | Service Unavailable  | Skip source, continue          |
| 502        | Bad Gateway          | Skip source, continue          |
| Timeout    | Network timeout      | Skip source (20s default)      |
| JSONError  | Invalid response     | Skip source, continue          |

All errors are non-fatal. The monitor continues with available data sources.
