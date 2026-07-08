---
name: factory-corporate-memory
description: >
  AG-09: Memória Corporativa da fábrica. Consulta moldes, fichas técnicas,
  fornecedores, matérias-primas, histórico de custos e problemas resolvidos.
  Use para perguntas como "Já fabricamos algo parecido?",
  "Qual molde usamos para o produto X?", "Quem é o fornecedor mais barato?"
category: factory
bundled: true
---

# AG-09 — Memória Corporativa

Organiza e consulta todo o conhecimento técnico da fábrica.

## Ferramentas disponíveis

| Função | Descrição |
|---|---|
| `listar_moldes(status)` | Lista moldes (ativo/inativo/todos) |
| `buscar_molde(codigo)` | Busca molde por código |
| `produtos_do_molde(codigo)` | SKUs que usam um molde |
| `buscar_ficha(sku)` | Ficha técnica completa do SKU |
| `listar_fichas(material)` | Todas as fichas, filtro por material |
| `buscar_fornecedor(categoria)` | Fornecedores por categoria |
| `fornecedor_mais_barato(materia_prima)` | Melhor preço de matéria-prima |
| `listar_materias_primas()` | Estoque de matérias-primas |
| `alertas_estoque_baixo()` | Matérias-primas abaixo do mínimo |
| `historico_custo_sku(sku, meses)` | Evolução do custo de produção |
| `buscar_solucoes(palavra_chave)` | FAQ de problemas resolvidos |
| `buscar_similar(descricao)` | Produtos similares por descrição |
| `stats()` | Estatísticas da base |

## Como usar

```python
# No Hermes execute_code:
import sys
sys.path.insert(0, "/workspace")
from hermes_agents.ag_09_memoria import *

# Buscar molde
molde = buscar_molde("M-001")
print(molde)

# Buscar similar — "Já fabricamos algo parecido com organizador de mesa?"
similares = buscar_similar("organizador mesa")
for s in similares:
    print(f"  {s['sku']}: {s['descricao']} (custo: R${s.get('ultimo_custo', 'N/A')})")

# Fornecedor mais barato
barato = fornecedor_mais_barato("polipropileno")
print(f"Fornecedor: {barato['fornecedor']} — R${barato['preco_unitario']}/kg")
```
