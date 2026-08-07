# Contatos — Paginação Real, Filtros e Dados de Remarketing — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trocar a navegação "Anterior/Próxima" de `/crm/contatos` por paginação numerada real, adicionar filtros (status, tag, WhatsApp, tempo sem comprar) e expor dados de remarketing (tags, WhatsApp, última compra, total gasto, data de nascimento) na listagem de clientes.

**Architecture:** Backend: nova função `listar_clientes_filtrado` em `core/cadastros.py`, ao lado de `list_paginado` (sem alterá-la), usando `LEFT JOIN LATERAL` em `vendas_pedidos` e `cad_cliente_tags`. A rota `GET /api/cadastros/<tabela>` ganha um branch condicional: `tabela == "clientes"` e `pagina` presente chama a função nova; qualquer outra tabela continua em `list_paginado`, idêntico a hoje. Frontend: `web/src/app/crm/contatos/page.tsx` é reescrita (implementação própria da tela, não usa `CrudPanel`) com barra de filtros, tabela reorganizada e paginação numerada.

**Tech Stack:** Flask + asyncpg (backend), Next.js 15 App Router + React 19 + Tailwind v4 (frontend), unittest + `unittest.mock` (testes Python).

## Global Constraints

- `core/cadastros.py::list_paginado`, `_list_pagina`, `_count` — nunca alterar. As outras 5 tabelas de Cadastros (empresas, usuários, fornecedores, transportadoras, vendedores) continuam chamando exatamente o que chamam hoje.
- `web/src/app/_components/CrudPanel.tsx` — não é tocado.
- `sort`/`order`/`status` sempre validados contra whitelist fixa no código antes de entrar no SQL — nunca interpolar valor bruto do request como identificador de coluna. Valores de filtro (busca, tag, status, whatsapp, sem_comprar_dias) são sempre parametrizados (`$1, $2...`), nunca concatenados na string SQL.
- `sem_comprar_dias` inclui clientes que **nunca compraram** (não é só "última compra > N dias atrás") — `compras.ultima_compra IS NULL OR compras.ultima_compra < CURRENT_DATE - $N::int`.
- Resposta de `GET /api/cadastros/clientes` mantém o mesmo formato de `list_paginado`: `{ data, total, pagina, por_pagina, total_paginas }` — nenhum envelope novo.
- Fora de escopo (não implementar): exportação CSV, gestão de tags (criar/remover), migração de volta pra `crm_contatos`, envio de campanha.
- Reaproveitar `fmtDataBR` de `web/src/lib/format.ts` para formatar datas — não escrever formatador novo (já existe fix documentado pro bug de fuso horário UTC).
- Ícones disponíveis em `web/src/app/_components/Icon.tsx` não incluem `chevronUp` nem `whatsapp` — usar `chevronDown` com `rotate-180` via className pra indicar ordenação ascendente, e um badge de texto ("WA") pro indicador de WhatsApp, não um ícone novo.

---

### Task 1: Backend — schema, índices, função de listagem filtrada e rota

**Files:**
- Modify: `hermes_agents/core/cadastros.py:59-81` (novas colunas + índice), `hermes_agents/core/cadastros.py:351-353` (novas funções, inseridas entre `list_paginado` e `get`)
- Modify: `hermes_agents/core/entidades.py:35-45` (novo índice em `vendas_pedidos.cliente_id`)
- Modify: `hermes_agents/routes/cadastros.py:7-28` (branch na rota `cad_list`), `hermes_agents/routes/cadastros.py` (nova rota `tags-disponiveis`, adicionada após `cad_fornecedor_resumo`)
- Test: `hermes_agents/tests/test_cadastros_clientes_filtrado.py` (novo, testes de `core.cadastros.listar_clientes_filtrado` e `tags_disponiveis`)
- Test: `hermes_agents/tests/test_cadastros_clientes_filtrado_rota.py` (novo, testes de rota)

**Interfaces:**
- Produces: `core.cadastros.listar_clientes_filtrado(pagina: int = 1, por_pagina: int = 50, busca: str = None, sort: str = "id", order: str = "desc", status: str = None, tag: str = None, whatsapp: bool = None, sem_comprar_dias: int = None) -> dict` retornando `{"data": [...], "total": int, "pagina": int, "por_pagina": int, "total_paginas": int}`, cada item de `data` com `id, nome, tipo, documento, email, telefone, status, whatsapp, data_nascimento, ultima_compra, total_gasto, qtd_pedidos, tags`.
- Produces: `core.cadastros.tags_disponiveis() -> list[str]`.
- Produces: rota `GET /api/cadastros/clientes/tags-disponiveis` → `{"data": ["VIP", "Atacado", ...]}`.
- Produces: `GET /api/cadastros/clientes?pagina=1&por_pagina=20&busca=&sort=&order=&status=&tag=&whatsapp=&sem_comprar_dias=` retornando o mesmo formato de `listar_clientes_filtrado`.
- Consumes: `core.get_db`, `core.run_async`, `core.log` (já importados no topo de `core/cadastros.py`); `core.cadastros._sem_campos_sensiveis` (já existe, linha 327).

- [ ] **Step 1: Escrever os dois arquivos de teste (falham porque as funções ainda não existem)**

Criar `hermes_agents/tests/test_cadastros_clientes_filtrado.py`:

