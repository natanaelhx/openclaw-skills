#!/usr/bin/env python3
"""
fetch_data.py — Busca funding rates via API Gateway do OpenClaw.
Usa APIRouter com fallback automático entre exchanges.
"""
import os
import sys
import json

# Adiciona shared/ ao path para usar o api_gateway
_shared = os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
if os.path.isdir(_shared):
    sys.path.insert(0, _shared)

try:
    from api_gateway.router import APIRouter
    _ROUTER = APIRouter()
    _HAS_GATEWAY = True
except ImportError:
    _ROUTER = None
    _HAS_GATEWAY = False


def fetch_rate(platform: str, pair: str) -> dict:
    """
    Busca funding rate para um par.
    Usa API Gateway quando disponível; fallback para endpoint direto.
    """
    if _HAS_GATEWAY:
        try:
            data = _ROUTER.fetch("funding_rate", symbol=pair)
            return {
                "platform":    data.get("_source", platform),
                "pair":        pair,
                "funding_rate": data.get("rate"),
                "rate_pct":    data.get("rate_pct"),
                "mark_price":  data.get("mark_price"),
                "timestamp":   data.get("next_funding_ts"),
                "next_funding": data.get("next_funding_dt"),
            }
        except Exception as e:
            return {"platform": platform, "pair": pair, "error": str(e)}

    # Fallback direto para Binance
    import requests
    endpoint = os.environ.get("FUNDING_ENDPOINT",
                              "https://fapi.binance.com/fapi/v1/premiumIndex")
    try:
        resp = requests.get(endpoint, params={"symbol": pair}, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
        rate = float(raw.get("lastFundingRate", 0))
        return {
            "platform":    "binance",
            "pair":        pair,
            "funding_rate": rate,
            "rate_pct":    f"{rate * 100:.4f}%",
            "mark_price":  float(raw.get("markPrice", 0)),
            "timestamp":   raw.get("nextFundingTime"),
        }
    except Exception as e:
        return {"platform": platform, "pair": pair, "error": str(e)}


def fetch_all(config_path: str = None) -> list:
    """Busca funding rates para todos os pares configurados."""
    import yaml
    from pathlib import Path

    cfg_file = config_path or Path(__file__).parent.parent / "config.yaml"
    try:
        with open(cfg_file) as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        config = {
            "platform_pairs": {
                "binance": ["BTCUSDT", "ETHUSDT"],
                "bybit":   ["BTCUSDT", "ETHUSDT"],
            }
        }

    results = []
    seen_pairs = set()
    for platform, pairs in config.get("platform_pairs", {}).items():
        for pair in pairs:
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            result = fetch_rate(platform, pair)
            results.append(result)

    return results


if __name__ == "__main__":
    results = fetch_all()
    print(json.dumps(results, indent=2))
