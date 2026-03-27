# Pool Strategy Guide — DeFi Liquidity Provision

## 1. What Is TVL (Total Value Locked)?

TVL is the total amount of assets deposited in a liquidity pool, measured in USD.

```
Pool: USDC/WETH
TVL: $5,000,000
→ ~$2.5M in USDC + ~$2.5M in WETH at current prices
```

**Why TVL matters:**
- Higher TVL = more liquidity depth = less slippage for traders
- Higher TVL generally means more trusted/established pool
- Higher TVL = your share of fees is smaller (more competition)

**TVL Tiers:**
| TVL Range      | Interpretation                          |
|----------------|-----------------------------------------|
| < $500K        | Risky — low liquidity, manipulation risk|
| $500K — $2M    | Moderate — viable but smaller pool      |
| $2M — $50M     | Good — solid depth, reasonable fees     |
| > $50M         | Large — deep liquidity, very established|

---

## 2. How APR Is Calculated

### Fee APR (APR Base)
Revenue from trading fees distributed to liquidity providers.

```
Fee APR = (Volume24h × FeeTier × 365) / TVL × 100

Example:
  Volume24h = $5,000,000
  FeeTier   = 0.3% (3000 bps)
  TVL       = $10,000,000

  Fee APR = (5,000,000 × 0.003 × 365) / 10,000,000 × 100
          = 54.75% APR
```

### Reward APR (APR Reward)
Additional token incentives distributed by the protocol.

```
Total APR = Fee APR + Reward APR
```

**Caution:** Reward APR can be unsustainable — token price may decline,
effectively reducing real yield. Always check both components separately.

### Uniswap V3 Fee Tiers
| Fee Tier  | Best For                                    |
|-----------|---------------------------------------------|
| 0.01%     | Stablecoin pairs (USDC/USDT, DAI/USDC)     |
| 0.05%     | Correlated assets (WBTC/ETH, stETH/ETH)    |
| 0.3%      | Most standard pairs (ETH/USDC, ARB/ETH)    |
| 1.0%      | Exotic/volatile pairs                       |

---

## 3. Impermanent Loss (IL) — Explained

Impermanent Loss occurs when the price ratio of the two tokens in a pool
changes after you deposit. You end up with less value than if you had simply
held the tokens.

### IL Formula (simplified)
```
IL = 2√r / (1+r) − 1
where r = price ratio change

Example: ETH price doubles (r=2)
IL = 2×√2 / (1+2) − 1 = 2×1.414 / 3 − 1 = −5.72%
```

### IL vs Price Change Table
| Price Change | Impermanent Loss |
|-------------|-----------------|
| 1.25× (25%) | −0.6%           |
| 1.5× (50%)  | −2.0%           |
| 2× (100%)   | −5.7%           |
| 3× (200%)   | −13.4%          |
| 4× (300%)   | −20.0%          |
| 5× (400%)   | −25.5%          |

### Key Insight
IL is **impermanent** — if prices return to original ratio, loss disappears.
You only realize the loss when you withdraw.

**Stablecoin pairs (USDC/USDT):** Near-zero IL — both assets maintain $1.

**Mitigating IL:**
- Choose correlated asset pairs (ETH/stETH, WBTC/WETH)
- Earn fees that outpace IL
- Use concentrated liquidity (Uniswap V3) in tight ranges
- Exit before IL compounds on diverging assets

---

## 4. How to Interpret Risk Scores

The monitor assigns three risk levels:

### BAIXO (Low Risk)
**Requirements:** Both tokens are in the safe-tokens list AND TVL > $2M AND APR < 200%

```
Examples:
- USDC/WETH on Uniswap V3 — $15M TVL — 25% APR → BAIXO
- DAI/USDC on Curve — $50M TVL — 8% APR → BAIXO
```

**What it means:** Established pool, trusted assets, realistic returns.
Suitable for conservative liquidity provision.

### MEDIO (Medium Risk)
**Requirements:** One or both tokens are less established, OR TVL is moderate.

