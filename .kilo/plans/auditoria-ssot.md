# Auditoria de Duplicação de Dados — SSOT

**Data:** 14/07/2026 | **Arquivos analisados:** 93+ arquivos TS/TSX | **Interfaces/Tipos encontrados:** 93

---

## Sumário Executivo

Foram encontradas **18 categorias de duplicação** distribuídas entre duplicação de **entidades de domínio**, **componentes UI** e **funções utilitárias**. As mais críticas envolvem `NotaFiscal`, `Conta` e `Produto`, onde múltiplos módulos definem variantes incompatíveis da mesma entidade.

---

## 1. Entidades de Domínio (Dados de Negócio)

### 1.1 — Produto (Product)

| Campo | SSOT (`api.ts:231`) | Duplicado em |
|-------|---------------------|--------------|
| Módulo Fonte | `web/src/lib/api.ts` | |
| Interface | `Product { sku, nome, margem_pct, receita_30d, vendidos_30d, estoque_lojas, total_lojas }` | |
| Duplicação 1 | `web/src/app/bi/types/index.ts` | `ProdutoVenda { nome, sku, valor, qtd, margem }` |
| Duplicação 2 | `web/src/app/pdv/page.tsx` | `CartItem { codigo, descricao, quantidade, valor_unitario }` |
| Duplicação 3 | `web/src/app/integracoes/bling/_components/BlingOrdersTab.tsx` | inline `itens: Array<{ codigo, descricao?, quantidade, valor }>` |
| Duplicação 4 | `web/src/lib/api.ts` (mesmo arquivo!) | `BlingProduct { id, codigo, descricao, preco, estoque_atual, estoque_minimo, situacao }` |
| Duplicação 5 | `web/src/app/produtos/[sku]/_components/VisaoGeralTab.tsx` | `produto: Record<string, unknown>` (sem tipo!) |

**Impacto:** 5 variantes incompatíveis do mesmo conceito. `CartItem` usa `codigo` enquanto `Product` usa `sku`. `ProdutoVenda` usa `valor` enquanto `BlingProduct` usa `preco`. Nenhum pode ser usado no lugar do outro sem conversão manual.

**Ação recomendada:**
- Consolidar `Product`, `BlingProduct`, `ProdutoVenda` e `CartItem` em uma hierarquia com uma base comum `IProductBase { sku: string; nome: string; preco: number }`
- `CartItem` deve estender `IProductBase` com `quantidade` e `valor_unitario`
- Mover `Product` para `web/src/lib/types/domain.ts`

---

### 1.2 — Nota Fiscal

| Campo | SSOT | Duplicado em |
|-------|------|--------------|
| Módulo Fonte | `web/src/app/integracoes/bling/_components/BlingFinancialTab.tsx:9-22` | |
| Interface | `NotaFiscal { id, numero, dataEmissao?, dataOperacao?, contato: { nome, numeroDocumento? }, situacao, tipo, chaveAcesso?, loja?: { id }, naturezaOperacao?: { id }, valorNota?, total? }` | |
| Duplicação | `web/src/app/fiscal/types/index.ts:1-27` | **Cópia exata** (14 campos idênticos) |
| Constantes | `NF_SITUACOES, NF_TIPOS` | **Cópia exata** em ambos os arquivos |
| Função | `detectarTipoNota()` | Só existe em fiscal, não no SSOT |

**Impacto:** Qualquer alteração no modelo de NF do Bling precisa ser sincronizada manualmente em 2 lugares. A função `detectarTipoNota()` deveria estar junto ao SSOT.

**Ação recomendada:**
- Mover `NotaFiscal`, `NF_SITUACOES`, `NF_TIPOS` e `detectarTipoNota()` para `web/src/lib/types/domain.ts`
- Ambos `BlingFinancialTab` e `fiscal/notas/` importam do mesmo lugar

---

### 1.3 — Conta Financeira (Pagar / Receber)

