"""Testes de integracao do RBAC por loja (Fase 4, piloto: estoque, PDV,
vendas, listagem de lojas) — confirma que cada rota so' restringe quando
lojas_permitidas() devolve uma lista, e continua vendo tudo quando devolve
None (usuario sem vinculo — comportamento identico ao de antes desta fase)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"


async def _mp(*a, **kw):
    return AsyncMock()


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

from flask import Flask
from routes.lojas_manage import lojas_bp
from routes.pdv import pdv_bp
from routes.vendas import vendas_bp


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(lojas_bp)
    app.register_blueprint(pdv_bp)
    app.register_blueprint(vendas_bp)
    return app.test_client()


class TestListarLojasComRestricao(unittest.TestCase):
    def setUp(self):
        self.client = _app()
        self.headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}

    def test_sem_restricao_ve_todas_as_lojas(self):
        lojas = [{"id": 1, "nome": "Loja A"}, {"id": 2, "nome": "Loja B"}]
        with patch("core.lojas.listar", return_value=lojas), \
             patch("core.rbac_lojas.lojas_permitidas", return_value=None):
            r = self.client.get("/api/lojas/manage", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.get_json()["lojas"]), 2)

    def test_com_restricao_ve_so_as_permitidas(self):
        lojas = [{"id": 1, "nome": "Loja A"}, {"id": 2, "nome": "Loja B"}]
        with patch("core.lojas.listar", return_value=lojas), \
             patch("core.rbac_lojas.lojas_permitidas", return_value=[1]):
            r = self.client.get("/api/lojas/manage", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        nomes = [l["nome"] for l in r.get_json()["lojas"]]
        self.assertEqual(nomes, ["Loja A"])


class TestPdvQuebrasCaixaComRestricao(unittest.TestCase):
    def setUp(self):
        self.client = _app()
        self.headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}

    def test_loja_id_explicito_ignora_restricao(self):
        """Pedido explicito de uma loja especifica sempre e' honrado — modo
        suave nao bloqueia, so' restringe o "todas"."""
        with patch("core.pdv.historico_quebras", return_value=[]) as mock_hist, \
             patch("core.rbac_lojas.lojas_permitidas") as mock_permitidas:
            r = self.client.get("/api/pdv/quebras-caixa?loja_id=5", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        mock_permitidas.assert_not_called()
        self.assertEqual(mock_hist.call_args.kwargs.get("loja_ids"), None)

    def test_sem_loja_id_aplica_restricao(self):
        with patch("core.pdv.historico_quebras", return_value=[]) as mock_hist, \
             patch("core.rbac_lojas.lojas_permitidas", return_value=[3]):
            r = self.client.get("/api/pdv/quebras-caixa", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mock_hist.call_args.kwargs.get("loja_ids"), [3])


class TestVendasListagemComRestricao(unittest.TestCase):
    def setUp(self):
        self.client = _app()
        self.headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}

    def test_sem_restricao_usa_listagem_generica(self):
        with patch("core.vendas.list", return_value=[{"id": 1}]) as mock_list, \
             patch("core.rbac_lojas.lojas_permitidas", return_value=None):
            r = self.client.get("/api/vendas/pedidos", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        mock_list.assert_called_once()

    def test_com_restricao_usa_listagem_por_loja(self):
        with patch("core.vendas.listar_pedidos_por_loja", return_value=[{"id": 1, "loja_id": 3}]) as mock_lp, \
             patch("core.rbac_lojas.lojas_permitidas", return_value=[3]):
            r = self.client.get("/api/vendas/pedidos", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        mock_lp.assert_called_once_with([3])
        self.assertEqual(r.get_json()["data"], [{"id": 1, "loja_id": 3}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
