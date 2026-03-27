---
name: liquidity-pool-monitor
description: >
  Monitora pools de liquidez DeFi em múltiplas chains (Ethereum, Arbitrum, Base,
  Optimism, Polygon). Busca dados de DefiLlama, Uniswap V3, Aerodrome e CoinGecko.
  Analisa APR, TVL, risco e sentimento de mercado para recomendar as melhores pools.
  Use quando o usuário perguntar sobre: pools de liquidez, LP, yield farming,
  APR de pools, pools seguras, impermanent loss, Uniswap, Aerodrome, Curve,
  melhores pools DeFi, onde fornecer liquidez, farming de taxa.
compatibility:
  python: ">=3.8"
  pip: [requests, pandas, numpy, tabulate]
  network: required
---

# Liquidity Pool Monitor

## Quando usar
- Usuário pergunta sobre pools de liquidez DeFi
- Usuário quer saber quais pools têm melhor APR agora
- Usuário quer pools seguras para fornecer liquidez
- Usuário menciona Uniswap, Aerodrome, Curve, Balancer
- Usuário pergunta sobre yield farming ou LP tokens

## Como executar

```bash
py ~/skills/liquidity-pool-monitor/scripts/pool_monitor.py
py ~/skills/liquidity-pool-monitor/scripts/pool_monitor.py --output file
py ~/skills/liquidity-pool-monitor/scripts/pool_monitor.py --no-cache
```

## Argumentos

| Argumento    | Valores             | Descrição                               |
|--------------|---------------------|-----------------------------------------|
| `--mode`     | live, full          | Modo de execução (default: live)        |
| `--output`   | terminal, file, both| Destino do relatório (default: both)    |
| `--no-cache` | (flag)              | Força rebusca ignorando cache           |
| `--exchange` | binance, bybit      | (compatibilidade, não utilizado)        |
| `--symbols`  | lista               | (compatibilidade, não utilizado)        |

## Fontes de dados
- DefiLlama Yields API (yields.llama.fi/pools)
- Uniswap V3 GraphQL (The Graph)
- Aerodrome Finance REST API
- CoinGecko API (preços e sentimento)

## Saídas geradas

| Arquivo                                    | Conteúdo                       |
|--------------------------------------------|--------------------------------|
| `~/liquidity_monitor/reports/pool_report_*.txt` | Relatório completo formatado   |
| `~/liquidity_monitor/data/pools_*.csv`     | Todos os pools carregados      |
| `~/liquidity_monitor/data/top_pools_*.csv` | Top 5 pools no range ideal     |
| `~/liquidity_monitor/cache/pools_cache.json`| Cache de pools (TTL: 30 min)  |

## Seções do relatório

1. **Sentimento de Mercado** — BTC dominance, market cap, mudança 24h
2. **Pools no Range Ideal** — Top 5 pools entre 3% e 80% APR com score composto
3. **Pools Mais Seguras** — 2 pools recomendadas baseadas no sentimento atual
4. **Melhores Performers 24h** — Pools com melhor yield baseado em volume

## Critérios de segurança

- **Tokens seguros**: USDC, USDT, DAI, WBTC, WETH, ETH, cbBTC, cbETH, stETH, rETH, LUSD
- **Protocolos confiáveis**: Uniswap V3, Curve, Balancer, Aerodrome, Velodrome
- **TVL mínimo**: $500,000
- **APR mínimo**: 3%

## Scores de risco

| Score | Critério                                               |
|-------|--------------------------------------------------------|
| BAIXO | Ambos tokens seguros + TVL > $2M + APR < 200%         |
| MEDIO | Um token seguro ou TVL moderado                        |
| ALTO  | APR > 200% ou TVL < $500K                             |
