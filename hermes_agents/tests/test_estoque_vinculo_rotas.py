"""Smoke test — rotas sync (psycopg2) resolvem loja por vinculo antes de filtrar."""
import sys, os, unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEstoquePorLojaResolveVinculo(unittest.TestCase):
    def test_filtro_de_loja_usa_nome_resolvido(self):
        from flask import Flask
        from routes.estoque import estoque_bp
        app = Flask(__name__)
        app.register_blueprint(estoque_bp)
        client = app.test_client()

        conn = MagicMock()
        cur = conn.cursor.return_value
        cur.fetchone.side_effect = [(0,)]
        cur.fetchall.return_value = []
        cur.description = []

        with patch("routes.estoque._db_sync", return_value=conn), \
             patch("core.lojas.loja_efetiva_sync", return_value="Loja Fisica Central") as mock_resolver, \
             patch("core.rbac.usuario_atual_da_request", return_value={"user_id": 1}), \
             patch("core.rbac_lojas.lojas_permitidas", return_value=None):
            r = client.get("/api/estoque/lojas?loja=Loja Virtual A")
        self.assertEqual(r.status_code, 200)
        mock_resolver.assert_called_once()
        executado = cur.execute.call_args_list[0][0][0]
        self.assertIn("Loja Fisica Central", cur.execute.call_args_list[0][0][1])


if __name__ == "__main__":
    unittest.main()
