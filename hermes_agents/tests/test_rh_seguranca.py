"""Testes de integracao — CRUD de RH (funcionarios, ponto, ferias, escala,
folha, beneficios, vale, comissoes) antes nao checava nenhuma permissao."""
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
from routes.rh import rh_bp
import core.rbac as rbac


class TestRHCRUDExigePermissao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(rh_bp)
        self.client = app.test_client()

    def tearDown(self):
        self._env_patch.stop()

    def test_criar_generico_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]), \
             patch("core.rh.create") as mock_create:
            r = self.client.post("/api/rh/funcionarios", json={"nome": "X"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_create.assert_not_called()

    def test_criar_generico_com_rh_criar_libera(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["rh.criar"]), \
             patch("core.rh.create", return_value={"id": 1}) as mock_create:
            r = self.client.post("/api/rh/funcionarios", json={"nome": "X"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_create.assert_called_once()

    def test_editar_generico_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["rh.criar"]), \
             patch("core.rh.update") as mock_update:
            r = self.client.put("/api/rh/funcionarios/1", json={"nome": "Y"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_update.assert_not_called()

    def test_excluir_generico_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["rh.criar", "rh.editar"]), \
             patch("core.rh.delete") as mock_delete:
            r = self.client.delete("/api/rh/funcionarios/1", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_delete.assert_not_called()

    def test_excluir_generico_com_rh_excluir_libera(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.rh.get", return_value={"id": 1, "nome": "X"}), \
             patch("core.rh.delete", return_value={"success": True}) as mock_delete:
            r = self.client.delete("/api/rh/funcionarios/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_delete.assert_called_once()

    def test_vale_criar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]), \
             patch("core.rh.criar_vale") as mock_criar:
            r = self.client.post("/api/rh/vale", json={"funcionario_id": 1, "valor": 100}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_criar.assert_not_called()

    def test_vale_criar_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["rh.criar"]), \
             patch("core.rh.criar_vale", return_value={"id": 1}) as mock_criar:
            r = self.client.post("/api/rh/vale", json={"funcionario_id": 1, "valor": 100}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_criar.assert_called_once()

    def test_comissoes_atualizar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]), \
             patch("core.rh.atualizar_comissao") as mock_atualizar:
            r = self.client.put("/api/rh/comissoes/1", json={"status": "paga"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_atualizar.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
