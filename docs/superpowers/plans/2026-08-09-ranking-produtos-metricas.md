# Ranking de Produtos — Métricas Novas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estender o modal "Ranking de produtos" do `/dashboard` de 3 pra 8 métricas de produto, agrupadas em 3 categorias (Vendas, Lucratividade, Estoque), tudo dado real.

**Architecture:** 2 funções novas em `core/relatorios.py` (mesmo padrão de `ranking_produtos()` já existente: query única contra `vendas_pedidos`/`vendas_itens`, sem union com `pdv_vendas` morto), 3 rotas novas em `routes/relatorios.py`, tipos+client novos em `web/src/lib/api.ts`, e reescrita de `RankingProdutosModal.tsx` com seletor de categoria + abas por categoria.

**Tech Stack:** Flask + asyncpg (backend), Next.js/React/TypeScript (frontend), Postgres.

## Global Constraints

- Loja física: vendas vêm do i9Logic (`origem='i9logic_pdv'` em `vendas_pedidos`) — `pdv_vendas`/`pdv_itens` está morto, NÃO usar em nenhuma query nova.
- Loja virtual: vendas vêm do sync Shopee, mesma tabela `vendas_pedidos`/`vendas_itens`.
- Estoque (`estoque_lojas`) é fonte única de saldo pros dois tipos de loja.
- Produtos de loja física sem `preco_custo` cadastrado (auditoria em andamento) devem aparecer sinalizados, nunca com lucro/margem inventado — mesmo padrão `custo_cadastrado` já usado em `ranking_produtos()`.
- Sem número fabricado: percentual de crescimento sem base de comparação (`anterior=0`) é `None`/"Novo", nunca "+∞%" ou "0%".
- Nenhuma mudança em `pdv_vendas`, `curvas()` (já inclui venda física corretamente), ou union legado dentro de `ranking_produtos()` — fora de escopo.

---

### Task 1: Backend — `produtos_tendencia()` e `risco_ruptura()` em `core/relatorios.py`

**Files:**
- Modify: `hermes_agents/core/relatorios.py` (adiciona as 2 funções logo depois de `ranking_produtos`, antes da seção `# ── 19. Financeiro ──`)
- Test: `hermes_agents/tests/test_relatorios.py`

**Interfaces:**
- Produces: `core.relatorios.produtos_tendencia(dias: int = 30) -> list[dict]` com chaves `sku, descricao, quantidade_atual, quantidade_anterior, crescimento_pct (float | None)`.
- Produces: `core.relatorios.risco_ruptura(dias: int = 30) -> list[dict]` com chaves `sku, descricao, estoque_atual, quantidade_vendida, velocidade_diaria, dias_restantes`, já ordenado por `dias_restantes` ascendente, limitado a 15 itens.

- [ ] **Step 1: Escrever os testes que falham**

Em `hermes_agents/tests/test_relatorios.py`, adicionar antes da linha `if __name__=="__main__":unittest.main(verbosity=2)`:

