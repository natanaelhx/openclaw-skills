#!/usr/bin/env python3
"""
format_output.py — Formata saída de funding rates para terminal ou arquivo.
Uso: python fetch_data.py | python format_output.py
     python format_output.py --file dados.json
"""
import json
import sys
import argparse
from datetime import datetime, timezone


def format_rate(item: dict) -> str:
    if "error" in item:
        return f"  ❌ {item.get('platform','?'):12} {item['pair']:<15} ERRO: {item['error']}"

    rate     = item.get("funding_rate", 0) or 0
    rate_pct = item.get("rate_pct") or f"{rate * 100:.4f}%"
    mark     = item.get("mark_price", 0) or 0
    nxt      = item.get("next_funding", "") or ""

    # Ícone baseado no valor
    if rate > 0.0008:
        icon = "🔴"  # alto positivo
    elif rate < -0.0003:
        icon = "🟢"  # negativo
    elif rate > 0.0003:
        icon = "🟡"  # moderado
    else:
        icon = "⚪"  # neutro

    mark_str = f"  mark=${mark:,.2f}" if mark else ""
    return (f"  {icon} {item.get('platform','?'):12} "
            f"{item['pair']:<16} {rate_pct:>10}{mark_str}"
            + (f"  next: {nxt}" if nxt else ""))


def print_report(data: list, output_file: str = None):
    now   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    width = 70
    lines = [
        f"╔{'═' * width}╗",
        f"║{'FUNDING RATES — ' + now:^{width}}║",
        f"╠{'═' * width}╣",
    ]
    for item in sorted(data, key=lambda x: abs(x.get("funding_rate") or 0), reverse=True):
        line = format_rate(item)
        lines.append(f"║{line:<{width}}║")
    lines.append(f"╚{'═' * width}╝")
    report = "\n".join(lines)

    print(report)
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(f"\n  Relatório salvo em: {output_file}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file",   help="Arquivo JSON de entrada (default: stdin)")
    parser.add_argument("--output", help="Salvar relatório neste arquivo")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            data = json.load(f)
    else:
        data = json.loads(sys.stdin.read())

    print_report(data, output_file=args.output)


if __name__ == "__main__":
    main()
