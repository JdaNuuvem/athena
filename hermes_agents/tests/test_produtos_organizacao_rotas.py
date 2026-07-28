"""CRUD de marcas/fabricantes/categorias/tags exige RBAC (produtos.ver para
listar, produtos.editar para criar) e audita toda criacao."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=1), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

from flask import Flask
from routes.produtos import produtos_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(produtos_bp)
    return app.test_client()


class TestMarcasCRUD(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env.start()
        self.client = _app()

    def tearDown(self):
        self._env.stop()

    def test_listar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(1, "op@x.com", "Operador")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]):
            r = self.client.get("/api/produtos/marcas", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_criar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(1, "op@x.com", "Operador")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["produtos.ver"]), \
             patch("core.catalogo.criar_marca") as mock_criar:
            r = self.client.post("/api/produtos/marcas", json={"nome": "Nike"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_criar.assert_not_called()

    def test_criar_com_permissao_libera_e_audita(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.catalogo.criar_marca", return_value={"id": 1, "nome": "Nike"}) as mock_criar, \
             patch("core.seguranca.auditar_alteracao") as mock_audit:
            r = self.client.post("/api/produtos/marcas", json={"nome": "Nike"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_criar.assert_called_once_with("Nike")
        mock_audit.assert_called_once()

    def test_criar_sem_nome_retorna_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.post("/api/produtos/marcas", json={}, headers=headers)
        self.assertEqual(r.status_code, 400)


class TestVincularTag(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env.start()
        self.client = _app()

    def tearDown(self):
        self._env.stop()

    def test_vincular_tag_com_permissao(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.catalogo.vincular_tag", return_value={"success": True}) as mock_vinc:
            r = self.client.post("/api/produtos/10/tags", json={"tag_id": 3}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_vinc.assert_called_once_with(10, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