```python
    @patch("core.relatorios.get_db")
    def test_produtos_tendencia_calcula_crescimento(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "SKU-A", "descricao": "Produto A", "qtd_atual": 30.0, "qtd_anterior": 10.0},
        ]
        mock_get_db.return_value = fake_db

        itens = rel.produtos_tendencia(30)

        self.assertEqual(len(itens), 1)
        item = itens[0]
        self.assertEqual(item["sku"], "SKU-A")
        self.assertEqual(item["quantidade_atual"], 30.0)
        self.assertEqual(item["quantidade_anterior"], 10.0)
        self.assertEqual(item["crescimento_pct"], 200.0)  # (30-10)/10*100

    @patch("core.relatorios.get_db")
    def test_produtos_tendencia_sem_base_anterior_nao_inventa_percentual(self, mock_get_db):
        """Produto novo (sem venda no periodo anterior) nao pode aparecer com
        '+inf%' ou '0%' — sem base de comparacao, o crescimento fica None."""
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "SKU-NOVO", "descricao": "Produto Novo", "qtd_atual": 15.0, "qtd_anterior": 0.0},
        ]
        mock_get_db.return_value = fake_db

        itens = rel.produtos_tendencia(30)

        self.assertIsNone(itens[0]["crescimento_pct"])

    @patch("core.relatorios.get_db")
    def test_produtos_tendencia_queda_a_zero_fica_menos_100(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "SKU-B", "descricao": "Produto B", "qtd_atual": 0.0, "qtd_anterior": 20.0},
        ]
        mock_get_db.return_value = fake_db

        itens = rel.produtos_tendencia(30)

        self.assertEqual(itens[0]["crescimento_pct"], -100.0)

    @patch("core.relatorios.get_db")
    def test_produtos_tendencia_sem_venda_em_nenhum_periodo_nao_aparece(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "SKU-C", "descricao": "Produto C", "qtd_atual": 0.0, "qtd_anterior": 0.0},
        ]
        mock_get_db.return_value = fake_db

        self.assertEqual(rel.produtos_tendencia(30), [])

    @patch("core.relatorios.get_db")
    def test_risco_ruptura_calcula_dias_restantes(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "SKU-D", "descricao": "Produto D", "qtd_vendida": 30.0, "estoque_atual": 15.0},
        ]
        mock_get_db.return_value = fake_db

        itens = rel.risco_ruptura(30)

        self.assertEqual(len(itens), 1)
        item = itens[0]
        self.assertEqual(item["velocidade_diaria"], 1.0)  # 30/30
        self.assertEqual(item["dias_restantes"], 15.0)  # 15/1.0

    @patch("core.relatorios.get_db")
    def test_risco_ruptura_exclui_sem_venda_ou_sem_estoque(self, mock_get_db):
        """Produto sem venda no periodo (velocidade=0) ou ja zerado (estoque=0)
        NAO e' risco de ruptura — sao os casos de 'parado' e 'ruptura ja
        consumada', metricas diferentes, nao podem se sobrepor aqui."""
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "SEM-VENDA", "descricao": "Sem venda", "qtd_vendida": 0.0, "estoque_atual": 50.0},
            {"sku": "SEM-ESTOQUE", "descricao": "Sem estoque", "qtd_vendida": 20.0, "estoque_atual": 0.0},
        ]
        mock_get_db.return_value = fake_db

        self.assertEqual(rel.risco_ruptura(30), [])

    @patch("core.relatorios.get_db")
    def test_risco_ruptura_ordena_por_dias_restantes_ascendente(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "URGENTE", "descricao": "Urgente", "qtd_vendida": 30.0, "estoque_atual": 3.0},  # 3 dias
            {"sku": "FOLGA", "descricao": "Com folga", "qtd_vendida": 30.0, "estoque_atual": 30.0},  # 30 dias
        ]
        mock_get_db.return_value = fake_db

        itens = rel.risco_ruptura(30)

        self.assertEqual(itens[0]["sku"], "URGENTE")
        self.assertEqual(itens[1]["sku"], "FOLGA")
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_relatorios.py -v -k "tendencia or ruptura"`
Expected: FAIL — `AttributeError: module 'core.relatorios' has no attribute 'produtos_tendencia'` (e equivalente pra `risco_ruptura`).

- [ ] **Step 3: Implementar as duas funções**

Em `hermes_agents/core/relatorios.py`, localizar a linha em branco logo após o fim de `ranking_produtos` (depois de `except Exception as e: return []` que fecha essa função, linha 417 na numeração atual) e antes do comentário `# ── 19. Financeiro ──`. Inserir:

```python

# ── 18c. Tendencia e risco de ruptura por produto ──

def produtos_tendencia(dias=30):
    """Crescimento de vendas por SKU: periodo atual vs periodo anterior de
    mesmo tamanho. anterior=0 com atual>0 vira crescimento_pct=None (produto
    novo/reativado, sem base de comparacao pra inventar percentual) — mesma
    filosofia anti-numero-fabricado de core/bi.py::_variacao()."""
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"""
            SELECT vi.sku,
                   MAX(vi.descricao) AS descricao,
                   SUM(CASE WHEN vp.data >= CURRENT_DATE - $1::int THEN vi.quantidade ELSE 0 END) AS qtd_atual,
                   SUM(CASE WHEN vp.data < CURRENT_DATE - $1::int THEN vi.quantidade ELSE 0 END) AS qtd_anterior
            FROM vendas_itens vi JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE vp.data >= CURRENT_DATE - $1::int * 2 AND vp.status != 'cancelado'
              AND vi.sku IS NOT NULL AND vi.sku != ''
            GROUP BY vi.sku
        """, dias)
        return [dict(r) for r in (rows or [])]
    try:
        linhas = run_async(_go())
    except Exception as e:
        return []

    resultado = []
    for r in linhas:
        atual = float(r["qtd_atual"] or 0)
        anterior = float(r["qtd_anterior"] or 0)
        if atual == 0 and anterior == 0:
            continue
        crescimento = round((atual - anterior) / anterior * 100, 1) if anterior else None
        resultado.append({
            "sku": r["sku"], "descricao": r["descricao"] or r["sku"],
            "quantidade_atual": round(atual, 2), "quantidade_anterior": round(anterior, 2),
            "crescimento_pct": crescimento,
        })
    return resultado


def risco_ruptura(dias=30):
    """Produtos vendendo bem MAS com estoque acabando — velocidade de venda
    alta, estoque baixo. Diferente de 'parado' (zero venda) e de rupturas()
    (zero estoque, ja consumada) — aqui e' o alerta ANTES de zerar."""
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"""
            SELECT vi.sku, MAX(vi.descricao) AS descricao, SUM(vi.quantidade) AS qtd_vendida,
                   (SELECT COALESCE(SUM(e.quantidade), 0) FROM estoque_lojas e WHERE e.sku = vi.sku) AS estoque_atual
            FROM vendas_itens vi JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE vp.data >= CURRENT_DATE - $1::int AND vp.status != 'cancelado'
              AND vi.sku IS NOT NULL AND vi.sku != ''
            GROUP BY vi.sku
        """, dias)
        return [dict(r) for r in (rows or [])]
    try:
        linhas = run_async(_go())
    except Exception as e:
        return []

    resultado = []
    for r in linhas:
        qtd_vendida = float(r["qtd_vendida"] or 0)
        estoque_atual = float(r["estoque_atual"] or 0)
        velocidade_diaria = qtd_vendida / dias
        if velocidade_diaria <= 0 or estoque_atual <= 0:
            continue
        resultado.append({
            "sku": r["sku"], "descricao": r["descricao"] or r["sku"],
            "estoque_atual": round(estoque_atual, 2), "quantidade_vendida": round(qtd_vendida, 2),
            "velocidade_diaria": round(velocidade_diaria, 3),
            "dias_restantes": round(estoque_atual / velocidade_diaria, 1),
        })
    resultado.sort(key=lambda p: p["dias_restantes"])
    return resultado[:15]

```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_relatorios.py -v -k "tendencia or ruptura"`
Expected: PASS (7 testes).

- [ ] **Step 5: Rodar a suíte completa de relatorios pra garantir que nada quebrou**

Run: `cd hermes_agents && python -m pytest tests/test_relatorios.py -v`
Expected: PASS (todos, incluindo os 3 testes de `ranking_produtos` já existentes).

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/relatorios.py hermes_agents/tests/test_relatorios.py
git commit -m "feat: adiciona produtos_tendencia e risco_ruptura aos relatorios de produto"
```

