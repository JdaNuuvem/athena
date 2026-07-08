---
name: factory-marketplace-manager
description: >
  AG-03: Gerente de Marketplaces. Monitora posição de anúncios, preços dos
  concorrentes, avaliações e gera sugestões de SEO, preço, kits e promoções.
category: factory
bundled: true
---

# AG-03 — Gerente de Marketplaces

Aumenta vendas nos marketplaces sem criar novos produtos.

## Ferramentas

| Função | Descrição |
|---|---|
| `verificar_posicoes()` | Posição de todos os anúncios ativos |
| `anuncios_caindo()` | Anúncios fora do top 10 |
| `comparar_precos_concorrentes(sku)` | Preço nosso vs concorrência |
| `gerar_sugestao_titulo(sku, kw, mp)` | Sugestão de título otimizado |
| `sugerir_kit(sku_a, sku_b, mp)` | Combo de produtos complementares |
| `sugerir_ajuste_preco(sku, mp)` | Ajuste baseado na concorrência |
| `relatorio_consolidado()` | Estado geral dos marketplaces |
| `executar_monitoramento()` | Ciclo completo com alertas |

## Como usar

```python
sys.path.insert(0, "/workspace")
from hermes_agents.ag_03_marketplaces import *

# Status geral
print(relatorio_consolidado())

# Preço vs concorrência
for p in comparar_precos_concorrentes("ORG001"):
    print(f"  Nosso: R${p['nosso_preco']} | {p['concorrente']}: R${p['preco_concorrente']} | Diff: {p['diff_pct']}%")

# Ciclo de monitoramento
alertas = executar_monitoramento()
for a in alertas:
    print(f"  {a}")
```
