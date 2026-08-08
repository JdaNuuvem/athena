"""Testes de rota — /api/shopee/divergencias (Task 6 da spec de Divergencia
de Saldo)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"

async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"),
    )), __aexit__=AsyncMock(return_value=None))
    return m

patch("asyncpg.create_pool", side_effect=_mock_pool).start()

from flask import Flask
from routes.shopee import shopee_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(shopee_bp)
    return app.test_client()


class TestDivergenciasShopeeRota(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def _headers(self):
        return {"Authorization": f"Bearer {_TEST_TOKEN}"}

    def test_listar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("shopee.divergencia.listar_divergencias") as mock_fn:
            r = self.client.get("/api/shopee/divergencias?loja_id=1", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_listar_com_permissao_libera(self):
        with patch("shopee.divergencia.listar_divergencias", return_value={"ok": True, "data": []}) as mock_fn:
            r = self.client.get("/api/shopee/divergencias?loja_id=1", headers=self._headers())
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once_with(1)

    def test_listar_com_permissao_granular_estoque_ver_libera(self):
        """Usa um token de sessao comum (nao master) com exatamente 'estoque.ver'
        concedida — fecha o buraco onde inverter os decorators GET/POST passaria
        despercebido (token master ignora RBAC granular e nao pegaria isso)."""
        token = rbac.gerar_token_sessao(8, "ver@x.com", "Operador")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["estoque.ver"]), \
             patch("shopee.divergencia.listar_divergencias", return_value={"ok": True, "data": []}) as mock_fn:
            r = self.client.get("/api/shopee/divergencias?loja_id=1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once_with(1)

    def test_resolver_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("shopee.divergencia.marcar_revisado") as mock_fn:
            r = self.client.post("/api/shopee/divergencias/1/resolver", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_resolver_com_permissao_libera(self):
        with patch("shopee.divergencia.marcar_revisado", return_value={"ok": True}) as mock_fn:
            r = self.client.post("/api/shopee/divergencias/1/resolver", headers=self._headers())
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once_with(1)

    def test_resolver_com_permissao_granular_estoque_editar_libera(self):
        """Mesma logica de test_listar_com_permissao_granular_estoque_ver_libera,
        mas pra rota POST /resolver com 'estoque.editar'."""
        token = rbac.gerar_token_sessao(9, "editar@x.com", "Operador")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["estoque.editar"]), \
             patch("shopee.divergencia.marcar_revisado", return_value={"ok": True}) as mock_fn:
            r = self.client.post("/api/shopee/divergencias/1/resolver", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once_with(1)

    def test_resolver_com_erro_retorna_400(self):
        with patch("shopee.divergencia.marcar_revisado", return_value={"erro": "snapshot nao encontrado"}):
            r = self.client.post("/api/shopee/divergencias/999/resolver", headers=self._headers())
        self.assertEqual(r.status_code, 400)

    def test_ajustar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("shopee.divergencia.aplicar_ajuste_divergencia") as mock_fn:
            r = self.client.post("/api/shopee/divergencias/1/ajustar", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_ajustar_com_permissao_libera(self):
        with patch("shopee.divergencia.aplicar_ajuste_divergencia", return_value={"ok": True}) as mock_fn:
            r = self.client.post("/api/shopee/divergencias/1/ajustar", headers=self._headers())
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once()
        self.assertEqual(mock_fn.call_args.args[0], 1)

    def test_ajustar_com_permissao_granular_estoque_editar_libera(self):
        """Mesma logica de test_resolver_com_permissao_granular_estoque_editar_libera,
        mas pra rota POST /ajustar."""
        token = rbac.gerar_token_sessao(9, "editar@x.com", "Operador")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["estoque.editar"]), \
             patch("shopee.divergencia.aplicar_ajuste_divergencia", return_value={"ok": True}) as mock_fn:
            r = self.client.post("/api/shopee/divergencias/1/ajustar", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once()

    def test_ajustar_com_erro_retorna_400(self):
        with patch("shopee.divergencia.aplicar_ajuste_divergencia", return_value={"erro": "snapshot nao encontrado"}):
            r = self.client.post("/api/shopee/divergencias/999/ajustar", headers=self._headers())
        self.assertEqual(r.status_code, 400)
