# Ranking de Produtos — Filtro por Loja Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o card "Top produtos" do dashboard e o modal "Ranking de produtos" respeitarem a loja selecionada — Shopee como fonte quando a loja é virtual, i9Logic quando é física, sem precisar chamar API nenhuma diretamente (a separação já existe em `vendas_pedidos.loja_id`/`estoque_lojas.loja_id`, só falta filtrar por ele).

**Architecture:** 5 funções de leitura (`core/relatorios.py` ×4, `core/bi.py` ×1) ganham parâmetro opcional `loja_id`, mesmo padrão `($N::int IS NULL OR loja_id = $N)` já usado em `core.vendas.dashboard()`. 5 rotas + `kpi_overview()` repassam o parâmetro. 5 client functions + o modal + a página do dashboard repassam `lojaId` (string, mesma convenção de `relatorioClientes`/`kpiOverview`).

**Tech Stack:** Flask + asyncpg (backend), Next.js/React/TypeScript (frontend), Postgres.

## Global Constraints

- `loja_id=None`/ausente → nenhum filtro, comportamento idêntico ao atual (todas as lojas).
- Nenhuma mudança na estrutura do union Bling+PDV legado (`ranking_produtos`, `estoque_parado`) — só acrescenta cláusula `WHERE`, não toca nas tabelas unidas nem no branch PDV (morto, fora de escopo).
- Convenção de tipo no frontend: `lojaId?: string`, guard `lojaId && lojaId !== "todas"` — mesma usada em `relatorioClientes`/`api.kpiOverview` (`web/src/lib/api.ts`), não a variante `number` usada em `relatorioDrePorLoja`.
- Sem chamada direta a API da Shopee ou do i9Logic nesta fase — a separação por fonte já é resultado do sync existente.

---

### Task 1: Backend — `loja_id` opcional nas 5 funções de dado

**Files:**
- Modify: `hermes_agents/core/relatorios.py` (`curvas:340`, `ranking_produtos:379`, `produtos_tendencia:445`, `risco_ruptura:483`)
- Modify: `hermes_agents/core/bi.py` (`estoque_parado:493`)
- Test: `hermes_agents/tests/test_relatorios.py`
- Test: `hermes_agents/tests/test_bi.py` (confirmar nome exato do arquivo antes de editar — deve existir dado que `core/bi.py` já tem testes de outras funções)

**Interfaces:**
- Produces: `core.relatorios.curvas(dias=90, loja_id=None)`, `core.relatorios.ranking_produtos(dias=30, loja_id=None)`, `core.relatorios.produtos_tendencia(dias=30, loja_id=None)`, `core.relatorios.risco_ruptura(dias=30, loja_id=None)`, `core.bi.estoque_parado(dias=60, limite=10, loja_id=None)` — todos os retornos (formato/campos dos itens) continuam idênticos aos já existentes, só o filtro de linhas muda.

- [ ] **Step 1: Confirmar nome do arquivo de teste de `core/bi.py`**

Run: `ls hermes_agents/tests/ | grep -i "^test_bi"`
Se o arquivo não existir com esse nome exato, ajuste os Steps 6-7 abaixo pro nome real encontrado (ex.: pode estar dentro de outro arquivo de teste de BI) antes de prosseguir.

- [ ] **Step 2: Escrever os testes que falham (core/relatorios.py)**

Em `hermes_agents/tests/test_relatorios.py`, adicionar antes de `if __name__=="__main__":unittest.main(verbosity=2)`:

