#!/usr/bin/env python3
"""
squeeze_monitor.py — Monitor de Long/Short Squeeze para mercados de futuros perpétuos.

Base de conhecimento: PhD-level em microestrutura de mercado, derivativos cripto,
finanças comportamentais e teoria de squeeze em mercados alavancados.

TEORIA DO SQUEEZE
=================
Um squeeze ocorre quando participantes do mercado com posições em uma direção
são forçados a fechar (ou reverter) por movimento adverso de preço, amplificando
o movimento original via cascata de liquidações e cobertura forçada.

LONG SQUEEZE (shorts ganham):
  - Longs sobrecarregados (alto L/S ratio, funding positivo extremo)
  - Preço cai → margin calls → longs fecham vendendo → preço cai mais
  - Resultado: queda acelerada, pânico, candlestick de corpo longo vermelho

SHORT SQUEEZE (longs ganham):
  - Shorts sobrecarregados (funding negativo extremo, L/S ratio baixo)
  - Preço sobe → short sellers precisam comprar para cobrir → preço sobe mais
  - Resultado: rally explosivo, gap ups, wick longo verde

INDICADORES USADOS (multi-fator):
  1. Funding Rate       — custo de carregar a posição (proxy de sentimento)
  2. Open Interest      — tamanho total de posições abertas (combustível do squeeze)
  3. Long/Short Ratio   — desequilíbrio de posicionamento (quem está sobrecarregado)
  4. Liquidações 24h    — velocidade de destruição de posições (acelerador)
  5. Preço (variação)   — confirmação de direção e momentum
  6. Mark vs Index      — basis (divergência indica pressão iminente)

MODELO DE SCORE (weighted composite):
  Score = Σ(indicador_i × peso_i) normalizado para [-100, +100]
  Positivo → pressão de SHORT SQUEEZE (longs em aperto)
  Negativo → pressão de LONG SQUEEZE  (shorts em aperto)

  | Indicador           | Peso | Lógica                                        |
  |---------------------|------|-----------------------------------------------|
  | Funding Rate        | 35%  | Extremo + → shorts sobrecarregados (squeeze ↑)|
  |                     |      | Extremo - → longs sobrecarregados (squeeze ↓) |
  | L/S Ratio           | 25%  | Alto → longs dominam → risco de long squeeze  |
  |                     |      | Baixo → shorts dominam → risco short squeeze  |
  | OI Change           | 20%  | OI subindo + funding extremo = squeeze iminente|
  | Liquidações 24h     | 15%  | Alta liquidação longs → long squeeze em curso |
  |                     |      | Alta liquidação shorts → short squeeze em curso|
  | Basis (Mark-Index)  | 5%   | Divergência positiva → contango → pressão long |

LIMIARES DE ALERTA:
  |Score| >= 60  → SQUEEZE ATIVO (alta probabilidade, agir com cautela)
  |Score| >= 40  → SQUEEZE FORMANDO (sinais convergentes, monitorar)
  |Score| >= 20  → PRESSÃO ELEVADA (atenção, sem sinal claro ainda)
  |Score| <  20  → NEUTRO

Autores: OpenClaw Research Desk
Data: 2026-03-27
"""

import sys
import os
import argparse
import json
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ── Path setup ────────────────────────────────────────────────────────────────
SKILL_DIR  = Path(__file__).resolve().parent.parent
SHARED_DIR = SKILL_DIR.parent / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

# ── Imports opcionais (API Gateway) ──────────────────────────────────────────
try:
    from api_gateway import APIRouter
    GATEWAY_AVAILABLE = True
except ImportError:
    GATEWAY_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CONFIGURAÇÃO & CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

BINANCE_FUTURES  = "https://fapi.binance.com/fapi/v1"
BINANCE_FDATA    = "https://fapi.binance.com/futures/data"

# Thresholds de funding rate (% ao período de 8h)
FUNDING_EXTREME_HIGH =  0.08   # >  0.08% → shorts sobrecarregados (squeeze up)
FUNDING_HIGH         =  0.04   # >  0.04% → pressão elevada
FUNDING_EXTREME_LOW  = -0.03   # < -0.03% → longs sobrecarregados (squeeze down)
FUNDING_LOW          = -0.01   # < -0.01% → pressão elevada

# Thresholds de Long/Short ratio
LS_EXTREME_HIGH = 2.0   # > 2.0 → longs muito dominantes → risco long squeeze
LS_HIGH         = 1.5
LS_EXTREME_LOW  = 0.6   # < 0.6 → shorts muito dominantes → risco short squeeze
LS_LOW          = 0.8

# Pesos do modelo composite
WEIGHTS = {
    "funding":      0.35,
    "long_short":   0.25,
    "oi_change":    0.20,
    "liquidations": 0.15,
    "basis":        0.05,
}

