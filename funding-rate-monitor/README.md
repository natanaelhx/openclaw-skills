# Funding Rate Monitor

Monitora taxas de funding de futuros perpétuos em múltiplas exchanges (Binance, Bybit, OKX, Gate, MEXC, Bitget, HTX) com fallback automático via API Gateway.

## Dependências

```bash
pip install requests pandas numpy tabulate pyyaml
```

## Uso rápido

```bash
# Monitor completo (live + backtest + testes)
py funding_monitor.py --mode full

# Só live
py funding_monitor.py --mode live --symbols BTCUSDT ETHUSDT SOLUSDT

# Monitor contínuo (lê config.yaml)
py scripts/monitor.py

# Executa uma vez
py scripts/monitor.py --once

# Pipeline: fetch → formatar
py scripts/fetch_data.py | py scripts/format_output.py

# Salvar relatório
py scripts/fetch_data.py | py scripts/format_output.py --output relatorio.txt

# Testes
py -m pytest tests/ -v
```

## Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `config.yaml` | Pares, frequência, thresholds de alerta |
| `scripts/funding_monitor.py` | Script principal (backtest, live, testes) |
| `scripts/fetch_data.py` | Coleta via API Gateway com fallback |
| `scripts/format_output.py` | Formata saída com ícones de alerta |
| `scripts/monitor.py` | Loop contínuo com alertas de threshold |
| `scripts/run_skill.sh` | Bash wrapper |
| `tests/test_basic.py` | Suite de testes |
| `references/exchange_apis.md` | Documentação das APIs |
| `references/strategy_guide.md` | Estratégia de Extreme Reversal |

## Variáveis de ambiente (opcional)

```bash
export FUNDING_ENDPOINT="https://fapi.binance.com/fapi/v1/premiumIndex"
export FUNDING_API_KEY="sua-key-opcional"
```

## Thresholds padrão

| Condição | Valor | Sinal |
|----------|-------|-------|
| Funding > +0.08% | Extremo positivo | SHORT |
| Funding < -0.03% | Extremo negativo | LONG |
| Entre -0.03% e +0.08% | Neutro | FLAT |
