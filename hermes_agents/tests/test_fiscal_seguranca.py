"""Testes de integracao — CRUD generico de fiscal (notas fiscais, tributos,
obrigacoes etc.) antes nao checava nenhuma permissao."""
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
from routes.fiscal import fiscal_bp
import core.rbac as rbac


class TestFiscalCRUDExigePermissao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(fiscal_bp)
        self.client = app.test_client()

    def tearDown(self):
        self._env_patch.stop()

    def test_criar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]), \
             patch("core.fiscal.create") as mock_create:
            r = self.client.post("/api/fiscal/notas_fiscais", json={"numero_nf": "1"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_create.assert_not_called()

    def test_criar_com_permissao_fiscal_libera(self):
        token = rbac.gerar_token_sessao(9, "financeiro@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["fiscal.criar"]), \
             patch("core.fiscal.create", return_value={"id": 1}) as mock_create:
            r = self.client.post("/api/fiscal/notas_fiscais", json={"numero_nf": "1"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_create.assert_called_once()

    def test_editar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["fiscal.criar"]), \
             patch("core.fiscal.update") as mock_update:
            r = self.client.put("/api/fiscal/notas_fiscais/1", json={"status": "x"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_update.assert_not_called()

    def test_excluir_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["fiscal.criar", "fiscal.editar"]), \
             patch("core.fiscal.delete") as mock_delete:
            r = self.client.delete("/api/fiscal/notas_fiscais/1", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_delete.assert_not_called()

    def test_excluir_com_permissao_libera_e_audita(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.fiscal.get", return_value={"id": 1, "numero_nf": "1"}), \
             patch("core.fiscal.delete", return_value={"success": True}) as mock_delete, \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.delete("/api/fiscal/notas_fiscais/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_delete.assert_called_once()
        mock_audit.assert_called_once_with("fiscal", "notas_fiscais", 1, {"id": 1, "numero_nf": "1"})


class TestFiscalLeituraExigePermissao(unittest.TestCase):
    """GET /api/fiscal/<tabela> e /<tabela>/<id> nao checavam NENHUMA
    permissao — so' create/update/delete usavam requer_permissao. Qualquer
    usuario autenticado podia listar notas fiscais e contas a receber/pagar
    do Bling. Corrigido com "fiscal.ver"."""

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(fiscal_bp)
        self.client = app.test_client()

    def tearDown(self):
        self._env_patch.stop()

    def test_listar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]), \
             patch("core.fiscal.list") as mock_list:
            r = self.client.get("/api/fiscal/notas_fiscais", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_list.assert_not_called()

    def test_listar_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(9, "financeiro@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["fiscal.ver"]), \
             patch("core.fiscal.list", return_value=[{"id": 1}]) as mock_list:
            r = self.client.get("/api/fiscal/notas_fiscais", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_list.assert_called_once()

    def test_get_um_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.fiscal.get") as mock_get:
            r = self.client.get("/api/fiscal/notas_fiscais/1", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_get.assert_not_called()

    def test_sync_notas_fiscais_sem_permissao_nega(self):
        """/api/fiscal/sync/notas-fiscais (botao "Sync Bling" da pagina de
        notas) tambem nao tinha checagem nenhuma — o <Can permission="fiscal:edit">
        do frontend nunca batia com o formato real ("fiscal.editar"), entao o
        botao ficava invisivel, mas a rota em si continuava aberta pra
        qualquer chamada direta."""
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.fiscal.sincronizar_notas_fiscais_bling") as mock_sync:
            r = self.client.post("/api/fiscal/sync/notas-fiscais", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_sync.assert_not_called()

    def test_sync_notas_fiscais_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(9, "financeiro@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["fiscal.editar"]), \
             patch("core.fiscal.sincronizar_notas_fiscais_bling", return_value={"sync": 3}) as mock_sync:
            r = self.client.post("/api/fiscal/sync/notas-fiscais", json={}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_sync.assert_called_once()


class TestFiscalNotaItensImpostosRotas(unittest.TestCase):
    """/notas-fiscais/<id>/itens e /impostos ignoravam completamente o id —
    _list("fiscal_nfe_itens", ...) sem WHERE devolvia os itens de TODAS as
    notas fiscais pra qualquer id pedido."""

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(fiscal_bp)
        self.client = app.test_client()

    def tearDown(self):
        self._env_patch.stop()

    def test_itens_passa_o_id_certo_pro_core(self):
        token = rbac.gerar_token_sessao(9, "financeiro@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["fiscal.ver"]), \
             patch("core.fiscal.itens_da_nota", return_value=[{"id": 1, "nota_id": 42}]) as mock_itens:
            r = self.client.get("/api/fiscal/notas-fiscais/42/itens", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_itens.assert_called_once_with(42)
        self.assertEqual(r.get_json()["data"], [{"id": 1, "nota_id": 42}])

    def test_impostos_passa_o_id_certo_pro_core(self):
        token = rbac.gerar_token_sessao(9, "financeiro@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["fiscal.ver"]), \
             patch("core.fiscal.impostos_da_nota", return_value=[{"id": 5, "nota_id": 77}]) as mock_impostos:
            r = self.client.get("/api/fiscal/notas-fiscais/77/impostos", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_impostos.assert_called_once_with(77)

    def test_itens_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.fiscal.itens_da_nota") as mock_itens:
            r = self.client.get("/api/fiscal/notas-fiscais/42/itens", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_itens.assert_not_called()


class TestItensImpostosDaNotaFiltramPorNota(unittest.TestCase):
    """Unidade: itens_da_nota/impostos_da_nota fazem SELECT ... WHERE nota_id
    = $1 — nao devolvem tudo do banco."""

    def test_itens_da_nota_usa_where_nota_id(self):
        import core.fiscal as fiscal
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[{"id": 1, "nota_id": 42, "numero_item": 1}])
        with patch("core.fiscal.get_db", AsyncMock(return_value=db)):
            resultado = fiscal.itens_da_nota(42)
        self.assertEqual(resultado, [{"id": 1, "nota_id": 42, "numero_item": 1}])
        query, nota_id = db.fetch.call_args.args
        self.assertIn("WHERE nota_id = $1", query)
        self.assertEqual(nota_id, 42)

    def test_impostos_da_nota_usa_where_nota_id(self):
        import core.fiscal as fiscal
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[])
        with patch("core.fiscal.get_db", AsyncMock(return_value=db)):
            fiscal.impostos_da_nota(77)
        query, nota_id = db.fetch.call_args.args
        self.assertIn("WHERE nota_id = $1", query)
        self.assertEqual(nota_id, 77)


class TestDanfeUrlResiliente(unittest.TestCase):
    """bling_erp.get_nfe_danfe_url substitui 2 rotas duplicadas que usavam
    2 chaves diferentes ("danfe" numa, "linkDanfe" noutra) sem fallback."""

    def test_tenta_linkDanfe_primeiro(self):
        import bling_erp
        with patch("bling_erp.get_nfe_detail", return_value={"data": {"linkDanfe": "https://x/danfe.pdf"}}):
            self.assertEqual(bling_erp.get_nfe_danfe_url(1), "https://x/danfe.pdf")

    def test_cai_para_danfe_se_linkDanfe_ausente(self):
        import bling_erp
        with patch("bling_erp.get_nfe_detail", return_value={"data": {"danfe": "https://y/danfe.pdf"}}):
            self.assertEqual(bling_erp.get_nfe_danfe_url(1), "https://y/danfe.pdf")

    def test_vazio_quando_nenhuma_chave_presente(self):
        import bling_erp
        with patch("bling_erp.get_nfe_detail", return_value={"data": {}}):
            self.assertEqual(bling_erp.get_nfe_danfe_url(1), "")

    def test_vazio_em_erro(self):
        import bling_erp
        with patch("bling_erp.get_nfe_detail", return_value={"error": "timeout"}):
            self.assertEqual(bling_erp.get_nfe_danfe_url(1), "")



class TestRotasFiscalRemovidas(unittest.TestCase):
    """Fase 1 da limpeza do modulo Fiscal removeu tabelas/cfop|ncm|cest e
    tributos/calcular/<id> — confirma que nao respondem mais (404), nao
    algum outro erro que sugira que a rota ainda existe."""

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(fiscal_bp)
        self.client = app.test_client()

    def tearDown(self):
        self._env_patch.stop()

    def test_tabelas_cfop_removida(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get("/api/fiscal/tabelas/cfop", headers=headers)
        self.assertEqual(r.status_code, 404)

    def test_tabelas_ncm_removida(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get("/api/fiscal/tabelas/ncm", headers=headers)
        self.assertEqual(r.status_code, 404)

    def test_tabelas_cest_removida(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get("/api/fiscal/tabelas/cest", headers=headers)
        self.assertEqual(r.status_code, 404)

    def test_tributos_calcular_removida(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get("/api/fiscal/tributos/calcular/1", headers=headers)
        self.assertEqual(r.status_code, 404)

    def test_contas_receber_bling_nao_e_mais_tabela_valida(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get("/api/fiscal/contas_receber_bling", headers=headers)
        self.assertEqual(r.status_code, 404)

    def test_contas_pagar_bling_nao_e_mais_tabela_valida(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get("/api/fiscal/contas_pagar_bling", headers=headers)
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