# Diretório de output
OUTPUT_DIR = Path.home() / "squeeze_monitor"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "reports").mkdir(exist_ok=True)
(OUTPUT_DIR / "data").mkdir(exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — COLETA DE DADOS
# ══════════════════════════════════════════════════════════════════════════════

class DataCollector:
    """
    Coleta todos os dados necessários para análise de squeeze.
    Usa API Gateway com fallback para chamadas diretas.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "OpenClaw-SqueezeMonitor/1.0"})
        self.router = APIRouter() if GATEWAY_AVAILABLE else None

    def _get(self, url: str, params: dict = None, timeout: int = 10) -> dict:
        try:
            r = self.session.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"_error": str(e)}

    # ── Funding Rate ──────────────────────────────────────────────────────────

    def get_funding_rate(self, symbol: str) -> dict:
        """Retorna funding rate atual + histórico recente."""
        # Funding atual
        current = self._get(f"{BINANCE_FUTURES}/premiumIndex", {"symbol": symbol})
        if "_error" in current:
            return {"rate": 0.0, "rate_pct": "0.0000%", "mark_price": 0.0,
                    "index_price": 0.0, "next_funding_ts": 0, "source": "error"}

        rate = float(current.get("lastFundingRate", 0))

        # Histórico de funding (últimas 30 amostras = 10 dias)
        history_raw = self._get(f"{BINANCE_FUTURES}/fundingRate",
                                {"symbol": symbol, "limit": 30})
        history = []
        if isinstance(history_raw, list):
            history = [float(x.get("fundingRate", 0)) * 100 for x in history_raw]

        avg_7d  = sum(history[-21:]) / len(history[-21:]) if history else 0
        avg_24h = sum(history[-3:]) / len(history[-3:]) if history else 0

        return {
            "symbol":          symbol,
            "rate":            rate,
            "rate_pct":        f"{rate * 100:.4f}%",
            "rate_float":      rate * 100,
            "mark_price":      float(current.get("markPrice", 0)),
            "index_price":     float(current.get("indexPrice", 0)),
            "next_funding_ts": int(current.get("nextFundingTime", 0)) // 1000,
            "avg_24h":         avg_24h,
            "avg_7d":          avg_7d,
            "history":         history[-21:],
            "source":          "binance",
        }

    # ── Open Interest ─────────────────────────────────────────────────────────

    def get_open_interest(self, symbol: str) -> dict:
        """Retorna OI atual + variação histórica."""
        # OI atual
        oi_now = self._get(f"{BINANCE_FUTURES}/openInterest", {"symbol": symbol})
        if "_error" in oi_now:
            return {"oi_usd": 0, "oi_change_1h": 0, "oi_change_24h": 0}

        oi_val = float(oi_now.get("openInterest", 0))

        # Histórico de OI (Binance futures data)
        oi_hist = self._get(
            "https://fapi.binance.com/futures/data/openInterestHist",
            {"symbol": symbol, "period": "1h", "limit": 25}
        )
        oi_change_1h  = 0.0
        oi_change_24h = 0.0
        oi_usd        = 0.0

        if isinstance(oi_hist, list) and len(oi_hist) > 1:
            latest     = float(oi_hist[-1].get("sumOpenInterestValue", 0))
            one_hr_ago = float(oi_hist[-2].get("sumOpenInterestValue", latest))
            day_ago    = float(oi_hist[0].get("sumOpenInterestValue", latest)) if len(oi_hist) >= 24 else latest
            oi_usd        = latest
            oi_change_1h  = ((latest - one_hr_ago) / one_hr_ago * 100) if one_hr_ago else 0
            oi_change_24h = ((latest - day_ago) / day_ago * 100) if day_ago else 0

        mark_price = float(self._get(f"{BINANCE_FUTURES}/premiumIndex",
                                     {"symbol": symbol}).get("markPrice", 1))
        oi_usd_calc = oi_val * mark_price if oi_usd == 0 else oi_usd

        return {
            "symbol":         symbol,
            "oi_contracts":   oi_val,
            "oi_usd":         oi_usd_calc,
            "oi_usd_b":       oi_usd_calc / 1e9,
            "oi_change_1h":   oi_change_1h,
            "oi_change_24h":  oi_change_24h,
            "source":         "binance",
        }

    # ── Long/Short Ratio ──────────────────────────────────────────────────────

    def get_long_short_ratio(self, symbol: str) -> dict:
        """
        Retorna L/S ratio de contas (account-based) e posições (position-based).
        Conta = quantos traders têm posição long vs short.
        Posição = volume total long vs short (inclui tamanho).
        Ambos contam — discrepância entre eles é sinal extra.
        """
        # Account-based (mais estável, menos ruidoso)
        acct = self._get(
            f"{BINANCE_FDATA}/globalLongShortAccountRatio",
            {"symbol": symbol, "period": "1h", "limit": 24}
        )
        # Position-based (mais sensível a baleias)
        pos = self._get(
            f"{BINANCE_FDATA}/topLongShortPositionRatio",
            {"symbol": symbol, "period": "1h", "limit": 24}
        )
        # Top traders L/S
        top = self._get(
            f"{BINANCE_FDATA}/topLongShortAccountRatio",
            {"symbol": symbol, "period": "1h", "limit": 24}
        )

        def parse_ratio(data):
            if isinstance(data, list) and data:
                latest = data[-1]
                hist   = data
                long_pct  = float(latest.get("longAccount", latest.get("longPosition", 0.5)))
                short_pct = float(latest.get("shortAccount", latest.get("shortPosition", 0.5)))
                ratio     = long_pct / short_pct if short_pct > 0 else 1.0
                # Tendência: comparar atual vs 6h atrás
                old = data[-7] if len(data) >= 7 else data[0]
                old_long  = float(old.get("longAccount", old.get("longPosition", 0.5)))
                old_short = float(old.get("shortAccount", old.get("shortPosition", 0.5)))
                old_ratio = old_long / old_short if old_short > 0 else 1.0
                trend = ((ratio - old_ratio) / old_ratio * 100) if old_ratio else 0
                return {
                    "ratio":     ratio,
                    "long_pct":  long_pct * 100,
                    "short_pct": short_pct * 100,
                    "trend_6h":  trend,
                }
            return {"ratio": 1.0, "long_pct": 50.0, "short_pct": 50.0, "trend_6h": 0.0}

        acct_data = parse_ratio(acct) if not isinstance(acct, dict) or "_error" not in acct else parse_ratio([])
        pos_data  = parse_ratio(pos)  if not isinstance(pos, dict)  or "_error" not in pos  else parse_ratio([])
        top_data  = parse_ratio(top)  if not isinstance(top, dict)  or "_error" not in top  else parse_ratio([])

        # Divergência entre retail (account) e top traders (top)
        divergence = acct_data["ratio"] - top_data["ratio"]

        return {
            "symbol":            symbol,
            "account":           acct_data,
            "position":          pos_data,
            "top_traders":       top_data,
            "divergence":        divergence,   # > 0 → retail mais long que top traders
            "composite_ratio":   (acct_data["ratio"] * 0.4 + pos_data["ratio"] * 0.4 + top_data["ratio"] * 0.2),
            "source":            "binance",
        }

    # ── Liquidações ───────────────────────────────────────────────────────────

    def get_liquidations(self, symbol: str) -> dict:
        """
        Retorna volume de liquidações 24h por lado.
        Binance só retorna liquidações recentes (limite 1000 ordens).
        Estimativa: acumular as últimas ordens de liquidação.
        """
        liq = self._get(
            f"{BINANCE_FUTURES}/forceOrders",
            {"symbol": symbol, "autoCloseType": "LIQUIDATION", "limit": 1000}
        )

        long_liq_usd  = 0.0  # Liquidações de longs (preço cai)
        short_liq_usd = 0.0  # Liquidações de shorts (preço sobe)
        long_count    = 0
        short_count   = 0
        total_liq_usd = 0.0

        if isinstance(liq, list):
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).timestamp() * 1000
            for order in liq:
                ts  = float(order.get("time", 0))
                if ts < cutoff:
                    continue
                qty   = float(order.get("origQty", 0))
                price = float(order.get("price", 0))
                usd   = qty * price
                side  = order.get("side", "")  # BUY = short being liquidated, SELL = long
                if side == "SELL":   # long position liquidated → sells into market
                    long_liq_usd  += usd
                    long_count    += 1
                elif side == "BUY":  # short position liquidated → buys from market
                    short_liq_usd += usd
                    short_count   += 1
                total_liq_usd += usd

        liq_ratio = (long_liq_usd / short_liq_usd) if short_liq_usd > 0 else (
                     10.0 if long_liq_usd > 0 else 1.0)

        return {
            "symbol":           symbol,
            "long_liq_usd":     long_liq_usd,
            "short_liq_usd":    short_liq_usd,
            "total_liq_usd":    total_liq_usd,
            "long_liq_count":   long_count,
            "short_liq_count":  short_count,
            "liq_ratio":        liq_ratio,   # > 1 → mais longs liquidados
            "dominant_side":    "LONGS" if long_liq_usd > short_liq_usd else "SHORTS",
            "source":           "binance",
        }

    # ── Preço e Variação ──────────────────────────────────────────────────────

    def get_price_data(self, symbol: str) -> dict:
        """Retorna preço, variação 1h/4h/24h e volume."""
        ticker = self._get(f"{BINANCE_FUTURES}/ticker/24hr", {"symbol": symbol})
        klines_1h = self._get(f"{BINANCE_FUTURES}/klines",
                              {"symbol": symbol, "interval": "1h", "limit": 5})
        klines_4h = self._get(f"{BINANCE_FUTURES}/klines",
                              {"symbol": symbol, "interval": "4h", "limit": 2})

        price     = float(ticker.get("lastPrice", 0))
        change_24h = float(ticker.get("priceChangePercent", 0))
        volume_24h = float(ticker.get("quoteVolume", 0))

        change_1h = 0.0
        if isinstance(klines_1h, list) and len(klines_1h) >= 2:
            open_1h   = float(klines_1h[-2][1])
            close_1h  = float(klines_1h[-1][4])
            change_1h = ((close_1h - open_1h) / open_1h * 100) if open_1h else 0

        change_4h = 0.0
        if isinstance(klines_4h, list) and len(klines_4h) >= 2:
            open_4h   = float(klines_4h[0][1])
            close_4h  = float(klines_4h[-1][4])
            change_4h = ((close_4h - open_4h) / open_4h * 100) if open_4h else 0

        return {
            "symbol":      symbol,
            "price":       price,
            "change_1h":   change_1h,
            "change_4h":   change_4h,
            "change_24h":  change_24h,
            "volume_24h":  volume_24h,
            "high_24h":    float(ticker.get("highPrice", 0)),
            "low_24h":     float(ticker.get("lowPrice", 0)),
            "source":      "binance",
        }


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — ENGINE DE ANÁLISE (Score Model)
# ══════════════════════════════════════════════════════════════════════════════

class SqueezeAnalyzer:
    """
    Engine principal de análise de squeeze.

    Modelo multi-fator baseado em:
    - Microestrutura de mercado (Kyle 1985, Glosten-Milgrom)
    - Teoria de squeeze em futuros (Pirrong 2001)
    - Comportamento de funding em perpetuals (Funding Rate Premium Theory)
    - Cascata de liquidações (Brunnermeier & Pedersen 2009 — margin spirals)
    """

    def __init__(self):
        self.collector = DataCollector()

    def analyze(self, symbol: str) -> dict:
        """Análise completa de squeeze para um símbolo."""
        print(f"  [{symbol}] Coletando dados...")

        # Coleta paralela (sequencial aqui por simplicidade)
        funding  = self.collector.get_funding_rate(symbol)
        oi       = self.collector.get_open_interest(symbol)
        ls       = self.collector.get_long_short_ratio(symbol)
        liq      = self.collector.get_liquidations(symbol)
        price    = self.collector.get_price_data(symbol)

        # Calcula score
        score, components = self._compute_score(funding, oi, ls, liq, price)
        signal = self._classify_signal(score)
        regime = self._market_regime(funding, ls, oi, liq, price)
        alerts = self._generate_alerts(score, signal, funding, ls, oi, liq, price)
        recommendation = self._generate_recommendation(score, signal, regime, funding, ls, liq)

        return {
            "symbol":         symbol,
            "timestamp":      datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "score":          round(score, 2),
            "signal":         signal,
            "regime":         regime,
            "components":     components,
            "raw": {
                "funding":    funding,
                "oi":         oi,
                "long_short": ls,
                "liquidations": liq,
                "price":      price,
            },
            "alerts":         alerts,
            "recommendation": recommendation,
        }

    def _compute_score(self, funding, oi, ls, liq, price) -> tuple:
        """
        Calcula score composite de squeeze em escala [-100, +100].

        Positivo (+) → pressão SHORT SQUEEZE (shorts sobrecarregados, longs ganham)
        Negativo (-) → pressão LONG SQUEEZE  (longs sobrecarregados, shorts ganham)

        Lógica:
          SHORT SQUEEZE conditions:
            - Funding muito negativo (shorts pagam longs, posição sobrecarregada)
            - L/S ratio baixo (shorts dominam, muita munição para squeeze)
            - OI crescendo com funding negativo (mais shorts abrindo = mais combustível)
            - Alta liquidação de longs (shorts sendo agressivos)
            - Preço começando a subir (trigger do squeeze)

          LONG SQUEEZE conditions:
            - Funding muito positivo (longs pagam shorts)
            - L/S ratio alto (longs dominam)
            - OI crescendo com funding positivo
            - Alta liquidação de shorts
            - Preço começando a cair
        """
        components = {}

        # ── 1. Funding Rate Score (peso 35%) ─────────────────────────────────
        # Escala: funding extremo positivo → score positivo (squeeze up)
        #         funding extremo negativo → score negativo (squeeze down)
        rate = funding.get("rate_float", 0)  # já em %
        if rate >= FUNDING_EXTREME_HIGH:
            # Shorts sobrecarregados → SHORT SQUEEZE iminente
            f_score = min(100, (rate / FUNDING_EXTREME_HIGH) * 80)
        elif rate >= FUNDING_HIGH:
            f_score = 40 + (rate - FUNDING_HIGH) / (FUNDING_EXTREME_HIGH - FUNDING_HIGH) * 40
        elif rate <= FUNDING_EXTREME_LOW:
            # Longs sobrecarregados → LONG SQUEEZE iminente (score negativo)
            f_score = max(-100, -(abs(rate) / abs(FUNDING_EXTREME_LOW)) * 80)
        elif rate <= FUNDING_LOW:
            f_score = -40 - (abs(rate) - abs(FUNDING_LOW)) / (abs(FUNDING_EXTREME_LOW) - abs(FUNDING_LOW)) * 40
        else:
            f_score = rate / FUNDING_HIGH * 40  # zona neutra proporcional

        components["funding"] = {
            "score":   round(f_score, 2),
            "weight":  WEIGHTS["funding"],
            "value":   f"{rate:.4f}%",
            "interpretation": _interpret_funding(rate),
        }

        # ── 2. Long/Short Ratio Score (peso 25%) ─────────────────────────────
        # L/S ratio alto → longs dominam → risco LONG SQUEEZE (score negativo)
        # L/S ratio baixo → shorts dominam → risco SHORT SQUEEZE (score positivo)
        ratio = ls.get("composite_ratio", 1.0)
        divergence = ls.get("divergence", 0)  # retail vs smart money

        if ratio >= LS_EXTREME_HIGH:
            ls_base = -min(100, (ratio / LS_EXTREME_HIGH) * 70)  # longs sobrecarregados
        elif ratio >= LS_HIGH:
            ls_base = -30 - (ratio - LS_HIGH) / (LS_EXTREME_HIGH - LS_HIGH) * 40
        elif ratio <= LS_EXTREME_LOW:
            ls_base = min(100, (LS_EXTREME_LOW / ratio) * 70)   # shorts sobrecarregados
        elif ratio <= LS_LOW:
            ls_base = 30 + (LS_LOW - ratio) / (LS_LOW - LS_EXTREME_LOW) * 40
        else:
            ls_base = (1.0 - ratio) / (LS_HIGH - 1.0) * 30

        # Divergência retail vs top traders amplifica o sinal
        # Retail compra, smart money vende → long squeeze provável
        div_bonus = -divergence * 10  # divergência positiva = mais risco long squeeze
        ls_score  = max(-100, min(100, ls_base + div_bonus))

        components["long_short"] = {
            "score":        round(ls_score, 2),
            "weight":       WEIGHTS["long_short"],
            "ratio":        round(ratio, 3),
            "long_pct":     round(ls.get("account", {}).get("long_pct", 50), 2),
            "short_pct":    round(ls.get("account", {}).get("short_pct", 50), 2),
            "divergence":   round(divergence, 3),
            "interpretation": _interpret_ls(ratio, divergence),
        }

        # ── 3. Open Interest Change Score (peso 20%) ─────────────────────────
        # OI crescendo + funding extremo = squeeze iminente (combustível aumentando)
        # OI caindo = posições sendo fechadas (squeeze se esgotando)
        oi_change_1h  = oi.get("oi_change_1h", 0)
        oi_change_24h = oi.get("oi_change_24h", 0)

        # Combina variação 1h (urgência) e 24h (tendência)
        oi_momentum = oi_change_1h * 0.6 + oi_change_24h * 0.4

        # Score depende de direção do funding (confirma ou contraria)
        if abs(rate) > FUNDING_HIGH:
            # OI crescendo na direção do funding extremo = perigoso
            oi_score = oi_momentum * (10 if f_score > 0 else -10)
        else:
            # OI crescendo sem funding extremo = neutro
            oi_score = oi_momentum * 3

        oi_score = max(-100, min(100, oi_score))

        components["oi_change"] = {
            "score":          round(oi_score, 2),
            "weight":         WEIGHTS["oi_change"],
            "oi_usd_b":       round(oi.get("oi_usd_b", 0), 3),
            "change_1h_pct":  round(oi_change_1h, 3),
            "change_24h_pct": round(oi_change_24h, 3),
            "interpretation": _interpret_oi(oi_change_1h, oi_change_24h, rate),
        }

        # ── 4. Liquidações Score (peso 15%) ──────────────────────────────────
        # Alta liquidação de longs → long squeeze em curso (score negativo)
        # Alta liquidação de shorts → short squeeze em curso (score positivo)
        long_liq  = liq.get("long_liq_usd", 0)
        short_liq = liq.get("short_liq_usd", 0)
        total_liq = liq.get("total_liq_usd", 1)
        liq_ratio = liq.get("liq_ratio", 1.0)

        if total_liq > 0:
            long_share  = long_liq  / total_liq
            short_share = short_liq / total_liq
            # Score: shorts liquidados → squeeze up (positivo)
            #        longs liquidados  → squeeze down (negativo)
            liq_score = (short_share - long_share) * 100
            # Amplifica pelo volume absoluto (grandes liquidações = mais significativo)
            if total_liq > 100_000_000:   # > $100M em liquidações
                liq_score *= 1.5
            elif total_liq > 10_000_000:  # > $10M
                liq_score *= 1.2
        else:
            liq_score = 0.0

        liq_score = max(-100, min(100, liq_score))

        components["liquidations"] = {
            "score":           round(liq_score, 2),
            "weight":          WEIGHTS["liquidations"],
            "long_liq_usd":    long_liq,
            "short_liq_usd":   short_liq,
            "total_liq_usd":   total_liq,
            "dominant_side":   liq.get("dominant_side", "N/A"),
            "interpretation":  _interpret_liq(long_liq, short_liq, total_liq),
        }

        # ── 5. Basis Score (peso 5%) ──────────────────────────────────────────
        # Basis = Mark Price - Index Price
        # Contango (basis > 0) → mercado paga prêmio por futures → longs em pressão
        # Backwardation (basis < 0) → futuros com desconto → shorts em pressão
        mark   = funding.get("mark_price", 0)
        index  = funding.get("index_price", 0)
        basis_pct = ((mark - index) / index * 100) if index > 0 else 0.0

        # Basis extremo (> 0.5%) = pressão significativa
        basis_score = -basis_pct * 20  # contango → score negativo (pressão long)
        basis_score = max(-100, min(100, basis_score))

        components["basis"] = {
            "score":      round(basis_score, 2),
            "weight":     WEIGHTS["basis"],
            "mark":       mark,
            "index":      index,
            "basis_pct":  round(basis_pct, 4),
            "interpretation": _interpret_basis(basis_pct),
        }

        # ── Score Composite ───────────────────────────────────────────────────
        composite = (
            f_score     * WEIGHTS["funding"]      +
            ls_score    * WEIGHTS["long_short"]   +
            oi_score    * WEIGHTS["oi_change"]    +
            liq_score   * WEIGHTS["liquidations"] +
            basis_score * WEIGHTS["basis"]
        )

        return composite, components

    def _classify_signal(self, score: float) -> dict:
        """Classifica o sinal de squeeze com base no score."""
        abs_score = abs(score)
        direction = "SHORT_SQUEEZE" if score >= 20 else "LONG_SQUEEZE" if score <= -20 else "NEUTRAL"

        if abs_score >= 60:
            level    = "🔴 SQUEEZE ATIVO"
            emoji    = "🚨"
            action   = "ALTA PROBABILIDADE — Cautela máxima. Squeeze em andamento ou iminente."
        elif abs_score >= 40:
            level    = "🟠 SQUEEZE FORMANDO"
            emoji    = "⚠️"
            action   = "Sinais convergentes. Monitorar de perto. Não abrir posição na direção do squeeze."
        elif abs_score >= 20:
            level    = "🟡 PRESSÃO ELEVADA"
            emoji    = "👀"
            action   = "Atenção aumentada. Dados sugerem desequilíbrio, mas sem confirmação."
        else:
            level    = "🟢 NEUTRO"
            emoji    = "✅"
            action   = "Mercado equilibrado. Sem pressão de squeeze significativa."

        return {
            "level":     level,
            "direction": direction,
            "score":     round(score, 2),
            "emoji":     emoji,
            "action":    action,
        }

    def _market_regime(self, funding, ls, oi, liq, price) -> str:
        """
        Identifica o regime de mercado atual.
        Baseado em: funding trend + OI trend + price momentum.
        """
        rate      = funding.get("rate_float", 0)
        avg_7d    = funding.get("avg_7d", 0)
        oi_1h     = oi.get("oi_change_1h", 0)
        oi_24h    = oi.get("oi_change_24h", 0)
        price_24h = price.get("change_24h", 0)
        ratio     = ls.get("composite_ratio", 1.0)

        # Regime 1: BULL RUN ALAVANCADO
        if rate > 0.05 and oi_24h > 5 and price_24h > 3 and ratio > 1.3:
            return "🚀 BULL RUN ALAVANCADO — Alto risco de long squeeze na reversão"

        # Regime 2: BEAR CAPITULATION
        if rate < -0.02 and oi_24h > 5 and price_24h < -3 and ratio < 0.8:
            return "🐻 BEAR CAPITULATION — Alto risco de short squeeze na recuperação"

        # Regime 3: ACUMULAÇÃO COM SHORTS DOMINANTES
        if rate < -0.01 and ratio < 0.85 and abs(price_24h) < 2:
            return "🔵 ACUMULAÇÃO — Shorts dominam, mercado comprimido, potencial short squeeze"

        # Regime 4: DISTRIBUIÇÃO COM LONGS DOMINANTES
        if rate > 0.02 and ratio > 1.4 and abs(price_24h) < 2:
            return "🟡 DISTRIBUIÇÃO — Longs dominam, mercado esticado, potencial long squeeze"

        # Regime 5: LIQUIDAÇÃO EM CURSO
        if liq.get("total_liq_usd", 0) > 50_000_000:
            dom = liq.get("dominant_side", "")
            return f"💥 LIQUIDAÇÃO MASSIVA — {dom} sendo destruídos"

        # Regime 6: FUNDING REVERTENDO
        if abs(rate) > abs(avg_7d) * 1.5 and abs(rate) > 0.02:
            return "🔄 FUNDING EXTREMO — Divergência vs média 7d, reversão provável"

        # Regime 7: OI DIVERGINDO DO PREÇO
        if oi_1h > 3 and price_24h < -2:
            return "⚡ OI SUBINDO / PREÇO CAINDO — Novos shorts entrando, cuidado"
        if oi_1h > 3 and price_24h > 2:
            return "⚡ OI SUBINDO / PREÇO SUBINDO — Novos longs entrando, momentum positivo"
        if oi_1h < -5:
            return "📉 OI CAINDO — Posições sendo fechadas, volatilidade reduzindo"

        return "⚖️ MERCADO EQUILIBRADO — Sem regime dominante identificado"

    def _generate_alerts(self, score, signal, funding, ls, oi, liq, price) -> list:
        """Gera lista de alertas específicos baseada nos dados."""
        alerts = []
        rate    = funding.get("rate_float", 0)
        ratio   = ls.get("composite_ratio", 1.0)
        oi_1h   = oi.get("oi_change_1h", 0)
        total_liq = liq.get("total_liq_usd", 0)

        # Alertas de funding
        if rate >= FUNDING_EXTREME_HIGH:
            alerts.append(f"🔴 FUNDING EXTREMO POSITIVO ({rate:.4f}%) — Longs pagando muito. Shorts sobrecarregados = risco SHORT SQUEEZE")
        elif rate >= FUNDING_HIGH:
            alerts.append(f"🟠 Funding alto ({rate:.4f}%) — Atenção para pressão de shorts")
        elif rate <= FUNDING_EXTREME_LOW:
            alerts.append(f"🔴 FUNDING EXTREMO NEGATIVO ({rate:.4f}%) — Shorts pagando muito. Longs sobrecarregados = risco LONG SQUEEZE")
        elif rate <= FUNDING_LOW:
            alerts.append(f"🟠 Funding baixo ({rate:.4f}%) — Atenção para pressão de longs")

        # Alertas de L/S ratio
        if ratio >= LS_EXTREME_HIGH:
            alerts.append(f"🔴 L/S RATIO EXTREMO ({ratio:.2f}) — Longs muito dominantes. Combustível para long squeeze acumulado.")
        elif ratio <= LS_EXTREME_LOW:
            alerts.append(f"🔴 L/S RATIO EXTREMO BAIXO ({ratio:.2f}) — Shorts muito dominantes. Combustível para short squeeze acumulado.")

        # Divergência retail vs smart money
        div = ls.get("divergence", 0)
        if abs(div) > 0.3:
            if div > 0:
                alerts.append(f"⚡ Divergência retail vs top traders: retail {div:+.2f}x mais long. Smart money possivelmente vendendo.")
            else:
                alerts.append(f"⚡ Divergência retail vs top traders: top traders {abs(div):.2f}x mais long que retail. Baleia acumulando?")

        # Alertas de OI
        if oi_1h > 5:
            alerts.append(f"📈 OI cresceu +{oi_1h:.1f}% na última hora — Novas posições entrando. Volatilidade aumentando.")
        elif oi_1h < -5:
            alerts.append(f"📉 OI caiu {oi_1h:.1f}% na última hora — Posições sendo fechadas ou liquidadas.")

        # Alertas de liquidações
        if total_liq > 100_000_000:
            dom = liq.get("dominant_side", "")
            alerts.append(f"💥 LIQUIDAÇÃO MASSIVA: ${total_liq/1e6:.1f}M em 24h — {dom} predominantes. Squeeze potencialmente em curso.")
        elif total_liq > 10_000_000:
            alerts.append(f"⚠️ Liquidações relevantes: ${total_liq/1e6:.1f}M em 24h.")

        # Score extremo
        if abs(score) >= 60:
            dir_str = "SHORT SQUEEZE" if score > 0 else "LONG SQUEEZE"
            alerts.append(f"🚨 SCORE CRÍTICO ({score:+.1f}) — {dir_str} com alta probabilidade. Evitar posições na direção do squeeze.")

        if not alerts:
            alerts.append("✅ Nenhum alerta ativo. Mercado sem sinais de squeeze detectados.")

        return alerts

    def _generate_recommendation(self, score, signal, regime, funding, ls, liq) -> dict:
        """
        Gera recomendação estruturada baseada na análise completa.
        NÃO é conselho financeiro — é análise técnica de microestrutura.
        """
        rate  = funding.get("rate_float", 0)
        ratio = ls.get("composite_ratio", 1.0)
        abs_score = abs(score)
        dir_squeeze = signal.get("direction", "NEUTRAL")

        if dir_squeeze == "SHORT_SQUEEZE" and abs_score >= 40:
            return {
                "postura":    "CAUTELOSO / CONTRARIAN",
                "para_longs": "⚠️ Não abrir long agora — preço pode já ter antecipado o squeeze. Aguardar realização.",
                "para_shorts": "🚨 RISCO ELEVADO para shorts — squeeze pode fechar sua posição forcosamente. Reduzir exposição ou usar stop apertado.",
                "funding_play": f"Funding positivo ({rate:.4f}%) → Considerar hedging: long spot + short perpetual para capturar funding sem risco direcional.",
                "warning":    "Squeezes de shorts são explosivos e rápidos. Em minutos, pode mover +5% a +15%.",
            }
        elif dir_squeeze == "LONG_SQUEEZE" and abs_score >= 40:
            return {
                "postura":    "CAUTELOSO / CONTRARIAN",
                "para_longs": "🚨 RISCO ELEVADO para longs — squeeze pode liquidar sua posição. Reduzir alavancagem urgente.",
                "para_shorts": "⚠️ Não abrir short agora — mercado pode já ter antecipado. Aguardar distribuição dos longs.",
                "funding_play": f"Funding negativo ({rate:.4f}%) → Considerar: short spot + long perpetual para capturar funding negativo.",
                "warning":    "Squeezes de longs são lentos mas devastadores. Drawdowns de -15% a -40% sem recuperação imediata.",
            }
        elif abs_score >= 20:
            return {
                "postura":    "MONITORAMENTO ATIVO",
                "para_longs": "Posições existentes: manter stop-loss ativo. Não adicionar alavancagem.",
                "para_shorts": "Posições existentes: manter stop-loss ativo. Não adicionar alavancagem.",
                "funding_play": f"Funding em {rate:.4f}% — monitorar evolução. Ainda não extremo o suficiente para trade de funding.",
                "warning":    "Pressão existe mas sem confirmação. Aguardar convergência de mais indicadores.",
            }
        else:
            return {
                "postura":    "NEUTRO",
                "para_longs": "Mercado equilibrado. Gestão de risco padrão.",
                "para_shorts": "Mercado equilibrado. Gestão de risco padrão.",
                "funding_play": f"Funding em {rate:.4f}% — neutro. Sem oportunidade de arbitragem óbvia.",
                "warning":    "Manter disciplina. Condições podem mudar rapidamente.",
            }


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — INTERPRETAÇÕES (Base de Conhecimento)
# ══════════════════════════════════════════════════════════════════════════════

def _interpret_funding(rate: float) -> str:
    if rate >= FUNDING_EXTREME_HIGH:
        return f"EXTREMO POSITIVO — Shorts sobrecarregados. Cada 8h, shorts pagam {rate:.4f}%. Custo anualizado: {rate*3*365:.1f}%. Risco SHORT SQUEEZE."
    elif rate >= FUNDING_HIGH:
        return f"ALTO — Pressão de carry sobre shorts. Squeeze possível se OI subir."
    elif rate >= 0.01:
        return f"LEVEMENTE POSITIVO — Normal em mercado de alta. Sem preocupação."
    elif rate >= -0.01:
        return f"NEUTRO — Mercado equilibrado entre longs e shorts."
    elif rate >= FUNDING_LOW:
        return f"LEVEMENTE NEGATIVO — Pressão sobre longs. Monitorar."
    elif rate >= FUNDING_EXTREME_LOW:
        return f"BAIXO — Longs pagando. Acumulação de pressão."
    else:
        return f"EXTREMO NEGATIVO — Longs sobrecarregados. Custo anualizado: {abs(rate)*3*365:.1f}%. Risco LONG SQUEEZE."

def _interpret_ls(ratio: float, divergence: float) -> str:
    div_str = ""
    if abs(divergence) > 0.2:
        if divergence > 0:
            div_str = " | Retail mais otimista que top traders — sinal bearish."
        else:
            div_str = " | Top traders mais otimistas que retail — sinal bullish."

    if ratio >= LS_EXTREME_HIGH:
        return f"LONGS EXTREMAMENTE DOMINANTES ({ratio:.2f}x) — Mercado sobrecomprado em posições. Longo acúmulo de longs = combustível para long squeeze.{div_str}"
    elif ratio >= LS_HIGH:
        return f"LONGS DOMINANTES ({ratio:.2f}x) — Desequilíbrio crescente.{div_str}"
    elif ratio <= LS_EXTREME_LOW:
        return f"SHORTS EXTREMAMENTE DOMINANTES ({ratio:.2f}x) — Mercado sobrevendido em posições. Short squeeze pode ser explosivo.{div_str}"
    elif ratio <= LS_LOW:
        return f"SHORTS DOMINANTES ({ratio:.2f}x) — Pressão crescente sobre shorts.{div_str}"
    else:
        return f"EQUILIBRADO ({ratio:.2f}x) — Sem desequilíbrio significativo.{div_str}"

def _interpret_oi(change_1h: float, change_24h: float, funding_rate: float) -> str:
    if change_1h > 5 and funding_rate > FUNDING_HIGH:
        return f"⚡ OI crescendo +{change_1h:.1f}%/h COM funding alto — Mais shorts entrando = mais combustível para SHORT SQUEEZE"
    elif change_1h > 5 and funding_rate < FUNDING_LOW:
        return f"⚡ OI crescendo +{change_1h:.1f}%/h COM funding baixo — Mais longs entrando = mais combustível para LONG SQUEEZE"
    elif change_1h > 3:
        return f"OI subindo +{change_1h:.1f}%/h — Novas posições sendo abertas. Volatilidade esperada."
    elif change_1h < -5:
        return f"OI caindo {change_1h:.1f}%/h — Desalavancagem em curso. Squeeze se esgotando ou posições fechando voluntariamente."
    elif change_24h > 10:
        return f"OI subiu +{change_24h:.1f}% em 24h — Acúmulo significativo de posições no dia."
    elif change_24h < -10:
        return f"OI caiu {change_24h:.1f}% em 24h — Desalavancagem diária significativa."
    else:
        return f"OI estável (1h: {change_1h:+.1f}%, 24h: {change_24h:+.1f}%) — Sem mudança relevante."

def _interpret_liq(long_liq: float, short_liq: float, total: float) -> str:
    if total < 1_000_000:
        return "Liquidações mínimas — Mercado sem estresse."
    longs_pct  = (long_liq / total * 100) if total > 0 else 0
    shorts_pct = (short_liq / total * 100) if total > 0 else 0
    if longs_pct > 70:
        return f"LONGS SENDO DESTRUÍDOS ({longs_pct:.0f}% das liq.) — Long squeeze ativo. ${long_liq/1e6:.1f}M em longs liquidados."
    elif shorts_pct > 70:
        return f"SHORTS SENDO DESTRUÍDOS ({shorts_pct:.0f}% das liq.) — Short squeeze ativo. ${short_liq/1e6:.1f}M em shorts liquidados."
    else:
        return f"Liquidações mistas — Longs: ${long_liq/1e6:.1f}M ({longs_pct:.0f}%) | Shorts: ${short_liq/1e6:.1f}M ({shorts_pct:.0f}%)"

def _interpret_basis(basis_pct: float) -> str:
    if basis_pct > 0.3:
        return f"CONTANGO FORTE (+{basis_pct:.4f}%) — Futuros com prêmio sobre spot. Longs estressados pagando carry."
    elif basis_pct >= 0.05:
        return f"Contango leve (+{basis_pct:.4f}%) — Normal em mercado de alta."
    elif basis_pct < -0.3:
        return f"BACKWARDATION FORTE ({basis_pct:.4f}%) — Futuros com desconto. Shorts estressados, demanda spot alta."
    elif basis_pct < -0.1:
        return f"Backwardation leve ({basis_pct:.4f}%) — Pressão vendedora no spot."
    else:
        return f"Basis neutro ({basis_pct:.4f}%) — Mark e Index alinhados."


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — RELATÓRIO
# ══════════════════════════════════════════════════════════════════════════════

class SqueezeReporter:

    @staticmethod
    def print_analysis(result: dict, save: bool = True):
        """Imprime e opcionalmente salva o relatório completo."""
        sym       = result["symbol"]
        score     = result["score"]
        signal    = result["signal"]
        regime    = result["regime"]
        comps     = result["components"]
        raw       = result["raw"]
        alerts    = result["alerts"]
        rec       = result["recommendation"]
        ts        = result["timestamp"]

        lines = []
        W = 72

        def sep(char="═"): return char * W
        def title(t): return f"║  {t:<{W-4}}║"
        def row(k, v): return f"  {k:<28} {v}"

        lines += [
            sep(),
            f"║{'SQUEEZE MONITOR — ANÁLISE DE MICROESTRUTURA':^{W-2}}║",
            f"║{'OpenClaw Research Desk — PhD-Level Market Analysis':^{W-2}}║",
            sep(),
            title(f"Symbol: {sym}   |   Timestamp: {ts}"),
            sep(),
        ]

        # Score principal
        bar_len = int(abs(score) / 100 * 30)
        if score > 0:
            bar = "▓" * bar_len + "░" * (30 - bar_len)
            bar_str = f"[SHORT SQUEEZE ←] [{bar}] {score:+.1f}"
        elif score < 0:
            bar = "░" * (30 - bar_len) + "▓" * bar_len
            bar_str = f"{score:+.1f} [{bar}] [→ LONG SQUEEZE]"
        else:
            bar_str = f"[═══════════ NEUTRO ═══════════] {score:+.1f}"

        lines += [
            f"  {signal['emoji']}  SQUEEZE SCORE: {score:+.1f} / 100",
            f"  {signal['level']}",
            f"  {bar_str}",
            f"  {signal['action']}",
            "",
            f"  REGIME: {regime}",
            sep("─"),
        ]

        # Preço
        price = raw["price"]
        lines += [
            f"  PREÇO E MOMENTUM",
            row("Preço atual:", f"${price.get('price', 0):,.2f}"),
            row("Variação 1h:", f"{price.get('change_1h', 0):+.2f}%"),
            row("Variação 4h:", f"{price.get('change_4h', 0):+.2f}%"),
            row("Variação 24h:", f"{price.get('change_24h', 0):+.2f}%"),
            row("Volume 24h:", f"${price.get('volume_24h', 0)/1e9:.2f}B"),
            sep("─"),
        ]

        # Componentes do score
        lines.append("  COMPONENTES DO SQUEEZE SCORE")
        lines.append(f"  {'Indicador':<22} {'Score':>7}  {'Peso':>6}  Contribuição")
        lines.append(f"  {'─'*60}")
        total_contrib = 0
        for key, label in [
            ("funding",      "Funding Rate"),
            ("long_short",   "L/S Ratio"),
            ("oi_change",    "OI Change"),
            ("liquidations", "Liquidações 24h"),
            ("basis",        "Basis (Mark-Index)"),
        ]:
            c = comps.get(key, {})
            s = c.get("score", 0)
            w = c.get("weight", 0)
            contrib = s * w
            total_contrib += contrib
            bar = "▓" * int(abs(s) / 10) if abs(s) > 0 else "·"
            lines.append(f"  {label:<22} {s:>+7.1f}  {w*100:>5.0f}%  {contrib:>+7.2f}  {bar}")
        lines.append(f"  {'─'*60}")
        lines.append(f"  {'SCORE COMPOSITE':<22} {score:>+7.1f}  {'100%':>6}  {total_contrib:>+7.2f}")
        lines.append(sep("─"))

        # Funding Rate detalhado
        fr = raw["funding"]
        ls = raw["long_short"]
        oi = raw["oi"]
        lq = raw["liquidations"]

        lines += [
            "  FUNDING RATE",
            row("Taxa atual:", f"{fr.get('rate_float', 0):+.4f}%  ({comps.get('funding', {}).get('interpretation', '')[:50]}...)"),
            row("Média 24h:", f"{fr.get('avg_24h', 0):+.4f}%"),
            row("Média 7d:", f"{fr.get('avg_7d', 0):+.4f}%"),
            row("Mark Price:", f"${fr.get('mark_price', 0):,.2f}"),
            row("Index Price:", f"${fr.get('index_price', 0):,.2f}"),
            row("Basis:", f"{comps.get('basis', {}).get('basis_pct', 0):+.4f}%  {comps.get('basis', {}).get('interpretation', '')[:40]}"),
            sep("─"),
        ]

        # L/S Ratio
        acct = ls.get("account", {})
        top  = ls.get("top_traders", {})
        lines += [
            "  LONG / SHORT RATIO",
            row("Ratio composto:", f"{ls.get('composite_ratio', 0):.3f}x  {comps.get('long_short', {}).get('interpretation', '')[:45]}..."),
            row("Contas — Longs:", f"{acct.get('long_pct', 0):.1f}%"),
            row("Contas — Shorts:", f"{acct.get('short_pct', 0):.1f}%"),
            row("Top traders ratio:", f"{top.get('ratio', 0):.3f}x"),
            row("Divergência retail/smart:", f"{ls.get('divergence', 0):+.3f}x  ({'retail mais long' if ls.get('divergence',0) > 0 else 'smart money mais long'})"),
            sep("─"),
        ]

        # Open Interest
        lines += [
            "  OPEN INTEREST",
            row("OI total:", f"${oi.get('oi_usd_b', 0):.2f}B"),
            row("Variação 1h:", f"{oi.get('oi_change_1h', 0):+.2f}%"),
            row("Variação 24h:", f"{oi.get('oi_change_24h', 0):+.2f}%"),
            row("Interpretação:", comps.get("oi_change", {}).get("interpretation", "")[:55]),
            sep("─"),
        ]

        # Liquidações
        lines += [
            "  LIQUIDAÇÕES 24H",
            row("Total:", f"${lq.get('total_liq_usd', 0)/1e6:.2f}M"),
            row("Longs liquidados:", f"${lq.get('long_liq_usd', 0)/1e6:.2f}M  ({lq.get('long_liq_count', 0)} ordens)"),
            row("Shorts liquidados:", f"${lq.get('short_liq_usd', 0)/1e6:.2f}M  ({lq.get('short_liq_count', 0)} ordens)"),
            row("Lado dominante:", lq.get("dominant_side", "N/A")),
            row("Interpretação:", comps.get("liquidations", {}).get("interpretation", "")[:55]),
            sep("─"),
        ]

        # Alertas
        lines.append("  ⚠️  ALERTAS ATIVOS")
        for alert in alerts:
            lines.append(f"  {alert}")
        lines.append(sep("─"))

        # Recomendação
        lines += [
            "  📋 RECOMENDAÇÃO DE POSTURA",
            f"  Postura geral:  {rec.get('postura', '')}",
            f"  Para longs:     {rec.get('para_longs', '')}",
            f"  Para shorts:    {rec.get('para_shorts', '')}",
            f"  Funding play:   {rec.get('funding_play', '')}",
            f"  ⚠️  {rec.get('warning', '')}",
            sep(),
            "  ⚠️  DISCLAIMER: Análise de microestrutura. NÃO é conselho financeiro.",
            "  Mercados de cripto são extremamente voláteis. Use gestão de risco sempre.",
            sep(),
        ]

        output = "\n".join(lines)
        print(output)

        if save:
            ts_file = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            fname   = OUTPUT_DIR / "reports" / f"squeeze_{sym}_{ts_file}.txt"
            fname.write_text(output)
            # Salva JSON também
            jname = OUTPUT_DIR / "data" / f"squeeze_{sym}_{ts_file}.json"
            jname.write_text(json.dumps(result, indent=2, default=str))
            print(f"\n  Relatório salvo: {fname}")
            print(f"  JSON salvo:      {jname}")

        return output


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — MULTI-SYMBOL DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def print_dashboard(results: list):
    """Dashboard resumido comparando múltiplos símbolos."""
    W = 72
    print("═" * W)
    print(f"{'SQUEEZE MONITOR — DASHBOARD MULTI-SYMBOL':^{W}}")
    print(f"{'Timestamp: ' + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'):^{W}}")
    print("═" * W)
    print(f"  {'Symbol':<10} {'Score':>7}  {'Signal':<22} {'Funding':>9}  {'L/S':>6}  {'OI 1h':>7}")
    print(f"  {'─'*65}")

    sorted_results = sorted(results, key=lambda x: abs(x.get("score", 0)), reverse=True)

    for r in sorted_results:
        sym    = r.get("symbol", "?")
        score  = r.get("score", 0)
        sig    = r.get("signal", {})
        level  = sig.get("level", "").split(" ", 2)[-1] if sig else "N/A"
        fr     = r.get("raw", {}).get("funding", {}).get("rate_float", 0)
        ls_r   = r.get("raw", {}).get("long_short", {}).get("composite_ratio", 1.0)
        oi_1h  = r.get("raw", {}).get("oi", {}).get("oi_change_1h", 0)
        emoji  = sig.get("emoji", " ") if sig else " "

        score_str = f"{score:+.1f}"
        fr_str    = f"{fr:+.4f}%"
        ls_str    = f"{ls_r:.2f}x"
        oi_str    = f"{oi_1h:+.1f}%"

        print(f"  {sym:<10} {score_str:>7}  {emoji} {level:<20} {fr_str:>9}  {ls_str:>6}  {oi_str:>7}")

    print("═" * W)
    print()

    # Top alertas globais
    all_alerts = []
    for r in sorted_results:
        sym = r.get("symbol", "?")
        for a in r.get("alerts", []):
            if "Nenhum" not in a:
                all_alerts.append(f"[{sym}] {a}")

    if all_alerts:
        print("  🚨 ALERTAS CRÍTICOS:")
        for a in all_alerts[:8]:
            print(f"  {a}")
        print()


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — MAIN / CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Squeeze Monitor — Análise de Long/Short Squeeze para perpetuals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python3 squeeze_monitor.py --symbols BTCUSDT ETHUSDT SOLUSDT
  python3 squeeze_monitor.py --symbols BTCUSDT --detail
  python3 squeeze_monitor.py --symbols BTCUSDT ETHUSDT --output file
  python3 squeeze_monitor.py --dashboard --symbols BTCUSDT ETHUSDT SOLUSDT BNBUSDT XRPUSDT
        """
    )
    parser.add_argument("--symbols",   nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
                        help="Símbolos a analisar")
    parser.add_argument("--detail",    action="store_true",
                        help="Exibe relatório completo para cada símbolo")
    parser.add_argument("--dashboard", action="store_true", default=True,
                        help="Exibe dashboard comparativo (padrão)")
    parser.add_argument("--output",    choices=["terminal", "file", "both"],
                        default="both", help="Destino do relatório")
    args = parser.parse_args()

    print("\n" + "═" * 72)
    print(f"{'SQUEEZE MONITOR — OpenClaw Research Desk':^72}")
    print(f"{'Análise de Microestrutura de Mercado — Futuros Perpétuos':^72}")
    print("═" * 72)
    print(f"  Symbols: {', '.join(args.symbols)}")
    print(f"  API Gateway: {'✅ ativo' if GATEWAY_AVAILABLE else '⚠️  indisponível (usando direto)'}")
    print("═" * 72 + "\n")

    analyzer = SqueezeAnalyzer()
    reporter = SqueezeReporter()
    results  = []

    for sym in args.symbols:
        try:
            result = analyzer.analyze(sym)
            results.append(result)
            if args.detail:
                reporter.print_analysis(result, save=(args.output in ["file", "both"]))
        except Exception as e:
            print(f"  ❌ Erro ao analisar {sym}: {e}")

    if results:
        print_dashboard(results)
        if not args.detail and args.output in ["file", "both"]:
            # Salva JSON de todos
            ts_file = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            jname   = OUTPUT_DIR / "data" / f"squeeze_all_{ts_file}.json"
            jname.write_text(json.dumps(results, indent=2, default=str))
            print(f"  JSON salvo: {jname}")

    print("\nDone.")


if __name__ == "__main__":
    main()