```python
    @patch("core.relatorios.get_db")
    def test_ranking_produtos_repassa_loja_id_pra_query(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"sku": "SKU-A", "quantidade": 10, "receita": 1000.0, "comissao": 0.0, "frete": 0.0}],
            [{"sku": "SKU-A", "descricao": "Produto A", "preco_custo": 30.0}],
        ]
        mock_get_db.return_value = fake_db

        rel.ranking_produtos(30, loja_id=5)

        primeira_query_params = fake_db.fetch.call_args_list[0].args[1:]
        self.assertEqual(primeira_query_params, (30, 5))

    @patch("core.relatorios.get_db")
    def test_ranking_produtos_sem_loja_id_mantem_comportamento_atual(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"sku": "SKU-A", "quantidade": 10, "receita": 1000.0, "comissao": 0.0, "frete": 0.0}],
            [{"sku": "SKU-A", "descricao": "Produto A", "preco_custo": 30.0}],
        ]
        mock_get_db.return_value = fake_db

        rel.ranking_produtos(30)

        primeira_query_params = fake_db.fetch.call_args_list[0].args[1:]
        self.assertEqual(primeira_query_params, (30, None))

    @patch("core.relatorios.get_db")
    def test_curvas_repassa_loja_id_pra_query(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.curvas(90, loja_id=3)

        self.assertEqual(fake_db.fetch.call_args.args[1:], (90, 3))

    @patch("core.relatorios.get_db")
    def test_curvas_sem_loja_id_mantem_comportamento_atual(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.curvas(90)

        self.assertEqual(fake_db.fetch.call_args.args[1:], (90, None))

    @patch("core.relatorios.get_db")
    def test_produtos_tendencia_repassa_loja_id_pra_query(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.produtos_tendencia(30, loja_id=8)

        self.assertEqual(fake_db.fetch.call_args.args[1:], (30, 8))

    @patch("core.relatorios.get_db")
    def test_produtos_tendencia_sem_loja_id_mantem_comportamento_atual(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.produtos_tendencia(30)

        self.assertEqual(fake_db.fetch.call_args.args[1:], (30, None))

    @patch("core.relatorios.get_db")
    def test_risco_ruptura_repassa_loja_id_pra_query(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.risco_ruptura(30, loja_id=2)

        self.assertEqual(fake_db.fetch.call_args.args[1:], (30, 2))

    @patch("core.relatorios.get_db")
    def test_risco_ruptura_sem_loja_id_mantem_comportamento_atual(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.risco_ruptura(30)

        self.assertEqual(fake_db.fetch.call_args.args[1:], (30, None))
```

- [ ] **Step 3: Rodar os testes e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_relatorios.py -v -k "loja_id"`
Expected: FAIL — `TypeError: ranking_produtos() got an unexpected keyword argument 'loja_id'` (e equivalente pras outras 3).

- [ ] **Step 4: Implementar `loja_id` nas 4 funções de `core/relatorios.py`**

Localizar (linha 340-346):
```python
def curvas(dias=90):
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT vi.sku, vi.descricao, SUM(vi.valor_total) as valor_total, SUM(vi.quantidade) as qtd
            FROM vendas_itens vi JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE vp.data >= CURRENT_DATE - $1::int AND vp.status != 'cancelado'
            GROUP BY vi.sku, vi.descricao ORDER BY valor_total DESC LIMIT 30""", dias)
```
Substituir por:
```python
def curvas(dias=90, loja_id=None):
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT vi.sku, vi.descricao, SUM(vi.valor_total) as valor_total, SUM(vi.quantidade) as qtd
            FROM vendas_itens vi JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE vp.data >= CURRENT_DATE - $1::int AND vp.status != 'cancelado'
              AND ($2::int IS NULL OR vp.loja_id = $2)
            GROUP BY vi.sku, vi.descricao ORDER BY valor_total DESC LIMIT 30""", dias, loja_id)
```

Localizar (linhas 379-407, a query principal de `ranking_produtos`):
```python
def ranking_produtos(dias=30):
    """Lucro/vendas por SKU somando Bling+marketplaces (vendas_itens/vendas_pedidos,
    mesma fonte unificada de produtos()/curvas() acima) e PDV loja fisica
    (pdv_itens/pdv_vendas, canal direto sem sync). Comissao de marketplace so'
    e' deduzida do canal 'shopee' (taxa conhecida via env var/config); demais
    marketplaces sincronizados via Bling entram brutos de comissao por falta
    de taxa cadastrada por canal — nao inventa numero. PDV e' de fato sem
    comissao (venda direta), entao 0 ali e' o valor correto, nao uma lacuna."""
    async def _go():
        db = await get_db()
        vendas_rows = await db.fetch(f"""
            SELECT sku, SUM(quantidade) AS quantidade, SUM(valor_total) AS receita,
                   SUM(CASE WHEN canal = 'shopee' THEN valor_total * {SHOPEE_COMISSAO_PCT} / 100.0 ELSE 0 END) AS comissao,
                   SUM(frete_alocado) AS frete
            FROM (
                SELECT vi.sku AS sku, vi.quantidade AS quantidade, vi.valor_total AS valor_total,
                       COALESCE(vp.marketplace, 'bling') AS canal,
                       CASE WHEN vp.total > 0 THEN vi.valor_total / vp.total * COALESCE(vp.frete, 0) ELSE 0 END AS frete_alocado
                FROM vendas_itens vi JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
                WHERE vp.data >= CURRENT_DATE - $1::int AND vp.status != 'cancelado'
                UNION ALL
                SELECT pi.produto_codigo AS sku, pi.quantidade AS quantidade, pi.valor_total AS valor_total,
                       'pdv' AS canal, 0 AS frete_alocado
                FROM pdv_itens pi JOIN pdv_vendas pv ON pv.id = pi.venda_id
                WHERE pv.data >= CURRENT_DATE - $1::int AND pv.status != 'cancelada'
            ) unificado
            WHERE sku IS NOT NULL AND sku != ''
            GROUP BY sku
        """, dias)
