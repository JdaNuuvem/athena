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
        self.assertIn("ORDER BY id DESC, id DESC", query)
        self.assertNotIn("WHERE", query)
        self.assertEqual(resultado["meta"], {"total": 2, "page": 1, "page_size": 25, "pages": 1})
        self.assertEqual(len(resultado["data"]), 2)

    def test_paginacao_tem_desempate_por_id_para_ordenacao_estavel(self):
        # status/funil_etapa/valor_potencial nao sao unicos — sem desempate por id,
        # o Postgres nao garante ordem estavel entre duas queries LIMIT/OFFSET
        # separadas quando ha empates (lead pode duplicar ou sumir entre paginas).
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(sort="status", order="asc")
        query = db_mock.fetch.call_args.args[0]
        self.assertIn("ORDER BY status ASC, id DESC", query)

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
        self.assertIn("ORDER BY valor_potencial ASC, id DESC", db_mock.fetch.call_args.args[0])

    def test_ordenacao_status_desc(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(sort="status", order="desc")
        self.assertIn("ORDER BY status DESC, id DESC", db_mock.fetch.call_args.args[0])

    def test_ordenacao_funil_etapa_asc(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(sort="funil_etapa", order="asc")
        self.assertIn("ORDER BY funil_etapa ASC, id DESC", db_mock.fetch.call_args.args[0])

    def test_order_invalido_cai_em_desc(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(sort="status", order="xyz")
        self.assertIn("ORDER BY status DESC, id DESC", db_mock.fetch.call_args.args[0])

    def test_sort_fora_da_whitelist_cai_no_default_id_sem_interpolar(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(sort="id; DROP TABLE crm_leads;--")
        query = db_mock.fetch.call_args.args[0]
        self.assertIn("ORDER BY id DESC, id DESC", query)
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

    def test_export_tem_desempate_por_id_para_ordenacao_estavel(self):
        # Mesma garantia de ordem estavel do branch paginado tambem vale pro
        # export: sem "id DESC" apos a coluna de ordenacao, o corte em 5000
        # linhas pode variar entre chamadas quando ha empates.
        db_mock = _mock_db(total=100, rows=[{"id": 1}])
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            crm.listar_leads_filtrado(export=True, sort="funil_etapa", order="asc")
        query = db_mock.fetch.call_args.args[0]
        self.assertIn("ORDER BY funil_etapa ASC, id DESC", query)


class TestListarLeadsFiltradoErro(unittest.TestCase):
    def test_erro_de_banco_retorna_lista_vazia_sem_quebrar(self):
        db_mock = AsyncMock()
        db_mock.fetchval = AsyncMock(side_effect=Exception("db down"))
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            resultado = crm.listar_leads_filtrado(page=3, page_size=50)
        self.assertEqual(resultado, {"data": [], "meta": {"total": 0, "page": 3, "page_size": 50, "pages": 0}})

    def test_page_nao_numerico_nao_quebra_degrada_graciosamente(self):
        db_mock = _mock_db()
        async def _fake_get_db(): return db_mock
        with patch("core.crm.get_db", _fake_get_db):
            resultado = crm.listar_leads_filtrado(page="abc", page_size=25)
        # Deve retornar fallback seguro sem levantar exceção
        self.assertEqual(resultado["data"], [])
        self.assertEqual(resultado["meta"]["total"], 0)
        self.assertEqual(resultado["meta"]["page_size"], 25)


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
        self.assertIs(mock_filtrado.call_args.kwargs["com_telefone"], False)

    def test_empresa_id_invalido_vira_none_em_vez_de_quebrar(self):
        with patch("core.crm.listar_leads_filtrado", return_value={"data": [], "meta": {}}) as mock_filtrado:
            r = self.client.get("/api/crm/leads?empresa_id=abc", headers=self._headers())
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(mock_filtrado.call_args.kwargs["empresa_id"])

    def test_export_true_vira_bool(self):
        with patch("core.crm.listar_leads_filtrado", return_value={"data": [], "meta": {}}) as mock_filtrado:
            self.client.get("/api/crm/leads?export=true", headers=self._headers())
        self.assertTrue(mock_filtrado.call_args.kwargs["export"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
