# Estoque — Frente 1: Elimina Dados Fabricados Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir os números fabricados (`Math.random()`) em `/estoque/depositos` por KPIs reais (SKUs, valor, itens em baixo estoque), e remover `/estoque/inventario` (duplicado de Contagem Cíclica, 100% mock, sem backend).

**Architecture:** Backend ganha uma função nova (`kpis_por_deposito()`) ao lado de `giro`/`ruptura`/`cobertura` em `core/estoque_analise.py`, reaproveitando as mesmas tabelas (`estoque_lojas`, `catalogo_produtos`, `produtos_loja`) e o mesmo critério de "baixo estoque" que `ruptura()` já usa — só agregado por depósito Bling em vez de por SKU. O mapeamento loja→depósito já existe (`lojas.bling_id`, a mesma coluna que alimenta `GET /api/lojas/deposito-map`), então a query faz `JOIN lojas` direto, sem chamar esse endpoint como um passo separado. Frontend combina a lista real de depósitos do Bling (já buscada hoje) com os KPIs calculados, tratando depósito sem loja mapeada como "sem dado" (`—`), nunca como zero.

**Tech Stack:** Flask + asyncpg (backend), Next.js/React + TypeScript (frontend).

## Global Constraints

- Nenhuma tabela nova no Postgres — "Depósito" é o conceito que já existe no Bling, mapeado via `lojas.bling_id`.
- Depósito sem loja ativa mapeada mostra `—` (sem dado), nunca `0` — os dois estados são diferentes (depósito vazio de verdade vs. depósito sem rastreio).
- `baixo_estoque` usa o mesmo critério de `core/estoque_analise.py::ruptura()`: `SUM(quantidade) < COALESCE(MAX(produtos_loja.estoque_minimo), MAX(catalogo_produtos.estoque_minimo), 0)`.
- Valor de estoque usa `catalogo_produtos.preco_custo` (`DECIMAL(12,2)`, nullable — trata ausência como 0).
- Rota nova exige `@requer_permissao("estoque.ver")` (mesma permissão das demais rotas de leitura de `routes/estoque.py`).
- `custos/page.tsx` não é tocado nesta frente (demanda já documentada em `docs/DEMANDAS.md`).

---

### Task 1: Backend — `kpis_por_deposito()` em `core/estoque_analise.py`

**Files:**
- Modify: `hermes_agents/core/estoque_analise.py` (adicionar função nova, ao lado de `ruptura()`)
- Test: `hermes_agents/tests/test_estoque_analise.py` (adicionar classe nova)

**Interfaces:**
- Produces: `kpis_por_deposito() -> list[dict]`, cada dict com `{"deposito_id": int, "skus": int, "valor": float, "baixo_estoque": int}`. Retorna `[]` em erro de banco. Um depósito só aparece no resultado se tiver pelo menos uma loja ativa com `bling_id` associada e pelo menos um SKU em `estoque_lojas` — ausência do `deposito_id` no resultado é o sinal de "sem dado" que a Task 3 (rota) e a Task 5 (frontend) consomem.

- [ ] **Step 1: Escrever os testes (falhando)**

Adicionar ao final de `hermes_agents/tests/test_estoque_analise.py`, antes de `if __name__ == "__main__":` (se o arquivo tiver esse bloco — senão, no final do arquivo):

