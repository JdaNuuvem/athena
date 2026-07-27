"""Testes de integracao — aprovacao de solicitacao de compra exige RBAC real,
nao mais um campo "aprovador" de texto livre enviado pelo cliente."""
import sys, os, json, unittest
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
from routes.compras import compras_bp
import core.rbac as rbac


class TestComprasAprovarRBAC(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(compras_bp)
        self.client = app.test_client()

    def tearDown(self):
        self._env_patch.stop()

    def test_sem_token_nega(self):
        r = self.client.post("/api/compras/solicitacoes/1/aprovar", json={})
        self.assertEqual(r.status_code, 403)

    def test_usuario_sem_permissao_compras_aprovar_e_negado(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]):
            r = self.client.post("/api/compras/solicitacoes/1/aprovar", json={}, headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_usuario_com_permissao_aprova_usando_identidade_real_do_token(self):
        """O nome/id gravados como aprovador devem vir do token autenticado,
        nunca do corpo da requisicao — mesmo que o cliente tente enviar outro."""
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["compras.aprovar"]), \
             patch("core.compras.aprovar_solicitacao", return_value={"id": 1, "status": "aprovada"}) as mock_aprovar:
            r = self.client.post(
                "/api/compras/solicitacoes/1/aprovar",
                json={"aprovador": "Diretor Falso"},
                headers=headers,
            )
        self.assertEqual(r.status_code, 200)
        mock_aprovar.assert_called_once()
        args = mock_aprovar.call_args[0]
        self.assertEqual(args[0], 1)
        self.assertEqual(args[1], 9)
        self.assertEqual(args[2], "gerente")

    def test_token_master_aprova(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.compras.aprovar_solicitacao", return_value={"id": 1, "status": "aprovada"}) as mock_aprovar:
            r = self.client.post("/api/compras/solicitacoes/1/aprovar", json={}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_aprovar.assert_called_once()


class TestComprasCRUDExigePermissao(unittest.TestCase):
    """CRUD generico de compras (create/update/delete) antes nao checava
    nenhuma permissao — qualquer usuario autenticado podia criar, editar ou
    excluir fornecedores, pedidos, cotacoes etc."""

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(compras_bp)
        self.client = app.test_client()

    def tearDown(self):
        self._env_patch.stop()

    def test_criar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]), \
             patch("core.compras.create") as mock_create:
            r = self.client.post("/api/compras/fornecedores", json={"nome": "X"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_create.assert_not_called()

    def test_criar_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["compras.criar"]), \
             patch("core.compras.create", return_value={"id": 1}) as mock_create:
            r = self.client.post("/api/compras/fornecedores", json={"nome": "X"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_create.assert_called_once()

    def test_editar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["compras.criar"]), \
             patch("core.compras.update") as mock_update:
            r = self.client.put("/api/compras/fornecedores/1", json={"nome": "Y"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_update.assert_not_called()

    def test_excluir_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["compras.criar", "compras.editar"]), \
             patch("core.compras.delete") as mock_delete:
            r = self.client.delete("/api/compras/fornecedores/1", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_delete.assert_not_called()

    def test_excluir_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["compras.excluir"]), \
             patch("core.compras.get", return_value={"id": 1, "nome": "X"}), \
             patch("core.compras.delete", return_value={"success": True}) as mock_delete:
            r = self.client.delete("/api/compras/fornecedores/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_delete.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
