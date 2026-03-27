#!/usr/bin/env python3
"""
add_api.py — Script interativo para adicionar nova API ao OpenClaw API Gateway.
Uso: python3 ~/skills/shared/api_gateway/add_api.py [--dry-run] [--name X] ...
"""
import os
import sys
import argparse
from pathlib import Path

GATEWAY_DIR = Path(__file__).parent
CATEGORIES  = ["cex", "dex", "aggregators", "onchain"]
SUPPORTS_LIST = [
    "price", "ohlcv", "orderbook", "trades",
    "funding_rate", "open_interest", "long_short_ratio",
    "liquidations", "pools", "tvl", "volume", "apr", "apy",
    "token_price", "global_market", "block_number", "balance",
    "contract_call",
]


def prompt(msg: str, default: str = "") -> str:
    val = input(f"  {msg}" + (f" [{default}]" if default else "") + ": ").strip()
    return val or default


def main():
    parser = argparse.ArgumentParser(description="Adicionar nova API ao OpenClaw Gateway")
    parser.add_argument("--dry-run",    action="store_true", help="Não salva arquivos")
    parser.add_argument("--name",       help="Nome da API (ex: hyperliquid)")
    parser.add_argument("--category",   help="Categoria: cex/dex/aggregators/onchain")
    parser.add_argument("--url",        help="URL base da API")
    parser.add_argument("--supports",   help="Dados suportados (separados por vírgula)")
    parser.add_argument("--rate-limit", type=int, default=60, help="Rate limit (req/min)")
    parser.add_argument("--key",        action="store_true", help="Requer API key")
    parser.add_argument("--docs",       help="URL da documentação")
    args = parser.parse_args()

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║        OPENCLAW — ADICIONAR NOVA API             ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    # Coleta informações
    name     = args.name     or prompt("Nome da API (ex: hyperliquid)")
    category = args.category or prompt("Categoria", "cex")
    base_url = args.url      or prompt("URL base (ex: https://api.hyperliquid.xyz)")
    supports = (args.supports.split(",") if args.supports
                else prompt("Dados suportados (ex: price,funding_rate)").split(","))
    supports = [s.strip() for s in supports if s.strip()]
    rate_lim = args.rate_limit or int(prompt("Rate limit (req/min)", "60") or "60")
    need_key = args.key or prompt("Requer API key? (s/n)", "n").lower() == "s"
    docs_url = args.docs or prompt("URL da documentação", "")

    if category not in CATEGORIES:
        print(f"  Categoria inválida. Use: {', '.join(CATEGORIES)}")
        sys.exit(1)

    class_name = _to_class_name(name)
    module_path = GATEWAY_DIR / category / f"{name}.py"
    init_path   = GATEWAY_DIR / category / "__init__.py"

    print()
    print("  Gerando arquivos...")
    print(f"  Módulo:  {module_path}")
    print(f"  Classe:  {class_name}")
    print()

    # Gera o arquivo do cliente
    client_code = _gen_client(name, class_name, category, base_url,
                               supports, rate_lim, need_key, docs_url)

    # Gera entrada do registry
    registry_entry = _gen_registry_entry(name, category, class_name,
                                          base_url, supports, rate_lim,
                                          need_key, docs_url)

    if args.dry_run:
        print("  [DRY-RUN] Conteúdo do cliente:")
        print("  " + "\n  ".join(client_code.split("\n")))
        print()
        print("  [DRY-RUN] Entrada do registry:")
        print("  " + "\n  ".join(registry_entry.split("\n")))
        print()
        print("  Nenhum arquivo foi criado (--dry-run ativo).")
        return

    # Escreve o arquivo
    module_path.write_text(client_code)
    print(f"  ✅ {module_path} criado")

    # Adiciona ao registry
    registry_path = GATEWAY_DIR / "registry.py"
    if registry_path.exists():
        content = registry_path.read_text()
        if f'"{name}"' not in content:
            # Insere antes do último }
            insert_point = content.rfind("}")
            new_content  = content[:insert_point] + f"\n{registry_entry}\n" + content[insert_point:]
            registry_path.write_text(new_content)
            print(f"  ✅ registry.py atualizado")
        else:
            print(f"  ⚠️ '{name}' já existe no registry.py")

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║  API adicionada com sucesso!                     ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  Próximos passos:                               ║")
    print(f"║  1. Implemente os métodos em:                   ║")
    print(f"║     {str(module_path)[-44:]:<44}║")
    print(f"║  2. Adicione ao PRIORITY_MAP em router.py       ║")
    print(f"║  3. Teste: python3 -c \"                         ║")
    print(f"║     from api_gateway.{category}.{name} import {class_name}\"  ║")
    print("╚══════════════════════════════════════════════════╝")
    print()


def _to_class_name(name: str) -> str:
    parts = name.replace("-", "_").split("_")
    return "".join(p.capitalize() for p in parts) + "Client"


def _gen_client(name, class_name, category, base_url,
                supports, rate_lim, need_key, docs_url) -> str:
    base_cls = {
        "cex":         "_base_cex.BaseCEXClient",
        "dex":         "_base_dex.BaseDEXClient",
        "aggregators": "base_client.BaseAPIClient",
        "onchain":     "_base_rpc.BaseRPCClient",
    }.get(category, "base_client.BaseAPIClient")
    parent_import = base_cls.split(".")[0]
    parent_class  = base_cls.split(".")[1]
    supports_str  = '", "'.join(supports)
    return f'''"""
{name}.py — Cliente {name.title()} para o OpenClaw API Gateway.
{f"Docs: {docs_url}" if docs_url else ""}
"""
from ..{parent_import} import {parent_class}


class {class_name}({parent_class}):

    NAME          = "{name}"
    BASE_URL      = "{base_url}"
    CALLS_PER_MIN = {rate_lim}
    CACHE_TTL     = 300
    REQUIRES_KEY  = {need_key}
    FREE_TIER     = True
    SUPPORTS      = ["{supports_str}"]

    def _health_check(self):
        # TODO: implementar health check
        self.session.get(self.BASE_URL, timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        # TODO: implementar fetch para cada data_type suportado
        raise NotImplementedError(
            f"{{self.__class__.__name__}}.fetch({{data_type!r}}) não implementado"
        )
'''


def _gen_registry_entry(name, category, class_name, base_url,
                         supports, rate_lim, need_key, docs_url) -> str:
    supports_str = '", "'.join(supports)
    key_req = "True" if need_key else "False"
    return f'''    "{name}": {{
        "module":       "api_gateway.{category}.{name}",
        "class":        "{class_name}",
        "display_name": "{name.title()}",
        "category":     "{category}",
        "free":         True,
        "key_required": {key_req},
        "rate_limit":   {rate_lim},
        "base_url":     {{
            "default": "{base_url}",
        }},
        "supports": ["{supports_str}"],
        "docs": "{docs_url}",
    }},'''


if __name__ == "__main__":
    main()