---

### Task 2: Backend — rotas `/estoque-parado`, `/produtos-tendencia`, `/risco-ruptura`

**Files:**
- Modify: `hermes_agents/routes/relatorios.py` (adiciona as 3 rotas logo após `/ranking-produtos`, linha 172-173 na numeração atual)
- Test: `hermes_agents/tests/test_all_endpoints.py`

**Interfaces:**
- Consumes: `core.bi.estoque_parado(dias: int, limite: int) -> list[dict]` (já existe), `core.relatorios.produtos_tendencia(dias: int) -> list[dict]` e `core.relatorios.risco_ruptura(dias: int) -> list[dict]` (Task 1).
- Produces: `GET /api/relatorios/estoque-parado?dias=&limite=`, `GET /api/relatorios/produtos-tendencia?dias=`, `GET /api/relatorios/risco-ruptura?dias=` — todas sem RBAC decorator (mesmo padrão de `/ranking-produtos`), retornam a lista direto como JSON (sem envelope `{itens:...}` — só `/ranking-produtos` e `/curvas` usam envelope, essas 3 novas não).

- [ ] **Step 1: Adicionar as rotas**

Em `hermes_agents/routes/relatorios.py`, localizar (linhas 168-173):
```python
@relatorios_bp.route("/ranking-produtos", methods=["GET"])
def rel_ranking_produtos():
    from core.relatorios import ranking_produtos
    dias = request.args.get("dias", 30, type=int)
    return jsonify({"itens": ranking_produtos(dias), "periodo_dias": dias})

```
Substituir por (mantém o bloco original, acrescenta as 3 rotas novas logo depois):
```python
@relatorios_bp.route("/ranking-produtos", methods=["GET"])
def rel_ranking_produtos():
    from core.relatorios import ranking_produtos
    dias = request.args.get("dias", 30, type=int)
    return jsonify({"itens": ranking_produtos(dias), "periodo_dias": dias})


@relatorios_bp.route("/estoque-parado", methods=["GET"])
def rel_estoque_parado():
    from core.bi import estoque_parado
    dias = request.args.get("dias", 60, type=int)
    limite = request.args.get("limite", 15, type=int)
    return jsonify(estoque_parado(dias, limite))


@relatorios_bp.route("/produtos-tendencia", methods=["GET"])
def rel_produtos_tendencia():
    from core.relatorios import produtos_tendencia
    dias = request.args.get("dias", 30, type=int)
    return jsonify(produtos_tendencia(dias))


@relatorios_bp.route("/risco-ruptura", methods=["GET"])
def rel_risco_ruptura():
    from core.relatorios import risco_ruptura
    dias = request.args.get("dias", 30, type=int)
    return jsonify(risco_ruptura(dias))

```

- [ ] **Step 2: Adicionar testes de rota (smoke — rota existe e responde)**