| Campo | Local | Estrutura |
|-------|-------|-----------|
| SSOT | `web/src/lib/api.ts:280` | `BlingReceivable { id, descricao, valor, data_vencimento, situacao }` |
| Variante 1 | `web/src/app/financeiro/_components/ReceberTab.tsx:7` | `Conta { id, cliente, descricao, valor, vencimento, data_recebimento?, status, forma_pagamento }` |
| Variante 2 | `web/src/app/financeiro/_components/PagarTab.tsx:7` | `Conta { id, fornecedor, descricao, valor, vencimento, data_pagamento?, status, forma_pagamento }` |
| Variante 3 | `web/src/app/integracoes/bling/_components/BlingFinancialTab.tsx:24` | `ContaReceber { id, numero, vencimento?, valor?, contato: { nome }, situacao }` |

**Impacto:** 3 interfaces chamadas `Conta`/`ContaReceber` com campos diferentes:
- `BlingReceivable` usa `data_vencimento` e `situacao` (português)
- `ReceberTab` usa `cliente`, `vencimento`, `data_recebimento`, `status` e tem `forma_pagamento`
- `PagarTab` usa `fornecedor`, `vencimento`, `data_pagamento`, `status` e tem `forma_pagamento`
- `ContaReceber` usa `numero`, `contato: { nome }`, `situacao`

**Ação recomendada:**
- Unificar em `ContaFinanceira { id, tipo: "pagar" | "receber", descricao, valor, vencimento, data_baixa?, status, forma_pagamento, contraparte?: string, referencia?: string }`
- Extensões específicas: `ContaPagar extends ContaFinanceira` e `ContaReceber extends ContaFinanceira`

---

### 1.4 — Pedido / Order

| Campo | Local | Estrutura |
|-------|-------|-----------|
| SSOT | `web/src/lib/api.ts:259` | `BlingOrder { id, numero, data, total_venda, situacao, contato_nome, imported_at }` |
| Duplicação | `web/src/app/integracoes/bling/_components/BlingOrdersTab.tsx:9-20` | `Pedido { id, numero, data?, dataSaida?, contato: { nome, numeroDocumento?, tipoPessoa? }, total, totalProdutos?, situacao: { id, valor } | string, itens?: Array<...>, loja?: { id } }` |

**Impacto:** `BlingOrder` (API) e `Pedido` (UI) representam o mesmo conceito com estruturas diferentes. `BlingOrder` tem `total_venda` (snake_case), `Pedido` tem `total` (camelCase). `BlingOrder` tem `contato_nome` como string, `Pedido` tem `contato: { nome }` como objeto.

**Ação recomendada:**
- Mover `Pedido` para `web/src/lib/types/domain.ts` como `Order` / `Pedido`
- `BlingOrder` deve ser o tipo wire (API response) e `Pedido` o tipo de domínio, com função de mapeamento

---

### 1.5 — Loja

| Campo | Local | Estrutura |
|-------|-------|-----------|
| Duplicação 1 | `web/src/app/metrics/page.tsx:7` | `type Loja = { id, tipo, nome, receita, pedidos, ticket_medio }` |
| Duplicação 2 | `web/src/lib/api.ts:299` | `BlingConfig { ... lojaId: number ... }` (apenas ID) |
| Duplicação 3 | `BlingFinancialTab, BlingOrdersTab` | `loja?: { id }` em várias interfaces |
| Duplicação 4 | `web/src/lib/api.ts:237` | `Product.estoque_lojas: Array<{ loja: string, preco: number, status: string }>` |

**Impacto:** `Loja` é uma entidade de 1ª classe mas não tem tipo centralizado. É referenciada como ID, como objeto `{ id }` ou como string `{ loja: string }` dependendo do contexto.

**Ação recomendada:**
- Criar `interface Loja { id: number; nome: string; tipo?: string }` em domain.ts
- Referenciar sempre como `loja: Loja | Pick<Loja, "id">`

---

### 1.6 — Cliente / Contato

Sem SSOT. Aparece inline em múltiplos lugares:
- `ReceberTab`: `cliente: string`
- `BlingOrdersTab`: `contato: { nome, numeroDocumento?, tipoPessoa? }`
- `BlingFinancialTab.NotaFiscal`: `contato: { nome, numeroDocumento? }`
- `BlingFinancialTab.ContaReceber`: `contato: { nome }` (estrutura reduzida)
- `BlingOrder`: `contato_nome: string`
- `ClientesTab`: colunas de tabela mas sem interface tipada
- `cadastros`: `contato: { tipo, valor, whatsapp }` (contato de cliente, entidade diferente)