```
Substituir por (mantém docstring, acrescenta `loja_id` no filtro Bling — branch PDV fica intocado, é tabela morta, filtrar lá não muda nada e sai do escopo):
```python
def ranking_produtos(dias=30, loja_id=None):
    """Lucro/vendas por SKU somando Bling+marketplaces (vendas_itens/vendas_pedidos,
    mesma fonte unificada de produtos()/curvas() acima) e PDV loja fisica
    (pdv_itens/pdv_vendas, canal direto sem sync). Comissao de marketplace so'
    e' deduzida do canal 'shopee' (taxa conhecida via env var/config); demais
    marketplaces sincronizados via Bling entram brutos de comissao por falta
    de taxa cadastrada por canal — nao inventa numero. PDV e' de fato sem
    comissao (venda direta), entao 0 ali e' o valor correto, nao uma lacuna.

    loja_id opcional: filtra so' os pedidos daquela loja. Bling/Shopee ja
    grava loja_id resolvido no sync (shop_id->loja), i9Logic idem
    (filial->loja) — filtrar por loja_id ja' separa Shopee de i9Logic sem
    precisar checar tipo de loja em lugar nenhum."""
    async def _go():
        db = await get_db()
        vendas_rows = await db.fetch(f"""
            SELECT sku, SUM(quantidade) AS quantidade, SUM(valor_total) AS receita,
                   SUM(CASE WHEN canal = 'shopee' THEN valor_total * {SHOPEE_COMISSAO_PCT} / 100.0 ELSE 0 END) AS comissao,
                   SUM(frete_alocado) AS frete
            FROM (
                SELECT vi.sku AS sku, vi.quantidade AS quantidade, vi.valor_total AS valor_total,
                       COALESCE(vp.marketplace, 'bling') AS canal,
                       CASE WHEN vp.total > 0 THEN vi.valor_total / vp.total * COALESCE(vp.frete, 0) ELSE 0 END AS frete_alocado
                FROM vendas_itens vi JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
                WHERE vp.data >= CURRENT_DATE - $1::int AND vp.status != 'cancelado'
                  AND ($2::int IS NULL OR vp.loja_id = $2)
                UNION ALL
                SELECT pi.produto_codigo AS sku, pi.quantidade AS quantidade, pi.valor_total AS valor_total,
                       'pdv' AS canal, 0 AS frete_alocado
                FROM pdv_itens pi JOIN pdv_vendas pv ON pv.id = pi.venda_id
                WHERE pv.data >= CURRENT_DATE - $1::int AND pv.status != 'cancelada'
            ) unificado
            WHERE sku IS NOT NULL AND sku != ''
            GROUP BY sku
        """, dias, loja_id)
```

Localizar (linhas 445-461):
```python
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
```
Substituir por:
```python
def produtos_tendencia(dias=30, loja_id=None):
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
              AND ($2::int IS NULL OR vp.loja_id = $2)
            GROUP BY vi.sku
        """, dias, loja_id)
```

Localizar (linhas 483-498):
```python
def risco_ruptura(dias=30):
    """Produtos vendendo bem MAS com estoque acabando — velocidade de venda
    alta, estoque baixo. Diferente de 'parado' (zero venda) e de rupturas()
    (zero estoque, ja consumada) — aqui e' o alerta ANTES de zerar."""
    dias = max(1, int(dias or 30))
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
```
Substituir por (filtra tanto a venda quanto o subquery de estoque pela MESMA loja — senão "dias restantes" mistura venda de uma loja com estoque de todas):
```python
def risco_ruptura(dias=30, loja_id=None):
    """Produtos vendendo bem MAS com estoque acabando — velocidade de venda
    alta, estoque baixo. Diferente de 'parado' (zero venda) e de rupturas()
    (zero estoque, ja consumada) — aqui e' o alerta ANTES de zerar."""
    dias = max(1, int(dias or 30))
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"""
            SELECT vi.sku, MAX(vi.descricao) AS descricao, SUM(vi.quantidade) AS qtd_vendida,
                   (SELECT COALESCE(SUM(e.quantidade), 0) FROM estoque_lojas e
                    WHERE e.sku = vi.sku AND ($2::int IS NULL OR e.loja_id = $2)) AS estoque_atual
            FROM vendas_itens vi JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE vp.data >= CURRENT_DATE - $1::int AND vp.status != 'cancelado'
              AND vi.sku IS NOT NULL AND vi.sku != ''
              AND ($2::int IS NULL OR vp.loja_id = $2)
            GROUP BY vi.sku
        """, dias, loja_id)
