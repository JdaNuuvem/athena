"""Testes de integracao do RBAC por loja aplicado em routes/shopee.py — nenhum
outro teste registra shopee_bp num Flask app e bate via HTTP, entao este
arquivo e' a unica cobertura real do decorator requer_acesso_loja nessas rotas
(inclusive o caso de loja_id vindo do PATH da URL, nao so' query/body)."""
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
from routes.shopee import shopee_bp


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(shopee_bp)
    return app.test_client()


class TestShopeeRotasComRestricaoDeLoja(unittest.TestCase):
    def setUp(self):
        self.client = _app()
        self.master = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        self.comum = {"Authorization": "Bearer qualquer"}

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    def test_query_loja_id_fora_da_lista_bloqueia_403(self, mock_permitidas, mock_verif):
        r = self.client.get("/api/shopee/margem?sku=X&preco=10&loja_id=999", headers=self.comum)
        self.assertEqual(r.status_code, 403)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    @patch("shopee.calcular_margem_produto", return_value={"ok": True})
    def test_query_loja_id_permitida_passa(self, mock_margem, mock_permitidas, mock_verif):
        r = self.client.get("/api/shopee/margem?sku=X&preco=10&loja_id=3", headers=self.comum)
        self.assertEqual(r.status_code, 200)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    def test_body_loja_id_fora_da_lista_bloqueia_403(self, mock_permitidas, mock_verif):
        r = self.client.post("/api/shopee/produtos/555/preco", json={"loja_id": 999, "price": 10}, headers=self.comum)
        self.assertEqual(r.status_code, 403)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    @patch("shopee.update_price", return_value={"ok": True})
    def test_body_loja_id_permitida_passa_e_preserva_closure_do_item_id(self, mock_update, mock_permitidas, mock_verif):
        r = self.client.post("/api/shopee/produtos/555/preco", json={"loja_id": 3, "price": 10}, headers=self.comum)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mock_update.call_args.args[0], 555)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    def test_path_loja_id_fora_da_lista_bloqueia_403(self, mock_permitidas, mock_verif):
        """Regressao: loja_id vindo do PATH (nao query/body) precisa ser
        repassado explicitamente pro _handler interno, senao o decorator
        nunca enxerga o valor e deixa passar sempre."""
        r = self.client.post("/api/shopee/lojas/999/conectar", json={}, headers=self.comum)
        self.assertEqual(r.status_code, 403)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    @patch("shopee.get_auth_url", return_value="https://exemplo/auth")
    def test_path_loja_id_permitida_passa(self, mock_auth, mock_permitidas, mock_verif):
        r = self.client.post("/api/shopee/lojas/3/conectar", json={}, headers=self.comum)
        self.assertEqual(r.status_code, 200)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    def test_rota_empilhada_com_requer_permissao_bloqueia_por_loja_antes(self, mock_permitidas, mock_verif):
        """requer_acesso_loja fica por fora de requer_permissao — bloqueia
        403 de loja mesmo sem chegar a checar a permissao de acao."""
        r = self.client.post(
            "/api/shopee/produtos/555/variacoes",
            json={"loja_id": 999, "tier_variation": [1], "model_list": [1]},
            headers=self.comum,
        )
        self.assertEqual(r.status_code, 403)

    def test_token_master_bypassa_qualquer_loja(self):
        with patch("shopee.calcular_margem_produto", return_value={"ok": True}):
            r = self.client.get("/api/shopee/margem?sku=X&preco=10&loja_id=999", headers=self.master)
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
