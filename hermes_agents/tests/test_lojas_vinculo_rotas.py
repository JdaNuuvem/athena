"""Smoke test da rota de vinculo de estoque fisica x virtual."""
import sys, os, unittest
from unittest.mock import patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRotaVinculoEstoque(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        from routes.lojas_manage import lojas_bp
        app = Flask(__name__)
        app.register_blueprint(lojas_bp)
        self.client = app.test_client()

    def test_put_com_loja_fisica_id_vincula(self):
        with patch("core.lojas.vincular_estoque", return_value={"ok": True, "loja_virtual": "A", "loja_fisica": "B"}), \
             patch("routes.lojas_manage.requer_permissao", lambda p: (lambda f: f)):
            r = self.client.put("/api/lojas/manage/1/vinculo-estoque", json={"loja_fisica_id": 2})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])

    def test_put_sem_loja_fisica_id_desvincula(self):
        with patch("core.lojas.desvincular_estoque", return_value={"ok": True, "loja_virtual": "A", "loja_fisica": "B", "skus_copiados": 3}), \
             patch("routes.lojas_manage.requer_permissao", lambda p: (lambda f: f)):
            r = self.client.put("/api/lojas/manage/1/vinculo-estoque", json={"loja_fisica_id": None})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
