"""Testes de core/rbac.py::requer_acesso_loja — decorator que bloqueia com
403 quando a request pede uma loja fora das permitidas pro usuario logado."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

os.environ.setdefault("ATHENA_TOKEN", "test-master-token-32-bytes-long!!")

async def _mp(*a, **kw):
    return AsyncMock()

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

from flask import Flask, jsonify
import core.rbac as rbac

app = Flask(__name__)
app.config["TESTING"] = True


@app.route("/testar/<int:loja_id>")
@rbac.requer_acesso_loja
def _rota_com_loja_no_path(loja_id):
    return jsonify({"ok": True, "loja_id": loja_id})


@app.route("/testar-query")
@rbac.requer_acesso_loja
def _rota_com_loja_na_query():
    return jsonify({"ok": True})


@app.route("/testar-sem-loja")
@rbac.requer_acesso_loja
def _rota_sem_loja():
    return jsonify({"ok": True})


class TestRequerAcessoLoja(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_token_master_sempre_passa(self):
        headers = {"Authorization": f"Bearer {os.environ['ATHENA_TOKEN']}"}
        with patch("core.rbac_lojas.lojas_permitidas") as mock_permitidas:
            r = self.client.get("/testar/5", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_permitidas.assert_not_called()

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    def test_usuario_comum_loja_permitida_passa(self, mock_permitidas, mock_verif):
        r = self.client.get("/testar/3", headers={"Authorization": "Bearer qualquer"})
        self.assertEqual(r.status_code, 200)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    def test_usuario_comum_loja_fora_da_lista_bloqueia_403(self, mock_permitidas, mock_verif):
        r = self.client.get("/testar/999", headers={"Authorization": "Bearer qualquer"})
        self.assertEqual(r.status_code, 403)
        self.assertIn("error", r.get_json())

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[])
    def test_usuario_sem_nenhuma_loja_vinculada_bloqueia_qualquer_uma(self, mock_permitidas, mock_verif):
        r = self.client.get("/testar/1", headers={"Authorization": "Bearer qualquer"})
        self.assertEqual(r.status_code, 403)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Admin"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=None)
    def test_usuario_com_ver_todas_passa_em_qualquer_loja(self, mock_permitidas, mock_verif):
        r = self.client.get("/testar/999", headers={"Authorization": "Bearer qualquer"})
        self.assertEqual(r.status_code, 200)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3])
    def test_loja_id_via_query_string(self, mock_permitidas, mock_verif):
        r = self.client.get("/testar-query?loja_id=999", headers={"Authorization": "Bearer qualquer"})
        self.assertEqual(r.status_code, 403)
        r_ok = self.client.get("/testar-query?loja_id=3", headers={"Authorization": "Bearer qualquer"})
        self.assertEqual(r_ok.status_code, 200)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    def test_rota_sem_loja_identificavel_deixa_passar(self, mock_verif):
        with patch("core.rbac_lojas.lojas_permitidas") as mock_permitidas:
            r = self.client.get("/testar-sem-loja", headers={"Authorization": "Bearer qualquer"})
        self.assertEqual(r.status_code, 200)
        mock_permitidas.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
