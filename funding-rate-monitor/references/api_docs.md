# API Docs — Funding Rate Monitor

## Endpoints Suportados

### Hyperliquid
- Endpoint: configurado via env `HYPERLIQUID_FUNDING_ENDPOINT`
- Autenticação: API Key via header `Authorization: Bearer <token>` (se necessário)
- Formato de resposta: `{"pair":"ETH-USDC","funding_rate":0.00123,"timestamp":1690000000}`

### Nado
- Endpoint: configurado via env `NADO_FUNDING_ENDPOINT`
- Formato de resposta: `{"pair":"ETH-USD","funding_rate":0.00045,"timestamp":1690000000}`

### Binance (via api_gateway)
- Endpoint: `GET /fapi/v1/premiumIndex?symbol=BTCUSDT`
- Sem autenticação para dados públicos

### Bybit (via api_gateway)
- Endpoint: `GET /v5/market/funding/history`

### OKX (via api_gateway)
- Endpoint: `GET /api/v5/public/funding-rate`

## Variáveis de Ambiente
```
HYPERLIQUID_FUNDING_ENDPOINT=https://...
NADO_FUNDING_ENDPOINT=https://...
FUNDING_API_KEY=<token_opcional>
```

## Formato padrão normalizado (api_gateway)
```json
{
  "symbol": "BTCUSDT",
  "funding_rate": 0.0001,
  "next_funding_time": 1690000000,
  "source": "binance"
}
```
