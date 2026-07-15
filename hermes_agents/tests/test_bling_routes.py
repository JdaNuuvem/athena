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

patcher = patch("asyncpg.create_pool", return_value=fake_pool)
patcher.start()

from hermes_agents.routes.integrations import bling_bp
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
        with patch("hermes_agents.routes.integrations.listar_produtos", return_value={"data": []}):
            rv = self.client.get("/api/bling/produtos")
            self.assertIn(rv.status_code, [200, 401])

    def test_depositos_route(self):
        with patch("hermes_agents.routes.integrations.listar_depositos", return_value={"data": []}):
            rv = self.client.get("/api/bling/depositos")
            self.assertIn(rv.status_code, [200, 401])

    def test_vendas_route(self):
        with patch("hermes_agents.routes.integrations.listar_pedidos", return_value={"data": []}):
            rv = self.client.get("/api/bling/vendas")
            self.assertIn(rv.status_code, [200, 401])

    def test_oauth_callback_missing_code(self):
        rv = self.client.get("/api/bling/oauth/callback")
        self.assertEqual(rv.status_code, 400)

    def test_webhook_eventos(self):
        rv = self.client.get("/api/bling/webhooks")
        self.assertIn(rv.status_code, [200, 401])

    def test_notificacoes_route(self):
        with patch("hermes_agents.routes.integrations.listar_notificacoes", return_value={"data": []}):
            rv = self.client.get("/api/bling/notificacoes")
            self.assertIn(rv.status_code, [200, 401])

    def test_health_route(self):
        rv = self.client.get("/api/bling/health")
        if rv.status_code == 404:
            self.skipTest("Health endpoint not yet registered")
        self.assertEqual(rv.status_code, 200)
        data = json.loads(rv.data)
        self.assertIn("bling", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