```python
"""Testes de core.cadastros.listar_clientes_filtrado — endpoint dedicado de
Contatos (paginacao real + filtros + dados de remarketing), sem tocar em
list_paginado/_list_pagina/_count, que continuam servindo as outras 5
tabelas de Cadastros."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

patcher = patch("asyncpg.create_pool")
patcher.start()

import core.cadastros as cadastros


class _FakeDB:
    def __init__(self, total=0, rows=None):
        self.total = total
        self.rows = rows if rows is not None else []
        self.fetchval_calls = []
        self.fetch_calls = []

    async def fetchval(self, query, *params):
        self.fetchval_calls.append((query, params))
        return self.total

    async def fetch(self, query, *params):
        self.fetch_calls.append((query, params))
        return self.rows


def _cliente(id=1, nome="Cliente A", ultima_compra=None, total_gasto=0, qtd_pedidos=0, tags=None):
    return {
        "id": id, "nome": nome, "tipo": "PF", "documento": "123", "email": "a@x.com",
        "telefone": "111", "status": "ativo", "whatsapp": False, "data_nascimento": None,
        "ultima_compra": ultima_compra, "total_gasto": total_gasto, "qtd_pedidos": qtd_pedidos,
        "tags": tags or [],
    }


class TestListarClientesFiltradoPaginacao(unittest.TestCase):
    def test_retorna_metadados_de_paginacao(self):
        fake = _FakeDB(total=45, rows=[_cliente()])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            resultado = cadastros.listar_clientes_filtrado(pagina=2, por_pagina=20)
        self.assertEqual(resultado["total"], 45)
        self.assertEqual(resultado["pagina"], 2)
        self.assertEqual(resultado["por_pagina"], 20)
        self.assertEqual(resultado["total_paginas"], 3)

    def test_pagina_fora_do_intervalo_devolve_lista_vazia(self):
        fake = _FakeDB(total=5, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            resultado = cadastros.listar_clientes_filtrado(pagina=99, por_pagina=20)
        self.assertEqual(resultado["data"], [])
        self.assertEqual(resultado["total"], 5)
        self.assertEqual(resultado["total_paginas"], 1)

    def test_pagina_invalida_nao_quebra(self):
        fake = _FakeDB(total=0, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            resultado = cadastros.listar_clientes_filtrado(pagina=0, por_pagina=-5)
        self.assertEqual(resultado["pagina"], 1)
        self.assertEqual(resultado["por_pagina"], 1)


class TestListarClientesFiltradoFiltros(unittest.TestCase):
    def test_filtro_status_isolado(self):
        fake = _FakeDB(total=1, rows=[_cliente()])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(status="ativo")
        query, params = fake.fetch_calls[-1]
        self.assertIn("c.status =", query)
        self.assertIn("ativo", params)

    def test_filtro_tag_isolado(self):
        fake = _FakeDB(total=1, rows=[_cliente()])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(tag="VIP")
        query, params = fake.fetch_calls[-1]
        self.assertIn("EXISTS", query)
        self.assertIn("VIP", params)

    def test_filtro_whatsapp_isolado(self):
        fake = _FakeDB(total=1, rows=[_cliente(whatsapp=True)])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(whatsapp=True)
        query, params = fake.fetch_calls[-1]
        self.assertIn("c.whatsapp =", query)
        self.assertIn(True, params)

    def test_filtro_sem_comprar_dias_inclui_quem_nunca_comprou(self):
        fake = _FakeDB(total=1, rows=[_cliente()])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(sem_comprar_dias=30)
        query, params = fake.fetch_calls[-1]
        self.assertIn("compras.ultima_compra IS NULL", query)
        self.assertIn(30, params)

    def test_combinacao_de_filtros(self):
        fake = _FakeDB(total=1, rows=[_cliente()])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(status="ativo", tag="VIP", whatsapp=True, sem_comprar_dias=60)
        query, params = fake.fetch_calls[-1]
        self.assertIn("c.status =", query)
        self.assertIn("EXISTS", query)
        self.assertIn("c.whatsapp =", query)
        self.assertIn("compras.ultima_compra IS NULL", query)
        self.assertEqual(len(params), 4)


class TestListarClientesFiltradoOrdenacao(unittest.TestCase):
    def test_sort_whitelist_aceita_colunas_derivadas(self):
        fake = _FakeDB(total=0, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(sort="ultima_compra", order="asc")
        query, _ = fake.fetch_calls[-1]
        self.assertIn("ORDER BY compras.ultima_compra ASC", query)

    def test_sort_total_gasto(self):
        fake = _FakeDB(total=0, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(sort="total_gasto", order="desc")
        query, _ = fake.fetch_calls[-1]
        self.assertIn("ORDER BY compras.total_gasto DESC", query)

    def test_sort_fora_da_whitelist_cai_no_default(self):
        fake = _FakeDB(total=0, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(sort="documento; DROP TABLE cad_clientes;--")
        query, _ = fake.fetch_calls[-1]
        self.assertIn("ORDER BY c.id", query)
        self.assertNotIn("DROP TABLE", query)

    def test_order_fora_da_whitelist_cai_no_default_desc(self):
        fake = _FakeDB(total=0, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(order="qualquer-coisa")
        query, _ = fake.fetch_calls[-1]
        self.assertIn("ORDER BY c.id DESC", query)


class TestListarClientesFiltradoRespostaEBusca(unittest.TestCase):
    def test_resposta_inclui_campos_de_remarketing(self):
        fake = _FakeDB(total=1, rows=[_cliente(ultima_compra="2026-07-01", total_gasto=500, qtd_pedidos=3, tags=["VIP"])])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            resultado = cadastros.listar_clientes_filtrado()
        item = resultado["data"][0]
        self.assertEqual(item["ultima_compra"], "2026-07-01")
        self.assertEqual(item["total_gasto"], 500)
        self.assertEqual(item["tags"], ["VIP"])

    def test_busca_livre_usa_mesmos_campos_de_clientes(self):
        fake = _FakeDB(total=0, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(busca="joao")
        query, params = fake.fetch_calls[-1]
        self.assertIn("c.nome ILIKE", query)
        self.assertIn("c.documento ILIKE", query)
        self.assertIn("c.email ILIKE", query)
        self.assertIn("c.telefone ILIKE", query)
        self.assertIn("%joao%", params)


class TestTagsDisponiveis(unittest.TestCase):
    def test_retorna_lista_de_tags(self):
        async def _fetch(query, *params):
            return [{"tag": "VIP"}, {"tag": "Atacado"}]
        fake_db = AsyncMock()
        fake_db.fetch = _fetch
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake_db)):
            resultado = cadastros.tags_disponiveis()
        self.assertEqual(resultado, ["VIP", "Atacado"])

    def test_erro_de_banco_devolve_lista_vazia(self):
        async def _fetch_falha(query, *params):
            raise RuntimeError("db down")
        fake_db = AsyncMock()
        fake_db.fetch = _fetch_falha
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake_db)):
            resultado = cadastros.tags_disponiveis()
        self.assertEqual(resultado, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

Criar `hermes_agents/tests/test_cadastros_clientes_filtrado_rota.py`:

```python
"""Testes de rota — GET /api/cadastros/clientes com pagina+filtros roteia
para listar_clientes_filtrado; outras tabelas continuam em list_paginado
(regressao); tags-disponiveis exige cadastros.ver."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

from flask import Flask
from routes.cadastros import cadastros_bp


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(cadastros_bp)
    return app.test_client()


class TestRotaClientesFiltrado(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_clientes_com_pagina_usa_listar_clientes_filtrado(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.cadastros.listar_clientes_filtrado", return_value={"data": [], "total": 0, "pagina": 1, "por_pagina": 20, "total_paginas": 1}) as mock_filtrado, \
             patch("core.cadastros.list_paginado") as mock_generico:
            r = self.client.get(
                "/api/cadastros/clientes?pagina=1&status=ativo&tag=VIP&whatsapp=true&sem_comprar_dias=30&sort=nome&order=asc",
                headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_filtrado.assert_called_once()
        mock_generico.assert_not_called()
        args = mock_filtrado.call_args.args
        self.assertEqual(args[0], 1)
        self.assertEqual(args[3], "nome")
        self.assertEqual(args[4], "asc")
        self.assertEqual(args[5], "ativo")
        self.assertEqual(args[6], "VIP")
        self.assertTrue(args[7])
        self.assertEqual(args[8], 30)

    def test_outra_tabela_continua_em_list_paginado(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.cadastros.list_paginado", return_value={"data": [], "total": 0, "pagina": 1, "por_pagina": 50, "total_paginas": 1}) as mock_generico, \
             patch("core.cadastros.listar_clientes_filtrado") as mock_filtrado:
            r = self.client.get("/api/cadastros/fornecedores?pagina=1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_generico.assert_called_once_with("fornecedores", 1, 50, None)
        mock_filtrado.assert_not_called()

    def test_clientes_sem_pagina_mantem_comportamento_antigo(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.cadastros.list", return_value=[{"id": 1}]) as mock_list, \
             patch("core.cadastros.listar_clientes_filtrado") as mock_filtrado:
            r = self.client.get("/api/cadastros/clientes", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_list.assert_called_once_with("clientes")
        mock_filtrado.assert_not_called()

    def test_tags_disponiveis_exige_permissao(self):
        import core.rbac as rbac
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]), \
             patch("core.cadastros.tags_disponiveis") as mock_tags:
            r = self.client.get("/api/cadastros/clientes/tags-disponiveis", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_tags.assert_not_called()

    def test_tags_disponiveis_com_permissao_retorna_lista(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.cadastros.tags_disponiveis", return_value=["VIP", "Atacado"]) as mock_tags:
            r = self.client.get("/api/cadastros/clientes/tags-disponiveis", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["data"], ["VIP", "Atacado"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_cadastros_clientes_filtrado.py tests/test_cadastros_clientes_filtrado_rota.py -v`
Expected: FAIL — `AttributeError: module 'core.cadastros' has no attribute 'listar_clientes_filtrado'` (e equivalente pra `tags_disponiveis`).

- [ ] **Step 3: Adicionar as novas colunas e o índice em `cad_cliente_tags`**

Em `hermes_agents/core/cadastros.py`, localizar (linhas 59-62):

```python
        await db.execute("ALTER TABLE cad_clientes ADD COLUMN IF NOT EXISTS email VARCHAR(200)")
        await db.execute("ALTER TABLE cad_clientes ADD COLUMN IF NOT EXISTS telefone VARCHAR(30)")
        await db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_cad_clientes_documento_unico
            ON cad_clientes (documento) WHERE documento IS NOT NULL AND documento != ''""")
