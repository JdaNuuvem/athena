"""Testes de integracao — CRUD generico de vendas e atualizacao de status
de pedido antes nao checavam nenhuma permissao, e o campo 'usuario' gravado
no historico de status vinha como texto livre do cliente."""
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
from routes.vendas import vendas_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(vendas_bp)
    return app.test_client()


class TestVendasCRUDExigePermissao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_criar_generico_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.vendas.create") as mock_create:
            r = self.client.post("/api/vendas/pedidos", json={"cliente": "X"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_create.assert_not_called()

    def test_criar_pedido_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.vendas.criar_pedido") as mock_criar:
            r = self.client.post("/api/vendas/pedido", json={"cliente": "X", "itens": []}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_criar.assert_not_called()

    def test_criar_pedido_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["vendas.criar"]), \
             patch("core.vendas.criar_pedido", return_value={"pedido": {"id": 1}, "total": 100}) as mock_criar:
            r = self.client.post("/api/vendas/pedido", json={"cliente": "X", "itens": []}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_criar.assert_called_once()

    def test_excluir_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["vendas.criar", "vendas.editar"]), \
             patch("core.vendas.delete") as mock_delete:
            r = self.client.delete("/api/vendas/pedidos/1", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_delete.assert_not_called()

    def test_excluir_com_permissao_libera_e_audita(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.vendas.get", return_value={"id": 1, "cliente": "X"}), \
             patch("core.vendas.delete", return_value={"success": True}) as mock_delete, \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.delete("/api/vendas/pedidos/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_delete.assert_called_once()
        mock_audit.assert_called_once_with("vendas", "pedidos", 1, {"id": 1, "cliente": "X"})


class TestVendasAtualizarStatusUsaIdentidadeReal(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_sem_permissao_vendas_editar_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["vendas.criar"]), \
             patch("core.vendas.atualizar_status") as mock_atualizar:
            r = self.client.put("/api/vendas/pedido/1/status", json={"status": "faturado"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_atualizar.assert_not_called()

    def test_usuario_gravado_vem_do_token_nao_do_corpo_da_requisicao(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["vendas.editar"]), \
             patch("core.vendas.atualizar_status", return_value={"id": 1, "status": "faturado"}) as mock_atualizar:
            r = self.client.put(
                "/api/vendas/pedido/1/status",
                json={"status": "faturado", "usuario": "Outra Pessoa"},
                headers=headers,
            )
        self.assertEqual(r.status_code, 200)
        mock_atualizar.assert_called_once_with(1, "faturado", "gerente")


if __name__ == "__main__":
    unittest.main(verbosity=2)
