# Leads — Paginação, Filtros, Ordenação e Exportador Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lapidar `/crm/leads` com paginação, filtros, ordenação e exportador CSV, mantendo as outras 11 telas que usam `CrudPanel` intocadas.

**Architecture:** Backend reaproveita a rota `GET /api/crm/leads` existente — um branch novo ativa filtros/paginação/ordenação server-side só quando a querystring tiver esses parâmetros; sem eles, cai no comportamento antigo. Frontend ganha um componente dedicado `LeadsPanel` (não genérico) que substitui `CrudPanel` só na tela de Leads; o modal de criar/editar é extraído de `CrudPanel` para um subcomponente `CrudFormModal` reutilizado por ambos, sem mudar a API pública de `CrudPanel`.

**Tech Stack:** Flask + asyncpg (backend), Next.js/React + TypeScript + Tailwind (frontend). Nenhuma dependência nova.

## Global Constraints

- `CrudPanel.tsx` mantém a mesma API pública (`props`, `FieldDef`, `Column`, `CrudService` continuam exportados do mesmo módulo) — as outras 11 telas não podem precisar de nenhuma mudança.
- Nenhuma rota nova no Flask — só a rota `GET /api/crm/leads` já existente ganha um branch condicional.
- `sort`/`order` do backend só aceitam valores de uma whitelist fixa (`id`, `valor_potencial`, `status`, `funil_etapa`) — nunca interpolar o valor bruto do usuário na cláusula `ORDER BY`.
- Todo valor de filtro vai parametrizado (`$1, $2...`) na query SQL — nunca concatenado direto.
- Exportação usa o mesmo endpoint com `export=true`, cap de 5000 linhas, sem lib nova (CSV montado à mão no frontend).
- Sem testes de frontend automatizados neste projeto (confirmado — sem `jest`/`vitest`, só `playwright test` para e2e manual/existente) — a verificação de UI é manual via browser real.

---

### Task 1: Backend — `listar_leads_filtrado()` em `core/crm.py`

**Files:**
- Modify: `hermes_agents/core/crm.py` (adicionar função nova perto de `_list`/`list`, por volta da linha 247)
- Test: `hermes_agents/tests/test_crm_leads_filtro.py` (novo arquivo)

**Interfaces:**
- Produces: `listar_leads_filtrado(page=1, page_size=25, sort="id", order="desc", status=None, funil_etapa=None, origem=None, empresa_id=None, com_telefone=None, q=None, export=False) -> dict`, retornando `{"data": [...], "meta": {"total": int, "page": int, "page_size": int, "pages": int}}` no caso paginado, ou `{"data": [...], "meta": {"total": int}}` quando `export=True`. Em erro de banco, retorna `{"data": [], "meta": {"total": 0, "page": page, "page_size": page_size, "pages": 0}}`.

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `hermes_agents/tests/test_crm_leads_filtro.py`:

```python
"""Testes — listar_leads_filtrado() e o branch de filtro/paginacao/ordenacao
da rota GET /api/crm/leads. Cobre: cada filtro isolado, combinacao de
filtros, ordenacao em cada coluna da whitelist, sort invalido caindo no
default seguro (nunca interpolado no SQL), paginacao, export com cap de
5000, e que a rota so' aciona o branch novo quando a querystring tem
parametros — sem eles (e nas outras tabelas do CRM), comportamento antigo
se mantem intacto."""
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
from routes.crm import crm_bp
import core.rbac as rbac
import core.crm as crm


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(crm_bp)
    return app.test_client()


def _mock_db(total=0, rows=None):
    db_mock = AsyncMock()
    db_mock.fetchval = AsyncMock(return_value=total)
    db_mock.fetch = AsyncMock(return_value=rows or [])
    return db_mock


class TestListarLeadsFiltradoQuery(unittest.TestCase):
    def test_sem_filtro_usa_query_base_sem_where(self):
        db_mock = _mock_db(total=2, rows=[{"id": 2}, {"id": 1}])
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            resultado = crm.listar_leads_filtrado()
        query = db_mock.fetch.call_args.args[0]
        self.assertIn("ORDER BY id DESC", query)
        self.assertNotIn("WHERE", query)
        self.assertEqual(resultado["meta"], {"total": 2, "page": 1, "page_size": 25, "pages": 1})
        self.assertEqual(len(resultado["data"]), 2)

    def test_filtro_status_isolado(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(status="qualificado")
        args = db_mock.fetch.call_args.args
        self.assertIn("status = $1", args[0])
        self.assertEqual(args[1], "qualificado")

    def test_filtro_funil_etapa_isolado(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(funil_etapa="proposta")
        args = db_mock.fetch.call_args.args
        self.assertIn("funil_etapa = $1", args[0])
        self.assertEqual(args[1], "proposta")

    def test_filtro_origem_e_ilike_com_wildcard(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(origem="site")
        args = db_mock.fetch.call_args.args
        self.assertIn("origem ILIKE $1", args[0])
        self.assertEqual(args[1], "%site%")

    def test_filtro_empresa_id_isolado(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(empresa_id=7)
        args = db_mock.fetch.call_args.args
        self.assertIn("empresa_id = $1", args[0])
        self.assertEqual(args[1], 7)

    def test_com_telefone_true(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(com_telefone=True)
        query = db_mock.fetch.call_args.args[0]
        self.assertIn("telefone IS NOT NULL AND telefone <> ''", query)

    def test_com_telefone_false(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(com_telefone=False)
        query = db_mock.fetch.call_args.args[0]
        self.assertIn("telefone IS NULL OR telefone = ''", query)

    def test_busca_q_cobre_quatro_colunas_com_or(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(q="joao")
        args = db_mock.fetch.call_args.args
        for col in ("nome", "email", "telefone", "origem"):
            self.assertIn(f"{col} ILIKE $1", args[0])
        self.assertEqual(args[1], "%joao%")

    def test_combinacao_de_filtros_usa_and_com_indices_corretos(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(status="novo", origem="bling")
        args = db_mock.fetch.call_args.args
        self.assertIn("status = $1 AND origem ILIKE $2", args[0])
        self.assertEqual(args[1], "novo")
        self.assertEqual(args[2], "%bling%")


class TestListarLeadsFiltradoOrdenacao(unittest.TestCase):
    def test_ordenacao_valor_potencial_asc(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(sort="valor_potencial", order="asc")
        self.assertIn("ORDER BY valor_potencial ASC", db_mock.fetch.call_args.args[0])

    def test_ordenacao_status_desc(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(sort="status", order="desc")
        self.assertIn("ORDER BY status DESC", db_mock.fetch.call_args.args[0])

    def test_ordenacao_funil_etapa_asc(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(sort="funil_etapa", order="asc")
        self.assertIn("ORDER BY funil_etapa ASC", db_mock.fetch.call_args.args[0])

    def test_order_invalido_cai_em_desc(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(sort="status", order="xyz")
        self.assertIn("ORDER BY status DESC", db_mock.fetch.call_args.args[0])

    def test_sort_fora_da_whitelist_cai_no_default_id_sem_interpolar(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(sort="id; DROP TABLE crm_leads;--")
        query = db_mock.fetch.call_args.args[0]
        self.assertIn("ORDER BY id DESC", query)
        self.assertNotIn("DROP TABLE", query)


class TestListarLeadsFiltradoPaginacao(unittest.TestCase):
    def test_pagina_2_calcula_offset(self):
        db_mock = _mock_db(total=30)
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            resultado = crm.listar_leads_filtrado(page=2, page_size=25)
        self.assertEqual(db_mock.fetch.call_args.args[-2:], (25, 25))
        self.assertEqual(resultado["meta"], {"total": 30, "page": 2, "page_size": 25, "pages": 2})

    def test_pagina_fora_do_intervalo_retorna_lista_vazia_com_total_correto(self):
        db_mock = _mock_db(total=5, rows=[])
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            resultado = crm.listar_leads_filtrado(page=99, page_size=25)
        self.assertEqual(resultado["data"], [])
        self.assertEqual(resultado["meta"]["total"], 5)

    def test_page_size_fora_da_whitelist_cai_em_25(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            resultado = crm.listar_leads_filtrado(page_size=999)
        self.assertEqual(resultado["meta"]["page_size"], 25)

    def test_pages_arredonda_para_cima(self):
        db_mock = _mock_db(total=26)
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            resultado = crm.listar_leads_filtrado(page_size=25)
        self.assertEqual(resultado["meta"]["pages"], 2)


class TestListarLeadsFiltradoExport(unittest.TestCase):
    def test_export_ignora_paginacao_aplica_cap_5000(self):
        db_mock = _mock_db(total=6000, rows=[{"id": 1}])
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            resultado = crm.listar_leads_filtrado(export=True, status="novo")
        query = db_mock.fetch.call_args.args[0]
        self.assertIn("LIMIT 5000", query)
        self.assertNotIn("OFFSET", query)
        self.assertEqual(resultado["meta"], {"total": 6000})
        self.assertEqual(len(resultado["data"]), 1)


class TestListarLeadsFiltradoErro(unittest.TestCase):
    def test_erro_de_banco_retorna_lista_vazia_sem_quebrar(self):
        db_mock = AsyncMock()
        db_mock.fetchval = AsyncMock(side_effect=Exception("db down"))
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            resultado = crm.listar_leads_filtrado(page=3, page_size=50)
        self.assertEqual(resultado, {"data": [], "meta": {"total": 0, "page": 3, "page_size": 50, "pages": 0}})


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_crm_leads_filtro.py -v`
Expected: FAIL — `AttributeError: module 'core.crm' has no attribute 'listar_leads_filtrado'`