```

Substituir por:

```python
        await db.execute("ALTER TABLE cad_clientes ADD COLUMN IF NOT EXISTS email VARCHAR(200)")
        await db.execute("ALTER TABLE cad_clientes ADD COLUMN IF NOT EXISTS telefone VARCHAR(30)")
        await db.execute("ALTER TABLE cad_clientes ADD COLUMN IF NOT EXISTS whatsapp BOOLEAN DEFAULT FALSE")
        await db.execute("ALTER TABLE cad_clientes ADD COLUMN IF NOT EXISTS data_nascimento DATE")
        await db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_cad_clientes_documento_unico
            ON cad_clientes (documento) WHERE documento IS NOT NULL AND documento != ''""")
```

Localizar (linhas 78-81):

```python
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_cliente_tags (
            id SERIAL PRIMARY KEY, cliente_id INT REFERENCES cad_clientes(id),
            tag VARCHAR(50), created_at TIMESTAMP DEFAULT NOW()
        )""")
```

Substituir por:

```python
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_cliente_tags (
            id SERIAL PRIMARY KEY, cliente_id INT REFERENCES cad_clientes(id),
            tag VARCHAR(50), created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_cad_cliente_tags_cliente_id ON cad_cliente_tags (cliente_id)")
```

- [ ] **Step 4: Adicionar o índice em `vendas_pedidos.cliente_id`**

Em `hermes_agents/core/entidades.py`, localizar o fim do loop de FKs (linhas 35-45):

```python
        for tabela, col_def in alteracoes:
            col_nome = col_def.split()[0]
            try:
                col_exists = await db.fetchval(
                    "SELECT column_name FROM information_schema.columns WHERE table_name=$1 AND column_name=$2",
                    tabela, col_nome)
                if not col_exists:
                    await db.execute(f"ALTER TABLE {tabela} ADD COLUMN {col_def}")
                    log(AGENT, f"FK adicionada: {tabela}.{col_nome}")
            except Exception as e:
                log(AGENT, f"FK skip {tabela}.{col_nome}: {e}")
```

Adicionar logo abaixo (ainda dentro de `_go()`, mesma indentação de 8 espaços do `for`):

```python
        for tabela, col_def in alteracoes:
            col_nome = col_def.split()[0]
            try:
                col_exists = await db.fetchval(
                    "SELECT column_name FROM information_schema.columns WHERE table_name=$1 AND column_name=$2",
                    tabela, col_nome)
                if not col_exists:
                    await db.execute(f"ALTER TABLE {tabela} ADD COLUMN {col_def}")
                    log(AGENT, f"FK adicionada: {tabela}.{col_nome}")
            except Exception as e:
                log(AGENT, f"FK skip {tabela}.{col_nome}: {e}")

        # Indice pro join de remarketing de Contatos (core/cadastros.py::listar_clientes_filtrado)
        # — nao existia, sustenta o LEFT JOIN LATERAL em vendas_pedidos por cliente_id.
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_vendas_pedidos_cliente_id ON vendas_pedidos (cliente_id)")
        except Exception as e:
            log(AGENT, f"Indice skip vendas_pedidos.cliente_id: {e}")
```

- [ ] **Step 5: Implementar `listar_clientes_filtrado` e `tags_disponiveis`**

Em `hermes_agents/core/cadastros.py`, localizar o fim de `list_paginado` (linhas 335-351):

```python
def list_paginado(tabela: str, pagina: int = 1, por_pagina: int = 50, busca: str = None) -> dict:
    pagina = max(1, pagina or 1)
    por_pagina = max(1, min(por_pagina or 50, 200))
    tabela_sql = _resolve(tabela)
    campos_busca = _CAMPOS_BUSCA.get(tabela)
    busca = (busca or "").strip() or None
    offset = (pagina - 1) * por_pagina
    dados = _list_pagina(tabela_sql, limit=por_pagina, offset=offset, campos_busca=campos_busca, busca=busca)
    total = _count(tabela_sql, campos_busca=campos_busca, busca=busca)
    total_paginas = max(1, -(-total // por_pagina)) if total else 1
    return {
        "data": [_sem_campos_sensiveis(tabela, r) for r in dados],
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": total_paginas,
    }

def get(tabela: str, id: int): return _sem_campos_sensiveis(tabela, _get(_resolve(tabela), id))
```

Inserir, entre essas duas funções, o bloco novo (fica exatamente ao lado de `list_paginado`, sem alterá-la):

```python
def list_paginado(tabela: str, pagina: int = 1, por_pagina: int = 50, busca: str = None) -> dict:
    pagina = max(1, pagina or 1)
    por_pagina = max(1, min(por_pagina or 50, 200))
    tabela_sql = _resolve(tabela)
    campos_busca = _CAMPOS_BUSCA.get(tabela)
    busca = (busca or "").strip() or None
    offset = (pagina - 1) * por_pagina
    dados = _list_pagina(tabela_sql, limit=por_pagina, offset=offset, campos_busca=campos_busca, busca=busca)
    total = _count(tabela_sql, campos_busca=campos_busca, busca=busca)
    total_paginas = max(1, -(-total // por_pagina)) if total else 1
    return {
        "data": [_sem_campos_sensiveis(tabela, r) for r in dados],
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": total_paginas,
    }

# ── Contatos: listagem filtrada com dados de remarketing ──
# Fica ao lado de list_paginado/_list_pagina/_count, sem alterá-las — as
# outras 5 tabelas de Cadastros continuam chamando list_paginado como hoje.

CLIENTES_SORT_MAP = {
    "id": "c.id",
    "nome": "c.nome",
    "ultima_compra": "compras.ultima_compra",
    "total_gasto": "compras.total_gasto",
}

_COMPRAS_LATERAL = """LEFT JOIN LATERAL (
        SELECT MAX(vp.data) AS ultima_compra, COALESCE(SUM(vp.total), 0) AS total_gasto, COUNT(*) AS qtd_pedidos
        FROM vendas_pedidos vp
        WHERE vp.cliente_id = c.id AND vp.status != 'cancelado'
    ) compras ON TRUE"""

_TAGS_LATERAL = """LEFT JOIN LATERAL (
        SELECT array_agg(t.tag ORDER BY t.tag) AS tags
        FROM cad_cliente_tags t
        WHERE t.cliente_id = c.id
    ) tags_agg ON TRUE"""

def listar_clientes_filtrado(pagina: int = 1, por_pagina: int = 50, busca: str = None,
                              sort: str = "id", order: str = "desc", status: str = None,
                              tag: str = None, whatsapp: bool = None, sem_comprar_dias: int = None) -> dict:
    pagina = max(1, pagina or 1)
    por_pagina = max(1, min(por_pagina or 50, 200))
    offset = (pagina - 1) * por_pagina
    sort_col = CLIENTES_SORT_MAP.get(sort, CLIENTES_SORT_MAP["id"])
    order_sql = "ASC" if str(order).lower() == "asc" else "DESC"
    busca = (busca or "").strip() or None

    where = []
    params = []

    def _param(v):
        params.append(v)
        return f"${len(params)}"

    if busca:
        p = _param(f"%{busca}%")
        where.append(f"(c.nome ILIKE {p} OR c.documento ILIKE {p} OR c.email ILIKE {p} OR c.telefone ILIKE {p})")
    if status:
        where.append(f"c.status = {_param(status)}")
    if whatsapp is not None:
        where.append(f"c.whatsapp = {_param(whatsapp)}")
    if tag:
        where.append(f"EXISTS (SELECT 1 FROM cad_cliente_tags t2 WHERE t2.cliente_id = c.id AND t2.tag = {_param(tag)})")
    if sem_comprar_dias is not None:
        where.append(f"(compras.ultima_compra IS NULL OR compras.ultima_compra < CURRENT_DATE - {_param(int(sem_comprar_dias))}::int)")

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    async def _go():
        db = await get_db()
        total_result = await db.fetchval(
            f"SELECT COUNT(*) FROM cad_clientes c {_COMPRAS_LATERAL} {where_sql}",
            *params)
        rows = await db.fetch(
            f"""SELECT c.*, compras.ultima_compra, compras.total_gasto, compras.qtd_pedidos,
                       COALESCE(tags_agg.tags, ARRAY[]::varchar[]) AS tags
                FROM cad_clientes c
                {_COMPRAS_LATERAL}
                {_TAGS_LATERAL}
                {where_sql}
                ORDER BY {sort_col} {order_sql} NULLS LAST
                LIMIT {por_pagina} OFFSET {offset}""",
            *params)
        return [dict(r) for r in rows], (total_result or 0)
    try:
        dados, total = run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro listar_clientes_filtrado: {e}")
        dados, total = [], 0
    total_paginas = max(1, -(-total // por_pagina)) if total else 1
    return {
        "data": [_sem_campos_sensiveis("clientes", r) for r in dados],
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": total_paginas,
    }

def tags_disponiveis() -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT DISTINCT tag FROM cad_cliente_tags WHERE tag IS NOT NULL ORDER BY tag")
        return [r["tag"] for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"Erro tags_disponiveis: {e}"); return []

def get(tabela: str, id: int): return _sem_campos_sensiveis(tabela, _get(_resolve(tabela), id))
```

- [ ] **Step 6: Rodar os testes de core e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_cadastros_clientes_filtrado.py -v`
Expected: PASS (13 testes).

- [ ] **Step 7: Ligar a rota**

Em `hermes_agents/routes/cadastros.py`, substituir o `cad_list` (linhas 7-28):

```python
@cadastros_bp.route("/<tabela>", methods=["GET"])
def cad_list(tabela):
    from core.cadastros import list as cad_list_fn, list_paginado, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    # ponytail: faltava @requer_permissao aqui — qualquer usuario com token
    # valido (mesmo sem nenhuma permissao atribuida) conseguia listar
    # /api/cadastros/empresas, /api/cadastros/usuarios etc. O CRM (crm.py) ja
    # exige crm.ver pro mesmo tipo de rota; Cadastros ficou pra tras.
    @requer_permissao("cadastros.ver")
    def _go():
        # ?pagina= opcional — sem ele mantem o comportamento antigo (ate 100
        # registros, sem total) para nao quebrar telas que ja consomem esta
        # rota sem paginacao (ClientesTab e as demais abas de Cadastros).
        pagina = request.args.get("pagina", type=int)
        if pagina is not None:
            por_pagina = request.args.get("por_pagina", default=50, type=int)
            busca = request.args.get("busca", default=None, type=str)
            return jsonify(list_paginado(tabela, pagina, por_pagina, busca))
        return jsonify({"data": cad_list_fn(tabela)})
    return _go()
```

Por:

```python
@cadastros_bp.route("/<tabela>", methods=["GET"])
def cad_list(tabela):
    from core.cadastros import list as cad_list_fn, list_paginado, listar_clientes_filtrado, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    # ponytail: faltava @requer_permissao aqui — qualquer usuario com token
    # valido (mesmo sem nenhuma permissao atribuida) conseguia listar
    # /api/cadastros/empresas, /api/cadastros/usuarios etc. O CRM (crm.py) ja
    # exige crm.ver pro mesmo tipo de rota; Cadastros ficou pra tras.
    @requer_permissao("cadastros.ver")
    def _go():
        # ?pagina= opcional — sem ele mantem o comportamento antigo (ate 100
        # registros, sem total) para nao quebrar telas que ja consomem esta
        # rota sem paginacao (ClientesTab e as demais abas de Cadastros).
        pagina = request.args.get("pagina", type=int)
        if pagina is not None:
            por_pagina = request.args.get("por_pagina", default=50, type=int)
            busca = request.args.get("busca", default=None, type=str)
            if tabela == "clientes":
                sort = request.args.get("sort", default="id", type=str)
                order = request.args.get("order", default="desc", type=str)
                status = request.args.get("status", default=None, type=str)
                tag = request.args.get("tag", default=None, type=str)
                whatsapp_raw = request.args.get("whatsapp", default=None, type=str)
                whatsapp = {"true": True, "false": False}.get((whatsapp_raw or "").lower())
                sem_comprar_dias = request.args.get("sem_comprar_dias", default=None, type=int)
                return jsonify(listar_clientes_filtrado(
                    pagina, por_pagina, busca, sort, order, status, tag, whatsapp, sem_comprar_dias))
            return jsonify(list_paginado(tabela, pagina, por_pagina, busca))
        return jsonify({"data": cad_list_fn(tabela)})
    return _go()
```

Adicionar nova rota após `cad_fornecedor_resumo` (final do arquivo):

```python
@cadastros_bp.route("/clientes/tags-disponiveis", methods=["GET"])
def cad_clientes_tags_disponiveis():
    from core.cadastros import tags_disponiveis

    @requer_permissao("cadastros.ver")
    def _go():
        return jsonify({"data": tags_disponiveis()})
    return _go()
```

- [ ] **Step 8: Rodar os testes de rota e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_cadastros_clientes_filtrado_rota.py -v`
Expected: PASS (5 testes).

- [ ] **Step 9: Rodar a suíte completa de cadastros pra garantir que não quebrou nada existente**

Run: `cd hermes_agents && python -m pytest tests/test_cadastros_seguranca.py tests/test_cadastros_clientes_filtrado.py tests/test_cadastros_clientes_filtrado_rota.py -v`
Expected: PASS (todos).

- [ ] **Step 10: Commit**

```bash
git add hermes_agents/core/cadastros.py hermes_agents/core/entidades.py hermes_agents/routes/cadastros.py hermes_agents/tests/test_cadastros_clientes_filtrado.py hermes_agents/tests/test_cadastros_clientes_filtrado_rota.py
git commit -m "feat: listagem filtrada de clientes com paginacao real e dados de remarketing"
```

---

### Task 2: Frontend — filtros, tabela reorganizada e paginação numerada

**Files:**
- Modify: `web/src/lib/api.ts:833-837` (5º parâmetro `filtros` em `cadListPaginado` + novo `cadClientesTagsDisponiveis`)
- Modify: `web/src/app/crm/contatos/page.tsx` (reescrita completa)

**Interfaces:**
- Consumes: `GET /api/cadastros/clientes?pagina=&por_pagina=&busca=&sort=&order=&status=&tag=&whatsapp=&sem_comprar_dias=` → `{ data, total, pagina, por_pagina, total_paginas }` (Task 1); `GET /api/cadastros/clientes/tags-disponiveis` → `{ data: string[] }` (Task 1); `fmtBRL`, `fmtDataBR` de `web/src/lib/format.ts` (já existentes).
- Produces: nenhuma interface nova consumida por outro código — página folha.

- [ ] **Step 1: Estender `cadListPaginado` e adicionar `cadClientesTagsDisponiveis`**

Em `web/src/lib/api.ts`, localizar (linhas 833-837):

```typescript
  cadListPaginado: (tabela: string, pagina: number, porPagina = 50, busca?: string) => {
    const q = new URLSearchParams({ pagina: String(pagina), por_pagina: String(porPagina) });
    if (busca) q.set("busca", busca);
    return request<{ data: unknown[]; total: number; pagina: number; por_pagina: number; total_paginas: number }>(`/api/cadastros/${tabela}?${q}`);
  },
```

Substituir por:

```typescript
  cadListPaginado: (tabela: string, pagina: number, porPagina = 50, busca?: string, filtros?: Record<string, string>) => {
    const q = new URLSearchParams({ pagina: String(pagina), por_pagina: String(porPagina) });
    if (busca) q.set("busca", busca);
    if (filtros) {
      for (const [k, v] of Object.entries(filtros)) {
        if (v) q.set(k, v);
      }
    }
    return request<{ data: unknown[]; total: number; pagina: number; por_pagina: number; total_paginas: number }>(`/api/cadastros/${tabela}?${q}`);
  },
  cadClientesTagsDisponiveis: () => request<{ data: string[] }>("/api/cadastros/clientes/tags-disponiveis"),
```

- [ ] **Step 2: Rodar `tsc` (deve continuar limpo — mudança é aditiva)**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros.

- [ ] **Step 3: Reescrever `web/src/app/crm/contatos/page.tsx`**

Substituir o arquivo inteiro por:

```tsx
"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { Can } from "@/lib/auth";
import Icon from "@/app/_components/Icon";
import PageHeader from "@/app/_components/PageHeader";
import { fmtBRL, fmtDataBR } from "@/lib/format";

interface Cliente {
  id: number;
  nome: string;
  tipo: string;
  documento: string | null;
  email: string | null;
  telefone: string | null;
  status: string;
  whatsapp: boolean;
  data_nascimento: string | null;
  ultima_compra: string | null;
  total_gasto: number;
  qtd_pedidos: number;
  tags: string[];
}

type Sort = "id" | "nome" | "ultima_compra" | "total_gasto";
type Order = "asc" | "desc";

function extrairErro(res: unknown): string | null {
  if (res && typeof res === "object" && "error" in res && (res as { error?: unknown }).error) {
    return String((res as { error: unknown }).error);
  }
  return null;
}

function janelaPaginas(atual: number, total: number): number[] {
  const inicio = Math.max(1, Math.min(atual - 2, total - 4));
  const fim = Math.min(total, inicio + 4);
  const janela: number[] = [];
  for (let i = Math.max(1, inicio); i <= fim; i++) janela.push(i);
  return janela;
}

export default function Page() {
  const [items, setItems] = useState<Cliente[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busca, setBusca] = useState("");
  const [buscaAtiva, setBuscaAtiva] = useState("");
  const [pagina, setPagina] = useState(1);
  const [porPagina, setPorPagina] = useState(20);
  const [total, setTotal] = useState(0);
  const [totalPaginas, setTotalPaginas] = useState(1);

  const [sort, setSort] = useState<Sort>("id");
  const [order, setOrder] = useState<Order>("desc");
  const [filtroStatus, setFiltroStatus] = useState("");
  const [filtroTag, setFiltroTag] = useState("");
  const [filtroWhatsapp, setFiltroWhatsapp] = useState("");
  const [filtroSemComprarDias, setFiltroSemComprarDias] = useState("");
  const [tagsDisponiveis, setTagsDisponiveis] = useState<string[]>([]);

  const [modal, setModal] = useState<{ open: boolean; mode: "create" | "edit"; row?: Cliente }>({ open: false, mode: "create" });
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const [statusAlvo, setStatusAlvo] = useState<Cliente | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  useEffect(() => {
    api.cadClientesTagsDisponiveis().then(r => setTagsDisponiveis(r.data || [])).catch(() => {});
  }, []);

  const filtrosAtivos = !!(filtroStatus || filtroTag || filtroWhatsapp || filtroSemComprarDias);

  const carregar = useCallback(async (paginaAlvo: number, buscaAlvo: string) => {
    setLoading(true);
    setError("");
    try {
      const filtros: Record<string, string> = { sort, order };
      if (filtroStatus) filtros.status = filtroStatus;
      if (filtroTag) filtros.tag = filtroTag;
      if (filtroWhatsapp) filtros.whatsapp = filtroWhatsapp;
      if (filtroSemComprarDias) filtros.sem_comprar_dias = filtroSemComprarDias;
      const res = await api.cadListPaginado("clientes", paginaAlvo, porPagina, buscaAlvo || undefined, filtros);
      setItems((res.data || []) as Cliente[]);
      setTotal(res.total ?? 0);
      setTotalPaginas(res.total_paginas ?? 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [sort, order, filtroStatus, filtroTag, filtroWhatsapp, filtroSemComprarDias, porPagina]);

  useEffect(() => { carregar(pagina, buscaAtiva); }, [carregar, pagina, buscaAtiva]);

  // debounce: espera parar de digitar antes de disparar a busca no servidor,
  // e volta pra pagina 1 (uma busca nova pode ter menos paginas que a atual).
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setPagina(1);
      setBuscaAtiva(busca.trim());
    }, 350);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [busca]);

  const alternarSort = (coluna: Sort) => {
    if (sort === coluna) {
      setOrder(o => (o === "asc" ? "desc" : "asc"));
    } else {
      setSort(coluna);
      setOrder("desc");
    }
    setPagina(1);
  };

  const limparFiltros = () => {
    setFiltroStatus("");
    setFiltroTag("");
    setFiltroWhatsapp("");
    setFiltroSemComprarDias("");
    setPagina(1);
  };

  const abrirNovo = () => {
    setForm({ tipo: "PF" });
    setSaveError("");
    setModal({ open: true, mode: "create" });
  };

  const abrirEdicao = (row: Cliente) => {
    setForm({
      nome: row.nome || "",
      tipo: row.tipo || "PF",
      documento: row.documento || "",
      email: row.email || "",
      telefone: row.telefone || "",
      whatsapp: row.whatsapp ? "true" : "false",
      data_nascimento: row.data_nascimento || "",
    });
    setSaveError("");
    setModal({ open: true, mode: "edit", row });
  };

  const fecharModal = () => {
    if (saving) return;
    setModal({ open: false, mode: "create" });
  };

  const salvar = async () => {
    if (!form.nome?.trim()) {
      setSaveError("Nome e obrigatorio.");
      return;
    }
    setSaving(true);
    setSaveError("");
    const payload = {
      nome: form.nome.trim(),
      tipo: form.tipo || "PF",
      documento: form.documento?.trim() || "",
      email: form.email?.trim() || "",
      telefone: form.telefone?.trim() || "",
      whatsapp: form.whatsapp === "true",
      data_nascimento: form.data_nascimento || null,
    };
    try {
      const res = modal.mode === "create"
        ? await api.cadCreate("clientes", payload)
        : await api.cadUpdate("clientes", Number(modal.row?.id), payload);
      const erro = extrairErro(res);
      if (erro) { setSaveError(erro); return; }
      setModal({ open: false, mode: "create" });
      await carregar(modal.mode === "create" ? 1 : pagina, buscaAtiva);
      if (modal.mode === "create") setPagina(1);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const alternarStatus = async (row: Cliente) => {
    const novoStatus = row.status === "ativo" ? "inativo" : "ativo";
    setTogglingId(row.id);
    try {
      const res = await api.cadUpdate("clientes", row.id, { status: novoStatus });
      const erro = extrairErro(res);
      if (erro) { setError(erro); return; }
      setStatusAlvo(null);
      await carregar(pagina, buscaAtiva);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setTogglingId(null);
    }
  };

  const inicioItem = total === 0 ? 0 : (pagina - 1) * porPagina + 1;
  const fimItem = Math.min(pagina * porPagina, total);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <PageHeader title="Contatos" subtitle="Agenda de clientes e contatos comerciais" />
        <Can permission="cadastros.criar">
          <button onClick={abrirNovo} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">+ Novo</button>
        </Can>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div className="relative w-full max-w-xs">
          <Icon name="search" size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-500" />
          <input
            type="text"
            placeholder="Buscar por nome, documento, email ou telefone..."
            value={busca}
            onChange={e => setBusca(e.target.value)}
            className="w-full rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 pl-8 pr-3 text-xs text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
          />
        </div>

        <select value={filtroStatus} onChange={e => { setFiltroStatus(e.target.value); setPagina(1); }}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none">
          <option value="">Status: todos</option>
          <option value="ativo">Ativo</option>
          <option value="inativo">Inativo</option>
        </select>

        <select value={filtroTag} onChange={e => { setFiltroTag(e.target.value); setPagina(1); }}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none">
          <option value="">Tag: todas</option>
          {tagsDisponiveis.map(t => <option key={t} value={t}>{t}</option>)}
        </select>

        <select value={filtroWhatsapp} onChange={e => { setFiltroWhatsapp(e.target.value); setPagina(1); }}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none">
          <option value="">WhatsApp: qualquer</option>
          <option value="true">Com WhatsApp</option>
          <option value="false">Sem WhatsApp</option>
        </select>

        <select value={filtroSemComprarDias} onChange={e => { setFiltroSemComprarDias(e.target.value); setPagina(1); }}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none">
          <option value="">Última compra: qualquer</option>
          <option value="30">Sem comprar há 30+ dias</option>
          <option value="60">Sem comprar há 60+ dias</option>
          <option value="90">Sem comprar há 90+ dias</option>
          <option value="180">Sem comprar há 180+ dias</option>
        </select>

        {filtrosAtivos && (
          <button onClick={limparFiltros} className="text-xs text-neutral-500 hover:text-neutral-300 px-2 py-1.5">
            Limpar filtros
          </button>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-900/50 bg-red-950/30 px-4 py-3 text-xs text-red-400">
          <Icon name="alert" size={15} className="shrink-0" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="overflow-hidden rounded-lg border border-neutral-800">
          <div className="divide-y divide-neutral-800/70">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex gap-4 px-4 py-3">
                {Array.from({ length: 6 }).map((_, j) => <div key={j} className="h-3 flex-1 animate-pulse rounded bg-neutral-800" />)}
              </div>
            ))}
          </div>
        </div>
      ) : items.length === 0 ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center">
          <p className="text-neutral-400 text-sm">{buscaAtiva || filtrosAtivos ? "Nenhum contato encontrado para esse filtro." : "Nenhum contato cadastrado."}</p>
        </div>
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3 cursor-pointer select-none hover:text-neutral-200" onClick={() => alternarSort("nome")}>
                  Nome
                  {sort === "nome" && (
                    <Icon name="chevronDown" size={11} className={"inline ml-0.5" + (order === "asc" ? " rotate-180" : "")} />
                  )}
                </th>
                <th className="text-left p-3">Contato</th>
                <th className="text-left p-3">Tags</th>
                <th className="text-left p-3 cursor-pointer select-none hover:text-neutral-200" onClick={() => alternarSort("ultima_compra")}>
                  Última compra
                  {sort === "ultima_compra" && (
                    <Icon name="chevronDown" size={11} className={"inline ml-0.5" + (order === "asc" ? " rotate-180" : "")} />
                  )}
                </th>
                <th className="text-right p-3 cursor-pointer select-none hover:text-neutral-200" onClick={() => alternarSort("total_gasto")}>
                  Total gasto
                  {sort === "total_gasto" && (
                    <Icon name="chevronDown" size={11} className={"inline ml-0.5" + (order === "asc" ? " rotate-180" : "")} />
                  )}
                </th>
                <th className="text-left p-3">Status</th>
                <th className="text-right p-3">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, i) => (
                <tr key={item.id} className={"border-b border-neutral-700/50 " + (i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50")}>
                  <td className="p-3 text-neutral-300">{item.nome}</td>
                  <td className="p-3 text-neutral-300">
                    <div>{item.email || "—"}</div>
                    <div className="flex items-center gap-1.5 text-neutral-500">
                      <span>{item.telefone || "—"}</span>
                      {item.whatsapp && (
                        <span className="px-1 py-0.5 rounded text-[9px] font-semibold bg-emerald-500/20 text-emerald-400">WA</span>
                      )}
                    </div>
                  </td>
                  <td className="p-3">
                    <div className="flex flex-wrap gap-1">
                      {item.tags.slice(0, 3).map(t => (
                        <span key={t} className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-500/20 text-indigo-400">{t}</span>
                      ))}
                      {item.tags.length > 3 && <span className="text-[10px] text-neutral-500">+{item.tags.length - 3}</span>}
                      {item.tags.length === 0 && <span className="text-neutral-600">—</span>}
                    </div>
                  </td>
                  <td className="p-3 text-neutral-300">{fmtDataBR(item.ultima_compra)}</td>
                  <td className="p-3 text-right text-neutral-300">{fmtBRL(item.total_gasto)}</td>
                  <td className="p-3">
                    <span className={"px-2 py-0.5 rounded text-[10px] font-medium " + (item.status === "ativo" ? "bg-emerald-500/20 text-emerald-400" : "bg-neutral-500/20 text-neutral-400")}>
                      {item.status === "ativo" ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td className="p-3">
                    <div className="flex justify-end gap-1">
                      <Can permission="cadastros.editar">
                        <button onClick={() => abrirEdicao(item)} title="Editar" className="rounded-md p-1.5 text-neutral-500 hover:bg-indigo-500/10 hover:text-indigo-400">
                          <Icon name="pencil" size={13} />
                        </button>
                      </Can>
                      <Can permission="cadastros.excluir">
                        <button
                          onClick={() => (item.status === "ativo" ? setStatusAlvo(item) : alternarStatus(item))}
                          disabled={togglingId === item.id}
                          title={item.status === "ativo" ? "Desativar" : "Reativar"}
                          className={"rounded-md p-1.5 disabled:opacity-50 " + (item.status === "ativo" ? "text-neutral-500 hover:bg-red-500/10 hover:text-red-400" : "text-neutral-500 hover:bg-emerald-500/10 hover:text-emerald-400")}
                        >
                          <Icon name="power" size={13} />
                        </button>
                      </Can>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-neutral-500">
          <span>Mostrando {inicioItem}–{fimItem} de {total}</span>
          <div className="flex items-center gap-2">
            <select value={porPagina} onChange={e => { setPorPagina(Number(e.target.value)); setPagina(1); }}
              className="rounded-lg border border-neutral-700 bg-neutral-800 px-2 py-1 text-neutral-300 focus:border-indigo-500 focus:outline-none">
              <option value={20}>20 / página</option>
              <option value={50}>50 / página</option>
              <option value={100}>100 / página</option>
            </select>
            <div className="flex gap-1">
              <button onClick={() => setPagina(1)} disabled={pagina <= 1}
                className="rounded-lg border border-neutral-700 px-2.5 py-1 text-neutral-300 hover:bg-neutral-800 disabled:opacity-40 disabled:hover:bg-transparent">
                «
              </button>
              <button onClick={() => setPagina(p => Math.max(1, p - 1))} disabled={pagina <= 1}
                className="rounded-lg border border-neutral-700 px-2.5 py-1 text-neutral-300 hover:bg-neutral-800 disabled:opacity-40 disabled:hover:bg-transparent">
                ‹
              </button>
              {janelaPaginas(pagina, totalPaginas).map(n => (
                <button key={n} onClick={() => setPagina(n)}
                  className={"rounded-lg border px-2.5 py-1 " + (n === pagina ? "border-indigo-500 bg-indigo-500/20 text-indigo-400" : "border-neutral-700 text-neutral-300 hover:bg-neutral-800")}>
                  {n}
                </button>
              ))}
              <button onClick={() => setPagina(p => Math.min(totalPaginas, p + 1))} disabled={pagina >= totalPaginas}
                className="rounded-lg border border-neutral-700 px-2.5 py-1 text-neutral-300 hover:bg-neutral-800 disabled:opacity-40 disabled:hover:bg-transparent">
                ›
              </button>
              <button onClick={() => setPagina(totalPaginas)} disabled={pagina >= totalPaginas}
                className="rounded-lg border border-neutral-700 px-2.5 py-1 text-neutral-300 hover:bg-neutral-800 disabled:opacity-40 disabled:hover:bg-transparent">
                »
              </button>
            </div>
          </div>
        </div>
      )}

      {modal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={fecharModal}>
          <div className="w-full max-w-[440px] rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
              <h3 className="text-sm font-semibold text-neutral-100">{modal.mode === "create" ? "Novo contato" : "Editar contato"}</h3>
              <button onClick={fecharModal} className="rounded-md p-1 text-neutral-500 hover:bg-neutral-700 hover:text-neutral-300">
                <Icon name="close" size={15} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 px-5 py-4">
              <div className="col-span-2">
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Nome *</label>
                <input type="text" value={form.nome || ""} onChange={e => setForm({ ...form, nome: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Tipo</label>
                <select value={form.tipo || "PF"} onChange={e => setForm({ ...form, tipo: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
                  <option value="PF">Pessoa Fisica (PF)</option>
                  <option value="PJ">Pessoa Juridica (PJ)</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Documento</label>
                <input type="text" placeholder={form.tipo === "PJ" ? "CNPJ" : "CPF"} value={form.documento || ""} onChange={e => setForm({ ...form, documento: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Email</label>
                <input type="email" value={form.email || ""} onChange={e => setForm({ ...form, email: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Telefone</label>
                <input type="text" value={form.telefone || ""} onChange={e => setForm({ ...form, telefone: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div className="flex items-center gap-2 pt-5">
                <input type="checkbox" id="whatsapp" checked={form.whatsapp === "true"} onChange={e => setForm({ ...form, whatsapp: e.target.checked ? "true" : "false" })}
                  className="rounded border-neutral-600 bg-neutral-700 text-indigo-500 focus:ring-indigo-500/50" />
                <label htmlFor="whatsapp" className="text-[11px] font-medium text-neutral-400">Telefone tem WhatsApp</label>
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Data de nascimento</label>
                <input type="date" value={form.data_nascimento || ""} onChange={e => setForm({ ...form, data_nascimento: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              {saveError && (
                <div className="col-span-2 text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2">{saveError}</div>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-neutral-700/70 px-5 py-4">
              <button onClick={fecharModal} disabled={saving} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200 disabled:opacity-50">Cancelar</button>
              <button onClick={salvar} disabled={saving} className="rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50">
                {saving ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {statusAlvo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setStatusAlvo(null)}>
          <div className="w-full max-w-[360px] rounded-xl border border-neutral-700 bg-neutral-800 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="mb-3 flex items-center gap-2 text-amber-400">
              <Icon name="alert" size={17} />
              <h3 className="text-sm font-semibold text-neutral-100">Desativar contato</h3>
            </div>
            <p className="mb-4 text-xs text-neutral-400">
              &quot;{statusAlvo.nome}&quot; ficara marcado como inativo. O registro nao e apagado e pode ser reativado a qualquer momento.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setStatusAlvo(null)} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button
                onClick={() => alternarStatus(statusAlvo)}
                disabled={togglingId === statusAlvo.id}
                className="rounded-lg bg-red-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-red-500 disabled:opacity-50"
              >
                {togglingId === statusAlvo.id ? "Aguarde..." : "Desativar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Rodar `tsc` e confirmar que está limpo**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros.

- [ ] **Step 5: Smoke visual (Playwright ou navegador)**

Iniciar o dev server (`npm run dev` dentro de `web/`), navegar até `/crm/contatos` e confirmar:
- Tabela renderiza com colunas Nome/Contato/Tags/Última compra/Total gasto/Status/Ações.
- Filtros (Status, Tag, WhatsApp, Sem comprar há) alteram a lista e voltam pra página 1.
- Paginação numerada funciona (clicar em número de página, «/‹/›/» respeitam os limites).
- Ordenar clicando em Nome/Última compra/Total gasto alterna asc/desc (seta gira).
- Criar/editar/desativar cliente continua funcionando, incluindo os campos novos (WhatsApp, Data de nascimento).

- [ ] **Step 6: Commit**

```bash
git add web/src/lib/api.ts "web/src/app/crm/contatos/page.tsx"
git commit -m "feat: paginacao numerada, filtros e dados de remarketing em /crm/contatos"
```

---

## Self-Review

**Cobertura do spec:** Novas colunas (whatsapp, data_nascimento) ✅ Task 1 Step 3. Índices novos (vendas_pedidos.cliente_id, cad_cliente_tags.cliente_id) ✅ Task 1 Steps 3-4. Parâmetros sort/order/status/tag/whatsapp/sem_comprar_dias na rota ✅ Task 1 Step 7. `listar_clientes_filtrado` com os dois LATERALs ✅ Task 1 Step 5. Rota `tags-disponiveis` ✅ Task 1 Steps 5+7. `cadListPaginado` com `filtros` + `cadClientesTagsDisponiveis` ✅ Task 2 Step 1. Barra de filtros, tabela reorganizada, paginação numerada, modal com WhatsApp/Data de nascimento, badges de tag ✅ Task 2 Step 3. Testes de cada filtro isolado/combinado/whitelist/paginação fora do intervalo/regressão de outra tabela ✅ Task 1 Steps 1, 6, 8.

**Placeholders:** nenhum "TBD"/"implementar depois" — todo código é completo e executável como escrito.

**Consistência de tipos:** `listar_clientes_filtrado` tem a mesma assinatura em todos os pontos (definição, chamada da rota, testes). `Cliente` (frontend) espelha exatamente os campos que `listar_clientes_filtrado` devolve. `janelaPaginas`/`extrairErro` são funções puras usadas só dentro do próprio arquivo, sem contrato externo.

## Execution Handoff

Plano completo e salvo em `docs/superpowers/plans/2026-08-07-contatos-paginacao-filtros-remarketing.md`. Duas opções de execução:

1. **Subagent-Driven (recomendado)** — dispatch de subagente por task, review entre tasks, iteração rápida.
2. **Inline Execution** — executo as tasks nesta sessão com checkpoints de revisão.

Qual prefere?
