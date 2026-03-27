# Domain Notes — Funding Rate

## O que é Funding Rate
- Taxa paga periodicamente entre longs e shorts em contratos perpétuos.
- Funding positivo: longs pagam shorts (mercado sobrecomprado).
- Funding negativo: shorts pagam longs (mercado sobrevendido).

## Leitura e Interpretação
| Faixa             | Sinal                          |
|-------------------|-------------------------------|
| > +0.08%          | Extremamente sobrecomprado    |
| +0.03% a +0.08%   | Sobrecomprado — cuidado       |
| -0.03% a +0.03%   | Neutro                        |
| < -0.03%          | Sobrevendido — possível bounce|

## Limites de Risco
- Funding acima de 0.1% ao dia anualiza para ~36% — custo de carry alto.
- Use `thresholds` no config.yaml para alertas customizados por par.

## Estratégias Relacionadas
- **Cash & Carry**: compra spot + short perp quando funding está alto.
- **Arbitragem de funding**: long em exchange com funding baixo, short onde está alto.
- **Contrarian signal**: funding extremo pode indicar reversão de tendência.

## Referências
- Veja `strategy_guide.md` para estratégias completas.
- Veja `exchange_apis.md` para detalhes de cada exchange.