```

- [ ] **Step 5: Rodar os testes de `core/relatorios.py` e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_relatorios.py -v`
Expected: PASS (todos, incluindo os 8 novos + os já existentes sem regressão).

- [ ] **Step 6: Escrever o teste que falha (core/bi.py::estoque_parado)**

No arquivo de teste confirmado no Step 1, adicionar (ajuste `import core.bi as bi` ou equivalente conforme o padrão já usado no arquivo — confira o import existente antes de escrever):

```python
    @patch("core.bi.get_db")
    def test_estoque_parado_repassa_loja_id_pra_query(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        bi.estoque_parado(60, 10, loja_id=4)

        self.assertEqual(fake_db.fetch.call_args.args[1:], (60, 4))

    @patch("core.bi.get_db")
    def test_estoque_parado_sem_loja_id_mantem_comportamento_atual(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        bi.estoque_parado(60, 10)

        self.assertEqual(fake_db.fetch.call_args.args[1:], (60, None))
```

- [ ] **Step 7: Rodar o teste e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_bi.py -v -k "loja_id"` (ajuste o caminho do arquivo se o Step 1 achou outro nome)
Expected: FAIL — `TypeError: estoque_parado() got an unexpected keyword argument 'loja_id'`.

- [ ] **Step 8: Implementar `loja_id` em `estoque_parado`**

Localizar (`hermes_agents/core/bi.py`, linhas 493-513):
```python
def estoque_parado(dias: int = 60, limite: int = 10) -> list:
    """Produtos com saldo em estoque mas sem nenhuma venda nos ultimos `dias` —
    capital imobilizado parado, calculado cruzando saldo real (estoque_lojas)
    com historico real de venda (vendas_itens/pdv_itens), nada estimado."""
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"""
            SELECT e.sku, MAX(c.descricao) AS nome, SUM(e.quantidade) AS quantidade, MAX(c.preco_custo) AS preco_custo
            FROM estoque_lojas e
            JOIN catalogo_produtos c ON c.sku = e.sku
            WHERE e.quantidade > 0
              AND e.sku NOT IN (
                  SELECT DISTINCT i.sku FROM vendas_itens i JOIN vendas_pedidos p ON p.id = i.pedido_id
                  WHERE p.data >= CURRENT_DATE - $1::int AND p.status != 'cancelado' AND i.sku IS NOT NULL
                  UNION
                  SELECT DISTINCT i.produto_codigo FROM pdv_itens i JOIN pdv_vendas v ON v.id = i.venda_id
                  WHERE DATE(v.data) >= CURRENT_DATE - $1::int AND i.produto_codigo IS NOT NULL
              )
            GROUP BY e.sku
        """, dias)
```
Substituir por (filtra tanto o saldo quanto a checagem de "vendeu recentemente" pela MESMA loja — branch PDV do NOT IN fica intocado, tabela morta, fora de escopo):
```python
def estoque_parado(dias: int = 60, limite: int = 10, loja_id: int = None) -> list:
    """Produtos com saldo em estoque mas sem nenhuma venda nos ultimos `dias` —
    capital imobilizado parado, calculado cruzando saldo real (estoque_lojas)
    com historico real de venda (vendas_itens/pdv_itens), nada estimado."""
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"""
            SELECT e.sku, MAX(c.descricao) AS nome, SUM(e.quantidade) AS quantidade, MAX(c.preco_custo) AS preco_custo
            FROM estoque_lojas e
            JOIN catalogo_produtos c ON c.sku = e.sku
            WHERE e.quantidade > 0
              AND ($2::int IS NULL OR e.loja_id = $2)
              AND e.sku NOT IN (
                  SELECT DISTINCT i.sku FROM vendas_itens i JOIN vendas_pedidos p ON p.id = i.pedido_id
                  WHERE p.data >= CURRENT_DATE - $1::int AND p.status != 'cancelado' AND i.sku IS NOT NULL
                    AND ($2::int IS NULL OR p.loja_id = $2)
                  UNION
                  SELECT DISTINCT i.produto_codigo FROM pdv_itens i JOIN pdv_vendas v ON v.id = i.venda_id
                  WHERE DATE(v.data) >= CURRENT_DATE - $1::int AND i.produto_codigo IS NOT NULL
              )
            GROUP BY e.sku
        """, dias, loja_id)