**Impacto:** Mesma entidade modelada como string, objeto com 1 campo, objeto com 3 campos. Impossível saber qual usar.

**Ação recomendada:**
- Criar `interface Contato { nome: string; documento?: string; tipoPessoa?: string }` em domain.ts
- Criar `interface Cliente { id: number; nome: string; tipo: string; documento: string; limite_credito: number; score: number; status: string; contatos: Contato[] }`
- Referenciar via `cliente: Pick<Cliente, "id" | "nome">` ou `cliente: Cliente`

---

### 1.7 — Fornecedor

| Campo | Local | Estrutura |
|-------|-------|-----------|
| Duplicação | `PagarTab.tsx` | `fornecedor: string` (apenas nome) |
| Definição parcial | `cadastros/_components/FornecedoresTab.tsx` | Colunas de tabela: `id, nome, tipo, documento, contato` |

**Impacto:** Não existe interface `Fornecedor`. O módulo de cadastros define colunas sem tipo, e o financeiro trata como string.

**Ação recomendada:**
- Criar `interface Fornecedor { id: number; nome: string; tipo: string; documento: string; contato: string }` em domain.ts

---

## 2. Componentes de UI Duplicados

### 2.1 — PageHeader

| Local | Estrutura |
|-------|-----------|
| `web/src/app/bi/_components/PageHeader.tsx` | `{ title: string; subtitle: string }` |
| `web/src/app/fiscal/_components/PageHeader.tsx` | `{ title: string; subtitle: string }` (idêntico) |

**Ação:** Mover para `web/src/app/_components/PageHeader.tsx`. BI e Fiscal importam dele.

---

### 2.2 — KpiCard

| Local | Props |
|-------|-------|
| `web/src/app/bi/_components/KpiCard.tsx` | `{ metric: { label, value, sub?, color? } }` |
| `web/src/app/fiscal/_components/KpiCard.tsx` | `{ metric: { label, value, color } }` (sem `sub`) |
| `web/src/app/dashboard/page.tsx:248` | `function KpiCard({ label, value, valueClassName })` — versão inline |

**Ação:** Consolidar em `web/src/app/_components/KpiCard.tsx` com props `{ label, value, sub?, color? }`. Dashboard deve usar o componente.

---

### 2.3 — KpiMetric (tipo)

| Local | Estrutura |
|-------|-----------|
| `web/src/app/bi/types/index.ts` | `{ label, value, sub?, color? }` |
| `web/src/app/fiscal/types/index.ts` | `{ label, value, color }` (sem `sub`) |

**Ação:** Consolidar em `web/src/lib/types/ui.ts` com `sub?` opcional.

---

### 2.4 — SubmenuItem / SubmenuCard

| Local | Estrutura |
|-------|-----------|
| `web/src/app/fiscal/types/index.ts` | `SubmenuItem { href, label, color }` |
| `web/src/app/bi/types/index.ts` | `SubmenuItem { href, label, color }` (idêntico) |
| `web/src/app/fiscal/_components/SubmenuCard.tsx` | Componente que usa SubmenuItem |
| `web/src/app/bi/page.tsx` | Inline `<Link>` em vez de SubmenuCard |
| `web/src/app/fiscal/page.tsx` | Usa SubmenuCard |
| `web/src/app/compras/page.tsx` | Inline `<Link>` com array SUBMENU |

**Ação:** Mover `SubmenuItem` para `web/src/lib/types/ui.ts`. Mover `SubmenuCard` para `web/src/app/_components/`. BI e Compras devem usar SubmenuCard.

---

### 2.5 — TabBar / TabOption

| Local | Estrutura |
|-------|-----------|
| `web/src/app/fiscal/_components/TabBar.tsx` | Componente genérico |
| `web/src/app/fiscal/types/index.ts` | `TabOption { key, label }` |
| `web/src/app/bi/vendas/page.tsx` | Inline tabs markup (sem TabBar) |
| `web/src/app/bi/tabelas/page.tsx` | Inline tabs markup (sem TabBar) |
| `web/src/app/integracoes/bling/_components/BlingFinancialTab.tsx` | Inline tabs markup |
| `web/src/app/produtos/[sku]/client.tsx` | Inline tabs markup |

