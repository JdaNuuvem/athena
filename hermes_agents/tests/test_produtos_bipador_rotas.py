"""Testes de rota — import de produtos/estoque do app de bipagem/estoque."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

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
import core.rbac as rbac


def _app():
    from routes.produtos_bipador import produtos_bipador_bp
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(produtos_bipador_bp)
    return app.test_client()


class TestRotasProdutosBipador(unittest.TestCase):
    def setUp(self):
        self.client = _app()

    def _headers_com_permissao(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            token = rbac.gerar_token_sessao(11, "u@x.com", "Gerente")
            return {"Authorization": f"Bearer {token}"}

    def test_importar_produtos_exige_produtos_editar(self):
        headers = self._headers_com_permissao()
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.post("/api/integracoes/produtos-fisicos/importar", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_importar_produtos_com_permissao_libera(self):
        headers = self._headers_com_permissao()
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.produtos_bipador.sincronizar_catalogo_bipador",
                   return_value={"ok": True, "importados": 5, "erros_registro": []}) as mock_sync:
            r = self.client.post("/api/integracoes/produtos-fisicos/importar", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["importados"], 5)
        mock_sync.assert_called_once()

    def test_importar_estoque_lojas_exige_produtos_editar(self):
        headers = self._headers_com_permissao()
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.post("/api/integracoes/produtos-fisicos/estoque-lojas/importar", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_importar_estoque_lojas_com_permissao_libera(self):
        headers = self._headers_com_permissao()
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.produtos_bipador.sincronizar_estoque_lojas_fisicas",
                   return_value={"ok": True, "atualizados": 3, "sem_sku_mapeado": 0, "por_loja": {}}) as mock_sync:
            r = self.client.post("/api/integracoes/produtos-fisicos/estoque-lojas/importar", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["atualizados"], 3)
        mock_sync.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
