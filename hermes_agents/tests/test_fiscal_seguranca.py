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


if __name__ == "__main__":
    unittest.main(verbosity=2)