Em `hermes_agents/tests/test_all_endpoints.py`, localizar a classe `TestRelatoriosEndpoints`, atualizar a docstring (linha 139) de:
```python
    """Todos os 20 endpoints de /api/relatorios/*."""
```
para:
```python
    """Todos os 23 endpoints de /api/relatorios/*."""
```

Localizar o método `test_dre_por_loja` (linhas 218-219, o último método da classe antes de `class TestLojasEndpoints`):
```python
    def test_dre_por_loja(self):
        self._assert_200_json(self.client.get("/api/relatorios/dre-por-loja?dias=30", headers=self.headers), "dre-por-loja")

```
Substituir por (mantém o método original, acrescenta os 3 novos logo depois, mesma linha em branco antes de `class TestLojasEndpoints`):
```python
    def test_dre_por_loja(self):
        self._assert_200_json(self.client.get("/api/relatorios/dre-por-loja?dias=30", headers=self.headers), "dre-por-loja")

    def test_estoque_parado(self):
        self._assert_200_json(self.client.get("/api/relatorios/estoque-parado?dias=60", headers=self.headers), "estoque-parado")

    def test_produtos_tendencia(self):
        self._assert_200_json(self.client.get("/api/relatorios/produtos-tendencia?dias=30", headers=self.headers), "produtos-tendencia")

    def test_risco_ruptura(self):
        self._assert_200_json(self.client.get("/api/relatorios/risco-ruptura?dias=30", headers=self.headers), "risco-ruptura")

```

- [ ] **Step 3: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_all_endpoints.py -v -k "TestRelatoriosEndpoints"`
Expected: PASS (23 testes — 20 antigos + 3 novos — todos 200 ou 500 conforme `_assert_200_json`, nunca 404).

- [ ] **Step 4: Commit**

```bash
git add hermes_agents/routes/relatorios.py hermes_agents/tests/test_all_endpoints.py
git commit -m "feat: expoe rotas de estoque-parado, produtos-tendencia e risco-ruptura"
```

---

### Task 3: Frontend — tipos e client em `web/src/lib/api.ts`

**Files:**
- Modify: `web/src/lib/api.ts`

**Interfaces:**
- Consumes: rotas da Task 2 (`/api/relatorios/estoque-parado`, `/produtos-tendencia`, `/risco-ruptura`) e `/api/relatorios/curvas` (já existente, sem client function ainda).
- Produces: `api.relatorioEstoqueParado(dias, limite?)`, `api.relatorioProdutosTendencia(dias)`, `api.relatorioRiscoRuptura(dias)`, `api.relatorioCurvas(dias)` — todas retornando Promise tipada, consumidas pela Task 4.

- [ ] **Step 1: Adicionar os tipos**

Em `web/src/lib/api.ts`, localizar o fim da interface `RankingProdutoItem` (linhas 2177-2188):
```typescript
export interface RankingProdutoItem {
  sku: string;
  descricao: string;
  quantidade: number;
  receita: number;
  custo: number;
  comissao: number;
  frete: number;
  lucro: number;
  margem_pct: number;
  custo_cadastrado: boolean;
}
```
Acrescentar logo depois:
```typescript

export interface EstoqueParadoItem {
  sku: string;
  nome: string;
  quantidade: number;
  valor_imobilizado: number;
  dias_sem_venda: number;
}

export interface ProdutoTendenciaItem {
  sku: string;
  descricao: string;
  quantidade_atual: number;
  quantidade_anterior: number;
  crescimento_pct: number | null;
}

export interface RiscoRupturaItem {
  sku: string;
  descricao: string;
  estoque_atual: number;
  quantidade_vendida: number;
  velocidade_diaria: number;
  dias_restantes: number;
}

export interface CurvaAbcItem {
  sku: string;
  descricao: string;
  valor_total: number;
  qtd: number;
  pct: number;
  pct_acum: number;
  classe: "A" | "B" | "C";
}

export interface CurvaAbcResponse {
  total_valor: number;
  total_itens: number;
  itens: CurvaAbcItem[];
}
```

- [ ] **Step 2: Adicionar as client functions**

Localizar a entrada `relatorioRankingProdutos` (linhas 712-713):
```typescript
  relatorioRankingProdutos: (dias: number) =>
    request<{ itens: RankingProdutoItem[]; periodo_dias: number }>(`/api/relatorios/ranking-produtos?dias=${dias}`),
```
Substituir por (mantém a entrada original, acrescenta as 4 novas logo depois, mesma vírgula-separação do objeto `api`):
```typescript
  relatorioRankingProdutos: (dias: number) =>
    request<{ itens: RankingProdutoItem[]; periodo_dias: number }>(`/api/relatorios/ranking-produtos?dias=${dias}`),
  relatorioEstoqueParado: (dias: number, limite = 15) =>
    request<EstoqueParadoItem[]>(`/api/relatorios/estoque-parado?dias=${dias}&limite=${limite}`),
  relatorioProdutosTendencia: (dias: number) =>
    request<ProdutoTendenciaItem[]>(`/api/relatorios/produtos-tendencia?dias=${dias}`),
  relatorioRiscoRuptura: (dias: number) =>
    request<RiscoRupturaItem[]>(`/api/relatorios/risco-ruptura?dias=${dias}`),
  relatorioCurvas: (dias: number) =>
    request<CurvaAbcResponse>(`/api/relatorios/curvas?dias=${dias}`),