**Ação:** Mover `TabBar` e `TabOption` para `web/src/app/_components/`. Todos os módulos devem usar.

---

### 2.6 — StatusBadge

| Local | Abordagem |
|-------|-----------|
| `web/src/app/fiscal/_components/StatusBadge.tsx` | Componente tipado com `variant: "success" | "danger" | "warning" | "neutral"` |
| `BlingFinancialTab.tsx:148-154` | Inline className condicional |
| `BlingOrdersTab.tsx:23` | `SIT_COLORS` record + inline |
| `ReceberTab.tsx:25` | Inline `sc` variable |
| `PagarTab.tsx:25` | Inline `sc` variable |
| `ClientesTab.tsx:14-17` | Inline render function |
| `fiscal/tabelas/page.tsx:95` | Inline badge classNames |

**Ação:** Mover `StatusBadge` para `web/src/app/_components/`. Todos os módulos devem usar.

---

### 2.7 — DataTable / Column

| Local | Estrutura |
|-------|-----------|
| `web/src/app/fiscal/_components/DataTable.tsx` | `DataTable<T>` genérico com `Column<T>[]` |
| `web/src/app/fiscal/types/index.ts` | `Column<T> { key, label, align?, render? }` |
| `web/src/app/cadastros/_components/CrudPanel.tsx` | `Column { key, label, render? }` (não genérico) |
| Financeiro (todas as tabs) | Inline `<table>` markup |

**Ação:** Unificar `Column` e `DataTable` em `web/src/app/_components/`. Migrar financeiro e cadastros para usar DataTable.

---

### 2.8 — ErrorAlert

| Local | Estrutura |
|-------|-----------|
| `web/src/app/fiscal/_components/ErrorAlert.tsx` | `{ message: string | null }` |
| `dashboard/page.tsx:90-93` | Inline error div idêntico |
| `produtos/page.tsx:42-46` | Inline error div idêntico |
| Múltiplas outras páginas | Inline error div idêntico |

**Ação:** Mover para `web/src/app/_components/ErrorAlert.tsx`. Usar em todas as páginas.

---

### 2.9 — LoadingState

| Local | Estrutura |
|-------|-----------|
| `web/src/app/fiscal/_components/LoadingState.tsx` | `{ message?: string }` |
| Todas as outras páginas | `<p className="text-neutral-500 text-sm">Carregando...</p>` inline |

**Ação:** Mover para `web/src/app/_components/LoadingState.tsx`.

---

### 2.10 — ChartTooltip

| Local |
|-------|
| `web/src/app/dashboard/page.tsx:58-66` |
| `web/src/app/bi/vendas/page.tsx:13-21` |
| `web/src/app/bi/_components/ForecastChart.tsx:11-23` (CustomTooltip) |
| `web/src/app/metrics/page.tsx:12-20` |

4 variantes do mesmo componente. Todas idênticas no conceito, diferem apenas no formatter.

**Ação:** Criar `web/src/app/_components/ChartTooltip.tsx` com prop `formatter?: (v: number) => string`.

---

## 3. Funções Utilitárias Duplicadas

### 3.1 — formatCurrency / fmtBRL

| Local | Implementação |
|-------|---------------|
| `web/src/lib/format.ts` | `fmtBRL(v)` — usa `Intl.NumberFormat` com `style: "currency"` |
| `web/src/app/bi/types/index.ts` | `formatCurrency(v)` — `"R$ " + toLocaleString("pt-BR")` |
| `web/src/app/fiscal/types/index.ts` | `formatCurrency(v)` — `"R$ " + toLocaleString("pt-BR")` |
| `web/src/app/dashboard/page.tsx:47` | `fmtBRL(v)` — `"R$ " + toLocaleString("pt-BR")` |
| `web/src/app/metrics/page.tsx:9-10` | `fmtBRL(v)` — versão compacta com `k` |

