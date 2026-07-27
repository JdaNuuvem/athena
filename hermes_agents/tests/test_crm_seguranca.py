"""Testes de integracao — CRUD generico de CRM (leads, contatos, negociacoes,
propostas, contratos) antes nao checava nenhuma permissao."""
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


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(crm_bp)
    return app.test_client()


class TestCRMCRUDExigePermissao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_criar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.crm.create") as mock_create:
            r = self.client.post("/api/crm/leads", json={"nome": "X"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_create.assert_not_called()

    def test_criar_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["crm.criar"]), \
             patch("core.crm.create", return_value={"id": 1}) as mock_create:
            r = self.client.post("/api/crm/leads", json={"nome": "X"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_create.assert_called_once()

    def test_editar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["crm.criar"]), \
             patch("core.crm.update") as mock_update:
            r = self.client.put("/api/crm/leads/1", json={"nome": "Y"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_update.assert_not_called()

    def test_excluir_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["crm.criar", "crm.editar"]), \
             patch("core.crm.delete") as mock_delete:
            r = self.client.delete("/api/crm/leads/1", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_delete.assert_not_called()

    def test_excluir_com_permissao_libera_e_audita(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.crm.get", return_value={"id": 1, "nome": "X"}), \
             patch("core.crm.delete", return_value={"success": True}) as mock_delete, \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.delete("/api/crm/leads/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_delete.assert_called_once()
        mock_audit.assert_called_once_with("crm", "leads", 1, {"id": 1, "nome": "X"})

    def test_importar_bling_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.crm.importar_contatos_bling") as mock_importar:
            r = self.client.post("/api/crm/importar-bling", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_importar.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