```

- [ ] **Step 3: Rodar `tsc` e confirmar sem erros novos**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros novos relacionados a `api.ts` (essas 4 funções ainda não têm consumidor até a Task 4 — `tsc` não reclama de função exportada não usada).

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/api.ts
git commit -m "feat: adiciona tipos e client de estoque-parado, tendencia, risco-ruptura e curva ABC"
```

---

### Task 4: Frontend — `RankingProdutosModal.tsx` com categorias e 8 abas

**Files:**
- Modify: `web/src/app/_components/RankingProdutosModal.tsx` (reescrita completa)

**Interfaces:**
- Consumes: `api.relatorioRankingProdutos`, `api.relatorioProdutosTendencia`, `api.relatorioCurvas`, `api.relatorioEstoqueParado`, `api.relatorioRiscoRuptura` (Task 3), tipos `RankingProdutoItem`, `ProdutoTendenciaItem`, `CurvaAbcItem`, `EstoqueParadoItem`, `RiscoRupturaItem` (Task 3).
- Consumes (já existentes): `TabBar` (`./TabBar`), `LoadingState` (`./LoadingState`), `ErrorAlert` (`./ErrorAlert`), `Icon` (`./Icon`).

- [ ] **Step 1: Reescrever o arquivo inteiro**

Ler `web/src/app/_components/RankingProdutosModal.tsx` (114 linhas) antes de editar — confirma que o consumidor (`web/src/app/dashboard/page.tsx:246`, `{showRanking && <RankingProdutosModal onClose={...} />}`) não muda, só o conteúdo interno do componente. Substituir o arquivo inteiro por:

