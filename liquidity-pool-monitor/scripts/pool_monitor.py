#!/usr/bin/env python3
"""
pool_monitor.py — Liquidity Pool Monitor
Monitors DeFi pools across Ethereum, Arbitrum, Base, Optimism, Polygon.
Sources: DefiLlama, Uniswap V3 GraphQL, Aerodrome REST, CoinGecko.
"""
import os, sys, json, time, argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    import requests
    import pandas as pd
    import numpy as np
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

# ── CONFIG ───────────────────────────────────────────────────────────────────
MIN_TVL_USD         = 500_000
MIN_APR             = 3.0
TARGET_APR_MIN      = 3.0
TARGET_APR_MAX      = 80.0
SAFE_TOKENS         = ["USDC","USDT","DAI","WBTC","WETH","ETH","cbBTC","cbETH","stETH","rETH","LUSD","USDC.e","USDT.e"]
SAFE_PROTOCOLS      = ["uniswap-v3","curve","balancer","aerodrome","velodrome"]
CHAINS_MONITORED    = ["Ethereum","Arbitrum","Base","Optimism","Polygon"]
CACHE_TTL_MINUTES   = 30
DATA_DIR   = Path(os.path.expanduser("~/liquidity_monitor/data"))
REPORT_DIR = Path(os.path.expanduser("~/liquidity_monitor/reports"))
CACHE_DIR  = Path(os.path.expanduser("~/liquidity_monitor/cache"))
for _d in [DATA_DIR, REPORT_DIR, CACHE_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

UNISWAP_ETH_URL     = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
UNISWAP_ARB_URL     = "https://api.thegraph.com/subgraphs/name/ianlapham/arbitrum-minimal"
AERODROME_URL       = "https://api.aerodrome.finance/api/v1/pools"
DEFILLAMA_URL       = "https://yields.llama.fi/pools"
COINGECKO_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_GLOBAL_URL= "https://api.coingecko.com/api/v3/global"

# ── API Gateway (opcional — router com fallback automático) ─────────────────
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

HEADERS = {"User-Agent": "pool-monitor/1.0", "Accept": "application/json"}

UNISWAP_GQL_QUERY = """
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
"""

# ── DATA FETCHER ──────────────────────────────────────────────────────────────
class DataFetcher:
    def __init__(self, force_refresh: bool = False):
        self.force_refresh = force_refresh
        self.session = requests.Session() if HAS_DEPS else None
        if self.session:
            self.session.headers.update(HEADERS)

    def _get(self, url: str, params: Optional[Dict] = None, timeout: int = 20) -> Optional[Dict]:
        """Safe GET request with error handling."""
        try:
            resp = self.session.get(url, params=params, timeout=timeout)
            if resp.status_code == 429:
                print("  [rate-limited, waiting 5s...]", end=" ", flush=True)
                time.sleep(5)
                resp = self.session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            print(f"  [connection error: {url[:50]}]", end=" ", flush=True)
            return None
        except requests.exceptions.Timeout:
            print(f"  [timeout: {url[:50]}]", end=" ", flush=True)
            return None
        except requests.exceptions.HTTPError as e:
            print(f"  [HTTP {e.response.status_code}]", end=" ", flush=True)
            return None
        except Exception as e:
            print(f"  [error: {e}]", end=" ", flush=True)
            return None

    def _post(self, url: str, payload: Dict, timeout: int = 20) -> Optional[Dict]:
        """Safe POST request with error handling."""
        try:
            resp = self.session.post(url, json=payload, timeout=timeout)
            if resp.status_code == 429:
                print("  [rate-limited, waiting 5s...]", end=" ", flush=True)
                time.sleep(5)
                resp = self.session.post(url, json=payload, timeout=timeout)
            if resp.status_code in (503, 502, 500):
                print(f"  [server error {resp.status_code}]", end=" ", flush=True)
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            print(f"  [connection error: {url[:50]}]", end=" ", flush=True)
            return None
        except requests.exceptions.Timeout:
            print(f"  [timeout]", end=" ", flush=True)
            return None
        except Exception as e:
            print(f"  [error: {e}]", end=" ", flush=True)
            return None

    def fetch_defillama_pools(self) -> "pd.DataFrame":
        """Fetch pool data from DefiLlama Yields API.
        Usa APIRouter quando disponível (fallback automático para outras fontes).
        """
        if not HAS_DEPS:
            return pd.DataFrame()

        # Tenta via APIRouter primeiro
        if _GATEWAY_AVAILABLE and _ROUTER:
            try:
                print("Buscando pools via APIRouter...", end=" ", flush=True)
                result = _ROUTER.fetch("pools_evm",
                                       chains=CHAINS_MONITORED,
                                       min_tvl=MIN_TVL_USD,
                                       min_apr=MIN_APR)
                pools = result.get("pools", [])
                if pools:
                    print(f"OK ({len(pools)} pools via {result.get('_source', 'router')})")
                    df = pd.DataFrame(pools)
                    # Garante colunas compatíveis com o restante do código
                    col_map = {"apr_total": "apy", "tvl_usd": "tvlUsd", "volume_24h": "volumeUsd24h"}
                    for src, dst in col_map.items():
                        if src in df.columns and dst not in df.columns:
                            df[dst] = df[src]
                    return df
            except Exception as e:
                print(f"Router falhou ({e}), usando chamada direta...")

        print("Buscando DefiLlama...", end=" ", flush=True)
        data = self._get(DEFILLAMA_URL, timeout=30)
        if not data or "data" not in data:
            print("FALHOU")
            return pd.DataFrame()

        rows = []
        chains_lower = [c.lower() for c in CHAINS_MONITORED]
        for pool in data["data"]:
            try:
                chain = pool.get("chain", "")
                if chain.lower() not in chains_lower:
                    continue
                tvl = float(pool.get("tvlUsd", 0) or 0)
                if tvl < MIN_TVL_USD:
                    continue
                apy = float(pool.get("apy", 0) or 0)
                if apy < MIN_APR:
                    continue
                status = pool.get("status", "active")
                if status and status != "active":
                    continue
                # Normalize chain name casing
                chain_norm = chain.capitalize()
                for ch in CHAINS_MONITORED:
                    if ch.lower() == chain.lower():
                        chain_norm = ch
                        break
                # Token symbols from underlyingTokens or parse symbol
                underlying = pool.get("underlyingTokens") or []
                symbol_str = pool.get("symbol", "")
                rows.append({
                    "pool_id":       pool.get("pool", ""),
                    "protocol":      pool.get("project", ""),
                    "chain":         chain_norm,
                    "symbol":        symbol_str,
                    "tokens":        "-".join(underlying) if underlying else symbol_str,
                    "tvlUsd":        tvl,
                    "apy":           apy,
                    "apyBase":       float(pool.get("apyBase", 0) or 0),
                    "apyReward":     float(pool.get("apyReward", 0) or 0),
                    "volumeUsd24h":  float(pool.get("volumeUsd1d", 0) or 0),
                    "il7d":          float(pool.get("il7d", 0) or 0),
                })
            except (ValueError, TypeError):
                continue

        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        print(f"OK ({len(df)} pools)")
        return df

    def fetch_uniswap_v3_pools(self, chain: str = "ethereum") -> "pd.DataFrame":
        """Fetch Uniswap V3 pools via GraphQL (The Graph)."""
        if not HAS_DEPS:
            return pd.DataFrame()
        chain_label = chain.capitalize()
        url = UNISWAP_ARB_URL if chain.lower() == "arbitrum" else UNISWAP_ETH_URL
        print(f"Buscando Uniswap V3 ({chain_label})...", end=" ", flush=True)
        result = self._post(url, {"query": UNISWAP_GQL_QUERY}, timeout=25)
        if not result or "data" not in result or not result["data"].get("pools"):
            print("FALHOU (GraphQL indisponivel)")
            return pd.DataFrame()

        rows = []
        for pool in result["data"]["pools"]:
            try:
                t0 = pool["token0"]["symbol"]
                t1 = pool["token1"]["symbol"]
                tvl = float(pool.get("totalValueLockedUSD", 0) or 0)
                if tvl <= 0:
                    continue
                fee_tier = int(pool.get("feeTier", 3000))
                day_data = pool.get("poolDayData", [])
                vol24h = float(day_data[0]["volumeUSD"]) if day_data else 0.0
                apr = (vol24h * fee_tier / 1_000_000 * 365) / tvl * 100 if tvl > 0 else 0.0
                rows.append({
                    "pool_id":      pool.get("id", ""),
                    "protocol":     "uniswap-v3",
                    "chain":        chain_label,
                    "symbol":       f"{t0}/{t1}",
                    "tokens":       f"{t0}-{t1}",
                    "token0":       t0,
                    "token1":       t1,
                    "tvlUsd":       tvl,
                    "apy":          apr,
                    "apyBase":      apr,
                    "apyReward":    0.0,
                    "volumeUsd24h": vol24h,
                    "il7d":         0.0,
                })
            except (KeyError, ValueError, TypeError, IndexError):
                continue

        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        print(f"OK ({len(df)} pools)")
        return df

    def fetch_aerodrome_pools(self) -> "pd.DataFrame":
        """Fetch Aerodrome Finance pools (Base chain)."""
        if not HAS_DEPS:
            return pd.DataFrame()
        print("Buscando Aerodrome...", end=" ", flush=True)
        raw = self._get(AERODROME_URL, timeout=20)
        if raw is None:
            print("FALHOU")
            return pd.DataFrame()

        # Handle both list and {"data": [...]} formats
        pool_list = raw if isinstance(raw, list) else raw.get("data", raw.get("pools", []))
        if not isinstance(pool_list, list):
            print("FALHOU (formato inesperado)")
            return pd.DataFrame()

        rows = []
        for pool in pool_list:
            try:
                symbol = pool.get("symbol", "")
                tvl = float(pool.get("tvl", pool.get("tvlUsd", 0)) or 0)
                if tvl < MIN_TVL_USD:
                    continue
                apy = float(pool.get("apr", pool.get("apy", 0)) or 0)
                if apy < MIN_APR:
                    continue
                vol24h = float(pool.get("volume24h", pool.get("volumeUsd24h", 0)) or 0)
                t0 = pool.get("token0", {}).get("symbol", "") if isinstance(pool.get("token0"), dict) else str(pool.get("token0", ""))
                t1 = pool.get("token1", {}).get("symbol", "") if isinstance(pool.get("token1"), dict) else str(pool.get("token1", ""))
                rows.append({
                    "pool_id":      pool.get("address", pool.get("id", "")),
                    "protocol":     "aerodrome",
                    "chain":        "Base",
                    "symbol":       symbol or f"{t0}/{t1}",
                    "tokens":       f"{t0}-{t1}",
                    "token0":       t0,
                    "token1":       t1,
                    "tvlUsd":       tvl,
                    "apy":          apy,
                    "apyBase":      apy,
                    "apyReward":    0.0,
                    "volumeUsd24h": vol24h,
                    "il7d":         0.0,
                })
            except (ValueError, TypeError, AttributeError):
                continue

        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        print(f"OK ({len(df)} pools)")
        return df

    def fetch_token_prices(self) -> Dict[str, Any]:
        """Fetch token prices from CoinGecko."""
        if not HAS_DEPS:
            return {}
        print("Buscando precos (CoinGecko)...", end=" ", flush=True)
        params = {
            "ids": "bitcoin,ethereum,usd-coin,tether,wrapped-bitcoin,arbitrum,optimism,matic-network",
            "vs_currencies": "usd",
            "include_market_cap": "true",
            "include_24hr_change": "true",
        }
        data = self._get(COINGECKO_PRICE_URL, params=params, timeout=15)
        if not data:
            print("FALHOU")
            return {}
        prices = {
            "BTC":   data.get("bitcoin", {}).get("usd", 0),
            "ETH":   data.get("ethereum", {}).get("usd", 0),
            "WBTC":  data.get("wrapped-bitcoin", {}).get("usd", 0),
            "USDC":  data.get("usd-coin", {}).get("usd", 1.0),
            "USDT":  data.get("tether", {}).get("usd", 1.0),
            "ARB":   data.get("arbitrum", {}).get("usd", 0),
            "OP":    data.get("optimism", {}).get("usd", 0),
            "MATIC": data.get("matic-network", {}).get("usd", 0),
            "btc_24h_change": data.get("bitcoin", {}).get("usd_24h_change", 0),
            "eth_24h_change": data.get("ethereum", {}).get("usd_24h_change", 0),
        }
        print(f"OK (ETH=${prices['ETH']:,.0f}, BTC=${prices['BTC']:,.0f})")
        return prices

    def fetch_market_sentiment(self) -> Dict[str, Any]:
        """Fetch global market sentiment from CoinGecko."""
        if not HAS_DEPS:
            return {"btc_dominance": 50, "total_mcap": 0, "mcap_change": 0, "sentiment": "NEUTRAL"}
        print("Buscando sentimento de mercado...", end=" ", flush=True)
        time.sleep(1)  # CoinGecko rate limit buffer
        data = self._get(COINGECKO_GLOBAL_URL, timeout=15)
        if not data or "data" not in data:
            print("FALHOU")
            return {"btc_dominance": 50, "total_mcap": 0, "mcap_change": 0, "sentiment": "NEUTRAL"}
        gd = data["data"]
        btc_dom  = float(gd.get("btc_dominance", 50) or 50)
        total_mc = float((gd.get("total_market_cap") or {}).get("usd", 0) or 0)
        mc_chg   = float(gd.get("market_cap_change_percentage_24h_usd", 0) or 0)
        if btc_dom < 50 and mc_chg > 0:
            sentiment = "RISK_ON"
        elif btc_dom > 55 or mc_chg < -3:
            sentiment = "RISK_OFF"
        else:
            sentiment = "NEUTRAL"
        print(f"OK (BTC dom={btc_dom:.1f}%, mcap chg={mc_chg:+.1f}%, sentiment={sentiment})")
        return {
            "btc_dominance": btc_dom,
            "total_mcap":    total_mc,
            "mcap_change":   mc_chg,
            "sentiment":     sentiment,
        }

    def get_all_pools(self) -> "pd.DataFrame":
        """Get all pools — from cache if fresh, else fetch all sources."""
        if not HAS_DEPS:
            print("ERROR: pandas/requests not installed.")
            return pd.DataFrame()

        cache_file = CACHE_DIR / "pools_cache.json"
        if not self.force_refresh and cache_file.exists():
            age_minutes = (time.time() - cache_file.stat().st_mtime) / 60
            if age_minutes < CACHE_TTL_MINUTES:
                print(f"Usando cache ({age_minutes:.0f} min atrás)...")
                try:
                    df = pd.read_json(cache_file)
                    print(f"Cache carregado: {len(df)} pools")
                    return df
                except Exception:
                    print("Cache corrompido, rebuscando...")

        frames: List["pd.DataFrame"] = []

        dl_df = self.fetch_defillama_pools()
        if not dl_df.empty:
            frames.append(dl_df)

        uni_eth = self.fetch_uniswap_v3_pools("ethereum")
        if not uni_eth.empty:
            frames.append(uni_eth)

        uni_arb = self.fetch_uniswap_v3_pools("arbitrum")
        if not uni_arb.empty:
            frames.append(uni_arb)

        aero_df = self.fetch_aerodrome_pools()
        if not aero_df.empty:
            frames.append(aero_df)

        if not frames:
            print("\nNenhuma fonte retornou dados.")
            return pd.DataFrame()

        combined = pd.concat(frames, ignore_index=True, sort=False)
        combined = combined.drop_duplicates(subset=["protocol", "chain", "symbol"], keep="first")
        combined = combined.reset_index(drop=True)

        # Fill missing columns
        for col in ["token0", "token1", "tokens"]:
            if col not in combined.columns:
                combined[col] = ""

        # Ensure numeric columns
        for col in ["tvlUsd", "apy", "apyBase", "apyReward", "volumeUsd24h", "il7d"]:
            if col in combined.columns:
                combined[col] = pd.to_numeric(combined[col], errors="coerce").fillna(0)

        # Save cache
        try:
            combined.to_json(cache_file, orient="records", date_format="iso")
            print(f"Cache salvo: {len(combined)} pools")
        except Exception as e:
            print(f"Aviso: nao foi possivel salvar cache: {e}")

        return combined


# ── POOL ANALYZER ─────────────────────────────────────────────────────────────
class PoolAnalyzer:
    def __init__(self, pools_df: "pd.DataFrame", market_data: Dict, token_prices: Dict):
        self.df = pools_df.copy() if not pools_df.empty else pd.DataFrame()
        self.market_data  = market_data
        self.token_prices = token_prices

    def _is_safe_token(self, symbol: str) -> bool:
        """Check if a token symbol is in the SAFE_TOKENS list."""
        if not symbol:
            return False
        upper = symbol.upper().strip()
        if upper in [t.upper() for t in SAFE_TOKENS]:
            return True
        # Check slash-separated parts (e.g. "USDC/WETH")
        for part in upper.split("/"):
            if part.strip() in [t.upper() for t in SAFE_TOKENS]:
                return True
        return False

    def _extract_tokens(self, row: "pd.Series") -> tuple:
        """Extract token0 and token1 from a row."""
        t0 = str(row.get("token0", "") or "")
        t1 = str(row.get("token1", "") or "")
        if not t0 or not t1:
            sym = str(row.get("symbol", "") or "")
            parts = sym.replace("-", "/").split("/")
            if len(parts) >= 2:
                t0, t1 = parts[0].strip(), parts[1].strip()
            elif len(parts) == 1:
                t0 = t1 = parts[0].strip()
        return t0, t1

    def filter_safe_pools(self) -> "pd.DataFrame":
        """Filter for safe pools: known tokens, trusted protocols, min TVL."""
        if self.df.empty:
            return pd.DataFrame()
        safe_protocols_lower = [p.lower() for p in SAFE_PROTOCOLS]
        rows = []
        for _, row in self.df.iterrows():
            proto = str(row.get("protocol", "") or "").lower()
            if proto not in safe_protocols_lower:
                continue
            tvl = float(row.get("tvlUsd", 0) or 0)
            if tvl < MIN_TVL_USD:
                continue
            t0, t1 = self._extract_tokens(row)
            if not (self._is_safe_token(t0) and self._is_safe_token(t1)):
                # Allow if at least one side is safe and symbol includes a safe token
                sym = str(row.get("symbol", "") or "")
                if not any(st.upper() in sym.upper() for st in SAFE_TOKENS):
                    continue
            rows.append(row)
        if not rows:
            return pd.DataFrame()
        result = pd.DataFrame(rows)
        result = result.sort_values(["apy", "tvlUsd"], ascending=[False, False])
        return result.reset_index(drop=True)

    def get_range_pools(self, apy_min: float = TARGET_APR_MIN, apy_max: float = TARGET_APR_MAX) -> "pd.DataFrame":
        """Get top pools in the target APR range with composite scoring."""
        safe = self.filter_safe_pools()
        if safe.empty:
            return pd.DataFrame()

        mask = (safe["apy"] >= apy_min) & (safe["apy"] <= apy_max)
        # IL filter: il7d <= 5 or null/zero
        il_col = safe.get("il7d", pd.Series([0]*len(safe)))
        il_mask = (safe["il7d"].fillna(0) <= 5)
        filtered = safe[mask & il_mask].copy()
        if filtered.empty:
            return pd.DataFrame()

        max_tvl = filtered["tvlUsd"].max() if not filtered.empty else 1
        filtered["tvl_score"]    = (filtered["tvlUsd"] / 10_000_000).clip(upper=1.0)
        filtered["volume_score"] = (filtered["volumeUsd24h"] / filtered["tvlUsd"].clip(lower=1)).clip(upper=1.0)

        def _safety(row):
            t0, t1 = self._extract_tokens(row)
            return 1.0 if (self._is_safe_token(t0) and self._is_safe_token(t1)) else 0.5

        filtered["safety_score"] = filtered.apply(_safety, axis=1)
        filtered["score"] = (
            filtered["apy"]           / TARGET_APR_MAX * 0.4 +
            filtered["tvl_score"]                      * 0.3 +
            filtered["volume_score"]                   * 0.2 +
            filtered["safety_score"]                   * 0.1
        )
        filtered = filtered.sort_values("score", ascending=False)
        return filtered.head(5).reset_index(drop=True)

    def get_safest_pools_for_market(self) -> "pd.DataFrame":
        """Return 2 pools best suited to current market sentiment."""
        safe = self.filter_safe_pools()
        if safe.empty:
            return pd.DataFrame()

        sentiment = self.market_data.get("sentiment", "NEUTRAL")

        def _add_reason(df: "pd.DataFrame", reason: str) -> "pd.DataFrame":
            if df.empty:
                return df
            df = df.copy()
            df["reason"] = reason
            return df

        stablecoin_keywords  = ["USDC", "USDT", "DAI", "LUSD"]
        volatile_keywords    = ["WBTC", "WETH", "ETH", "BTC", "cbBTC"]

        def _has_keyword(sym: str, keywords: List[str]) -> bool:
            s = sym.upper()
            return any(k in s for k in keywords)

        if sentiment == "RISK_OFF":
            mask = safe["symbol"].apply(lambda s: _has_keyword(s, stablecoin_keywords))
            preferred = safe[mask].copy()
            proto_mask = preferred["protocol"].str.lower().isin(["curve", "uniswap-v3"])
            if proto_mask.any():
                preferred = preferred[proto_mask]
            preferred = _add_reason(preferred.head(2), "Mercado RISK_OFF: priorizar stablecoins")
            return preferred

        elif sentiment == "RISK_ON":
            mask = safe["symbol"].apply(lambda s: _has_keyword(s, volatile_keywords))
            preferred = safe[mask].copy()
            preferred = _add_reason(preferred.head(2), "Mercado RISK_ON: oportunidade em ativos volateis")
            return preferred

        else:  # NEUTRAL
            stable_mask = safe["symbol"].apply(lambda s: _has_keyword(s, stablecoin_keywords))
            vol_mask    = safe["symbol"].apply(lambda s: _has_keyword(s, volatile_keywords))
            part1 = safe[stable_mask].head(1)
            part2 = safe[vol_mask].head(1)
            mixed = pd.concat([part1, part2], ignore_index=True).head(2)
            mixed = _add_reason(mixed, "Mercado NEUTRAL: mix de estavel e volatil")
            return mixed

    def get_best_performing_24h(self) -> "pd.DataFrame":
        """Get pools with best 24h yield (volume/TVL based)."""
        if self.df.empty:
            return pd.DataFrame()
        df = self.df[self.df["volumeUsd24h"] > 0].copy()
        if df.empty:
            return pd.DataFrame()
        df["yield_24h"] = df["volumeUsd24h"] * 0.003 / df["tvlUsd"].clip(lower=1) * 100
        df = df[df["yield_24h"] > 0.008]
        df = df.sort_values("yield_24h", ascending=False)
        return df.head(5).reset_index(drop=True)

    def score_pool_risk(self, row: "pd.Series") -> str:
        """Assign a risk label to a pool row."""
        t0, t1 = self._extract_tokens(row)
        safe_both = self._is_safe_token(t0) and self._is_safe_token(t1)
        tvl = float(row.get("tvlUsd", 0) or 0)
        apy = float(row.get("apy", 0) or 0)
        if apy > 200 or tvl < 500_000:
            return "ALTO"
        if safe_both and tvl > 2_000_000 and apy < 200:
            return "BAIXO"
        return "MEDIO"


# ── REPORT GENERATOR ──────────────────────────────────────────────────────────
class ReportGenerator:
    def _fmt_usd(self, v: float) -> str:
        if v >= 1_000_000_000:
            return f"${v/1_000_000_000:.2f}B"
        if v >= 1_000_000:
            return f"${v/1_000_000:.2f}M"
        if v >= 1_000:
            return f"${v/1_000:.1f}K"
        return f"${v:.2f}"

    def _fmt_pct(self, v: float) -> str:
        return f"{v:.2f}%"

    def generate_daily_summary(self, analyzer: "PoolAnalyzer") -> str:
        now_utc = datetime.now(timezone.utc)
        lines: List[str] = []

        lines.append("=" * 70)
        lines.append("  LIQUIDITY POOL MONITOR  —  DeFi Yield Intelligence")
        lines.append("=" * 70)
        lines.append(f"  Data/Hora UTC : {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"  Chains        : {', '.join(CHAINS_MONITORED)}")
        lines.append(f"  Min TVL       : {self._fmt_usd(MIN_TVL_USD)}")
        lines.append(f"  Range APR     : {TARGET_APR_MIN:.0f}% — {TARGET_APR_MAX:.0f}%")
        lines.append("")

        # ── Market Sentiment ──
        md = analyzer.market_data
        tp = analyzer.token_prices
        lines.append("─" * 70)
        lines.append("  SENTIMENTO DE MERCADO")
        lines.append("─" * 70)
        sentiment_icon = {"RISK_ON": "[RISK ON ]", "RISK_OFF": "[RISK OFF]", "NEUTRAL": "[NEUTRAL ]"}.get(
            md.get("sentiment", "NEUTRAL"), "[NEUTRAL ]"
        )
        lines.append(f"  Status        : {sentiment_icon}  {md.get('sentiment','N/A')}")
        lines.append(f"  BTC Dominance : {md.get('btc_dominance', 0):.2f}%")
        mcap = md.get("total_mcap", 0)
        lines.append(f"  Market Cap    : {self._fmt_usd(mcap)}")
        lines.append(f"  MCap 24h Chg  : {md.get('mcap_change', 0):+.2f}%")
        if tp:
            btc_chg = tp.get("btc_24h_change", 0) or 0
            eth_chg = tp.get("eth_24h_change", 0) or 0
            lines.append(f"  BTC           : {self._fmt_usd(tp.get('BTC', 0))} ({btc_chg:+.2f}%)")
            lines.append(f"  ETH           : {self._fmt_usd(tp.get('ETH', 0))} ({eth_chg:+.2f}%)")
        lines.append("")

        # ── Range Pools ──
        lines.append("─" * 70)
        lines.append(f"  POOLS NO RANGE IDEAL ({TARGET_APR_MIN:.0f}% a {TARGET_APR_MAX:.0f}% APR)  — Top 5")
        lines.append("─" * 70)
        range_df = analyzer.get_range_pools()
        if range_df.empty:
            lines.append("  Nenhuma pool no range encontrada.")
        else:
            hdr = f"  {'#':<3} {'Symbol':<22} {'Protocol':<18} {'Chain':<12} {'APR%':>8} {'TVL':>12} {'Risco':<7}"
            lines.append(hdr)
            lines.append("  " + "-" * 86)
            for i, (_, row) in enumerate(range_df.iterrows(), 1):
                risk = analyzer.score_pool_risk(row)
                lines.append(
                    f"  {i:<3} {str(row.get('symbol',''))[:22]:<22} "
                    f"{str(row.get('protocol',''))[:18]:<18} "
                    f"{str(row.get('chain',''))[:12]:<12} "
                    f"{self._fmt_pct(row.get('apy', 0)):>8} "
                    f"{self._fmt_usd(row.get('tvlUsd', 0)):>12} "
                    f"{risk:<7}"
                )
        lines.append("")

        # ── Safest for Market ──
        lines.append("─" * 70)
        lines.append("  2 POOLS MAIS SEGURAS PARA O MOMENTO")
        lines.append("─" * 70)
        safe_df = analyzer.get_safest_pools_for_market()
        if safe_df.empty:
            lines.append("  Dados insuficientes.")
        else:
            for i, (_, row) in enumerate(safe_df.iterrows(), 1):
                lines.append(f"  {i}. {row.get('symbol','')}  [{row.get('protocol','')} / {row.get('chain','')}]")
                lines.append(f"     APR: {self._fmt_pct(row.get('apy', 0))}  |  TVL: {self._fmt_usd(row.get('tvlUsd', 0))}")
                if "reason" in row and row["reason"]:
                    lines.append(f"     Razao: {row['reason']}")
                lines.append("")

        # ── Best 24h Performers ──
        lines.append("─" * 70)
        lines.append("  MELHORES PERFORMERS 24H  — Top 5")
        lines.append("─" * 70)
        perf_df = analyzer.get_best_performing_24h()
        if perf_df.empty:
            lines.append("  Sem dados de volume 24h suficientes.")
        else:
            hdr2 = f"  {'#':<3} {'Symbol':<22} {'Protocol':<18} {'Chain':<12} {'Yield24h':>10} {'Vol24h':>12}"
            lines.append(hdr2)
            lines.append("  " + "-" * 80)
            for i, (_, row) in enumerate(perf_df.iterrows(), 1):
                lines.append(
                    f"  {i:<3} {str(row.get('symbol',''))[:22]:<22} "
                    f"{str(row.get('protocol',''))[:18]:<18} "
                    f"{str(row.get('chain',''))[:12]:<12} "
                    f"{self._fmt_pct(row.get('yield_24h', 0)):>10} "
                    f"{self._fmt_usd(row.get('volumeUsd24h', 0)):>12}"
                )
        lines.append("")

        # ── Footer ──
        lines.append("─" * 70)
        lines.append("  FONTES DE DADOS")
        lines.append("─" * 70)
        lines.append("  1. DefiLlama Yields API  — https://yields.llama.fi/pools")
        lines.append("  2. Uniswap V3 GraphQL    — The Graph (Ethereum + Arbitrum)")
        lines.append("  3. Aerodrome Finance     — https://api.aerodrome.finance/api/v1/pools")
        lines.append("  4. CoinGecko API         — https://api.coingecko.com/api/v3/")
        lines.append(f"  Gerado em: {now_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        lines.append("=" * 70)

        return "\n".join(lines)

    def save_report(self, text: str, filepath: "Path") -> None:
        """Write report text to file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)

    def print_summary(self, analyzer: "PoolAnalyzer") -> str:
        """Generate, print, and return the report."""
        report = self.generate_daily_summary(analyzer)
        print(report)
        return report


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    if not HAS_DEPS:
        print("ERROR: Missing dependencies. Run: py -m pip install requests pandas numpy tabulate")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Liquidity Pool Monitor")
    parser.add_argument("--mode",     default="live", choices=["live", "full"],
                        help="Mode: live (default) or full")
    parser.add_argument("--symbols",  nargs="*", help="(compatibility, not used)")
    parser.add_argument("--exchange", default="binance",
                        help="(compatibility, not used)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Force refresh even if cache is fresh")
    parser.add_argument("--output",   default="both",
                        choices=["terminal", "file", "both"],
                        help="Output destination (default: both)")
    args = parser.parse_args()

    print()
    print("=" * 50)
    print("  LIQUIDITY POOL MONITOR  v1.0")
    print("=" * 50)
    print()

    fetcher = DataFetcher(force_refresh=args.no_cache)

    # Fetch pools
    pools_df = fetcher.get_all_pools()
    if pools_df.empty:
        print()
        print("AVISO: Nenhum dado de pool disponivel no momento.")
        print("Possíveis causas: APIs fora do ar, sem conexao, rate limit.")
        print("Tente novamente em alguns minutos ou use --no-cache.")
        sys.exit(0)

    print(f"\nTotal de pools carregadas: {len(pools_df)}")

    # Fetch market data
    market_data   = fetcher.fetch_market_sentiment()
    time.sleep(1)
    token_prices  = fetcher.fetch_token_prices()
    print()

    # Analyze
    analyzer  = PoolAnalyzer(pools_df, market_data, token_prices)
    reporter  = ReportGenerator()

    # Output
    if args.output in ("terminal", "both"):
        report_text = reporter.print_summary(analyzer)
    else:
        report_text = reporter.generate_daily_summary(analyzer)

    if args.output in ("file", "both"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORT_DIR / f"pool_report_{ts}.txt"
        reporter.save_report(report_text, report_path)
        print(f"\nRelatorio salvo em: {report_path}")

        # Also save CSVs
        if not pools_df.empty:
            csv_path = DATA_DIR / f"pools_{ts}.csv"
            pools_df.to_csv(csv_path, index=False)
            print(f"CSV salvo em: {csv_path}")

        range_df = analyzer.get_range_pools()
        if not range_df.empty:
            top_path = DATA_DIR / f"top_pools_{ts}.csv"
            range_df.to_csv(top_path, index=False)
            print(f"Top pools CSV: {top_path}")

    print()
    print("Concluido.")


if __name__ == "__main__":
    main()