```

- [ ] **Step 9: Rodar o teste de `estoque_parado` e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_bi.py -v -k "loja_id"` (mesmo caminho do Step 7)
Expected: PASS.

- [ ] **Step 10: Rodar as suítes completas envolvidas e confirmar zero regressão**

Run: `cd hermes_agents && python -m pytest tests/test_relatorios.py tests/test_bi.py -v`
Expected: PASS (todos).

- [ ] **Step 11: Commit**

```bash
git add hermes_agents/core/relatorios.py hermes_agents/core/bi.py hermes_agents/tests/test_relatorios.py hermes_agents/tests/test_bi.py
git commit -m "feat: loja_id opcional em ranking_produtos/curvas/produtos_tendencia/risco_ruptura/estoque_parado"
```

---

### Task 2: Backend — rotas e `kpi_overview` repassam `loja_id`

**Files:**
- Modify: `hermes_agents/routes/relatorios.py` (`/curvas:154`, `/ranking-produtos:168`, `/estoque-parado:175`, `/produtos-tendencia:183`, `/risco-ruptura:190`)
- Modify: `hermes_agents/athena_bridge.py` (`kpi_overview:1983-2050`, especificamente a chamada a `ranking_produtos` na linha 2039)
- Test: `hermes_agents/tests/test_all_endpoints.py`
- Test: `hermes_agents/tests/test_kpi_overview.py`

**Interfaces:**
- Consumes: `core.relatorios.curvas/ranking_produtos/produtos_tendencia/risco_ruptura(dias, loja_id=None)`, `core.bi.estoque_parado(dias, limite, loja_id=None)` (Task 1).
- Produces: as 5 rotas aceitam `?loja_id=<int>` opcional; `GET /api/kpi/overview?loja_id=<int>` filtra `top_skus` pela loja.

- [ ] **Step 1: Adicionar `loja_id` nas 5 rotas**

Em `hermes_agents/routes/relatorios.py`, localizar (linhas 154-194):
```python
@relatorios_bp.route("/curvas", methods=["GET"])
def rel_curvas():
    from core.relatorios import curvas
    dias = request.args.get("dias", 90, type=int)
    return jsonify(curvas(dias))


@relatorios_bp.route("/produtos", methods=["GET"])
def rel_produtos():
    from core.relatorios import produtos
    dias = request.args.get("dias", 30, type=int)
    return jsonify(produtos(dias))


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
Substituir por (só `/produtos` fica sem `loja_id` — não faz parte do escopo desta feature, não é consumida pelo card/modal):
```python
@relatorios_bp.route("/curvas", methods=["GET"])
def rel_curvas():
    from core.relatorios import curvas
    dias = request.args.get("dias", 90, type=int)
    loja_id = request.args.get("loja_id", type=int)
    return jsonify(curvas(dias, loja_id))


@relatorios_bp.route("/produtos", methods=["GET"])
def rel_produtos():
    from core.relatorios import produtos
    dias = request.args.get("dias", 30, type=int)
    return jsonify(produtos(dias))


@relatorios_bp.route("/ranking-produtos", methods=["GET"])
def rel_ranking_produtos():
    from core.relatorios import ranking_produtos
    dias = request.args.get("dias", 30, type=int)
    loja_id = request.args.get("loja_id", type=int)
    return jsonify({"itens": ranking_produtos(dias, loja_id), "periodo_dias": dias})


@relatorios_bp.route("/estoque-parado", methods=["GET"])
def rel_estoque_parado():
    from core.bi import estoque_parado
    dias = request.args.get("dias", 60, type=int)
    limite = request.args.get("limite", 15, type=int)
    loja_id = request.args.get("loja_id", type=int)
    return jsonify(estoque_parado(dias, limite, loja_id))


@relatorios_bp.route("/produtos-tendencia", methods=["GET"])
def rel_produtos_tendencia():
    from core.relatorios import produtos_tendencia
    dias = request.args.get("dias", 30, type=int)
    loja_id = request.args.get("loja_id", type=int)
    return jsonify(produtos_tendencia(dias, loja_id))


@relatorios_bp.route("/risco-ruptura", methods=["GET"])
def rel_risco_ruptura():
    from core.relatorios import risco_ruptura
    dias = request.args.get("dias", 30, type=int)
    loja_id = request.args.get("loja_id", type=int)
    return jsonify(risco_ruptura(dias, loja_id))
