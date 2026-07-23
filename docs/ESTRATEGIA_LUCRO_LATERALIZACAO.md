# Estratégias de Lateralização & Lucro — Athena

**Complemento ao `PLANO_LATERALIZACAO_SHOPEE.md`** — funcionalidades pensadas para maximizar margem e escalar sem doer.

---

## 1. Precificação Inteligente por Loja

O custo de operar não é igual em todas as lojas Shopee. Cada uma pode ter comissão, frete, ou taxa diferentes. O Athena precisa calcular o **preço mínimo viável** por loja automaticamente.

| Funcionalidade | Como funciona |
|----------------|--------------|
| **Markup por loja** | Configurar % de markup base sobre o custo do produto. Loja A: 2.0x, Loja B: 1.8x. Ao replicar, já publica com o preço correto de cada loja |
| **Regra por categoria** | Markup diferente por categoria (ex: eletrônicos margem menor, moda margem maior) |
| **Teto por concorrência** | Se o preço médio do mercado é R$ 50, não publicar acima de R$ 55 a menos que tenha diferencial |
| **Margem mínima de segurança** | Bloquear publicação se o preço final (após comissão + frete) der margem negativa |

**Impacto no lucro:** Impede que uma loja opere no prejuízo escondido (produto barato demais que mal cobre a comissão da Shopee).

```
Cadastro do produto → Custo: R$ 10,00
                     → Loja A (comissão 15%): markup 2.5x → R$ 25 → margem real: ~R$ 11,25
                     → Loja B (comissão 18%): markup 2.8x → R$ 28 → margem real: ~R$ 12,96
```

---

## 2. Lucro Real por Loja (DRE por Canal)

O Athena já tem DRE consolidado. Precisa de um **DRE por loja Shopee**:

```
Receita Bruta (vendas Shopee Loja A)
  - Comissão Shopee (% variável por categoria)
  - Taxa de frete (média por pedido)
  - Custos dos produtos (CMV)
  - Custos fixos rateados (estoque, embalagem)
  - Custos de marketing (se anúncio pago)
= Lucro Líquido por Loja
```

**UI:** Dashboard com cards comparativos:

```
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Loja A      │ │ Loja B      │ │ Loja C      │
│ Receita: 50k│ │ Receita: 35k│ │ Receita: 12k│
│ Custo: 28k  │ │ Custo: 22k  │ │ Custo: 9k   │
│ Lucro: 22k  │ │ Lucro: 13k  │ │ Lucro: 3k   │
│ Margem: 44% │ │ Margem: 37% │ │ Margem: 25% │ ← ⚠ loja C com margem baixa
└─────────────┘ └─────────────┘ └─────────────┘
```

**Impacto:** Saber qual loja está performando bem e qual está comendo margem. Decidir se vale manter ou ajustar preços.

---

## 3. Catálogo Diferenciado por Loja

Nem todo produto deve ir para todas as lojas. Alguns podem ter posicionamento diferente.

**Regras de publicação:**
- **Grupos de produtos** — rotular produtos como "Premium" (só loja A + B), "Econômico" (só loja C), "Todos"
- **Restrição por categoria** — loja C não vende eletrônicos, só moda
- **Limite de SKUs** — loja nova começa com top 50 produtos (mais vendidos da loja principal)
- **Exclusividade regional** — produto X só na loja que atende região Y

**UI ao replicar:**
```
Replicar produtos para Loja B
┌─ Apenas produtos do grupo "Premium"  [         ] ← filtro por grupo
├─ Categoria: [Todas ▼]
├─ Preço mínimo: [R$ 0,00]
├─ Preço máximo: [R$ 0,00]
└─ [Replicar 47 produtos selecionados]  [Simular]
```

**Impacto:** Evita canibalização entre lojas. Cada loja com identidade própria.

---

## 4. Regras de Desconto Sazonal Automático

Não replicar preço fixo — replicar com **regra de precificação dinâmica**.

| Gatilho | Ação |
|---------|------|
| Produto parado > 30 dias sem venda | Baixar preço 10% |
| Produto com estoque alto (> 90 dias) | Baixar preço 15% |
| Black Friday / Natal | Aplicar desconto programado X% |
| Loja nova (primeiros 30 dias) | Preço 10% abaixo da loja principal (para ganhar tração) |

**Backend:** Módulo `automacoes/agendamentos` + regras configuráveis.

**Impacto:** Loja nova começa com preço competitivo sem você precisar lembrar de ajustar.

---

