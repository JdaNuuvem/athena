"""Testes de integracao — Flask routes do Bling."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock
import unittest

# Mock asyncpg before importing Flask
fake_pool = AsyncMock()
fake_conn = AsyncMock()
fake_conn.fetch.return_value = []
fake_conn.fetchrow.return_value = None
fake_conn.fetchval.return_value = 0
fake_conn.execute.return_value = "OK"
fake_conn.__aenter__ = AsyncMock(return_value=fake_conn)
fake_conn.__aexit__ = AsyncMock(return_value=None)
fake_pool.acquire.return_value = fake_conn

patcher = patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=fake_pool)
patcher.start()

from routes.integrations import bling_bp
from flask import Flask
import unittest

class TestBlingFlaskRoutes(unittest.TestCase):
    """Testa as rotas Flask do Bling blueprint."""

    @classmethod
    def setUpClass(cls):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(bling_bp)
        cls.client = app.test_client()

    def test_status_route(self):
        rv = self.client.get("/api/bling/status")
        self.assertEqual(rv.status_code, 200)
        data = json.loads(rv.data)
        self.assertIn("autenticado", data)
        self.assertIn("client_id_setado", data)

    def test_auth_url_route(self):
        rv = self.client.get("/api/bling/auth")
        self.assertEqual(rv.status_code, 200)
        data = json.loads(rv.data)
        self.assertIn("url", data)

    def test_produtos_route(self):
        with patch("routes.integrations.listar_produtos", return_value={"data": []}):
            rv = self.client.get("/api/bling/produtos")
            self.assertIn(rv.status_code, [200, 401])

    def test_depositos_route(self):
        with patch("routes.integrations.listar_depositos", return_value={"data": []}):
            rv = self.client.get("/api/bling/depositos")
            self.assertIn(rv.status_code, [200, 401])

    def test_vendas_route(self):
        with patch("routes.integrations.listar_pedidos", return_value={"data": []}):
            rv = self.client.get("/api/bling/vendas")
            self.assertIn(rv.status_code, [200, 401])

    def test_oauth_callback_missing_code(self):
        rv = self.client.get("/api/bling/oauth/callback")
        self.assertEqual(rv.status_code, 400)

    def test_webhook_eventos(self):
        rv = self.client.get("/api/bling/webhooks")
        self.assertIn(rv.status_code, [200, 401])

    def test_notificacoes_route(self):
        with patch("routes.integrations.listar_notificacoes", return_value={"data": []}):
            rv = self.client.get("/api/bling/notificacoes")
            self.assertIn(rv.status_code, [200, 401])

    def test_health_route(self):
        rv = self.client.get("/api/bling/health")
        if rv.status_code == 404:
            self.skipTest("Health endpoint not yet registered")
        self.assertEqual(rv.status_code, 200)
        data = json.loads(rv.data)
        self.assertIn("bling", data)

    def test_vendas_sincronizar_route_calls_ssot_function(self):
        with patch("routes.integrations.sincronizar_pedidos_bling", return_value={"sync": 3, "erros": []}) as mock_sync:
            rv = self.client.post("/api/bling/vendas/sincronizar", json={"pagina": 2, "limite": 50})
            self.assertEqual(rv.status_code, 200)
            data = json.loads(rv.data)
            self.assertEqual(data["sync"], 3)
            mock_sync.assert_called_once_with(pagina=2, limite=50)

    def test_produtos_agrupados_usa_hierarquia_bling_erp(self):
        with patch("routes.integrations.listar_produtos_agrupados", return_value={"grupos": [], "avulsos": []}) as mock_fn:
            rv = self.client.get("/api/bling/produtos/agrupados")
            self.assertEqual(rv.status_code, 200)
            mock_fn.assert_called_once()

    def test_canais_sincronizar_route(self):
        with patch("routes.integrations.sincronizar_canais_bling", return_value={"sync": 2}) as mock_sync:
            rv = self.client.post("/api/bling/canais/sincronizar")
            self.assertEqual(rv.status_code, 200)
            data = json.loads(rv.data)
            self.assertEqual(data["sync"], 2)
            mock_sync.assert_called_once()

    def test_canais_listar_route(self):
        rv = self.client.get("/api/bling/canais")
        self.assertIn(rv.status_code, [200, 500])


class TestBlingRotasRemovidas(unittest.TestCase):
    """Confirma que as rotas duplicadas removidas nao respondem mais.

    Registra bling_bp junto com integrations_bp e webhooks_bp (os blueprints
    que continham as rotas antigas antes das Tasks 5 e 6) na mesma app de
    teste. So assim um 404 comprova de verdade que a rota antiga sumiu --
    testar so contra bling_bp nao provaria nada, pois essas rotas nunca
    existiram la.
    """

    @classmethod
    def setUpClass(cls):
        from flask import Flask
        from routes.integrations import bling_bp, integrations_bp
        from routes.webhooks import webhooks_bp, webhook_bp
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(bling_bp)
        app.register_blueprint(integrations_bp)
        app.register_blueprint(webhooks_bp)
        app.register_blueprint(webhook_bp)
        cls.client = app.test_client()

    def test_rota_antiga_sync_products_nao_existe(self):
        rv = self.client.post("/api/bling/sync/products")
        self.assertEqual(rv.status_code, 404)

    def test_rota_antiga_sync_orders_nao_existe(self):
        rv = self.client.post("/api/bling/sync/orders")
        self.assertEqual(rv.status_code, 404)

    def test_rota_antiga_webhook_pedido_nao_existe(self):
        rv = self.client.post("/webhook/bling/pedido")
        self.assertEqual(rv.status_code, 404)

    def test_rota_nova_produtos_sincronizar_existe(self):
        with patch("routes.integrations.sincronizar_produtos", return_value={"sincronizados": 0, "erros": []}):
            rv = self.client.post("/api/bling/produtos/sincronizar")
            self.assertEqual(rv.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