```

- [ ] **Step 2: Repassar `loja_id` em `kpi_overview`**

Em `hermes_agents/athena_bridge.py`, localizar (linha 2038-2039):
```python
            from core.relatorios import ranking_produtos
            ranking = ranking_produtos(periodo)
```
Substituir por (`loja_id` já é extraído na linha 1991 desta mesma função, `loja_id = request.args.get("loja_id", type=int)` — só faltava repassar):
```python
            from core.relatorios import ranking_produtos
            ranking = ranking_produtos(periodo, loja_id)
```

Também remover o comentário agora desatualizado logo acima (linhas 2035-2037):
```python
            # Limitacao aceita: ranking_produtos nao filtra por loja hoje —
            # este card ignora loja_id (a query original tambem nunca
            # funcionou com ou sem esse filtro, entao nao e' regressao).
```
Substituir por:
```python
            # ranking_produtos ja filtra por loja_id (ver core/relatorios.py) —
            # Shopee/i9Logic ja gravam loja_id certo no sync, filtrar aqui
            # separa loja virtual de fisica sem checar tipo em lugar nenhum.
```

- [ ] **Step 3: Adicionar testes de rota (smoke — `loja_id` é aceito)**

Em `hermes_agents/tests/test_all_endpoints.py`, dentro de `TestRelatoriosEndpoints`, localizar `test_estoque_parado`/`test_produtos_tendencia`/`test_risco_ruptura` (adicionados numa task anterior) e o `test_curvas`/`test_ranking_produtos` (se existir; senão adicionar do zero seguindo o padrão `_assert_200_json` já usado nesta classe). Acrescentar, na mesma classe, logo após o último teste de relatórios:

```python
    def test_ranking_produtos_com_loja_id(self):
        self._assert_200_json(self.client.get("/api/relatorios/ranking-produtos?dias=30&loja_id=1", headers=self.headers), "ranking-produtos+loja_id")

    def test_curvas_com_loja_id(self):
        self._assert_200_json(self.client.get("/api/relatorios/curvas?dias=90&loja_id=1", headers=self.headers), "curvas+loja_id")

    def test_estoque_parado_com_loja_id(self):
        self._assert_200_json(self.client.get("/api/relatorios/estoque-parado?dias=60&loja_id=1", headers=self.headers), "estoque-parado+loja_id")

    def test_produtos_tendencia_com_loja_id(self):
        self._assert_200_json(self.client.get("/api/relatorios/produtos-tendencia?dias=30&loja_id=1", headers=self.headers), "produtos-tendencia+loja_id")

    def test_risco_ruptura_com_loja_id(self):
        self._assert_200_json(self.client.get("/api/relatorios/risco-ruptura?dias=30&loja_id=1", headers=self.headers), "risco-ruptura+loja_id")