## 5. Reprecificação por Concorrência

Monitorar preço dos concorrentes e ajustar automaticamente (ou com alerta).

**Já existe no Athena:** módulo `concorrentes` no banco de dados (tabela do schema.sql) + agente `ag_01_caçador`.

**O que integrar:**
- Ao publicar um produto, buscar preço médio dos concorrentes na Shopee
- Se preço sugerido for > 20% acima da média, alertar
- (Opcional) Ajustar preço automaticamente para ficar X% abaixo do concorrente mais barato

**Impacto:** Produto não morre por precificação errada na estreia.

---

## 6. Sugestão de Kits e Cross-Sell

Ao publicar um produto, o Athena sugere criar **kits/bundles** baseado em histórico de vendas.

**Funcionamento:**
- Analisar vendas da loja origem: "Quem comprou X também comprou Y"
- Ao replicar, sugerir: "Criar kit X+Y com preço promocional?"
- O kit vira um produto separado na loja destino com SKU composto

**Impacto:** Aumento de ticket médio sem esforço extra.

---

## 7. Rotação de Estoque entre Lojas

Produto encalhado na Loja A mas vendendo bem na Loja B? O Athena sugere transferência.

**Funcionamento:**
- Dashboard: "Produto X: 50 unidades paradas na Loja A, 0 na Loja B (vendeu 20 nos últimos 7 dias)"
- Botão "Sugerir transferência" ou "Ajustar preço na Loja A para queimar"

**Impacto:** Menos capital parado em estoque morto.

---

## 8. Alerta de Margem Negativa

Antes de publicar ou ajustar preço, o Athena valida se a margem não vai ficar negativa após taxas.

**Regra:** `preço_final - comissão_shopee - frete_médio - custo_produto > margem_mínima`

Se violar, o sistema **bloqueia** a operação com explicação:
```
❌ Não é possível publicar "Sabonete X" na Loja C
   Preço: R$ 12,00
   Comissão (18%): -R$ 2,16
   Frete médio: -R$ 5,00
   Custo: -R$ 8,00
   Margem: -R$ 3,16 (prejuízo)
   Sugestão: preço mínimo R$ 18,00 para margem de 15%
```

**Impacto:** Zero produto publicado no prejuízo por descuido.

---

## Matriz completa

| # | Funcionalidade | Esforço | Impacto no lucro |
|---|---------------|---------|-----------------|
| 1 | Precificação inteligente por loja | 6-8h | 🔴 Alto — impede prejuízo |
| 2 | DRE por loja (lucro real) | 4-6h | 🔴 Alto — visibilidade |
| 3 | Catálogo diferenciado por loja | 3-4h | 🟡 Médio — posicionamento |
| 4 | Desconto sazonal automático | 4-6h | 🟡 Médio — queima estoque |
| 5 | Reprecificação por concorrência | 8-12h | 🟡 Médio — competitividade |
| 6 | Sugestão de kits / cross-sell | 4-6h | 🟢 Baixo — upsell |
| 7 | Rotação de estoque entre lojas | 3-4h | 🟡 Médio — menos capital parado |
| 8 | Alerta de margem negativa | 2-3h | 🔴 Alto — bloqueia prejuízo |
| | **Total** | **34-49h** | |

---

## Ordem recomendada de implementação

```
Fase 1 — Não quebrar (2-3h)
  └─ Alerta de margem negativa (#8) → bloqueia operação no vermelho

Fase 2 — Enxergar (4-6h)
  └─ DRE por loja (#2) → tabela de lucro real por canal

Fase 3 — Precificar (6-8h)
  └─ Precificação inteligente (#1) + markup por loja

Fase 4 — Escalar (10-16h)
  └─ Catálogo diferenciado (#3) + Desconto sazonal (#4) + Rotação (#7)

Fase 5 — Otimizar (12-18h)
  └─ Reprecificação concorrência (#5) + Kits/cross-sell (#6)
```

---

## Resumo

O Athena já tem a base: catálogo, estoque por loja, OAuth multiloja, `add_item()`. O que transforma isso numa **máquina de lateralização lucrativa** são as camadas de:

1. **Proteção** — Alerta de margem negativa (#8)
2. **Visibilidade** — DRE por loja (#2)
3. **Automação de preço** — Markup por loja (#1) + regras sazonais (#4)
4. **Seleção inteligente** — Catálogo diferenciado (#3) + rotação (#7)
5. **Otimização** — Concorrência (#5) + cross-sell (#6)
