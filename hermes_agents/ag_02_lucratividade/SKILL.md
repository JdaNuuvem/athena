---
name: factory-profitability-analyst
description: >
  AG-02: Analista de Lucratividade. Calcula lucro REAL por SKU descontando
  matéria-prima, mão de obra, taxas, frete e impostos. Identifica produtos
  que vendem muito mas geram pouco lucro.
category: factory
bundled: true
---

# AG-02 — Analista de Lucratividade

Responde: "Qual produto REALMENTE dá lucro?"

## Ferramentas

| Função | Descrição |
|---|---|
| `calcular_lucro_real(preco, custo, taxa, frete)` | Cálculo isolado de lucro líquido |
| `analisar_sku(sku, dias)` | Análise completa de lucratividade de um SKU |
| `top_lucrativos(n)` | Ranking dos SKUs mais lucrativos |
| `bottom_deficitarios(n)` | SKUs com margem negativa |
| `relatorio_diario()` | Resumo de vendas e receita do dia |
| `verificar_alertas()` | SKUs abaixo da margem mínima |

## Como usar

```python
sys.path.insert(0, "/workspace")
from hermes_agents.ag_02_lucratividade import *

# Análise de um SKU
analise = analisar_sku("ORG001")
print(f"SKU: {analise['sku']} | Margem: {analise['margem_pct']}% | Status: {analise['status']}")

# Top 5 lucrativos
for p in top_lucrativos(5):
    print(f"  {p['sku']}: R${p['receita_liquida']:.2f}")

# Deficitários
for p in bottom_deficitarios(5):
    print(f"  ⚠️ {p['sku']}: R${p['receita_total']:.2f} — eliminando custo variável já fica no vermelho")
```
