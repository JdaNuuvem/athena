"""Testes de integracao — rotas de exclusao forcada de loja
(GET .../impacto-exclusao, POST .../excluir-forcado). Ambas gated so' pela
permissao dedicada lojas.excluir_forcado (Admin-only por padrao), sem
@requer_acesso_loja (acao administrativa central). Padrao _app()/_TEST_TOKEN
e' o mesmo de tests/test_lojas_manage_seguranca.py."""
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
from routes.lojas_manage import lojas_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(lojas_bp)
    return app.test_client()


class TestExclusaoForcadaRotas(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_impacto_exclusao_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["configuracoes.editar"]), \
             patch("core.lojas.impacto_exclusao") as mock_impacto:
            r = self.client.get("/api/lojas/manage/1/impacto-exclusao", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_impacto.assert_not_called()

    def test_impacto_exclusao_com_permissao_libera(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.impacto_exclusao",
                    return_value={"loja": {"id": 1}, "impacto": {}, "total_linhas": 0}) as mock_impacto:
            r = self.client.get("/api/lojas/manage/1/impacto-exclusao", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_impacto.assert_called_once_with(1)

    def test_impacto_exclusao_com_erro_retorna_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.impacto_exclusao", return_value={"erro": "Loja nao encontrada"}):
            r = self.client.get("/api/lojas/manage/999/impacto-exclusao", headers=headers)
        self.assertEqual(r.status_code, 400)

    def test_excluir_forcado_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["configuracoes.excluir"]), \
             patch("core.lojas.excluir_forcado") as mock_excluir:
            r = self.client.post("/api/lojas/manage/1/excluir-forcado",
                                  json={"confirmar_nome": "Loja X"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_excluir.assert_not_called()

    def test_excluir_forcado_com_permissao_libera_e_audita(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.obter", return_value={"id": 1, "nome": "Loja X"}), \
             patch("core.lojas.excluir_forcado",
                   return_value={"ok": True, "apagado": {"pdv_caixas": 2},
                                 "negociacoes_crm_desvinculadas": 0}) as mock_excluir, \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.post("/api/lojas/manage/1/excluir-forcado",
                                  json={"confirmar_nome": "Loja X"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_excluir.assert_called_once_with(1, "Loja X")
        mock_audit.assert_called_once_with(
            "lojas", "manage-forcado", 1,
            {"id": 1, "nome": "Loja X", "apagado": {"pdv_caixas": 2}, "negociacoes_crm_desvinculadas": 0})

    def test_excluir_forcado_com_erro_retorna_400_e_nao_audita(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.obter", return_value={"id": 1, "nome": "Loja X"}), \
             patch("core.lojas.excluir_forcado", return_value={"erro": "Nome de confirmacao nao confere"}), \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.post("/api/lojas/manage/1/excluir-forcado",
                                  json={"confirmar_nome": "Nome Errado"}, headers=headers)
        self.assertEqual(r.status_code, 400)
        mock_audit.assert_not_called()

    def test_excluir_forcado_nao_faz_strip_no_nome_confirmado(self):
        """confirmar_nome precisa chegar exatamente como o body mandou —
        strip() na rota mascararia o caso 'espaco extra' que excluir_forcado()
        precisa reprovar."""
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.obter", return_value={"id": 1, "nome": "Loja X"}), \
             patch("core.lojas.excluir_forcado",
                   return_value={"erro": "Nome de confirmacao nao confere"}) as mock_excluir:
            self.client.post("/api/lojas/manage/1/excluir-forcado",
                              json={"confirmar_nome": "Loja X "}, headers=headers)
        mock_excluir.assert_called_once_with(1, "Loja X ")

    def test_listar_lojas_manage_repassa_status(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.listar",
                   return_value=[{"id": 1, "nome": "Loja X", "status": "inativa", "ativa": False}]):
            r = self.client.get("/api/lojas/manage", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["lojas"][0]["status"], "inativa")

    def test_core_listar_inclui_coluna_status(self):
        import core.lojas as lojas_core
        db = AsyncMock()
        db.fetch.return_value = [{"id": 1, "nome": "Loja X", "ativa": False, "status": "inativa",
                                   "created_at": None, "bling_id": None, "tipo": "fisica",
                                   "shopee_markup_pct": 100, "grupos_publicacao": None,
                                   "shopee_conectado": False}]
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas_core.listar()
        sql = db.fetch.call_args[0][0]
        self.assertIn("status", sql)
        self.assertEqual(resultado[0]["status"], "inativa")


if __name__ == "__main__":
    unittest.main(verbosity=2)
