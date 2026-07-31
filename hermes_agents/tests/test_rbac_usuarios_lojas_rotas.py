"""Testes de integracao das rotas GET/PUT /api/rbac/usuarios/<id>/lojas —
vincular/desvincular usuario a lojas (controla acesso, ver core/usuario_lojas.py)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"
os.environ.setdefault("ATHENA_TOKEN", _TEST_TOKEN)


async def _mp(*a, **kw):
    return AsyncMock()


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

from flask import Flask
from routes.rbac import rbac_bp


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(rbac_bp)
    return app.test_client()


class TestRbacUsuariosLojasRotas(unittest.TestCase):
    def setUp(self):
        self.client = _app()
        self.headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}

    def test_get_lista_lojas_do_usuario(self):
        with patch("core.usuario_lojas.listar_lojas_do_usuario", return_value=[{"id": 3, "nome": "Loja 3"}]) as mock_listar:
            r = self.client.get("/api/rbac/usuarios/7/lojas", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["lojas"], [{"id": 3, "nome": "Loja 3"}])
        mock_listar.assert_called_once_with(7)

    def test_put_substitui_vinculos(self):
        with patch("core.usuario_lojas.substituir_vinculos", return_value={"usuario_id": 7, "loja_ids": [3, 4]}) as mock_sub:
            r = self.client.put("/api/rbac/usuarios/7/lojas", json={"loja_ids": [3, 4]}, headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"usuario_id": 7, "loja_ids": [3, 4]})
        mock_sub.assert_called_once_with(7, [3, 4])

    def test_put_lista_vazia_remove_todos_os_vinculos(self):
        with patch("core.usuario_lojas.substituir_vinculos", return_value={"usuario_id": 7, "loja_ids": []}) as mock_sub:
            r = self.client.put("/api/rbac/usuarios/7/lojas", json={"loja_ids": []}, headers=self.headers)
        self.assertEqual(r.status_code, 200)
        mock_sub.assert_called_once_with(7, [])

    def test_put_sem_loja_ids_retorna_400(self):
        r = self.client.put("/api/rbac/usuarios/7/lojas", json={}, headers=self.headers)
        self.assertEqual(r.status_code, 400)

    def test_put_loja_ids_nao_numerico_retorna_400(self):
        r = self.client.put("/api/rbac/usuarios/7/lojas", json={"loja_ids": ["abc"]}, headers=self.headers)
        self.assertEqual(r.status_code, 400)

    def test_put_propaga_erro_de_infra_como_500(self):
        with patch("core.usuario_lojas.substituir_vinculos", return_value={"error": "falha de conexao"}):
            r = self.client.put("/api/rbac/usuarios/7/lojas", json={"loja_ids": [3]}, headers=self.headers)
        self.assertEqual(r.status_code, 500)


if __name__ == "__main__":
    unittest.main(verbosity=2)
