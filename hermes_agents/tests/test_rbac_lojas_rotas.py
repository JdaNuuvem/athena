"""Testes de integracao do RBAC por loja (Fase 4, piloto: estoque, PDV,
vendas, listagem de lojas) — confirma que cada rota so' restringe quando
lojas_permitidas() devolve uma lista, e continua vendo tudo quando devolve
None (usuario sem vinculo — comportamento identico ao de antes desta fase)."""
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

    def test_master_com_loja_id_explicito_bypassa_restricao(self):
        """Token master sempre passa, mesmo pedindo uma loja especifica —
        requer_acesso_loja da' bypass total antes de qualquer checagem."""
        with patch("core.pdv.historico_quebras", return_value=[]) as mock_hist, \
             patch("core.rbac_lojas.lojas_permitidas") as mock_permitidas:
            r = self.client.get("/api/pdv/quebras-caixa?loja_id=5", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        mock_permitidas.assert_not_called()
        self.assertEqual(mock_hist.call_args.kwargs.get("loja_ids"), None)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    def test_usuario_comum_loja_id_permitida_passa(self, mock_permitidas, mock_verif):
        """Desde a correcao de seguranca, loja_id explicito de usuario comum
        e' validado contra lojas_permitidas() em vez de ignorado."""
        with patch("core.pdv.historico_quebras", return_value=[]):
            r = self.client.get("/api/pdv/quebras-caixa?loja_id=3", headers={"Authorization": "Bearer qualquer"})
        self.assertEqual(r.status_code, 200)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    def test_usuario_comum_loja_id_fora_da_lista_bloqueia_403(self, mock_permitidas, mock_verif):
        """Buraco de seguranca corrigido: usuario comum nao pode mais ver
        quebras de caixa de uma loja fora da sua lista so' passando o ID."""
        r = self.client.get("/api/pdv/quebras-caixa?loja_id=999", headers={"Authorization": "Bearer qualquer"})
        self.assertEqual(r.status_code, 403)

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
        # ponytail: aqui havia assertEqual contra o dict exato do mock. A rota
        # passou a enriquecer pedidos com item_principal/total_itens
        # (enriquecer_item_principal, commit ee8e600), entao a igualdade
        # byte-a-byte quebrou — sem que o RBAC por loja tivesse regredido.
        # O que este teste precisa provar e' que os dados vieram de
        # listar_pedidos_por_loja; campos derivados a mais sao legitimos.
        dados = r.get_json()["data"]
        self.assertEqual(len(dados), 1)
        self.assertEqual(dados[0]["id"], 1)
        self.assertEqual(dados[0]["loja_id"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