```

- [ ] **Step 4: Adicionar teste de `kpi_overview` repassando `loja_id`**

Em `hermes_agents/tests/test_kpi_overview.py`, dentro de `TestKpiOverviewTopSkus`, acrescentar após `test_erro_no_ranking_nao_quebra_a_rota`:

```python
    @patch("core.relatorios.ranking_produtos")
    def test_repassa_loja_id_pro_ranking_produtos(self, mock_ranking):
        mock_ranking.return_value = []
        cursor = _FakeCursor(fetchone_values=[
            {"v": 0.0}, {"v": 0.0}, {"v": 0}, {"v": 0},
            {"v": 0}, {"v": 0}, {"v": 0}, {"v": 0},
        ])
        with patch("athena_bridge._db_sync", return_value=_FakeConn(cursor)):
            self.client.get("/api/kpi/overview?loja_id=7", headers=self.headers)
        mock_ranking.assert_called_once_with(30, 7)
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_all_endpoints.py tests/test_kpi_overview.py -v -k "loja_id"`
Expected: PASS (6 testes novos).

- [ ] **Step 6: Rodar as suítes completas envolvidas**

Run: `cd hermes_agents && python -m pytest tests/test_all_endpoints.py tests/test_kpi_overview.py -v`
Expected: PASS (todos, sem regressão nos já existentes).

- [ ] **Step 7: Commit**

```bash
git add hermes_agents/routes/relatorios.py hermes_agents/athena_bridge.py hermes_agents/tests/test_all_endpoints.py hermes_agents/tests/test_kpi_overview.py
git commit -m "feat: rotas de relatorios e kpi/overview repassam loja_id opcional"
```

---

### Task 3: Frontend — client functions em `api.ts` ganham `lojaId?`

**Files:**
- Modify: `web/src/lib/api.ts` (`relatorioRankingProdutos:712`, `relatorioEstoqueParado:714`, `relatorioProdutosTendencia:716`, `relatorioRiscoRuptura:718`, `relatorioCurvas:720`)

**Interfaces:**
- Consumes: rotas da Task 2 (`?loja_id=`).
- Produces: `api.relatorioRankingProdutos(dias, lojaId?)`, `api.relatorioEstoqueParado(dias, limite?, lojaId?)`, `api.relatorioProdutosTendencia(dias, lojaId?)`, `api.relatorioRiscoRuptura(dias, lojaId?)`, `api.relatorioCurvas(dias, lojaId?)` — `lojaId?: string`, mesma convenção de `relatorioClientes`/`kpiOverview` (guard `lojaId && lojaId !== "todas"`), consumidas pela Task 4.

- [ ] **Step 1: Atualizar as 5 client functions**

Em `web/src/lib/api.ts`, localizar (linhas 712-721):
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
Substituir por:
```typescript
  relatorioRankingProdutos: (dias: number, lojaId?: string) =>
    request<{ itens: RankingProdutoItem[]; periodo_dias: number }>(`/api/relatorios/ranking-produtos?dias=${dias}${lojaId && lojaId !== "todas" ? `&loja_id=${lojaId}` : ""}`),
  relatorioEstoqueParado: (dias: number, limite = 15, lojaId?: string) =>
    request<EstoqueParadoItem[]>(`/api/relatorios/estoque-parado?dias=${dias}&limite=${limite}${lojaId && lojaId !== "todas" ? `&loja_id=${lojaId}` : ""}`),
  relatorioProdutosTendencia: (dias: number, lojaId?: string) =>
    request<ProdutoTendenciaItem[]>(`/api/relatorios/produtos-tendencia?dias=${dias}${lojaId && lojaId !== "todas" ? `&loja_id=${lojaId}` : ""}`),
  relatorioRiscoRuptura: (dias: number, lojaId?: string) =>
    request<RiscoRupturaItem[]>(`/api/relatorios/risco-ruptura?dias=${dias}${lojaId && lojaId !== "todas" ? `&loja_id=${lojaId}` : ""}`),
  relatorioCurvas: (dias: number, lojaId?: string) =>
    request<CurvaAbcResponse>(`/api/relatorios/curvas?dias=${dias}${lojaId && lojaId !== "todas" ? `&loja_id=${lojaId}` : ""}`),
