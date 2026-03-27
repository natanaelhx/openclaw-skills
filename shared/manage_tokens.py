#!/usr/bin/env python3
"""
manage_tokens.py — Gerencia tokens, alertas e API keys do OpenClaw.

Uso:
  python3 manage_tokens.py add BTC ETH SOL
  python3 manage_tokens.py remove BTC
  python3 manage_tokens.py list
  python3 manage_tokens.py key set coinmarketcap CMC-xxx-yyy
  python3 manage_tokens.py key list
  python3 manage_tokens.py key remove coinmarketcap
  python3 manage_tokens.py key info coinmarketcap
"""
import os
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))

from user_config import UserConfig

FREE_KEY_URLS = {
    "coinmarketcap": "https://pro.coinmarketcap.com/signup",
    "dextools":      "https://developer.dextools.io/",
    "coinglass":     "https://coinglass.com/account/signup",
    "defillama_pro": "https://defillama.com/pro-api",
    "coingecko_pro": "https://www.coingecko.com/en/api",
}


def cmd_key(args: list, cfg: UserConfig):
    if not args:
        print("Uso: key set|list|remove|info <api_name> [key_value]")
        return

    sub = args[0]

    if sub == "set":
        if len(args) < 3:
            print("Uso: key set <api_name> <key_value>")
            return
        api_name = args[1]
        key_val  = args[2]
        result   = cfg.set_api_key(api_name, key_val)
        icon = "✅" if result["success"] else "❌"
        print(f"  {icon} {result['message']}")

    elif sub == "list":
        keys = cfg.list_api_keys()
        print("\n  API Keys configuradas:")
        print("  " + "─" * 40)
        for api, val in sorted(keys.items()):
            status = val if val else "não configurada"
            icon   = "🔑" if val else "  "
            print(f"  {icon} {api:<20} {status}")
        print()

    elif sub == "remove":
        if len(args) < 2:
            print("Uso: key remove <api_name>")
            return
        result = cfg.remove_api_key(args[1])
        icon   = "✅" if result["success"] else "❌"
        print(f"  {icon} {result['message']}")

    elif sub == "info":
        if len(args) < 2:
            print("Uso: key info <api_name>")
            return
        api_name = args[1]
        url = FREE_KEY_URLS.get(api_name)
        if url:
            print(f"\n  Como obter API key gratuita para {api_name}:")
            print(f"  1. Acesse: {url}")
            print(f"  2. Crie uma conta gratuita")
            print(f"  3. Gere sua API key no dashboard")
            print(f"  4. Configure com: key set {api_name} <sua-key>")
        else:
            print(f"  {api_name} não precisa de API key ou usa endpoints públicos gratuitos.")
        print()

    else:
        print(f"Subcomando desconhecido: {sub}. Use: set, list, remove, info")


def cmd_add(tokens: list, cfg: UserConfig):
    for token in tokens:
        result = cfg.add_token(token)
        icon   = "✅" if result["success"] else "⚠️"
        print(f"  {icon} {result['message']}")


def cmd_remove(tokens: list, cfg: UserConfig):
    for token in tokens:
        result = cfg.remove_token(token)
        icon   = "✅" if result["success"] else "⚠️"
        print(f"  {icon} {result['message']}")


def cmd_list(cfg: UserConfig):
    tokens  = cfg.get_tokens()
    chains  = cfg.get_chains()
    alerts  = cfg.get_alerts()
    print("\n  Tokens monitorados:", ", ".join(tokens))
    print("  Chains monitoradas:", ", ".join(chains))
    print("\n  Alertas:")
    for k, v in alerts.items():
        print(f"    {k}: {v}")
    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cfg  = UserConfig()
    cmd  = sys.argv[1].lower()
    rest = sys.argv[2:]

    if cmd == "add":
        cmd_add(rest, cfg)
    elif cmd == "remove":
        cmd_remove(rest, cfg)
    elif cmd == "list":
        cmd_list(cfg)
    elif cmd == "key":
        cmd_key(rest, cfg)
    else:
        print(f"Comando desconhecido: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
