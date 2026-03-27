# OpenClaw — Skills Reference

> Documentação completa de todas as skills, módulos compartilhados, APIs e comandos.
> Atualizado em: 2026-03-26

---

## Índice

1. [Visão Geral da Arquitetura](#visão-geral-da-arquitetura)
2. [Skill: Funding Rate Monitor](#skill-funding-rate-monitor)
3. [Skill: Liquidity Pool Monitor](#skill-liquidity-pool-monitor)
4. [Módulo Compartilhado: API Gateway](#módulo-compartilhado-api-gateway)
5. [APIs Registradas](#apis-registradas)
6. [Configuração e API Keys](#configuração-e-api-keys)
7. [Comandos de Referência Rápida](#comandos-de-referência-rápida)
8. [Estratégias de Trading](#estratégias-de-trading)

---

## Visão Geral da Arquitetura

```
~/skills/
├── shared/                          ← Módulo compartilhado entre todas as skills
│   ├── user_config.py               ← Config central (tokens, chains, API keys)
│   ├── manage_tokens.py             ← CLI de gerenciamento
│   └── api_gateway/                 ← Gateway com 35 APIs mapeadas
│       ├── registry.py              ← Registro central de todas as APIs
│       ├── base_client.py           ← Cliente base (retry, cache, rate limit)
│       ├── router.py                ← Roteador com fallback automático
│       ├── normalizer.py            ← Normaliza dados de fontes diferentes
│       ├── health_checker.py        ← Verifica quais APIs estão online
│       ├── add_api.py               ← Adiciona nova API interativamente
│       ├── cex/                     ← 9 corretoras centralizadas
│       ├── dex/                     ← 11 corretoras descentralizadas
│       ├── aggregators/             ← 7 agregadores de dados
│       └── onchain/                 ← 8 RPCs on-chain
│
├── funding-rate-monitor/            ← Skill 1
│   ├── SKILL.md
│   ├── scripts/
│   │   ├── funding_monitor.py
│   │   └── run_skill.sh
│   └── references/
│       ├── strategy_guide.md
│       └── exchange_apis.md
│
├── liquidity-pool-monitor/          ← Skill 2
│   ├── SKILL.md
│   ├── scripts/
│   │   └── pool_monitor.py
│   └── references/
│       ├── pool_strategy_guide.md
│       └── defi_apis.md
│
├── funding-rate-monitor.skill       ← Pacote comprimido (inclui shared/)
└── liquidity-pool-monitor.skill     ← Pacote comprimido (inclui shared/)
```

**Princípio central:** Toda skill usa o `APIRouter` para buscar dados. O router decide automaticamente qual API usar, com fallback automático se a principal falhar. Nenhuma skill precisa saber qual API está sendo usada.

---

## Skill: Funding Rate Monitor

### O que faz

Monitora taxas de funding de futuros perpétuos, executa backtests da estratégia "Extreme Reversal" e valida qualidade dos dados via testes automatizados.

### Quando usar

- Usuário pergunta sobre funding rate, taxa de funding, funding fee
- Longs/shorts estão pagando demais
- Mercado sobrecomprado em futuros
- Monitorar/alertar funding para ativos específicos

### Instalação de dependências

```bash
py -m pip install requests pandas numpy tabulate
```

### Execução

```bash
# Modo completo (live + backtest + testes)
bash ~/skills/funding-rate-monitor/scripts/run_skill.sh

# Direto
py ~/skills/funding-rate-monitor/scripts/funding_monitor.py --mode full

# Só live
py ~/skills/funding-rate-monitor/scripts/funding_monitor.py --mode live --symbols BTCUSDT ETHUSDT SOLUSDT

# Só backtest
py ~/skills/funding-rate-monitor/scripts/funding_monitor.py --mode backtest --symbols BTCUSDT --output both

# Testes automatizados
py ~/skills/funding-rate-monitor/scripts/funding_monitor.py --mode test

# Via Bybit
py ~/skills/funding-rate-monitor/scripts/funding_monitor.py --mode live --exchange bybit --symbols BTCUSDT
```

### Argumentos

| Argumento   | Valores                    | Padrão   | Descrição                        |
|-------------|----------------------------|----------|----------------------------------|
| `--mode`    | live, backtest, full, test | full     | Modo de execução                 |
| `--symbols` | SYMBOL [SYMBOL ...]        | BTC ETH  | Symbols a monitorar              |
| `--exchange`| binance, bybit             | binance  | Exchange principal               |
| `--limit`   | INT                        | 500      | Registros históricos a buscar    |
| `--output`  | terminal, file, both       | both     | Destino do relatório             |

### Arquivos gerados

| Arquivo | Descrição |
|---------|-----------|
| `~/funding_backtest/data/{symbol}_funding_history.csv` | Histórico de funding rates |
| `~/funding_backtest/data/equity_curve_{symbol}.csv` | Curva de equity do backtest |
| `~/funding_backtest/reports/backtest_{symbol}.txt` | Relatório completo |
| `~/.moltbot/cache/*.json` | Cache de dados (30min TTL) |

### Fontes de dados

| Fonte | Endpoints |
|-------|-----------|
| **Binance Futures** `https://fapi.binance.com/fapi/v1` | `/premiumIndex`, `/fundingRate`, `/klines` |
| **Bybit** `https://api.bybit.com/v5/market` | `/tickers`, `/funding/history` |

**Via API Gateway (automático):** Binance → Bybit → OKX → Bitget → Gate → MEXC → HTX

### Campos da resposta Binance `/premiumIndex`

```json
{
  "symbol": "BTCUSDT",
  "lastFundingRate": "0.00010000",   ← × 100 para %
  "nextFundingTime": 1711497600000,  ← Unix ms
  "markPrice": "65432.10000000",
  "indexPrice": "65430.55000000"
}
```

### Arquitetura interna

```
funding_monitor.py
├── SECTION 1: CONFIG     — constantes, imports, setup de diretórios
├── SECTION 2: FETCH      — chamadas de API, coleta de dados, salva CSV
├── SECTION 3: BACKTEST   — engine da estratégia, métricas
├── SECTION 4: TESTS      — suite de validação automatizada
├── SECTION 5: REPORT     — formatação e saída em arquivo
└── SECTION 6: MAIN       — CLI entrypoint, orquestração
```

### Integração com API Gateway

```python
# O funding_monitor.py detecta o gateway automaticamente
# Se ~/skills/shared/ existe, usa APIRouter com fallback
# Fallback transparente para chamada direta se o gateway falhar
```

---

## Skill: Liquidity Pool Monitor

### O que faz

Monitora pools de liquidez DeFi em múltiplas chains (Ethereum, Arbitrum, Base, Optimism, Polygon). Analisa APR, TVL, risco e sentimento de mercado para recomendar as melhores pools.

### Quando usar

- Usuário pergunta sobre pools de liquidez, LP, yield farming
- Melhores pools com APR agora
- Pools seguras para fornecer liquidez
- Menciona Uniswap, Aerodrome, Curve, Balancer, Velodrome
- Pergunta sobre impermanent loss ou farming de taxa

### Instalação de dependências

```bash
py -m pip install requests pandas numpy tabulate
```

### Execução

```bash
# Modo padrão
py ~/skills/liquidity-pool-monitor/scripts/pool_monitor.py

# Salvar em arquivo
py ~/skills/liquidity-pool-monitor/scripts/pool_monitor.py --output file

# Forçar rebusca (ignora cache)
py ~/skills/liquidity-pool-monitor/scripts/pool_monitor.py --no-cache
```

### Argumentos

| Argumento    | Valores             | Padrão   | Descrição                         |
|--------------|---------------------|----------|-----------------------------------|
| `--mode`     | live, full          | live     | Modo de execução                  |
| `--output`   | terminal, file, both| both     | Destino do relatório              |
| `--no-cache` | (flag)              | off      | Força rebusca ignorando cache     |

### Arquivos gerados

| Arquivo | Descrição |
|---------|-----------|
| `~/liquidity_monitor/reports/pool_report_*.txt` | Relatório completo formatado |
| `~/liquidity_monitor/data/pools_*.csv` | Todos os pools carregados |
| `~/liquidity_monitor/data/top_pools_*.csv` | Top 5 pools no range ideal |
| `~/liquidity_monitor/cache/pools_cache.json` | Cache (TTL: 30 min) |

### Fontes de dados

| Fonte | URL | Dados |
|-------|-----|-------|
| **DefiLlama** | `https://yields.llama.fi/pools` | TVL, APY, volume, IL, todas as chains |
| **Uniswap V3** | The Graph subgraph | Pools ETH + ARB, fee APR calculado |
| **Aerodrome** | `https://api.aerodrome.finance/api/v1/pools` | Pools Base chain |
| **CoinGecko** | `/simple/price` + `/global` | Preços, dominância BTC, sentimento |

**Via API Gateway (automático):** DefiLlama → Uniswap V3 → Curve → Balancer → Aerodrome → Velodrome → SushiSwap → PancakeSwap

### Critérios de filtragem padrão

| Parâmetro | Valor padrão |
|-----------|-------------|
| TVL mínimo | $500.000 |
| APR mínimo | 3% |
| APR máximo | 80% |
| Chains | Ethereum, Arbitrum, Base, Optimism, Polygon |

### Tokens considerados seguros

```
USDC, USDT, DAI, WBTC, WETH, ETH, cbBTC, cbETH, stETH, rETH, LUSD, USDC.e, USDT.e
```

### Protocolos confiáveis

```
uniswap-v3, curve, balancer, aerodrome, velodrome
```

### Scores de risco

| Score | Critério |
|-------|----------|
| **BAIXO** | Ambos tokens seguros + TVL > $2M + APR < 200% |
| **MÉDIO** | Um token seguro ou TVL moderado |
| **ALTO** | APR > 200% ou TVL < $500K |

### Score composto de pool

```
score = APR/80    × 0.4   (qualidade do APR — 40%)
      + TVL/$10M  × 0.3   (profundidade — 30%)
      + Vol/TVL   × 0.2   (atividade — 20%)
      + Safety    × 0.1   (segurança dos tokens — 10%)
```

### Seções do relatório

1. **Sentimento de Mercado** — BTC dominance, market cap, variação 24h
2. **Pools no Range Ideal** — Top 5 pools entre 3% e 80% APR
3. **Pools Mais Seguras** — 2 pools recomendadas baseadas no sentimento
4. **Melhores Performers 24h** — Maior yield com base em volume recente

### Lógica de sentimento de mercado

| Condição | Sentimento |
|----------|-----------|
| BTC dominance < 50% E market cap subiu | RISK_ON |
| BTC dominance > 55% OU market cap caiu > 3% | RISK_OFF |
| Demais casos | NEUTRAL |

**RISK_ON** → recomendar pools voláteis (ETH/USDC, WBTC/ETH)
**RISK_OFF** → recomendar só stablecoins (USDC/USDT, DAI/USDC)

---

## Módulo Compartilhado: API Gateway

### Localização

```
~/skills/shared/api_gateway/
```

### Arquitetura

```
api_gateway/
├── __init__.py          ← Exports: APIRegistry, BaseAPIClient, APIRouter, DataNormalizer, HealthChecker
├── registry.py          ← Registro de 35 APIs com metadados completos
├── base_client.py       ← BaseAPIClient com retry, cache, rate limit
├── router.py            ← APIRouter com fallback automático
├── normalizer.py        ← DataNormalizer (formato padrão único)
├── health_checker.py    ← HealthChecker (paralelo, com latência)
├── add_api.py           ← Script para adicionar nova API
├── _base_cex.py         ← Base para clientes CEX
├── _base_dex.py         ← Base para clientes DEX
├── _base_rpc.py         ← Base para clientes RPC
├── cex/                 ← Binance, Bybit, OKX, Coinbase, Kraken, Gate, MEXC, Bitget, HTX
├── dex/                 ← UniV3, UniV2, Aerodrome, Velodrome, Curve, Balancer, PancakeSwap, SushiSwap, Raydium, Orca, Jupiter
├── aggregators/         ← DefiLlama, CoinGecko, CMC, DexScreener, CoinGlass, TheGraph, DexTools
└── onchain/             ← Ethereum, Arbitrum, Base, Optimism, Polygon, Solana, BSC, Avalanche
```

### BaseAPIClient — recursos automáticos

| Recurso | Detalhe |
|---------|---------|
| **Cache em disco** | `~/.moltbot/cache/` · TTL configurável (padrão 30min) |
| **Rate limiting** | Token bucket por API · respeita limites gratuitos |
| **Retry automático** | 3 tentativas · backoff exponencial (2s, 4s, 8s) |
| **Fallback 429** | Aguarda e retenta ao receber rate limit |
| **Sessão HTTP** | `User-Agent: OpenClaw/1.0` · keep-alive |

### APIRouter — prioridade de fallback

| Tipo de dado | Ordem de prioridade |
|-------------|---------------------|
| `funding_rate` | Binance → Bybit → OKX → Bitget → Gate → MEXC → HTX |
| `open_interest` | CoinGlass → Binance → Bybit → OKX → Bitget |
| `long_short_ratio` | CoinGlass → Binance → Bybit → Bitget |
| `liquidations` | CoinGlass → Binance → Bybit → OKX |
| `price` | Binance → CoinGecko → CoinMarketCap → DexScreener |
| `ohlcv` | Binance → Bybit → OKX → Kraken → Coinbase |
| `pools_evm` | DefiLlama → Uniswap V3 → Curve → Balancer → Aerodrome → Velodrome → SushiSwap → PancakeSwap |
| `pools_solana` | DefiLlama → Raydium → Orca |
| `tvl` | DefiLlama |
| `global_market` | CoinGecko → CoinMarketCap → CoinGlass |
| `token_pairs_dex` | DexScreener → DexTools → The Graph |

### DataNormalizer — formato padrão

#### Funding Rate
```python
{
    "symbol":          "BTCUSDT",
    "rate":            0.0008,       # float
    "rate_pct":        "0.0800%",    # string formatada
    "next_funding_ts": 1700000000,   # unix timestamp
    "next_funding_dt": "2024-01-01 08:00 UTC",
    "mark_price":      45000.0,
    "index_price":     44998.0,
    "source":          "binance",
    "fetched_at":      "2024-01-01T00:00:00Z",
}
```

#### Pool de Liquidez
```python
{
    "pool_id":    "0xabc...",
    "protocol":   "uniswap-v3",
    "chain":      "Ethereum",
    "token0":     "USDC",
    "token1":     "ETH",
    "symbol":     "USDC/ETH",
    "fee_tier":   0.05,         # % (ex: 0.05%)
    "tvl_usd":    4200000.0,
    "volume_24h": 890000.0,
    "apr_base":   12.3,         # % anual de fees
    "apr_reward": 2.1,          # % anual de incentivos
    "apr_total":  14.4,
    "il_7d":      -0.3,
    "yield_24h":  0.039,        # yield real 24h (%)
    "risk_score": "BAIXO",
    "source":     "defillama",
    "fetched_at": "...",
}
```

#### Preço
```python
{
    "symbol":     "BTC",
    "price_usd":  45000.0,
    "change_1h":  0.3,
    "change_24h": -1.2,
    "change_7d":  5.6,
    "volume_24h": 28000000000.0,
    "market_cap": 870000000000.0,
    "source":     "coingecko",
    "fetched_at": "...",
}
```

### Usar o router em qualquer código

```python
import sys
sys.path.insert(0, '/path/to/skills/shared')
from api_gateway.router import APIRouter

router = APIRouter()

# Funding rate com fallback automático
data = router.fetch('funding_rate', symbol='BTCUSDT')
print(f"Taxa: {data['rate_pct']} via {data['_source']}")

# Pools EVM
result = router.fetch('pools_evm', chains=['Ethereum', 'Arbitrum'], min_tvl=1_000_000)
for pool in result['pools'][:5]:
    print(f"{pool['symbol']:20} APR: {pool['apr_total']:.1f}%  TVL: ${pool['tvl_usd']:,.0f}")

# Comparar todas as fontes
all_rates = router.fetch_all_sources('funding_rate', symbol='BTCUSDT')
for r in all_rates:
    print(f"{r['_source']:12} → {r['rate_pct']}")
```

---

## APIs Registradas

### CEX — Corretoras Centralizadas (9)

| API | Rate Limit | Key? | Dados suportados |
|-----|-----------|------|-----------------|
| **Binance** | 1200/min | Opcional | price, ohlcv, orderbook, funding_rate, open_interest, long_short_ratio, liquidations, mark_price |
| **Bybit** | 120/min | Não | price, ohlcv, funding_rate, open_interest, long_short_ratio, liquidations |
| **OKX** | 60/min | Não | price, ohlcv, funding_rate, open_interest, liquidations, mark_price |
| **Coinbase** | 30/min | Não | price, ohlcv, orderbook, trades |
| **Kraken** | 60/min | Não | price, ohlcv, orderbook, funding_rate, open_interest |
| **Gate.io** | 900/min | Não | price, ohlcv, funding_rate, open_interest, long_short_ratio |
| **MEXC** | 240/min | Não | price, ohlcv, funding_rate, open_interest |
| **Bitget** | 120/min | Não | price, ohlcv, funding_rate, open_interest, long_short_ratio |
| **HTX (Huobi)** | 100/min | Não | price, ohlcv, funding_rate, open_interest |

### DEX — Corretoras Descentralizadas (11)

| API | Chain(s) | Interface | Dados suportados |
|-----|---------|-----------|-----------------|
| **Uniswap V3** | ETH, ARB, OP, Base, Polygon | GraphQL | pools, tvl, volume, fees, apr |
| **Uniswap V2** | Ethereum | GraphQL | pools, tvl, volume |
| **Aerodrome** | Base | REST + GraphQL | pools, tvl, volume, apr, emissions, gauges |
| **Velodrome** | Optimism | REST + GraphQL | pools, tvl, volume, apr, emissions |
| **Curve** | ETH, ARB, OP, Base, Polygon, AVAX, BSC | REST | pools, tvl, volume, apr, crv_apy |
| **Balancer V2** | ETH, ARB, Polygon, Base, OP | GraphQL | pools, tvl, volume, apr |
| **PancakeSwap V3** | BSC, ETH, ARB, Base | GraphQL + REST | pools, tvl, volume, apr |
| **SushiSwap** | ETH, ARB, Polygon, OP, Base, AVAX, BSC | REST | pools, tvl, volume, apr |
| **Raydium** | Solana | REST | pools, tvl, volume, apr |
| **Orca** | Solana | REST | pools, tvl, volume, apr |
| **Jupiter** | Solana | REST | price, swap_routes, token_list |

### Agregadores Multi-fonte (7)

| API | Key? | Dados suportados |
|-----|------|-----------------|
| **DefiLlama** | Não | tvl, pools, yields, apr, apy, protocol_tvl, chain_tvl, stablecoins, bridges, token_price |
| **CoinGecko** | Opcional (Pro) | price, market_cap, volume, ohlcv, global_market, btc_dominance, trending |
| **CoinMarketCap** | **Sim** (gratuita) | price, market_cap, volume, rankings, global_metrics, fear_greed |
| **DexScreener** | Não | pairs, token_pairs, search_pairs, price, volume, liquidity |
| **CoinGlass** | Opcional | open_interest, liquidations, long_short_ratio, funding_rate, fear_greed |
| **The Graph** | Não | qualquer subgraph, uniswap_v3, aave, compound, synthetix |
| **DexTools** | **Sim** (trial gratuita) | pool_info, price, ohlcv, liquidity, token_audit |

### RPCs On-chain (8)

| Chain | Chain ID | Providers gratuitos |
|-------|---------|---------------------|
| **Ethereum** | 1 | Cloudflare, ANKR, LlamaRPC, PublicNode, DRPC |
| **Arbitrum** | 42161 | Arbitrum oficial, ANKR, LlamaRPC, PublicNode, DRPC |
| **Base** | 8453 | Base oficial, ANKR, LlamaRPC, PublicNode, DRPC |
| **Optimism** | 10 | OP oficial, ANKR, LlamaRPC, PublicNode |
| **Polygon** | 137 | Polygon RPC, ANKR, LlamaRPC, PublicNode, DRPC |
| **Solana** | mainnet | Solana oficial, ANKR, PublicNode |
| **BSC** | 56 | Binance dataseed, ANKR, PublicNode, DRPC |
| **Avalanche** | 43114 | AVAX oficial, ANKR, PublicNode, DRPC |

---

## Configuração e API Keys

### Arquivo de configuração

Localização: `~/.moltbot/user_config.json`

```json
{
  "tokens": ["BTC", "ETH", "SOL"],
  "chains": ["Ethereum", "Arbitrum", "Base", "Optimism", "Polygon"],
  "alerts": {
    "funding_high":  0.08,
    "funding_low":  -0.03,
    "min_apr":       3.0,
    "max_apr":      80.0,
    "min_tvl":   500000
  },
  "api_keys": {
    "coinmarketcap": null,
    "dextools":      null,
    "coinglass":     null,
    "defillama_pro": null,
    "coingecko_pro": null
  }
}
```

### Gerenciar tokens monitorados

```bash
# Listar configuração atual
py ~/skills/shared/manage_tokens.py list

# Adicionar tokens
py ~/skills/shared/manage_tokens.py add SOL LINK AVAX

# Remover token
py ~/skills/shared/manage_tokens.py remove LINK
```

### Gerenciar API keys

```bash
# Ver keys configuradas
py ~/skills/shared/manage_tokens.py key list

# Configurar key (valida antes de salvar)
py ~/skills/shared/manage_tokens.py key set coinmarketcap CMC-xxxx-yyyy
py ~/skills/shared/manage_tokens.py key set dextools      DTK-xxxx-yyyy
py ~/skills/shared/manage_tokens.py key set coinglass     CGL-xxxx-yyyy
py ~/skills/shared/manage_tokens.py key set coingecko_pro CG-xxxx-yyyy

# Remover key (volta para endpoints públicos)
py ~/skills/shared/manage_tokens.py key remove coinmarketcap

# Ver onde obter a key gratuita
py ~/skills/shared/manage_tokens.py key info coinmarketcap
```

### Onde obter keys gratuitas

| API | URL | Plano gratuito |
|-----|-----|----------------|
| CoinMarketCap | https://pro.coinmarketcap.com/signup | Basic: 10k calls/mês |
| DexTools | https://developer.dextools.io/ | Trial: 30 req/min |
| CoinGlass | https://coinglass.com/account/signup | Endpoints básicos |
| CoinGecko Pro | https://www.coingecko.com/en/api | Demo: 30 req/min |

---

## Comandos de Referência Rápida

### Health check de todas as APIs

```bash
py -3 ~/skills/shared/api_gateway/health_checker.py
```

Ou por categoria:
```bash
py -3 -c "
import sys; sys.path.insert(0,'shared')
from api_gateway.health_checker import HealthChecker
HealthChecker().check_by_category('cex')
"
```

### Testar funding rate via router

```bash
py -3 -c "
import sys; sys.path.insert(0,'skills/shared')
from api_gateway.router import APIRouter
r = APIRouter()
d = r.fetch('funding_rate', symbol='BTCUSDT')
print(f'Fonte: {d[\"_source\"]}  |  Rate: {d[\"rate_pct\"]}  |  Mark: {d[\"mark_price\"]}')
"
```

### Testar pools via router

```bash
py -3 -c "
import sys; sys.path.insert(0,'skills/shared')
from api_gateway.router import APIRouter
r = APIRouter()
res = r.fetch('pools_evm', chains=['Ethereum','Arbitrum'], min_tvl=1_000_000, min_apr=5.0)
for p in res['pools'][:5]:
    print(f\"{p['protocol']:20} {p['symbol']:20} APR:{p['apr_total']:6.1f}%  TVL:\${p['tvl_usd']/1e6:.1f}M\")
"
```

### Adicionar nova API ao gateway

```bash
# Interativo
py -3 ~/skills/shared/api_gateway/add_api.py

# Direto com argumentos
py -3 ~/skills/shared/api_gateway/add_api.py \
  --name hyperliquid \
  --category cex \
  --url https://api.hyperliquid.xyz \
  --supports "price,funding_rate,open_interest" \
  --rate-limit 100

# Dry run (preview sem criar arquivos)
py -3 ~/skills/shared/api_gateway/add_api.py --dry-run --name hyperliquid --category cex --url https://api.hyperliquid.xyz
```

### Reempacotar skills

```bash
py -3 -c "
import zipfile
from pathlib import Path
skills_dir = Path.home() / 'skills'
for skill, name in [('funding-rate-monitor','funding-rate-monitor'),('liquidity-pool-monitor','liquidity-pool-monitor')]:
    out = skills_dir / f'{name}.skill'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for d in [skills_dir/skill, skills_dir/'shared']:
            for f in d.rglob('*'):
                if '__pycache__' not in str(f) and f.suffix != '.pyc' and f.is_file():
                    zf.write(f, f.relative_to(skills_dir))
    print(f'{name}.skill criado')
"
```

### Limpar cache

```bash
py -3 -c "
import sys; sys.path.insert(0,'skills/shared')
from api_gateway.base_client import CacheManager
CacheManager().clear_all()
print('Cache limpo')
"
```

---

## Estratégias de Trading

### Funding Rate Extreme Reversal

**Regras de entrada:**

| Condição | Sinal |
|----------|-------|
| Funding > **+0.08%** | SHORT — longs sobrecarregados, reversão esperada |
| Funding < **-0.03%** | LONG — shorts sobrecarregados, squeeze esperado |
| Entre -0.03% e +0.08% | FLAT — sem posição |

**Gestão de risco:**

| Parâmetro | Valor |
|-----------|-------|
| Stop Loss | 2% |
| Take Profit | 3% |
| Saída adicional | quando funding normaliza de volta à zona neutra |
| Alavancagem recomendada | 1x (sem alavancagem) |
| Tamanho máximo | 5–10% do portfólio por trade |

**Thresholds adaptativos:** quando o histórico não tem rates acima dos limiares absolutos, o script usa automaticamente os percentis 85%/15% dos dados observados (evita backtest sem sinais em altcoins).

**Eficácia por condição de mercado:**

| Mercado | Funding SHORT | Funding LONG | Observação |
|---------|--------------|--------------|------------|
| Bull run | ⭐⭐⭐⭐⭐ Alta | ⭐⭐⭐ Média | Spikes frequentes acima de +0.08% |
| Bear | ⭐⭐⭐ Média | ⭐⭐ Baixa | Funding negativo pode persistir semanas |
| Sideways | ⭐⭐⭐ Boa | ⭐⭐⭐ Boa | Menos sinais mas maior qualidade |

**Riscos:**
- Trend override — bull/bear market pode manter funding extremo por dias
- Cascade risk — gaps de preço em crashes atravessam o stop
- Limite de 8h entre cada funding settlement
- Sinais diferentes entre exchanges (Binance ≠ Bybit ≠ OKX)

---

### Estratégia de Pools de Liquidez

**Framework de decisão:**

```
1. Sentimento RISK_OFF?
   → Pools estáveis apenas (USDC/USDT, DAI/USDC, LUSD/USDC)
   → APR 3–15%, IL praticamente zero

2. Sentimento RISK_ON?
   → Pairs correlacionados (ETH/USDC, WBTC/ETH, stETH/ETH)
   → APR 15–50%, fees compensam IL em mercados trending

3. TVL > $2M?
   → Sim: pool estabelecida, menor risco de manipulação
   → Não: evitar ou posição muito pequena

4. APR sustentável?
   → < 80%: avaliação normal
   → 80–200%: verificar composição (quanto é reward token)
   → > 200%: alto risco, provavelmente insustentável
```

**Impermanent Loss de referência:**

| Variação de preço | IL estimado |
|-------------------|-------------|
| +25% | -0.6% |
| +50% | -2.0% |
| +100% (2x) | -5.7% |
| +200% (3x) | -13.4% |
| +400% (5x) | -25.5% |

> **Nota:** IL é impermanente — se os preços voltarem ao ratio original, o loss desaparece. Só se realiza ao retirar liquidez.

**Pares com IL baixo:** USDC/USDT, DAI/USDC, stETH/WETH, WBTC/cbBTC

---

*Última atualização: 2026-03-26 | OpenClaw v1.0 | Python 3.13*