```

- [ ] **Step 2: Rodar `tsc` e confirmar sem erros novos**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros novos (os call-sites existentes — `RankingProdutosModal.tsx`, chamadas sem segundo/terceiro argumento — continuam válidos, `lojaId`/`limite` são opcionais).

- [ ] **Step 3: Commit**

```bash
git add web/src/lib/api.ts
git commit -m "feat: client functions de relatorios de produto aceitam lojaId opcional"
```

---

### Task 4: Frontend — modal e dashboard repassam a loja selecionada

**Files:**
- Modify: `web/src/app/_components/RankingProdutosModal.tsx` (`props:66`, `useEffect:79-100`)
- Modify: `web/src/app/dashboard/page.tsx` (`kpiOverview` já correto na linha 78; invocação do modal na linha 246)

**Interfaces:**
- Consumes: `api.relatorioRankingProdutos/relatorioProdutosTendencia/relatorioCurvas/relatorioEstoqueParado/relatorioRiscoRuptura(dias, lojaId?)` (Task 3).
- Produces: `<RankingProdutosModal onClose={...} lojaId={...} />` — prop nova, opcional (retrocompatível com qualquer outro caller que não passe `lojaId`).

- [ ] **Step 1: Adicionar prop `lojaId` no modal e repassar nos 5 fetches**

Em `web/src/app/_components/RankingProdutosModal.tsx`, localizar (linha 66):
```tsx
export default function RankingProdutosModal({ onClose }: { onClose: () => void }) {
```
Substituir por:
```tsx
export default function RankingProdutosModal({ onClose, lojaId }: { onClose: () => void; lojaId?: string }) {
```

Localizar o `useEffect` de busca (linhas 79-100):
```tsx
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
```
Substituir por:
```tsx
  useEffect(() => {
    setLoading(true);
    setErro(null);
    const tarefas: Promise<unknown>[] =
      categoria === "vendas"
        ? [
            api.relatorioRankingProdutos(dias, lojaId).then((r) => setRanking(r.itens || [])),
            api.relatorioProdutosTendencia(dias, lojaId).then(setTendencia),
          ]
        : categoria === "lucratividade"
        ? [
            api.relatorioRankingProdutos(dias, lojaId).then((r) => setRanking(r.itens || [])),
            api.relatorioCurvas(dias, lojaId).then((r) => setAbc(r.itens || [])),
          ]
        : [
            api.relatorioEstoqueParado(dias, 15, lojaId).then(setParado),
            api.relatorioRiscoRuptura(dias, lojaId).then(setRuptura),
          ];
    Promise.all(tarefas)
      .catch((e) => setErro(e instanceof Error ? e.message : "Erro ao carregar ranking"))
      .finally(() => setLoading(false));
  }, [categoria, dias, lojaId]);
```

- [ ] **Step 2: Passar `lojaId` do dashboard pro modal**

Em `web/src/app/dashboard/page.tsx`, localizar (linha 246):
```tsx
      {showRanking && <RankingProdutosModal onClose={() => setShowRanking(false)} />}
```
Substituir por (`lojaId` já vem de `useStore()` na linha 68 desta página, já usado em todas as outras chamadas — só faltava passar pro modal):
```tsx
      {showRanking && <RankingProdutosModal onClose={() => setShowRanking(false)} lojaId={lojaId} />}
```

- [ ] **Step 3: Rodar `tsc` e confirmar zero erros**

Run: `cd web && npx tsc --noEmit`
Expected: zero erros.

- [ ] **Step 4: Smoke visual**

Rodar `npm run dev` em `web/`, navegar até `/dashboard`:
- Com "Todas as lojas" selecionada no seletor global: card "Top produtos" e modal "Ranking de produtos" mostram dado agregado (comportamento atual, sem mudança visível).
- Selecionar uma loja virtual específica: card "Top produtos" recarrega mostrando só produtos daquela loja; abrir o modal, cada categoria/aba reflete só aquela loja (verificar Network tab: as chamadas incluem `?loja_id=<id>` correto).
- Selecionar uma loja física específica: mesma verificação — card e modal mostram só produtos daquela loja física (dado sincronizado via i9Logic).
- Trocar de loja com o modal já aberto: categoria ativa recarrega automaticamente (não precisa fechar/reabrir o modal).
- Se o banco local não estiver acessível (mesma limitação já documentada em tasks anteriores desta sessão), mocke as respostas de `/api/**` no browser com payloads diferentes por `loja_id` pra confirmar que o componente de fato usa o parâmetro certo em cada chamada, documentando a limitação com a mesma honestidade já usada antes.

- [ ] **Step 5: Commit**

```bash
git add "web/src/app/_components/RankingProdutosModal.tsx" web/src/app/dashboard/page.tsx
git commit -m "feat: dashboard e modal de ranking repassam a loja selecionada"
```

---

## Self-Review

**Cobertura da spec:** 5 funções ganham `loja_id` ✅ (Task 1), 5 rotas + `kpi_overview` repassam ✅ (Task 2), 5 client functions ✅ (Task 3), modal + dashboard ✅ (Task 4). Constraint "sem loja_id = comportamento atual" ✅ testado explicitamente em cada uma das 5 funções (Task 1). Constraint "sem tocar union Bling+PDV" ✅ nenhuma task mexe nas tabelas unidas nem no branch PDV, só acrescenta `WHERE`. Constraint "convenção `lojaId?: string`" ✅ Task 3/4 seguem exatamente `relatorioClientes`/`kpiOverview`.

**Placeholders:** nenhum "TBD"/"implementar depois" — todo código é completo, incluindo os 12 testes novos (8 na Task 1, 6 na Task 2 contando o de `kpi_overview`).

**Consistência de tipos:** `loja_id` é `int | None` em todas as 5 funções Python e em todas as 5 rotas (mesmo `request.args.get("loja_id", type=int)`, que já devolve `None` quando ausente). `lojaId` é `string | undefined` em todas as 5 client functions e no modal — a conversão pra `int` só acontece no backend (query string sempre chega como texto, Flask converte). O único ponto de atenção verificado: `risco_ruptura`/`estoque_parado` usam `$2` DUAS vezes na mesma query SQL (subquery + filtro externo) mas isso continua sendo UM único parâmetro posicional — `db.fetch(sql, dias, loja_id)`, não dois — confirmado nos testes da Task 1 (`call_args.args[1:]` sempre uma tupla de 2 elementos).

## Execution Handoff

Plano completo e salvo em `docs/superpowers/plans/2026-08-09-ranking-produtos-filtro-loja.md`. Duas opções de execução:

1. **Subagent-Driven (recomendado)** — dispatch de subagente por task, review entre tasks, iteração rápida.
2. **Inline Execution** — executo as tasks nesta sessão com checkpoints de revisão.

Qual prefere?