- [ ] **Step 3: Implementar `listar_leads_filtrado()`**

Em `hermes_agents/core/crm.py`, adicionar logo após a definição de `list`/`get` (depois da linha `def get(tabela: str, id: int): return _get(f"crm_{_tabela_real(tabela)}", id)`, por volta da linha 248):

```python
# ── Leads — listagem paginada com filtro/ordenacao server-side ──
# Endpoint generico list(tabela) acima nao pagina/filtra — serve as outras
# 7 tabelas do CRM sem mudanca. Isso aqui e' especifico de leads, chamado
# pela rota so' quando a querystring tem parametros de filtro/paginacao
# (ver routes/crm.py::crm_list) — sem eles, o comportamento antigo se
# mantem intacto pras 11 outras telas que usam o CrudPanel generico.
_LEADS_SORT_WHITELIST = {
    "id": "id",
    "valor_potencial": "valor_potencial",
    "status": "status",
    "funil_etapa": "funil_etapa",
}
_LEADS_PAGE_SIZES = (25, 50, 100)

def listar_leads_filtrado(page=1, page_size=25, sort="id", order="desc",
                           status=None, funil_etapa=None, origem=None,
                           empresa_id=None, com_telefone=None, q=None,
                           export=False) -> dict:
    sort_col = _LEADS_SORT_WHITELIST.get(sort, "id")
    order_dir = "ASC" if str(order).lower() == "asc" else "DESC"
    page = max(int(page or 1), 1)
    page_size = page_size if page_size in _LEADS_PAGE_SIZES else 25

    conds = []
    vals = []
    if status:
        vals.append(status)
        conds.append(f"status = ${len(vals)}")
    if funil_etapa:
        vals.append(funil_etapa)
        conds.append(f"funil_etapa = ${len(vals)}")
    if origem:
        vals.append(f"%{origem}%")
        conds.append(f"origem ILIKE ${len(vals)}")
    if empresa_id:
        vals.append(empresa_id)
        conds.append(f"empresa_id = ${len(vals)}")
    if com_telefone is True:
        conds.append("telefone IS NOT NULL AND telefone <> ''")
    elif com_telefone is False:
        conds.append("(telefone IS NULL OR telefone = '')")
    if q:
        vals.append(f"%{q}%")
        p = len(vals)
        conds.append(f"(nome ILIKE ${p} OR email ILIKE ${p} OR telefone ILIKE ${p} OR origem ILIKE ${p})")

    where_sql = f"WHERE {' AND '.join(conds)}" if conds else ""

    async def _go():
        db = await get_db()
        total = await db.fetchval(f"SELECT COUNT(*) FROM crm_leads {where_sql}", *vals) or 0
        if export:
            rows = await db.fetch(
                f"SELECT * FROM crm_leads {where_sql} ORDER BY {sort_col} {order_dir} LIMIT 5000",
                *vals)
            return {"data": [dict(r) for r in rows], "meta": {"total": total}}
        offset = (page - 1) * page_size
        rows = await db.fetch(
            f"SELECT * FROM crm_leads {where_sql} ORDER BY {sort_col} {order_dir} "
            f"LIMIT ${len(vals)+1} OFFSET ${len(vals)+2}",
            *vals, page_size, offset)
        pages = max(1, (total + page_size - 1) // page_size)
        return {
            "data": [dict(r) for r in rows],
            "meta": {"total": total, "page": page, "page_size": page_size, "pages": pages},
        }
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro listar_leads_filtrado: {e}")
        return {"data": [], "meta": {"total": 0, "page": page, "page_size": page_size, "pages": 0}}
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_crm_leads_filtro.py -v`
Expected: PASS (todos os testes desta classe — os de rota, na Task 2, ainda vão falhar)

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/crm.py hermes_agents/tests/test_crm_leads_filtro.py
git commit -m "feat: adiciona listagem paginada/filtrada/ordenada de leads no core do CRM"
```

---

### Task 2: Backend — rota `GET /api/crm/leads` aceita filtros

**Files:**
- Modify: `hermes_agents/routes/crm.py:1-38` (imports no topo, e a função `crm_list`)
- Test: `hermes_agents/tests/test_crm_leads_filtro.py` (adicionar classes ao arquivo criado na Task 1)

**Interfaces:**
- Consumes: `core.crm.listar_leads_filtrado(**kwargs)` da Task 1 — mesma assinatura de keyword args.
- Produces: `GET /api/crm/leads?<querystring>` — se a querystring tiver qualquer um dos parâmetros (`page`, `page_size`, `sort`, `order`, `status`, `funil_etapa`, `origem`, `empresa_id`, `com_telefone`, `q`, `export`), chama `listar_leads_filtrado`; senão, comportamento antigo (`core.crm.list("leads")`).

- [ ] **Step 1: Escrever os testes de rota (falhando)**

Adicionar ao final de `hermes_agents/tests/test_crm_leads_filtro.py`, antes do `if __name__ == "__main__":`:

```python
class TestRotaLeadsComFiltro(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def _headers(self):
        return {"Authorization": f"Bearer {_TEST_TOKEN}"}

    def test_sem_querystring_usa_list_antigo(self):
        with patch("core.crm.list", return_value=[{"id": 1}]) as mock_list, \
             patch("core.crm.listar_leads_filtrado") as mock_filtrado:
            r = self.client.get("/api/crm/leads", headers=self._headers())
        self.assertEqual(r.status_code, 200)
        mock_list.assert_called_once_with("leads")
        mock_filtrado.assert_not_called()
        self.assertEqual(r.get_json(), {"data": [{"id": 1}]})

    def test_com_querystring_usa_listar_filtrado_com_kwargs_corretos(self):
        with patch("core.crm.list") as mock_list, \
             patch("core.crm.listar_leads_filtrado",
                   return_value={"data": [], "meta": {"total": 0, "page": 1, "page_size": 25, "pages": 0}}) as mock_filtrado:
            r = self.client.get(
                "/api/crm/leads?page=1&page_size=25&sort=valor_potencial&order=asc&status=novo",
                headers=self._headers())
        self.assertEqual(r.status_code, 200)
        mock_list.assert_not_called()
        mock_filtrado.assert_called_once_with(
            page=1, page_size=25, sort="valor_potencial", order="asc",
            status="novo", funil_etapa=None, origem=None, empresa_id=None,
            com_telefone=None, q=None, export=False,
        )

    def test_outra_tabela_ignora_branch_de_leads(self):
        with patch("core.crm.list", return_value=[]) as mock_list, \
             patch("core.crm.listar_leads_filtrado") as mock_filtrado:
            r = self.client.get("/api/crm/empresas?page=1", headers=self._headers())
        self.assertEqual(r.status_code, 200)
        mock_list.assert_called_once_with("empresas")
        mock_filtrado.assert_not_called()

    def test_sem_permissao_nega_mesmo_com_filtro(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.crm.listar_leads_filtrado") as mock_filtrado:
            r = self.client.get("/api/crm/leads?status=novo", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_filtrado.assert_not_called()

    def test_com_telefone_true_vira_bool_true(self):
        with patch("core.crm.listar_leads_filtrado", return_value={"data": [], "meta": {}}) as mock_filtrado:
            self.client.get("/api/crm/leads?com_telefone=true", headers=self._headers())
        self.assertTrue(mock_filtrado.call_args.kwargs["com_telefone"])

    def test_com_telefone_false_vira_bool_false(self):
        with patch("core.crm.listar_leads_filtrado", return_value={"data": [], "meta": {}}) as mock_filtrado:
            self.client.get("/api/crm/leads?com_telefone=false", headers=self._headers())
        self.assertFalse(mock_filtrado.call_args.kwargs["com_telefone"])

    def test_empresa_id_invalido_vira_none_em_vez_de_quebrar(self):
        with patch("core.crm.listar_leads_filtrado", return_value={"data": [], "meta": {}}) as mock_filtrado:
            r = self.client.get("/api/crm/leads?empresa_id=abc", headers=self._headers())
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(mock_filtrado.call_args.kwargs["empresa_id"])

    def test_export_true_vira_bool(self):
        with patch("core.crm.listar_leads_filtrado", return_value={"data": [], "meta": {}}) as mock_filtrado:
            self.client.get("/api/crm/leads?export=true", headers=self._headers())
        self.assertTrue(mock_filtrado.call_args.kwargs["export"])
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_crm_leads_filtro.py::TestRotaLeadsComFiltro -v`
Expected: FAIL — a rota ainda ignora a querystring, então `mock_filtrado.assert_not_called()` falha nos testes que esperam ela ser chamada (e vice-versa).

- [ ] **Step 3: Implementar o branch na rota**

Em `hermes_agents/routes/crm.py`, adicionar os helpers de parsing logo após os imports (depois da linha 5, antes de `@crm_bp.route("/funil"...)`):

```python
_LEADS_QUERY_PARAMS = ("page", "page_size", "sort", "order", "status", "funil_etapa",
                        "origem", "empresa_id", "com_telefone", "q", "export")

def _tem_filtro_leads(args) -> bool:
    return any(p in args for p in _LEADS_QUERY_PARAMS)

def _int_ou(args, nome, default):
    try:
        return int(args.get(nome, default))
    except (TypeError, ValueError):
        return default

def _int_ou_none(args, nome):
    bruto = args.get(nome)
    if not bruto:
        return None
    try:
        return int(bruto)
    except ValueError:
        return None

def _parse_filtro_leads(args) -> dict:
    com_telefone_bruto = args.get("com_telefone")
    return {
        "page": _int_ou(args, "page", 1),
        "page_size": _int_ou(args, "page_size", 25),
        "sort": args.get("sort", "id"),
        "order": args.get("order", "desc"),
        "status": args.get("status") or None,
        "funil_etapa": args.get("funil_etapa") or None,
        "origem": args.get("origem") or None,
        "empresa_id": _int_ou_none(args, "empresa_id"),
        "com_telefone": (com_telefone_bruto.lower() == "true") if com_telefone_bruto is not None else None,
        "q": args.get("q") or None,
        "export": args.get("export", "").lower() == "true",
    }
```

Substituir a função `crm_list` existente (linhas 29-38) por:

```python
@crm_bp.route("/<tabela>", methods=["GET"])
def crm_list(tabela):
    from core.crm import list as crm_list_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("crm.ver")
    def _go():
        if tabela == "leads" and _tem_filtro_leads(request.args):
            from core.crm import listar_leads_filtrado
            return jsonify(listar_leads_filtrado(**_parse_filtro_leads(request.args)))
        return jsonify({"data": crm_list_fn(tabela)})
    return _go()
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_crm_leads_filtro.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Rodar a suíte completa do CRM pra checar retrocompatibilidade**

Run: `cd hermes_agents && python -m pytest tests/test_crm_seguranca.py tests/test_crm_agenda.py tests/test_crm_negociacao_ganha.py tests/test_crm_leads_filtro.py -v`
Expected: PASS — nenhuma das 11 outras telas/tabelas quebrou.

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/crm.py hermes_agents/tests/test_crm_leads_filtro.py
git commit -m "feat: rota GET /api/crm/leads aceita filtros/paginacao/ordenacao via querystring"
```

---

### Task 3: Frontend — extrair `CrudFormModal` reutilizável de `CrudPanel.tsx`

**Files:**
- Create: `web/src/app/_components/CrudFormModal.tsx`
- Modify: `web/src/app/_components/CrudPanel.tsx:8-18` (interface `FieldDef`), `:238-272` (JSX do modal)

**Interfaces:**
- Produces: `export interface FieldDef { key, label, type?, options?, step?, min?, max?, numeric? }` (movida de `CrudPanel.tsx`, idêntica). `export default function CrudFormModal({ mode, fields, formData, onChange, onSave, onClose })`.
- Consumes (por `CrudPanel.tsx`): `import CrudFormModal, { type FieldDef } from "./CrudFormModal";` — `CrudPanel.tsx` reexporta `FieldDef` para não quebrar as 11 telas que fazem `import { type FieldDef } from "../../_components/CrudPanel"`.

- [ ] **Step 1: Criar `CrudFormModal.tsx`**

```tsx
"use client";

import Icon from "./Icon";

export interface FieldDef {
  key: string;
  label: string;
  type?: "text" | "number" | "select" | "date" | "datetime";
  options?: { label: string; value: string }[];
  step?: string;
  min?: number;
  max?: number;
  // Campo "select" cujo valor deve ser enviado como numero (ex.: FK de id) em vez de string.
  numeric?: boolean;
}

interface CrudFormModalProps {
  mode: "create" | "edit";
  fields: FieldDef[];
  formData: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onSave: () => void;
  onClose: () => void;
}

export default function CrudFormModal({ mode, fields, formData, onChange, onSave, onClose }: CrudFormModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="w-full max-w-[440px] max-h-[85vh] overflow-y-auto rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
          <h3 className="text-sm font-semibold text-neutral-100">{mode === "create" ? "Novo registro" : "Editar registro"}</h3>
          <button onClick={onClose} className="rounded-md p-1 text-neutral-500 hover:bg-neutral-700 hover:text-neutral-300">
            <Icon name="close" size={15} />
          </button>
        </div>
        <div className="grid grid-cols-2 gap-3 px-5 py-4">
          {fields.filter(f => f.key !== "id").map(f => (
            <div key={f.key} className={f.type === "select" || f.key === "endereco" ? "col-span-2" : "col-span-2 sm:col-span-1"}>
              <label className="mb-1 block text-[11px] font-medium text-neutral-400">{f.label}</label>
              {f.type === "select" && f.options ? (
                <select value={formData[f.key] ?? ""} onChange={e => onChange(f.key, e.target.value)}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
                  <option value="">Selecione...</option>
                  {f.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              ) : (
                <input type={f.type === "number" ? "number" : f.type === "date" ? "date" : f.type === "datetime" ? "datetime-local" : "text"}
                  step={f.type === "number" ? (f.step ?? "any") : undefined} min={f.min} max={f.max}
                  value={formData[f.key] ?? ""} onChange={e => onChange(f.key, e.target.value)}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              )}
            </div>
          ))}
        </div>
        <div className="flex justify-end gap-2 border-t border-neutral-700/70 px-5 py-4">
          <button onClick={onClose} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:text-neutral-200">Cancelar</button>
          <button onClick={onSave} className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500">Salvar</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Editar `CrudPanel.tsx` pra usar o novo componente**

Substituir o bloco `export interface FieldDef { ... }` (linhas 8-18) por:

```tsx
import CrudFormModal, { type FieldDef } from "./CrudFormModal";
export type { FieldDef };
```

(Remover o import antigo de `Icon` só se não for mais usado em outro ponto do arquivo — `CrudPanel.tsx` ainda usa `Icon` para `search`, `pencil`, `trash`, `alert`, `inbox`, então manter `import Icon from "./Icon";`.)

Substituir o bloco JSX do modal (linhas 238-272, de `{modal.open && formFields && (` até o `)}` de fechamento) por:

```tsx
{modal.open && formFields && (
  <CrudFormModal
    mode={modal.mode}
    fields={formFields}
    formData={formData}
    onChange={(key, value) => setFormData(prev => ({ ...prev, [key]: value }))}
    onSave={handleSave}
    onClose={() => setModal({ open: false, mode: "create" })}
  />
)}
```

- [ ] **Step 3: Type-check**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros novos (o projeto pode já ter avisos pré-existentes — comparar antes/depois se necessário)

- [ ] **Step 4: Verificar visualmente que uma tela existente (ex.: Cadastros → Clientes) ainda abre o modal de criar/editar normalmente**

Rodar `npm run dev` em `web/`, abrir `/cadastros` aba Clientes, clicar "Novo", confirmar que o modal abre e os campos renderizam igual a antes.

- [ ] **Step 5: Commit**

```bash
git add web/src/app/_components/CrudFormModal.tsx web/src/app/_components/CrudPanel.tsx
git commit -m "refactor: extrai modal de criar/editar do CrudPanel para CrudFormModal reutilizavel"
```

---

### Task 4: Frontend — `api.ts` (tipos + `crmLeadsListar`/`crmLeadsExportar`) e ícone `download`

**Files:**
- Modify: `web/src/lib/api.ts:848-852` (bloco `crmList`/`crmCreate`/`crmUpdate`/`crmDelete`)
- Modify: `web/src/app/_components/Icon.tsx:44` (adicionar entrada `download` no dicionário `paths`)

**Interfaces:**
- Produces: `export interface LeadFiltro { page?, pageSize?, sort?, order?, status?, funilEtapa?, origem?, empresaId?, comTelefone?, q? }`; `api.crmLeadsListar(filtro: LeadFiltro) => Promise<{ data: Record<string, unknown>[]; meta: { total: number; page: number; page_size: number; pages: number } }>`; `api.crmLeadsExportar(filtro: LeadFiltro) => Promise<{ data: Record<string, unknown>[]; meta: { total: number } }>`.
- Consumes (Task 5): `LeadsPanel.tsx` importa `api.crmLeadsListar`, `api.crmLeadsExportar` e o tipo `LeadFiltro` de `@/lib/api`, e `<Icon name="download" />` de `Icon.tsx`.

- [ ] **Step 1: Adicionar tipo e helper de querystring em `api.ts`**

Em `web/src/lib/api.ts`, imediatamente antes do bloco `crmList: ...` (linha 848), adicionar:

```typescript
export interface LeadFiltro {
  page?: number;
  pageSize?: 25 | 50 | 100;
  sort?: "id" | "valor_potencial" | "status" | "funil_etapa";
  order?: "asc" | "desc";
  status?: string;
  funilEtapa?: string;
  origem?: string;
  empresaId?: number;
  comTelefone?: boolean;
  q?: string;
}

function leadsQueryString(f: LeadFiltro, opts?: { export?: boolean }): string {
  const q = new URLSearchParams();
  if (f.page) q.set("page", String(f.page));
  if (f.pageSize) q.set("page_size", String(f.pageSize));
  if (f.sort) q.set("sort", f.sort);
  if (f.order) q.set("order", f.order);
  if (f.status) q.set("status", f.status);
  if (f.funilEtapa) q.set("funil_etapa", f.funilEtapa);
  if (f.origem) q.set("origem", f.origem);
  if (f.empresaId) q.set("empresa_id", String(f.empresaId));
  if (f.comTelefone !== undefined) q.set("com_telefone", String(f.comTelefone));
  if (f.q) q.set("q", f.q);
  if (opts?.export) q.set("export", "true");
  return q.toString();
}
```

Logo após a linha `crmDelete: (tabela: string, id: number) => request<{ success: boolean }>(\`/api/crm/${tabela}/${id}\`, { method: "DELETE" }),` (linha 852), adicionar:

```typescript
  crmLeadsListar: (filtro: LeadFiltro) =>
    request<{ data: Record<string, unknown>[]; meta: { total: number; page: number; page_size: number; pages: number } }>(
      `/api/crm/leads?${leadsQueryString(filtro)}`
    ),
  crmLeadsExportar: (filtro: LeadFiltro) =>
    request<{ data: Record<string, unknown>[]; meta: { total: number } }>(
      `/api/crm/leads?${leadsQueryString(filtro, { export: true })}`
    ),
```

- [ ] **Step 2: Adicionar ícone `download` em `Icon.tsx`**

Em `web/src/app/_components/Icon.tsx`, adicionar ao dicionário `paths` (após a linha `moon: "..."`, linha 44):

```typescript
  download: "M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3",
```

- [ ] **Step 3: Type-check**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/api.ts web/src/app/_components/Icon.tsx
git commit -m "feat: adiciona api.crmLeadsListar/crmLeadsExportar e icone download"
```

---

### Task 5: Frontend — componente `LeadsPanel.tsx`

**Files:**
- Create: `web/src/app/crm/leads/_components/LeadsPanel.tsx`

**Interfaces:**
- Consumes: `api.crmList`, `api.crmLeadsListar`, `api.crmLeadsExportar`, `api.crmCreate`, `api.crmUpdate`, `api.crmDelete` de `@/lib/api`; `type LeadFiltro` de `@/lib/api`; `fmtBRL` de `@/lib/format`; `Can` de `@/lib/auth`; `Icon` de `../../../_components/Icon`; `CrudFormModal, { type FieldDef }` de `../../../_components/CrudFormModal`.
- Produces: `export default function LeadsPanel(): JSX.Element` — sem props, self-contained (Task 6 só faz `<LeadsPanel />`).

- [ ] **Step 1: Criar o arquivo com estado, fetch e fields do formulário**

```tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type LeadFiltro } from "@/lib/api";
import { fmtBRL } from "@/lib/format";
import { Can } from "@/lib/auth";
import Icon from "../../../_components/Icon";
import CrudFormModal, { type FieldDef } from "../../../_components/CrudFormModal";

const ETAPAS_FUNIL = ["captacao", "qualificacao", "prospeccao", "proposta", "negociacao", "fechamento"];

const STATUS_CORES: Record<string, string> = {
  novo: "bg-indigo-500/20 text-indigo-400",
  contatado: "bg-amber-500/20 text-amber-400",
  qualificado: "bg-sky-500/20 text-sky-400",
  convertido: "bg-emerald-500/20 text-emerald-400",
  perdido: "bg-red-500/20 text-red-400",
};

const PAGE_SIZES = [25, 50, 100] as const;
type SortField = "id" | "valor_potencial" | "status" | "funil_etapa";

const LEADS_COLUNAS_EXPORT = ["id", "nome", "email", "telefone", "empresa_id", "origem", "funil_etapa", "valor_potencial", "status", "observacoes"];

function normalizarPayloadLead(data: Record<string, unknown>) {
  const bruto = data.empresa_id;
  const empresa_id = bruto === "" || bruto == null ? null : Number(bruto);
  return { ...data, empresa_id };
}

function csvEscape(v: unknown): string {
  const s = String(v ?? "");
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export default function LeadsPanel() {
  const [empresas, setEmpresas] = useState<{ id: number; nome: string }[]>([]);
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [meta, setMeta] = useState({ total: 0, page: 1, page_size: 25, pages: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<25 | 50 | 100>(25);
  const [sort, setSort] = useState<SortField>("id");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [status, setStatus] = useState("");
  const [funilEtapa, setFunilEtapa] = useState("");
  const [empresaId, setEmpresaId] = useState("");
  const [origem, setOrigem] = useState("");
  const [origemDebounced, setOrigemDebounced] = useState("");
  const [comTelefone, setComTelefone] = useState<"" | "true" | "false">("");
  const [busca, setBusca] = useState("");
  const [buscaDebounced, setBuscaDebounced] = useState("");

  const [modal, setModal] = useState<{ open: boolean; mode: "create" | "edit"; row?: Record<string, unknown> }>({ open: false, mode: "create" });
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [exportando, setExportando] = useState(false);

  useEffect(() => {
    api.crmList("empresas")
      .then(res => setEmpresas((res.data || []) as { id: number; nome: string }[]))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const t = setTimeout(() => setBuscaDebounced(busca), 300);
    return () => clearTimeout(t);
  }, [busca]);

  useEffect(() => {
    const t = setTimeout(() => setOrigemDebounced(origem), 300);
    return () => clearTimeout(t);
  }, [origem]);

  useEffect(() => {
    setPage(1);
  }, [status, funilEtapa, empresaId, comTelefone, buscaDebounced, origemDebounced, pageSize]);

  const filtro = useMemo<LeadFiltro>(() => ({
    page, pageSize, sort, order,
    status: status || undefined,
    funilEtapa: funilEtapa || undefined,
    origem: origemDebounced || undefined,
    empresaId: empresaId ? Number(empresaId) : undefined,
    comTelefone: comTelefone === "" ? undefined : comTelefone === "true",
    q: buscaDebounced || undefined,
  }), [page, pageSize, sort, order, status, funilEtapa, origemDebounced, empresaId, comTelefone, buscaDebounced]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.crmLeadsListar(filtro);
      setData(res.data || []);
      setMeta(res.meta || { total: 0, page: 1, page_size: pageSize, pages: 1 });
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  }, [filtro, pageSize]);

  useEffect(() => { fetchData(); }, [fetchData, reloadKey]);

  const empresaOptions = useMemo(() => empresas.map(e => ({ label: e.nome, value: String(e.id) })), [empresas]);
  const empresaNomePorId = useMemo(() => Object.fromEntries(empresas.map(e => [String(e.id), e.nome])), [empresas]);

  const leadsFields = useMemo<FieldDef[]>(() => [
    { key: "nome", label: "Nome" },
    { key: "empresa_id", label: "Empresa", type: "select", options: empresaOptions },
    { key: "email", label: "E-mail" },
    { key: "telefone", label: "Telefone" },
    { key: "origem", label: "Origem" },
    { key: "funil_etapa", label: "Etapa do funil", type: "select", options: ETAPAS_FUNIL.map(e => ({ label: e.replace(/_/g, " "), value: e })) },
    { key: "valor_potencial", label: "Valor potencial (R$)", type: "number", step: "0.01" },
    { key: "status", label: "Status", type: "select", options: Object.keys(STATUS_CORES).map(s => ({ label: s, value: s })) },
    { key: "observacoes", label: "Observações" },
  ], [empresaOptions]);

  const temFiltroAtivo = !!(status || funilEtapa || empresaId || origem || comTelefone || busca);
  const limparFiltros = () => {
    setStatus(""); setFunilEtapa(""); setEmpresaId(""); setOrigem(""); setComTelefone(""); setBusca("");
  };

  // resto do componente nas proximas steps
  return null;
}
```

- [ ] **Step 2: Type-check**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros (variáveis `data`, `error`, `loading`, `modal`, `confirmDelete`, `exportando`, `temFiltroAtivo`, `limparFiltros`, `leadsFields`, `empresaNomePorId` ficam "declared but never used" — normal nesse ponto intermediário, não bloqueia a implementação; conferir de novo no Step final)

- [ ] **Step 3: Adicionar as ações de CRUD (criar/editar/excluir) e ordenação**

Substituir a linha `// resto do componente nas proximas steps` e o `return null;` por:

```tsx
  const openCreate = () => { setFormData({}); setModal({ open: true, mode: "create" }); };

  const openEdit = (row: Record<string, unknown>) => {
    const fd: Record<string, string> = {};
    for (const f of leadsFields) fd[f.key] = String(row[f.key] ?? "");
    setFormData(fd);
    setModal({ open: true, mode: "edit", row });
  };

  const handleSave = async () => {
    const payload: Record<string, unknown> = {};
    for (const f of leadsFields) {
      const val = formData[f.key] ?? "";
      payload[f.key] = f.type === "number" ? (parseFloat(val) || 0) : val;
    }
    const normalizado = normalizarPayloadLead(payload);
    try {
      if (modal.mode === "create") await api.crmCreate("leads", normalizado);
      else await api.crmUpdate("leads", Number(modal.row?.id), normalizado);
      setModal({ open: false, mode: "create" });
      setReloadKey(k => k + 1);
    } catch (e) { alert(String(e)); }
  };

  const handleDelete = async (id: number) => {
    try { await api.crmDelete("leads", id); setConfirmDelete(null); setReloadKey(k => k + 1); }
    catch (e) { alert(String(e)); }
  };

  const toggleSort = (field: SortField) => {
    if (sort === field) setOrder(o => (o === "asc" ? "desc" : "asc"));
    else { setSort(field); setOrder("desc"); }
    setPage(1);
  };

  const handleExportar = async () => {
    setExportando(true);
    try {
      const res = await api.crmLeadsExportar(filtro);
      const linhas = res.data || [];
      const header = LEADS_COLUNAS_EXPORT.join(",");
      const body = linhas.map(row => LEADS_COLUNAS_EXPORT.map(c => {
        if (c === "empresa_id") return csvEscape(row[c] ? (empresaNomePorId[String(row[c])] || row[c]) : "");
        return csvEscape(row[c]);
      }).join(",")).join("\n");
      const csv = `${header}\n${body}`;
      const blob = new Blob([`﻿${csv}`], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `leads_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) { alert(String(e)); }
    finally { setExportando(false); }
  };

  return null; // JSX vem no proximo step
```

- [ ] **Step 4: Type-check**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros

- [ ] **Step 5: Substituir `return null;` pelo JSX completo (filtros, tabela ordenável, paginação, modal, confirmação de exclusão)**

```tsx
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {!loading && !error && (
            <span className="rounded-full bg-neutral-800 px-2 py-0.5 text-[10px] font-medium text-neutral-400">
              {meta.total} lead{meta.total === 1 ? "" : "s"}
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Icon name="search" size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-500" />
            <input
              type="text"
              placeholder="Buscar nome, e-mail, telefone..."
              value={busca}
              onChange={e => setBusca(e.target.value)}
              className="w-52 rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 pl-8 pr-3 text-xs text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
            />
          </div>
          <button
            onClick={handleExportar}
            disabled={exportando}
            className="flex items-center gap-1.5 rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs font-medium text-neutral-300 transition-colors hover:bg-neutral-700 disabled:opacity-50"
          >
            <Icon name="download" size={13} /> {exportando ? "Exportando..." : "Exportar CSV"}
          </button>
          <Can permission="crm.criar">
            <button
              onClick={openCreate}
              className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500"
            >
              <span className="text-sm leading-none">+</span> Novo
            </button>
          </Can>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select value={status} onChange={e => setStatus(e.target.value)}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
          <option value="">Status: todos</option>
          {Object.keys(STATUS_CORES).map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={funilEtapa} onChange={e => setFunilEtapa(e.target.value)}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
          <option value="">Etapa: todas</option>
          {ETAPAS_FUNIL.map(e => <option key={e} value={e}>{e.replace(/_/g, " ")}</option>)}
        </select>
        <select value={empresaId} onChange={e => setEmpresaId(e.target.value)}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
          <option value="">Empresa: todas</option>
          {empresas.map(emp => <option key={emp.id} value={emp.id}>{emp.nome}</option>)}
        </select>
        <input
          type="text"
          placeholder="Origem contém..."
          value={origem}
          onChange={e => setOrigem(e.target.value)}
          className="w-36 rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
        />
        <select value={comTelefone} onChange={e => setComTelefone(e.target.value as "" | "true" | "false")}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
          <option value="">Telefone: qualquer</option>
          <option value="true">Com telefone</option>
          <option value="false">Sem telefone</option>
        </select>
        {temFiltroAtivo && (
          <button onClick={limparFiltros} className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-[11px] text-neutral-500 hover:text-neutral-300">
            <Icon name="close" size={11} /> Limpar filtros
          </button>
        )}
      </div>

      {loading ? (
        <div className="overflow-hidden rounded-xl border border-neutral-800">
          <div className="divide-y divide-neutral-800/70">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex gap-4 px-4 py-3">
                {Array.from({ length: 9 }).map((_, j) => (
                  <div key={j} className="h-3 flex-1 animate-pulse rounded bg-neutral-800" />
                ))}
              </div>
            ))}
          </div>
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 rounded-xl border border-red-900/50 bg-red-950/30 px-4 py-3 text-xs text-red-400">
          <Icon name="alert" size={15} className="shrink-0" />
          {error}
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-neutral-800">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-neutral-800 bg-neutral-900/60 text-left text-neutral-400">
                  <th className="cursor-pointer select-none whitespace-nowrap px-4 py-2.5 font-medium" onClick={() => toggleSort("id")}>
                    <span className="inline-flex items-center gap-1">ID {sort === "id" && <Icon name="chevronDown" size={11} className={order === "asc" ? "rotate-180" : ""} />}</span>
                  </th>
                  <th className="whitespace-nowrap px-4 py-2.5 font-medium">Nome</th>
                  <th className="whitespace-nowrap px-4 py-2.5 font-medium">Empresa</th>
                  <th className="whitespace-nowrap px-4 py-2.5 font-medium">E-mail</th>
                  <th className="whitespace-nowrap px-4 py-2.5 font-medium">Telefone</th>
                  <th className="whitespace-nowrap px-4 py-2.5 font-medium">Origem</th>
                  <th className="cursor-pointer select-none whitespace-nowrap px-4 py-2.5 font-medium" onClick={() => toggleSort("funil_etapa")}>
                    <span className="inline-flex items-center gap-1">Etapa do funil {sort === "funil_etapa" && <Icon name="chevronDown" size={11} className={order === "asc" ? "rotate-180" : ""} />}</span>
                  </th>
                  <th className="cursor-pointer select-none whitespace-nowrap px-4 py-2.5 font-medium" onClick={() => toggleSort("valor_potencial")}>
                    <span className="inline-flex items-center gap-1">Valor potencial {sort === "valor_potencial" && <Icon name="chevronDown" size={11} className={order === "asc" ? "rotate-180" : ""} />}</span>
                  </th>
                  <th className="cursor-pointer select-none whitespace-nowrap px-4 py-2.5 font-medium" onClick={() => toggleSort("status")}>
                    <span className="inline-flex items-center gap-1">Status {sort === "status" && <Icon name="chevronDown" size={11} className={order === "asc" ? "rotate-180" : ""} />}</span>
                  </th>
                  <th className="px-4 py-2.5 font-medium text-right">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800/70">
                {data.map((row, i) => (
                  <tr key={String(row.id)} className={`text-neutral-300 transition-colors hover:bg-neutral-800/50 ${i % 2 === 1 ? "bg-neutral-900/30" : ""}`}>
                    <td className="whitespace-nowrap px-4 py-2.5">{String(row.id ?? "—")}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">{String(row.nome ?? "—")}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">{row.empresa_id ? (empresaNomePorId[String(row.empresa_id)] || `#${row.empresa_id}`) : "—"}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">{String(row.email ?? "—")}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">{String(row.telefone ?? "—")}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">{String(row.origem ?? "—")}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">{String(row.funil_etapa ?? "—")}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">{fmtBRL(Number(row.valor_potencial) || 0)}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">
                      {(() => {
                        const s = String(row.status ?? "novo");
                        return <span className={`px-2 py-0.5 rounded text-[10px] ${STATUS_CORES[s] || "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
                      })()}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end items-center gap-1">
                        <Can permission="crm.editar">
                          <button onClick={() => openEdit(row)} title="Editar"
                            className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-indigo-500/10 hover:text-indigo-400">
                            <Icon name="pencil" size={13} />
                          </button>
                        </Can>
                        <Can permission="crm.excluir">
                          <button onClick={() => setConfirmDelete(Number(row.id))} title="Excluir"
                            className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-red-500/10 hover:text-red-400">
                            <Icon name="trash" size={13} />
                          </button>
                        </Can>
                      </div>
                    </td>
                  </tr>
                ))}
                {data.length === 0 && (
                  <tr>
                    <td colSpan={10} className="px-4 py-10">
                      <div className="flex flex-col items-center gap-2 text-neutral-500">
                        <Icon name="inbox" size={22} />
                        <span className="text-xs">{temFiltroAtivo ? "Nenhum lead corresponde aos filtros" : "Nenhum lead cadastrado"}</span>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-neutral-800 px-4 py-2.5 text-[11px] text-neutral-400">
            <span>
              {meta.total === 0
                ? "Nenhum registro"
                : `Mostrando ${(meta.page - 1) * meta.page_size + 1}–${Math.min(meta.page * meta.page_size, meta.total)} de ${meta.total}`}
            </span>
            <div className="flex items-center gap-2">
              <select value={pageSize} onChange={e => setPageSize(Number(e.target.value) as 25 | 50 | 100)}
                className="rounded-lg border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px] text-neutral-300 focus:border-indigo-500 focus:outline-none">
                {PAGE_SIZES.map(n => <option key={n} value={n}>{n} / página</option>)}
              </select>
              <button disabled={meta.page <= 1} onClick={() => setPage(p => p - 1)}
                className="rounded-lg p-1.5 text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200 disabled:opacity-30 disabled:hover:bg-transparent">
                <Icon name="chevronLeft" size={14} />
              </button>
              <span>Página {meta.page} de {meta.pages}</span>
              <button disabled={meta.page >= meta.pages} onClick={() => setPage(p => p + 1)}
                className="rounded-lg p-1.5 text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200 disabled:opacity-30 disabled:hover:bg-transparent">
                <Icon name="chevronRight" size={14} />
              </button>
            </div>
          </div>
        </div>
      )}

      {modal.open && (
        <CrudFormModal
          mode={modal.mode}
          fields={leadsFields}
          formData={formData}
          onChange={(key, value) => setFormData(prev => ({ ...prev, [key]: value }))}
          onSave={handleSave}
          onClose={() => setModal({ open: false, mode: "create" })}
        />
      )}

      {confirmDelete !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setConfirmDelete(null)}>
          <div className="w-full max-w-[340px] rounded-xl border border-neutral-700 bg-neutral-800 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="mb-3 flex items-center gap-2 text-red-400">
              <Icon name="alert" size={17} />
              <h3 className="text-sm font-semibold text-neutral-100">Confirmar exclusão</h3>
            </div>
            <p className="mb-4 text-xs text-neutral-400">Tem certeza que deseja excluir este lead? Essa ação não pode ser desfeita.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmDelete(null)} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:text-neutral-200">Cancelar</button>
              <button onClick={() => handleDelete(confirmDelete)} className="rounded-lg bg-red-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-500">Excluir</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Type-check final**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros

- [ ] **Step 7: Commit**

```bash
git add web/src/app/crm/leads/_components/LeadsPanel.tsx
git commit -m "feat: LeadsPanel com filtros, ordenacao, paginacao e exportador CSV"
```

---

### Task 6: Frontend — trocar `crm/leads/page.tsx` para usar `LeadsPanel`

**Files:**
- Modify: `web/src/app/crm/leads/page.tsx` (reescrita completa — todo o conteúdo atual migrou para `LeadsPanel.tsx` na Task 5)

**Interfaces:**
- Consumes: `LeadsPanel` de `./_components/LeadsPanel` (Task 5).

- [ ] **Step 1: Reescrever `page.tsx`**

```tsx
"use client";

import LeadsPanel from "./_components/LeadsPanel";

export default function Page() {
  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Leads</h1>
        <p className="text-xs text-neutral-500 mt-1">Capte e gerencie novos leads</p>
      </div>
      <LeadsPanel />
    </div>
  );
}
```

- [ ] **Step 2: Type-check e build completo**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: build passa sem erros

- [ ] **Step 3: Commit**

```bash
git add web/src/app/crm/leads/page.tsx
git commit -m "feat: crm/leads usa LeadsPanel no lugar do CrudPanel generico"
```

---

### Task 7: Verificação end-to-end manual (browser real)

**Files:** nenhum (só verificação)

**Interfaces:** N/A

- [ ] **Step 1: Subir o backend e o frontend localmente (ou usar o ambiente já rodando em produção, se preferível pelo usuário)**

- [ ] **Step 2: Roteiro de verificação via browser (Playwright MCP ou manual)**

1. Abrir `/crm/leads`, confirmar que a tabela carrega com paginação (rodapé "Mostrando X–Y de Z", seletor de itens por página, botões Anterior/Próxima).
2. Aplicar filtro de Status — confirmar que a tabela atualiza e a URL de rede (`/api/crm/leads?...status=...`) reflete o filtro.
3. Aplicar filtro de Etapa do funil, depois combinar com Status — confirmar resultado é interseção (AND).
4. Digitar em Origem — confirmar debounce (não dispara request a cada tecla) e resultado filtrado.
5. Selecionar Empresa no dropdown — confirmar filtro aplicado.
6. Alternar Telefone entre "Com telefone" / "Sem telefone" — confirmar resultado.
7. Clicar "Limpar filtros" — confirmar que todos os filtros resetam e a lista volta ao total completo.
8. Clicar no cabeçalho "Valor potencial" — confirmar ordenação ascendente, clicar de novo — confirmar descendente (seta inverte).
9. Repetir para "Status" e "Etapa do funil".
10. Mudar itens por página (25 → 50 → 100) — confirmar que a página volta pra 1 e a contagem de linhas muda.
11. Navegar Próxima/Anterior — confirmar que os dados mudam e os botões desabilitam nos extremos.
12. Aplicar um filtro (ex.: Status = "novo"), clicar "Exportar CSV" — confirmar que baixa um arquivo `leads_AAAA-MM-DD.csv`, abrir e conferir que as linhas batem com o que está filtrado na tela (mesmos leads, mesma ordenação).
13. Criar um lead novo (botão "Novo") — confirmar que o modal (agora via `CrudFormModal`) funciona igual a antes, e o novo lead aparece na lista após salvar.
14. Editar um lead existente — confirmar que abre com os dados preenchidos e salva corretamente.
15. Excluir um lead — confirmar diálogo de confirmação e remoção da lista.
16. Navegar para outra tela que usa `CrudPanel` (ex.: `/cadastros` aba Clientes, ou `/crm/empresas`) — confirmar que continua funcionando exatamente como antes (sem paginação/filtro/sort — isso é esperado, fora de escopo).

- [ ] **Step 2: Reportar quaisquer divergências encontradas e corrigir antes de considerar a task concluída**

---

## Self-Review

**Spec coverage:** paginação (Task 1 + 5), filtros por status/etapa/origem/empresa/telefone (Task 1 + 5), busca geral (Task 1 `q` + Task 5), ordenação por valor/status/etapa/id (Task 1 + 5), exportador CSV respeitando filtros (Task 1 `export=true` + Task 5 `handleExportar`), isolamento do `CrudPanel` genérico (Task 3 extração sem mudar API pública), retrocompatibilidade das outras 11 telas (Task 2 Step 5, Task 3 Step 4) — todos cobertos.

**Placeholder scan:** nenhum "TBD"/"implementar depois" — todo código é completo e executável.

**Type consistency:** `LeadFiltro` (Task 4) usa os mesmos nomes de campo consumidos em `LeadsPanel.tsx` (Task 5: `page, pageSize, sort, order, status, funilEtapa, origem, empresaId, comTelefone, q`). `listar_leads_filtrado` (Task 1) usa os mesmos nomes de kwargs que `_parse_filtro_leads` (Task 2) produz (`page, page_size, sort, order, status, funil_etapa, origem, empresa_id, com_telefone, q, export`). `FieldDef` definida uma única vez em `CrudFormModal.tsx` (Task 3) e reexportada por `CrudPanel.tsx` — `LeadsPanel.tsx` importa direto de `CrudFormModal`.
