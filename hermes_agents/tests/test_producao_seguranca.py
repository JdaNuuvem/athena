"""Testes de integracao — iniciar/finalizar OP, parar/liberar maquina e o
CRUD generico de producao (ops, bom, maquinas, apontamentos, consumo,
perdas, custos) antes nao checavam nenhuma permissao."""
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
from routes.producao import producao_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(producao_bp)
    return app.test_client()


class TestProducaoExigePermissao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_iniciar_op_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.producao.iniciar_op") as mock_iniciar:
            r = self.client.post("/api/producao/op/1/iniciar", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_iniciar.assert_not_called()

    def test_iniciar_op_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["producao.editar"]), \
             patch("core.producao.iniciar_op", return_value={"id": 1, "status": "em_andamento"}) as mock_iniciar:
            r = self.client.post("/api/producao/op/1/iniciar", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_iniciar.assert_called_once()

    def test_parar_maquina_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.producao.parar_maquina") as mock_parar:
            r = self.client.post("/api/producao/maquina/1/parar", json={"motivo": "manutencao"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_parar.assert_not_called()

    def test_criar_generico_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.producao.create") as mock_create:
            r = self.client.post("/api/producao/ops", json={"produto": "X"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_create.assert_not_called()

    def test_excluir_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["producao.criar", "producao.editar"]), \
             patch("core.producao.delete") as mock_delete:
            r = self.client.delete("/api/producao/ops/1", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_delete.assert_not_called()

    def test_excluir_com_permissao_libera_e_audita(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.producao.get", return_value={"id": 1, "produto": "X"}), \
             patch("core.producao.delete", return_value={"success": True}) as mock_delete, \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.delete("/api/producao/ops/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_delete.assert_called_once()
        mock_audit.assert_called_once_with("producao", "ops", 1, {"id": 1, "produto": "X"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