```
Examples:
- ARB/WETH on Uniswap V3 — $3M TVL — 45% APR → MEDIO
- LUSD/USDC on Curve — $800K TVL — 12% APR → MEDIO
```

**What it means:** Acceptable risk/reward. Monitor regularly. Watch for IL
on volatile pairs. Check reward token sustainability.

### ALTO (High Risk)
**Requirements:** APR > 200% OR TVL < $500K

```
Examples:
- NewToken/ETH — $200K TVL — 500% APR → ALTO
- USDC/WETH — $300K TVL → ALTO (too small)
```

**What it means:** Very high risk. Could be:
- Farming scam (artificially high APR)
- Rug pull risk (low TVL, easy to drain)
- Unsustainable tokenomics
- Only for high-risk-tolerance allocations (<5% of portfolio)

---

## 5. When to Prefer Stablecoins vs Volatile Pairs

### Stablecoin Pairs (USDC/USDT, DAI/USDC, LUSD/USDC)

**Choose stablecoins when:**
- Market sentiment is RISK_OFF (falling prices, fear)
- BTC dominance > 55% (capital fleeing to safety)
- Market cap down > 3% in 24h
- You cannot afford to lose principal
- Bear market conditions

**Advantages:**
- Near-zero impermanent loss
- Predictable returns (fee APR only)
- Capital preserved during downturns
- Ideal for DeFi "savings account" strategy

**Disadvantages:**
- Lower APR (typically 3-15%)
- No upside from price appreciation
- Counterparty risk on USDC/USDT (centralized issuers)

**Best pools:** Curve 3pool, Uniswap USDC/USDT 0.01%, Aerodrome USDC/USDT stable

---

### Volatile Pairs (ETH/USDC, WBTC/ETH, ARB/ETH)

**Choose volatile pairs when:**
- Market sentiment is RISK_ON (rising prices, greed)
- BTC dominance < 50% (altcoin season likely)
- Market cap up > 3% in 24h
- You're bullish on the underlying assets
- Bull market conditions

**Advantages:**
- Higher APR (fee income from higher volume)
- Exposure to price upside
- Fees can offset IL in trending markets

**Disadvantages:**
- Impermanent loss in sideways/volatile markets
- Returns unpredictable
- Requires active monitoring/rebalancing

**Best pools:** Uniswap V3 ETH/USDC 0.05%, Aerodrome WETH/USDC, Balancer 80/20

---

### Composite Score Explained

The `get_range_pools()` function scores each pool:

```python
score = APR/MAX_APR * 0.4        # APR quality (40% weight)
      + TVL_score   * 0.3        # TVL depth   (30% weight)
      + Vol_score   * 0.2        # Volume/TVL  (20% weight)
      + Safety      * 0.1        # Token safety(10% weight)
```

| Component  | Weight | How Calculated                                    |
|------------|--------|---------------------------------------------------|
| APR score  | 40%    | APR / 80 (max target APR), capped at 1.0          |
| TVL score  | 30%    | TVL / $10M, capped at 1.0                         |
| Vol score  | 20%    | Volume24h / TVL ratio, capped at 1.0              |
| Safety     | 10%    | 1.0 if both tokens safe, else 0.5                 |

A pool with 80% APR, $10M TVL, active volume, and safe tokens → score ≈ 1.0 (perfect).

---

## 6. Quick Decision Framework

```
Q1: What is market sentiment?
  RISK_OFF → Go stablecoin pools only
  RISK_ON  → Consider volatile ETH/BTC pairs
  NEUTRAL  → Mix: 50% stable, 50% volatile

Q2: What APR range is acceptable?
  Conservative: 3-15% (stables + Curve)
  Moderate:     15-50% (Uniswap V3 majors)
  Aggressive:   50-80% (newer protocols, rewards)
  Avoid:        > 80% (unsustainable)

Q3: What is the TVL?
  < $1M  → Skip (risky)
  $1-5M  → Acceptable with caution
  > $5M  → Preferred

Q4: Is there impermanent loss risk?
  Stablecoin pair → IL ≈ 0, safe
  Correlated pair → IL low-moderate
  Uncorrelated    → IL moderate-high, need higher fees to compensate
```
