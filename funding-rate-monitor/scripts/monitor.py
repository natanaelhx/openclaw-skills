#!/usr/bin/env python3
"""
monitor.py — Loop contínuo de monitoramento de funding rates.
Usa config.yaml para frequência e pares.
Uso: python monitor.py [--once]
"""
import time
import json
import sys
import argparse
from pathlib import Path

# Adiciona scripts/ ao path para imports locais
sys.path.insert(0, str(Path(__file__).parent))

from fetch_data import fetch_all
from format_output import print_report


def load_config():
    import yaml
    cfg_file = Path(__file__).parent.parent / "config.yaml"
    if cfg_file.exists():
        with open(cfg_file) as f:
            return yaml.safe_load(f)
    return {"update_frequency_minutes": 60}


def check_thresholds(data: list, config: dict) -> list:
    """Retorna alertas para pares que ultrapassaram limites."""
    alerts = []
    thresholds = config.get("thresholds", {})
    default    = config.get("default_thresholds", {})

    for item in data:
        if "error" in item:
            continue
        pair = item.get("pair", "")
        rate = item.get("funding_rate", 0) or 0
        t    = thresholds.get(pair, default)

        r_min = t.get("funding_rate_min", -0.03)
        r_max = t.get("funding_rate_max",  0.08)

        if rate > r_max:
            alerts.append({"pair": pair, "rate": rate, "alert": "ACIMA DO LIMITE", "limit": r_max})
        elif rate < r_min:
            alerts.append({"pair": pair, "rate": rate, "alert": "ABAIXO DO LIMITE", "limit": r_min})

    return alerts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Executa uma vez e sai")
    args = parser.parse_args()

    config   = load_config()
    interval = config.get("update_frequency_minutes", 60) * 60

    while True:
        print(f"\n  Buscando dados...")
        data    = fetch_all()
        alerts  = check_thresholds(data, config)

        print_report(data)

        if alerts:
            print("\n  ⚠️  ALERTAS:")
            for a in alerts:
                pct = f"{a['rate'] * 100:.4f}%"
                lim = f"{a['limit'] * 100:.4f}%"
                print(f"     {a['pair']}: {pct} — {a['alert']} (limite: {lim})")

        if args.once:
            break

        print(f"\n  Próxima atualização em {interval // 60} min...")
        time.sleep(interval)


if __name__ == "__main__":
    main()