```python
class TestKpisPorDeposito(unittest.TestCase):
    def test_sem_linhas_retorna_lista_vazia(self):
        async def fake_fetch(query, *params):
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.kpis_por_deposito()
        self.assertEqual(resultado, [])

    def test_agrega_skus_e_valor_de_um_deposito(self):
        async def fake_fetch(query, *params):
            return [
                {"deposito_id": 10, "sku": "A", "saldo": 5, "minimo": 0, "preco_custo": 20.0},
                {"deposito_id": 10, "sku": "B", "saldo": 3, "minimo": 0, "preco_custo": 10.0},
            ]
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.kpis_por_deposito()
        self.assertEqual(resultado, [{"deposito_id": 10, "skus": 2, "valor": 130.0, "baixo_estoque": 0}])

    def test_saldo_abaixo_do_minimo_conta_em_baixo_estoque(self):
        async def fake_fetch(query, *params):
            return [{"deposito_id": 10, "sku": "A", "saldo": 2, "minimo": 5, "preco_custo": 0.0}]
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.kpis_por_deposito()
        self.assertEqual(resultado, [{"deposito_id": 10, "skus": 1, "valor": 0.0, "baixo_estoque": 1}])

    def test_dois_depositos_agregados_separadamente(self):
        async def fake_fetch(query, *params):
            return [
                {"deposito_id": 10, "sku": "A", "saldo": 5, "minimo": 0, "preco_custo": 1.0},
                {"deposito_id": 20, "sku": "A", "saldo": 5, "minimo": 0, "preco_custo": 1.0},
                {"deposito_id": 20, "sku": "B", "saldo": 5, "minimo": 0, "preco_custo": 1.0},
            ]
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.kpis_por_deposito()
        por_id = {r["deposito_id"]: r for r in resultado}
        self.assertEqual(por_id[10]["skus"], 1)
        self.assertEqual(por_id[20]["skus"], 2)

    def test_preco_custo_ausente_nao_quebra_soma(self):
        async def fake_fetch(query, *params):
            return [{"deposito_id": 10, "sku": "A", "saldo": 5, "minimo": 0, "preco_custo": 0.0}]
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.kpis_por_deposito()
        self.assertEqual(resultado[0]["valor"], 0.0)

    def test_erro_de_banco_retorna_lista_vazia(self):
        with patch("core.estoque_analise.get_db", side_effect=Exception("db down")):
            resultado = analise.kpis_por_deposito()
        self.assertEqual(resultado, [])
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_analise.py::TestKpisPorDeposito -v`
Expected: FAIL — `AttributeError: module 'core.estoque_analise' has no attribute 'kpis_por_deposito'`

- [ ] **Step 3: Implementar `kpis_por_deposito()`**

Em `hermes_agents/core/estoque_analise.py`, adicionar logo após a função `ruptura()` (procure o fim dela — depois do `return rows` final e antes da próxima função `cobertura`, se existir, ou no fim do arquivo):

