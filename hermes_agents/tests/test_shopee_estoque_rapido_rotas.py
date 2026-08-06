"""Testes de integracao — rotas GET/PUT /api/shopee/estoque-rapido em
routes/shopee.py (aba Estoque Rapido)."""
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
from routes.shopee import shopee_bp

_TEST_TOKEN = "test-master-token-32-bytes-long!!"


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(shopee_bp)
    return app.test_client()


class TestEstoqueRapidoGet(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_lista_grid_chama_core_com_params(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("shopee.listar_grid_estoque_rapido",
                    return_value={"lojas": [], "produtos": [], "total": 0}) as mock_listar:
            r = self.client.get("/api/shopee/estoque-rapido?busca=SKU1&pagina=2&por_pagina=25", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_listar.assert_called_once_with(busca="SKU1", pagina=2, por_pagina=25)


class TestEstoqueRapidoCelula(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_sem_campos_obrigatorios_retorna_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.put("/api/shopee/estoque-rapido/celula", json={"sku": "SKU1"}, headers=headers)
        self.assertEqual(r.status_code, 400)

    def test_sem_token_retorna_403(self):
        r = self.client.put("/api/shopee/estoque-rapido/celula",
                             json={"sku": "SKU1", "loja_id": 1, "quantidade": 10})
        self.assertEqual(r.status_code, 403)

    def test_com_token_master_chama_core(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("shopee.atualizar_celula_estoque_rapido",
                    return_value={"ok": True, "salvo_local": True, "erro_shopee": None, "linha": {}}) as mock_at:
            r = self.client.put("/api/shopee/estoque-rapido/celula",
                                 json={"sku": "SKU1", "loja_id": 1, "quantidade": 10}, headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["ok"], True)
        mock_at.assert_called_once()
        args, kwargs = mock_at.call_args
        self.assertEqual(args[0], "SKU1")
        self.assertEqual(args[1], 1)
        self.assertEqual(args[2], 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