```tsx
"use client";

import { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";
import type {
  RankingProdutoItem, ProdutoTendenciaItem, CurvaAbcItem, EstoqueParadoItem, RiscoRupturaItem,
} from "@/lib/api";
import TabBar from "./TabBar";
import LoadingState from "./LoadingState";
import ErrorAlert from "./ErrorAlert";
import Icon from "./Icon";

type Categoria = "vendas" | "lucratividade" | "estoque";
type Aba =
  | "vendidos" | "menos_vendidos" | "em_alta" | "em_queda"
  | "lucro" | "menos_lucro" | "margem" | "abc"
  | "parado" | "ruptura";

const CATEGORIAS: { key: Categoria; label: string }[] = [
  { key: "vendas", label: "Vendas" },
  { key: "lucratividade", label: "Lucratividade" },
  { key: "estoque", label: "Estoque" },
];

const ABAS_POR_CATEGORIA: Record<Categoria, { key: Aba; label: string }[]> = {
  vendas: [
    { key: "vendidos", label: "Mais vendidos" },
    { key: "menos_vendidos", label: "Menos vendidos" },
    { key: "em_alta", label: "Em alta" },
    { key: "em_queda", label: "Em queda" },
  ],
  lucratividade: [
    { key: "lucro", label: "Mais lucro" },
    { key: "menos_lucro", label: "Menos lucro" },
    { key: "margem", label: "Maior margem %" },
    { key: "abc", label: "Curva ABC" },
  ],
  estoque: [
    { key: "parado", label: "Parado em estoque" },
    { key: "ruptura", label: "Risco de ruptura" },
  ],
};

const ABA_PADRAO: Record<Categoria, Aba> = { vendas: "vendidos", lucratividade: "lucro", estoque: "parado" };

function fmtBRL(v: number) {
  return "R$ " + v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function ItemCard({ rank, titulo, subtitulo, children }: { rank: number; titulo: string; subtitulo: React.ReactNode; children: React.ReactNode }) {
  return (
    <div
      className="instrument-hover flex items-center gap-3 px-3 py-2 rounded-lg"
      style={{ background: "var(--panel-850)", border: "1px solid var(--panel-border)" }}
    >
      <span className="numeric text-xs w-5 text-right shrink-0" style={{ color: "var(--ink-700)" }}>{rank}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm truncate" style={{ color: "var(--ink-100)" }}>{titulo}</p>
        <p className="font-mono text-xs" style={{ color: "var(--ink-500)" }}>{subtitulo}</p>
      </div>
      <div className="text-right shrink-0">{children}</div>
    </div>
  );
}

export default function RankingProdutosModal({ onClose }: { onClose: () => void }) {
  const [dias, setDias] = useState(30);
  const [categoria, setCategoria] = useState<Categoria>("vendas");
  const [aba, setAba] = useState<Aba>("vendidos");
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const [ranking, setRanking] = useState<RankingProdutoItem[]>([]);
  const [tendencia, setTendencia] = useState<ProdutoTendenciaItem[]>([]);
  const [abc, setAbc] = useState<CurvaAbcItem[]>([]);
  const [parado, setParado] = useState<EstoqueParadoItem[]>([]);
  const [ruptura, setRuptura] = useState<RiscoRupturaItem[]>([]);

  useEffect(() => {
    setLoading(true);
    setErro(null);
    const tarefas: Promise<unknown>[] =
      categoria === "vendas"
        ? [
            api.relatorioRankingProdutos(dias).then((r) => setRanking(r.itens || [])),
            api.relatorioProdutosTendencia(dias).then(setTendencia),
          ]
        : categoria === "lucratividade"
        ? [
            api.relatorioRankingProdutos(dias).then((r) => setRanking(r.itens || [])),
            api.relatorioCurvas(dias).then((r) => setAbc(r.itens || [])),
          ]
        : [
            api.relatorioEstoqueParado(dias).then(setParado),
            api.relatorioRiscoRuptura(dias).then(setRuptura),
          ];
    Promise.all(tarefas)
      .catch((e) => setErro(e instanceof Error ? e.message : "Erro ao carregar ranking"))
      .finally(() => setLoading(false));
  }, [categoria, dias]);

  const trocarCategoria = (novaCategoria: string) => {
    const cat = novaCategoria as Categoria;
    setCategoria(cat);
    setAba(ABA_PADRAO[cat]);
  };

  const vendidos = useMemo(() => ranking.filter((i) => i.quantidade > 0), [ranking]);

  const listaVendas = useMemo(() => {
    if (aba === "vendidos") return [...vendidos].sort((a, b) => b.quantidade - a.quantidade).slice(0, 15);
    if (aba === "menos_vendidos") return [...vendidos].sort((a, b) => a.quantidade - b.quantidade).slice(0, 15);
    return [];
  }, [vendidos, aba]);

  const listaTendencia = useMemo(() => {
    if (aba === "em_alta") {
      return [...tendencia]
        .sort((a, b) => {
          if (a.crescimento_pct === null && b.crescimento_pct === null) return b.quantidade_atual - a.quantidade_atual;
          if (a.crescimento_pct === null) return -1;
          if (b.crescimento_pct === null) return 1;
          return b.crescimento_pct - a.crescimento_pct;
        })
        .slice(0, 15);
    }
    if (aba === "em_queda") {
      return [...tendencia]
        .filter((t) => t.crescimento_pct !== null)
        .sort((a, b) => (a.crescimento_pct as number) - (b.crescimento_pct as number))
        .slice(0, 15);
    }
    return [];
  }, [tendencia, aba]);

  const listaLucratividade = useMemo(() => {
    if (aba === "lucro") return [...vendidos].sort((a, b) => b.lucro - a.lucro).slice(0, 15);
    if (aba === "menos_lucro") return [...vendidos].sort((a, b) => a.lucro - b.lucro).slice(0, 15);
    if (aba === "margem")
      return [...vendidos].filter((i) => i.custo_cadastrado).sort((a, b) => b.margem_pct - a.margem_pct).slice(0, 15);
    return [];
  }, [vendidos, aba]);

  const listaAbc = useMemo(() => (aba === "abc" ? abc : []), [abc, aba]);
  const listaParado = useMemo(() => (aba === "parado" ? parado : []), [parado, aba]);
  const listaRuptura = useMemo(() => (aba === "ruptura" ? ruptura : []), [ruptura, aba]);

  const vazio =
    (categoria === "vendas" && (aba === "vendidos" || aba === "menos_vendidos") && listaVendas.length === 0) ||
    (categoria === "vendas" && (aba === "em_alta" || aba === "em_queda") && listaTendencia.length === 0) ||
    (categoria === "lucratividade" && aba !== "abc" && listaLucratividade.length === 0) ||
    (categoria === "lucratividade" && aba === "abc" && listaAbc.length === 0) ||
    (categoria === "estoque" && aba === "parado" && listaParado.length === 0) ||
    (categoria === "estoque" && aba === "ruptura" && listaRuptura.length === 0);

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="instrument-enter instrument w-full max-w-2xl max-h-[85vh] overflow-y-auto p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-sm font-medium" style={{ color: "var(--ink-100)" }}>Ranking de produtos</h2>
            <p className="text-xs mt-0.5" style={{ color: "var(--ink-500)" }}>
              Todos os canais — Shopee (virtual) e i9Logic (física) — últimos {dias} dias
            </p>
          </div>
          <button onClick={onClose} style={{ color: "var(--ink-500)" }} aria-label="Fechar">
            <Icon name="close" size={16} />
          </button>
        </div>

        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <TabBar tabs={CATEGORIAS} active={categoria} onChange={trocarCategoria} />
          <select
            value={dias}
            onChange={(e) => setDias(Number(e.target.value))}
            className="text-xs rounded-lg px-2 py-1.5 ml-auto bg-neutral-800 border border-neutral-700 text-neutral-300"
          >
            <option value={7}>7 dias</option>
            <option value={30}>30 dias</option>
            <option value={90}>90 dias</option>
          </select>
        </div>

        <div className="mb-4">
          <TabBar tabs={ABAS_POR_CATEGORIA[categoria]} active={aba} onChange={(k) => setAba(k as Aba)} />
        </div>

        {loading ? (
          <div className="py-8 text-center"><LoadingState message="Calculando ranking..." /></div>
        ) : erro ? (
          <ErrorAlert message={erro} />
        ) : vazio ? (
          <p className="text-xs py-8 text-center" style={{ color: "var(--ink-500)" }}>
            {categoria === "estoque" && aba === "ruptura"
              ? "Nenhum produto vendendo com estoque em risco de acabar no período."
              : "Nenhum dado no período."}
          </p>
        ) : (
          <div className="space-y-1.5">
            {(aba === "vendidos" || aba === "menos_vendidos") &&
              listaVendas.map((item, i) => (
                <ItemCard
                  key={item.sku}
                  rank={i + 1}
                  titulo={item.descricao}
                  subtitulo={
                    <>
                      {item.sku} · {item.quantidade} un
                      {!item.custo_cadastrado && <span style={{ color: "var(--status-warn)" }}> · custo não cadastrado</span>}
                    </>
                  }
                >
                  <p className="numeric text-sm font-medium" style={{ color: "var(--ink-100)" }}>{item.quantidade} un</p>
                  <p className="numeric text-xs" style={{ color: "var(--ink-700)" }}>{fmtBRL(item.receita)}</p>
                </ItemCard>
              ))}

            {(aba === "em_alta" || aba === "em_queda") &&
              listaTendencia.map((item, i) => (
                <ItemCard
                  key={item.sku}
                  rank={i + 1}
                  titulo={item.descricao}
                  subtitulo={`${item.sku} · ${item.quantidade_atual} un (era ${item.quantidade_anterior})`}
                >
                  {item.crescimento_pct === null ? (
                    <p className="numeric text-sm font-medium" style={{ color: "var(--status-ok)" }}>Novo</p>
                  ) : (
                    <p
                      className="numeric text-sm font-medium"
                      style={{ color: item.crescimento_pct >= 0 ? "var(--status-ok)" : "var(--status-crit)" }}
                    >
                      {item.crescimento_pct >= 0 ? "+" : ""}
                      {item.crescimento_pct}%
                    </p>
                  )}
                </ItemCard>
              ))}

            {(aba === "lucro" || aba === "menos_lucro" || aba === "margem") &&
              listaLucratividade.map((item, i) => (
                <ItemCard
                  key={item.sku}
                  rank={i + 1}
                  titulo={item.descricao}
                  subtitulo={
                    <>
                      {item.sku} · {item.quantidade} un
                      {!item.custo_cadastrado && <span style={{ color: "var(--status-warn)" }}> · custo não cadastrado</span>}
                    </>
                  }
                >
                  <p className="numeric text-sm font-medium" style={{ color: item.lucro >= 0 ? "var(--status-ok)" : "var(--status-crit)" }}>
                    {fmtBRL(item.lucro)}
                  </p>
                  <p className="numeric text-xs" style={{ color: "var(--ink-700)" }}>{item.margem_pct}% margem</p>
                </ItemCard>
              ))}

            {aba === "abc" &&
              listaAbc.map((item, i) => (
                <ItemCard key={item.sku} rank={i + 1} titulo={item.descricao} subtitulo={`${item.sku} · ${item.qtd} un · ${item.pct_acum}% acumulado`}>
                  <p className="numeric text-sm font-medium" style={{ color: "var(--ink-100)" }}>{fmtBRL(item.valor_total)}</p>
                  <span
                    className="numeric text-[10px] font-semibold px-1.5 py-0.5 rounded"
                    style={{
                      color: item.classe === "A" ? "var(--status-ok)" : item.classe === "B" ? "var(--status-warn)" : "var(--ink-500)",
                      border: "1px solid currentColor",
                    }}
                  >
                    Classe {item.classe}
                  </span>
                </ItemCard>
              ))}

            {aba === "parado" &&
              listaParado.map((item, i) => (
                <ItemCard key={item.sku} rank={i + 1} titulo={item.nome} subtitulo={`${item.sku} · ${item.quantidade} un paradas`}>
                  <p className="numeric text-sm font-medium" style={{ color: "var(--status-warn)" }}>{fmtBRL(item.valor_imobilizado)}</p>
                  <p className="numeric text-xs" style={{ color: "var(--ink-700)" }}>sem venda há {item.dias_sem_venda}d</p>
                </ItemCard>
              ))}

            {aba === "ruptura" &&
              listaRuptura.map((item, i) => (
                <ItemCard key={item.sku} rank={i + 1} titulo={item.descricao} subtitulo={`${item.sku} · ${item.estoque_atual} un em estoque`}>
                  <p className="numeric text-sm font-medium" style={{ color: item.dias_restantes <= 7 ? "var(--status-crit)" : "var(--status-warn)" }}>
                    {item.dias_restantes}d restantes
                  </p>
                  <p className="numeric text-xs" style={{ color: "var(--ink-700)" }}>{item.velocidade_diaria}/dia</p>
                </ItemCard>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Confirmar que `TabBar` aceita a prop `tabs` no formato usado (`{key, label}[]`)**

Ler `web/src/app/_components/TabBar.tsx` — já confere: `tabs: TabOption[]` com `TabOption = {key: string; label: string}` (`web/src/lib/types/ui.ts:18-21`), `active: string`, `onChange: (key: string) => void`. `CATEGORIAS` e `ABAS_POR_CATEGORIA[categoria]` batem com esse formato (o cast `as Aba`/`as Categoria` nos handlers é necessário porque `TabBar.onChange` é tipado `(key: string) => void`, genérico pra qualquer consumidor).

- [ ] **Step 3: Rodar `tsc` e confirmar zero erros**

Run: `cd web && npx tsc --noEmit`
Expected: zero erros relacionados a `RankingProdutosModal.tsx` ou `api.ts`.

- [ ] **Step 4: Smoke visual**

Rodar `npm run dev` em `web/`, navegar até `/dashboard`, clicar em "Ver ranking completo", confirmar:
- 3 categorias aparecem (Vendas, Lucratividade, Estoque), clicar troca a lista de abas embaixo.
- Cada uma das 8 abas carrega sem erro no console e mostra card com número coerente com a métrica (un. pra vendidos, R$ pra lucro/parado, % pra margem/tendência, dias pra ruptura, classe A/B/C pra ABC).
- Trocar o seletor de dias (7/30/90) recarrega a categoria ativa.
- Produto sem custo cadastrado aparece com o aviso "custo não cadastrado" nas abas de vendidos/lucro/margem (esperado até a auditoria de loja física terminar — ver spec).
- Estado vazio (sem dado no período) mostra mensagem, não tela em branco.

- [ ] **Step 5: Commit**

```bash
git add web/src/app/_components/RankingProdutosModal.tsx
git commit -m "feat: modal de ranking de produtos ganha 3 categorias e 8 metricas"
```

---

## Self-Review

**Cobertura da spec:** Mais/Menos vendidos ✅ (Task 4, reaproveita `ranking_produtos`), Em alta/Em queda ✅ (Task 1 `produtos_tendencia` + Task 4), Mais/Menos lucro ✅ (Task 4, sort em `ranking_produtos`), Maior margem % ✅ (Task 4, filter+sort em `ranking_produtos`), Curva ABC ✅ (Task 4, `relatorioCurvas` novo consumindo rota já existente), Parado em estoque ✅ (Task 2 rota nova sobre `estoque_parado` já existente + Task 4), Risco de ruptura ✅ (Task 1 `risco_ruptura` + Task 2 + Task 4). Constraint "sem `pdv_vendas`" ✅ nenhuma query nova toca essa tabela. Constraint "sem número fabricado" ✅ `crescimento_pct: None` pros casos sem base de comparação, testado explicitamente (Step 1 da Task 1).

**Placeholders:** nenhum "TBD"/"implementar depois" — todo código é completo, incluindo os 300+ linhas do modal reescrito.

**Consistência de tipos:** `ProdutoTendenciaItem`/`RiscoRupturaItem`/`CurvaAbcItem`/`EstoqueParadoItem` (Task 3) têm exatamente os mesmos campos que `produtos_tendencia`/`risco_ruptura`/`curvas` (existente)/`estoque_parado` (existente) retornam (Task 1 e funções já existentes lidas antes de escrever a spec). `Aba`/`Categoria` (Task 4) batem com `ABAS_POR_CATEGORIA`/`ABA_PADRAO`/`CATEGORIAS` — todas as 10 chaves de aba usadas nos handlers de render (`aba === "..."`) existem em algum `ABAS_POR_CATEGORIA[cat]`.

## Execution Handoff

Plano completo e salvo em `docs/superpowers/plans/2026-08-09-ranking-produtos-metricas.md`. Duas opções de execução:

1. **Subagent-Driven (recomendado)** — dispatch de subagente por task, review entre tasks, iteração rápida.
2. **Inline Execution** — executo as tasks nesta sessão com checkpoints de revisão.

Qual prefere?