```python
def kpis_por_deposito() -> list:
    """KPIs reais de estoque por deposito (SKUs, valor, itens em baixo
    estoque), agregados a partir de estoque_lojas + catalogo_produtos e
    atribuidos ao deposito Bling correspondente via lojas.bling_id — mesmo
    mapeamento usado por GET /api/lojas/deposito-map. Depositos Bling sem
    loja ativa mapeada (ex.: canais virtuais) nao aparecem no resultado;
    quem chama trata a ausencia como "sem dado", nunca como zero."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT l.bling_id AS deposito_id, e.sku,
                   SUM(e.quantidade) AS saldo,
                   COALESCE(MAX(pl.estoque_minimo), MAX(c.estoque_minimo), 0) AS minimo,
                   COALESCE(MAX(c.preco_custo), 0) AS preco_custo
            FROM estoque_lojas e
            JOIN lojas l ON l.id = e.loja_id
            JOIN catalogo_produtos c ON c.sku = e.sku
            LEFT JOIN produtos_loja pl ON pl.sku = e.sku AND pl.loja = e.loja
            WHERE l.bling_id IS NOT NULL AND l.ativa = TRUE
            GROUP BY l.bling_id, e.sku
        """)
        por_deposito: dict = {}
        for r in rows:
            dep = por_deposito.setdefault(r["deposito_id"], {
                "deposito_id": r["deposito_id"], "skus": 0, "valor": 0.0, "baixo_estoque": 0,
            })
            dep["skus"] += 1
            dep["valor"] += float(r["saldo"]) * float(r["preco_custo"])
            if float(r["saldo"]) < float(r["minimo"]):
                dep["baixo_estoque"] += 1
        return list(por_deposito.values())
    try:
        return run_async(_go())
    except Exception as e:
        _log_erro("estoque_analise.kpis_por_deposito", e)
        return []
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_analise.py -v`
Expected: PASS (todos, incluindo os pré-existentes de giro/ruptura/cobertura — nada foi tocado neles)

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/estoque_analise.py hermes_agents/tests/test_estoque_analise.py
git commit -m "feat: adiciona kpis_por_deposito com dado real de estoque"
```

---

### Task 2: Backend — rota `GET /api/estoque/depositos/kpis`

**Files:**
- Modify: `hermes_agents/routes/estoque.py` (adicionar rota nova, perto de `/analise/cobertura`)
- Test: `hermes_agents/tests/test_estoque_analise_rotas.py` (adicionar classe nova)

**Interfaces:**
- Consumes: `core.estoque_analise.kpis_por_deposito()` da Task 1.
- Produces: `GET /api/estoque/depositos/kpis` → `{"data": [{"deposito_id": int, "skus": int, "valor": float, "baixo_estoque": int}, ...]}`. Exige permissão `estoque.ver` (403 sem ela).

- [ ] **Step 1: Escrever os testes (falhando)**

Adicionar ao final de `hermes_agents/tests/test_estoque_analise_rotas.py`:

```python
class TestRotaDepositosKpis(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": "test-master-token-32-bytes-long!!"})
        self._env_patch.start()
        from flask import Flask
        from routes.estoque import estoque_bp
        app = Flask(__name__)
        app.register_blueprint(estoque_bp)
        self.client = app.test_client()

    def tearDown(self):
        self._env_patch.stop()

    def test_com_permissao_retorna_200_e_chave_data(self):
        headers = {"Authorization": "Bearer test-master-token-32-bytes-long!!"}
        with patch("core.estoque_analise.kpis_por_deposito", return_value=[{"deposito_id": 1, "skus": 2, "valor": 100.0, "baixo_estoque": 0}]):
            r = self.client.get("/api/estoque/depositos/kpis", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"data": [{"deposito_id": 1, "skus": 2, "valor": 100.0, "baixo_estoque": 0}]})

    def test_sem_permissao_nega(self):
        import core.rbac as rbac
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.estoque_analise.kpis_por_deposito") as mock_kpis:
            r = self.client.get("/api/estoque/depositos/kpis", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_kpis.assert_not_called()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_analise_rotas.py::TestRotaDepositosKpis -v`
Expected: FAIL — `404 NOT FOUND` (rota não existe ainda)

- [ ] **Step 3: Implementar a rota**

Em `hermes_agents/routes/estoque.py`, adicionar logo após a rota `/analise/cobertura` (depois do bloco `estoque_analise_cobertura`, antes de `/sugestao-rotacao`):

```python
@estoque_bp.route('/depositos/kpis', methods=['GET'])
def estoque_depositos_kpis():
    from core.estoque_analise import kpis_por_deposito
    from core.rbac import requer_permissao

    @requer_permissao("estoque.ver")
    def _go():
        return jsonify({"data": kpis_por_deposito()})
    return _go()
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_analise_rotas.py -v`
Expected: PASS (todos, incluindo os pré-existentes de giro/ruptura/cobertura)

- [ ] **Step 5: Rodar a suíte completa do módulo de estoque pra checar retrocompatibilidade**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_analise.py tests/test_estoque_analise_rotas.py -v`
Expected: PASS (todos)

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/estoque.py hermes_agents/tests/test_estoque_analise_rotas.py
git commit -m "feat: rota GET /api/estoque/depositos/kpis"
```

---

### Task 3: Frontend — `api.ts` (função `estoqueDepositosKpis`)

**Files:**
- Modify: `web/src/lib/api.ts` (adicionar função nova, perto de `listarBlingDepositos`)

**Interfaces:**
- Produces: `export async function estoqueDepositosKpis(): Promise<{ data: DepositoKpi[] }>`, onde `DepositoKpi = { deposito_id: number; skus: number; valor: number; baixo_estoque: number }` (interface exportada).
- Consumes (Task 5): `web/src/app/estoque/depositos/page.tsx` importa `estoqueDepositosKpis` e o tipo `DepositoKpi`.

- [ ] **Step 1: Adicionar a função em `api.ts`**

Em `web/src/lib/api.ts`, logo após a função `listarBlingDepositos` (por volta da linha 1435, depois do `}` de fechamento), adicionar:

```typescript
export interface DepositoKpi {
  deposito_id: number;
  skus: number;
  valor: number;
  baixo_estoque: number;
}