**Impacto:** 5 implementações de formatação de moeda. `lib/format.ts` usa `Intl.NumberFormat` (padrão correto), as demais concatenam manualmente `"R$ "`. Se o locale mudar, precisa alterar em 5 lugares.

**Ação:** Eliminar duplicações. `lib/format.ts` já é o SSOT. Exportar `fmtBRL` e `fmtBRLCompact`. Remover `formatCurrency` do BI e Fiscal, importar de `@/lib/format`.

---

### 3.2 — SubItem (tipo)

| Local | Estrutura |
|-------|-----------|
| `web/src/app/cadastros/_components/SidebarLayout.tsx:5` | `interface SubItem { key: string; label: string; children?: SubItem[] }` |
| `web/src/app/financeiro/_components/FluxoCaixaTab.tsx:30` | `interface SubItem { key: string; label: string; children?: SubItem[] }` — **idêntico** |

**Ação:** Mover para `web/src/lib/types/ui.ts`.

---

## 4. Tabela Resumo

| # | Entidade | Módulo Fonte (SSOT) | Módulos que duplicam | Status | Ação Recomendada |
|---|----------|---------------------|----------------------|--------|------------------|
| 1 | `NotaFiscal` + constantes | `BlingFinancialTab.tsx` | `fiscal/types/index.ts` (cópia exata) | 🔴 Crítico | Mover para `lib/types/domain.ts` |
| 2 | `Product` / `Produto` | `api.ts` (`Product`) | BI (`ProdutoVenda`), PDV (`CartItem`), BlingOrders (`itens`), Bling (`BlingProduct`) | 🔴 Crítico | Hierarquia com `IProductBase` em `domain.ts` |
| 3 | `Conta` (Pagar/Receber) | Nenhum (sem SSOT) | `ReceberTab`, `PagarTab`, `BlingFinancialTab`, `api.ts` (`BlingReceivable`) | 🔴 Crítico | Criar `ContaFinanceira` base, estender para Pagar/Receber |
| 4 | `Pedido` / `Order` | `api.ts` (`BlingOrder`) | `BlingOrdersTab` (`Pedido`) | 🟡 Alto | Unificar em `domain.ts`, mapear wire→domain |
| 5 | `formatCurrency` / `fmtBRL` | `lib/format.ts` | BI, Fiscal, Dashboard, Metrics (4 duplicações) | 🔴 Crítico | Remover duplicações, importar de `lib/format` |
| 6 | `PageHeader` | `fiscal/_components/` | `bi/_components/` (cópia exata) | 🟡 Alto | Mover para `app/_components/` |
| 7 | `KpiCard` + `KpiMetric` | `fiscal/_components/` | BI (`_components/`), Dashboard (inline) | 🟡 Alto | Unificar em `app/_components/KpiCard.tsx` |
| 8 | `SubmenuItem` + `SubmenuCard` | `fiscal/` | `bi/types/`, BI page (inline), Compras (inline) | 🟡 Alto | Mover para `app/_components/SubmenuCard.tsx` |
| 9 | `TabBar` + `TabOption` | `fiscal/_components/` | BI (inline), Bling (inline), Produtos (inline) | 🟡 Alto | Mover para `app/_components/TabBar.tsx` |
| 10 | `StatusBadge` | `fiscal/_components/` | Financeiro (6 tabs), Bling (2 tabs), Tabelas, Clientes | 🟡 Alto | Mover para `app/_components/StatusBadge.tsx` |
| 11 | `DataTable` + `Column` | `fiscal/` | `cadastros/CrudPanel`, Financeiro (inline tables) | 🟡 Alto | Unificar em `app/_components/DataTable.tsx` |
| 12 | `ErrorAlert` | `fiscal/_components/` | Dashboard, Produtos, múltiplas páginas (inline) | 🟡 Médio | Mover para `app/_components/ErrorAlert.tsx` |
| 13 | `LoadingState` | `fiscal/_components/` | Todas as páginas (inline) | 🟡 Médio | Mover para `app/_components/LoadingState.tsx` |
| 14 | `ChartTooltip` | Nenhum | Dashboard, BI/Vendas, BI/Forecast, Metrics (4 inline) | 🟡 Médio | Criar `app/_components/ChartTooltip.tsx` |
| 15 | `Loja` | Nenhum (sem SSOT) | Metrics (type), Bling (id/nome inline), Product (estoque_lojas) | 🟡 Médio | Criar `Loja` em `domain.ts` |
| 16 | `Cliente` / `Contato` | Nenhum (sem SSOT) | 6 locais diferentes como string ou objeto inline | 🔴 Crítico | Criar `Cliente` e `Contato` em `domain.ts` |
| 17 | `Fornecedor` | Nenhum (sem SSOT) | PagarTab (string), FornecedoresTab (colunas sem tipo) | 🟡 Médio | Criar `Fornecedor` em `domain.ts` |
| 18 | `SubItem` | `cadastros/SidebarLayout` | `financeiro/FluxoCaixaTab` (idêntico) | 🟢 Baixo | Mover para `lib/types/ui.ts` |

