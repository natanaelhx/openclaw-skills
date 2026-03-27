# Liquidity Pool Monitor

Monitora pools de liquidez DeFi em múltiplas chains (Ethereum, Arbitrum, Base, Optimism, Polygon) com APR, TVL, risco e sentimento de mercado.

## Dependências

```bash
pip install requests pandas numpy tabulate pyyaml
```

## Uso rápido

```bash
# Execução padrão
py scripts/pool_monitor.py

# Salvar em arquivo
py scripts/pool_monitor.py --output file

# Forçar rebusca (ignora cache)
py scripts/pool_monitor.py --no-cache

# Testes
py -m pytest tests/ -v
```

## Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `config.yaml` | Chains, filtros, tokens seguros, protocolos confiáveis |
| `scripts/pool_monitor.py` | Script principal |
| `tests/test_basic.py` | Suite de testes |
| `references/defi_apis.md` | Documentação das APIs DeFi |
| `references/pool_strategy_guide.md` | Guia de estratégia de pools |

## Filtros padrão (config.yaml)

| Parâmetro | Valor |
|-----------|-------|
| TVL mínimo | $500.000 |
| APR mínimo | 3% |
| APR máximo | 80% |
| Chains | ETH, ARB, Base, OP, Polygon |

## Score de risco

| Score | Critério |
|-------|----------|
| **BAIXO** | Ambos tokens seguros + TVL > $2M + protocolo confiável |
| **MÉDIO** | Um token seguro ou TVL moderado |
| **ALTO** | APR > 200% ou TVL < $500K ou protocolo desconhecido |