export async function estoqueDepositosKpis(): Promise<{ data: DepositoKpi[] }> {
  const res = await fetch("/api/estoque/depositos/kpis");
  if (!res.ok) return { data: [] };
  return res.json().catch(() => ({ data: [] }));
}
```

- [ ] **Step 2: Type-check**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros novos

- [ ] **Step 3: Commit**

```bash
git add web/src/lib/api.ts
git commit -m "feat: adiciona api.estoqueDepositosKpis"
```

---

### Task 4: Frontend — reescreve `depositos/page.tsx` com dado real

**Files:**
- Modify: `web/src/app/estoque/depositos/page.tsx` (reescrita completa)

**Interfaces:**
- Consumes: `listarBlingDepositos`, `estoqueDepositosKpis`, `type BlingDeposito`, `type DepositoKpi` de `@/lib/api` (Task 3); `formatCurrency` de `../types`; `PageHeader`, `KpiCard`, `DataTable`, `StatusBadge`, `LoadingState`, `ErrorAlert` de `@/app/_components/*` (já existiam, sem mudança).

- [ ] **Step 1: Reescrever o arquivo**

```tsx
"use client";

import { useState, useEffect } from "react";
import type { KpiMetric, Column } from "@/lib/types/ui";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import DataTable from "@/app/_components/DataTable";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import { formatCurrency } from "../types";
import { listarBlingDepositos, estoqueDepositosKpis, type BlingDeposito, type DepositoKpi } from "@/lib/api";

interface DepositoRow {
  nome: string;
  codigo: string;
  ativo: boolean;
  skus: number | null;
  valor: number | null;
  baixoEstoque: number | null;
}

const SEM_DADO_TITLE = "Sem estoque rastreado neste depósito";

const COLUMNS: Column<DepositoRow>[] = [
  { key: "nome", label: "Depósito", render: (v) => <span className="text-neutral-200">{v as string}</span> },
  { key: "codigo", label: "Código", render: (v) => <span className="font-mono text-neutral-400 text-[11px]">{v as string}</span> },
  {
    key: "skus", label: "SKUs", align: "center",
    render: (v) => v === null
      ? <span className="text-neutral-600" title={SEM_DADO_TITLE}>—</span>
      : <span className="font-mono text-neutral-200">{v as number}</span>,
  },
  {
    key: "valor", label: "Valor Estoque", align: "right",
    render: (v) => v === null
      ? <span className="text-neutral-600" title={SEM_DADO_TITLE}>—</span>
      : <span className="font-mono text-emerald-400">{formatCurrency(v as number)}</span>,
  },
  {
    key: "baixoEstoque", label: "Baixo Estoque", align: "center",
    render: (v) => v === null
      ? <span className="text-neutral-600" title={SEM_DADO_TITLE}>—</span>
      : (v as number) > 0
        ? <StatusBadge label={String(v)} variant="warning" />
        : <span className="text-neutral-500">0</span>,
  },
  { key: "ativo", label: "Status", render: (v, row) => <StatusBadge label={row.ativo ? "Ativo" : "Inativo"} variant={row.ativo ? "success" : "neutral"} /> },
];

export default function DepositosPage() {
  const [depositos, setDepositos] = useState<BlingDeposito[]>([]);
  const [kpis, setKpis] = useState<DepositoKpi[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listarBlingDepositos(), estoqueDepositosKpis()])
      .then(([depRes, kpiRes]) => {
        setDepositos(depRes.data || []);
        setKpis(kpiRes.data || []);
      })
      .catch(e => setError(e instanceof Error ? e.message : "Erro ao carregar depósitos"))
      .finally(() => setLoading(false));
  }, []);

  const kpisPorId = Object.fromEntries(kpis.map(k => [k.deposito_id, k]));

  const rows: DepositoRow[] = depositos.map(d => {
    const kpi = kpisPorId[d.id];
    return {
      nome: d.descricao,
      codigo: String(d.id),
      ativo: d.situacao === "A",
      skus: kpi ? kpi.skus : null,
      valor: kpi ? kpi.valor : null,
      baixoEstoque: kpi ? kpi.baixo_estoque : null,
    };
  });

  const rowsComDado = rows.filter(r => r.skus !== null);
  const kpiCards: KpiMetric[] = [
    { label: "Depósitos Ativos", value: String(rows.filter(r => r.ativo).length), color: "text-emerald-400" },
    { label: "Total SKUs", value: String(rowsComDado.reduce((s, r) => s + (r.skus ?? 0), 0)), color: "text-blue-400" },
    { label: "Valor Total", value: formatCurrency(rowsComDado.reduce((s, r) => s + (r.valor ?? 0), 0)), color: "text-indigo-400" },
    { label: "Itens Baixo Estoque", value: String(rowsComDado.reduce((s, r) => s + (r.baixoEstoque ?? 0), 0)), color: "text-amber-400" },
  ];

  return (
    <div className="p-6 space-y-4">
      <PageHeader title="Depósitos" subtitle="Depósitos do Bling com estoque real das lojas vinculadas" />
      {loading ? (
        <LoadingState message="Carregando depósitos..." />
      ) : error ? (
        <ErrorAlert message={error} />
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {kpiCards.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
          </div>
          <DataTable columns={COLUMNS} data={rows} keyExtractor={r => r.codigo} countLabel={`${rows.length} depósitos`} />
        </>
      )}
    </div>
  );
}
```

Nota: a coluna "Tipo"/"Loja"/"Endereço" e o array `DEPOSITOS_MOCK` (proprio/terceiro/virtual, endereço com corredor/estante) saem — essa granularidade não tem fonte de dado real hoje (registrado como fora de escopo na spec). A tabela passa a mostrar só o que vem de verdade do Bling + o cálculo real de estoque.

- [ ] **Step 2: Type-check**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros

- [ ] **Step 3: Commit**

```bash
git add web/src/app/estoque/depositos/page.tsx
git commit -m "feat: Depositos mostra KPIs reais de estoque em vez de Math.random()"
```

---

### Task 5: Remove Inventário e os mocks órfãos

**Files:**
- Delete: `web/src/app/estoque/inventario/page.tsx`
- Delete: `web/src/app/estoque/data/inventario.ts`
- Delete: `web/src/app/estoque/data/depositos.ts`

**Interfaces:** N/A (remoção pura).

- [ ] **Step 1: Confirmar que nada mais importa esses arquivos**

Run (a partir da raiz do repo): `grep -rn "estoque/data/inventario\|estoque/data/depositos\|INVENTARIOS_MOCK\|gerarItensInventario\|DEPOSITOS_MOCK\|totaisPorDeposito" web/src --include="*.tsx" --include="*.ts"`
Expected: nenhum resultado fora dos próprios arquivos sendo removidos e de `web/src/app/estoque/inventario/page.tsx`/`web/src/app/estoque/depositos/page.tsx` (que a Task 4 já reescreveu sem essas referências). Se aparecer qualquer outro arquivo, pare e investigue antes de apagar.

- [ ] **Step 2: Apagar os arquivos**

```bash
git rm web/src/app/estoque/inventario/page.tsx
git rm web/src/app/estoque/data/inventario.ts
git rm web/src/app/estoque/data/depositos.ts
```

- [ ] **Step 3: Type-check e build completo**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: build passa sem erros. `/estoque/inventario` deixa de existir como rota gerada (confirme no output do build que a rota não é mais listada, ou navegue manualmente depois do deploy e confirme 404).

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor: remove Inventario (duplicado de Contagem Ciclica, sem backend)"
```

---

## Self-Review

**Spec coverage:** Depósitos com dado real (Tasks 1-4), Inventário removido (Task 5), Custos intocado (nenhuma task toca nele, conforme a spec) — todos os itens da spec cobertos.

**Placeholder scan:** nenhum "TBD"/"implementar depois" — todo código é completo e executável.

**Type consistency:** `DepositoKpi` (Task 3, `api.ts`) tem os mesmos campos que `kpis_por_deposito()` retorna (Task 1: `deposito_id, skus, valor, baixo_estoque`) e que a rota da Task 2 repassa sem transformação (`jsonify({"data": kpis_por_deposito()})`). `depositos/page.tsx` (Task 4) usa exatamente esses nomes de campo (`kpi.deposito_id`, `kpi.skus`, `kpi.valor`, `kpi.baixo_estoque`) ao consumir `estoqueDepositosKpis()`.