---

## 5. Plano de Refatoração (Ordem Recomendada)

### Fase 1 — Infraestrutura de Tipos (sem quebrar nada)
1. Criar `web/src/lib/types/domain.ts` — tipos de domínio puros
2. Criar `web/src/lib/types/ui.ts` — tipos de interface
3. Mover `formatCurrency`/`fmtBRL` → consolidar em `lib/format.ts`
4. Remover duplicações de `formatCurrency` no BI e Fiscal

### Fase 2 — Componentes Compartilhados
5. Mover `PageHeader`, `KpiCard`, `TabBar`, `StatusBadge`, `DataTable`, `ErrorAlert`, `LoadingState`, `SubmenuCard`, `ChartTooltip` para `web/src/app/_components/`
6. Atualizar imports no BI e Fiscal
7. Migrar Dashboard, Financeiro, Cadastros, Bling para usar componentes compartilhados

### Fase 3 — Entidades de Domínio
8. Consolidar `NotaFiscal` → `lib/types/domain.ts`
9. Consolidar `Product`/`BlingProduct`/`ProdutoVenda`/`CartItem` → hierarquia em `domain.ts`
10. Criar `ContaFinanceira` base → unificar Pagar/Receber
11. Consolidar `Pedido`/`BlingOrder` → `domain.ts` + mapper
12. Criar `Cliente`, `Contato`, `Fornecedor`, `Loja` → `domain.ts`

### Fase 4 — Limpeza Final
13. Remover `types/index.ts` do BI e Fiscal (vazios após migração)
14. Remover `_components/` duplicados do BI e Fiscal
15. TypeScript check global

---

## 6. Estrutura Alvo

```
web/src/
  lib/
    types/
      domain.ts          ← Todas as entidades de negócio
      ui.ts              ← Tipos de componentes UI
    format.ts            ← ✅ Já é o SSOT de formatação
  app/
    _components/
      PageHeader.tsx     ← Unificado
      KpiCard.tsx        ← Unificado
      SubmenuCard.tsx    ← Unificado
      TabBar.tsx         ← Unificado
      StatusBadge.tsx    ← Unificado
      DataTable.tsx      ← Unificado
      ErrorAlert.tsx     ← Unificado
      LoadingState.tsx   ← Unificado
      ChartTooltip.tsx   ← Novo, unificado
    bi/
      page.tsx           ← Importa de _components/ e lib/types/
      vendas/ page.tsx
      indicadores/ page.tsx
      forecast/ page.tsx
      ml/ page.tsx
    fiscal/
      page.tsx           ← Importa de _components/ e lib/types/
      notas/ page.tsx
      tributos/ page.tsx
      obrigacoes/ page.tsx
      tabelas/ page.tsx
    financeiro/          ← Migrado para usar DataTable, StatusBadge
    cadastros/           ← Migrado para usar DataTable, StatusBadge
    dashboard/           ← Migrado para usar KpiCard, ErrorAlert, ChartTooltip
    integracoes/bling/   ← Migrado para usar TabBar, StatusBadge
```

---

**Total de linhas a eliminar:** ~350 linhas de código duplicado (componentes + tipos + funções).
**Total de arquivos a eliminar:** ~12 arquivos (`_components/` + `types/` duplicados no BI e Fiscal).
