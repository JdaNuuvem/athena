---
name: factory-product-hunter
description: >
  AG-01: Caçador de Produtos. Pesquisa marketplaces diariamente em busca de
  produtos em alta, baixa concorrência e viáveis para fabricação própria.
  Use para "O que devemos fabricar?", "Tendências da semana", "Novos produtos".
category: factory
bundled: true
---

# AG-01 — Caçador de Produtos

Descobre novas oportunidades de receita antes da concorrência.

## Fontes monitoradas

Shopee · Mercado Livre · Amazon · Temu · TikTok Shop · Google Trends · Pinterest

## Ferramentas

| Função | Descrição |
|---|---|
| `executar_cacada(categoria)` | Coleta + analisa + salva produtos de todos os marketplaces |
| `top_oportunidades(n)` | Top N produtos com maior score do dia |
| `coletar_tendencias()` | Tendências do Google Trends e Pinterest |
| `pesquisar_marketplace(mp, cat)` | Pesquisa um marketplace específico |
| `analisar_viabilidade(produto)` | Score de viabilidade de fabricação |

## Como usar

```python
sys.path.insert(0, "/workspace")
from hermes_agents.ag_01_cacador import *

# Caçada completa
resultados = executar_cacada()
for p in resultados[:10]:
    print(f"[{p['score_final']}/100] {p['nome']} — R${p['preco_medio']} — Margem: {p['margem_estimada']}%")

# Tendências
tendencias = coletar_tendencias()
for t in tendencias:
    print(f"  {t['termo']}: +{t['crescimento']}% — {t['volume']} buscas")
```
