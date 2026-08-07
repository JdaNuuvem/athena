"""Testes de integracao do filtro de loja em routes/vendas.py — dashboard()
e list() nao aceitavam loja_id nenhum, entao a pagina /vendas sempre
mostrava vendas de TODAS as lojas, ignorando o dropdown "Loja em operacao"
do frontend. Mesmo padrao de test_relatorios_rbac_lojas_rotas.py."""
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
from routes.vendas import vendas_bp


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(vendas_bp)
    return app.test_client()


class TestVendasDashboardFiltroLoja(unittest.TestCase):
    def setUp(self):
        self.client = _app()
        self.master = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        self.comum = {"Authorization": "Bearer qualquer"}

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    def test_loja_id_fora_da_lista_bloqueia_403(self, mock_permitidas, mock_verif):
        r = self.client.get("/api/vendas/dashboard?loja_id=999", headers=self.comum)
        self.assertEqual(r.status_code, 403)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    @patch("core.vendas.dashboard", return_value={"total_vendas": 100})
    def test_loja_id_permitida_repassa_pro_core(self, mock_dash, mock_permitidas, mock_verif):
        r = self.client.get("/api/vendas/dashboard?dias=7&loja_id=3", headers=self.comum)
        self.assertEqual(r.status_code, 200)
        mock_dash.assert_called_once_with(7, 3)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": None, "email": "", "role": ""})
    @patch("core.vendas.dashboard", return_value={"total_vendas": 500})
    def test_sem_loja_id_repassa_none(self, mock_dash, mock_verif):
        r = self.client.get("/api/vendas/dashboard", headers=self.master)
        self.assertEqual(r.status_code, 200)
        mock_dash.assert_called_once_with(30, None)


class TestVendasListFiltroLoja(unittest.TestCase):
    def setUp(self):
        self.client = _app()
        self.master = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        self.comum = {"Authorization": "Bearer qualquer"}

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    def test_loja_id_fora_da_lista_bloqueia_403(self, mock_permitidas, mock_verif):
        r = self.client.get("/api/vendas/pedidos?loja_id=999", headers=self.comum)
        self.assertEqual(r.status_code, 403)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    @patch("core.vendas.listar_filtrado", return_value={"data": [{"id": 1, "loja_id": 3}]})
    def test_loja_id_permitida_vai_por_listar_filtrado(self, mock_filtrado, mock_permitidas, mock_verif):
        r = self.client.get("/api/vendas/pedidos?loja_id=3", headers=self.comum)
        self.assertEqual(r.status_code, 200)
        mock_filtrado.assert_called_once_with("pedidos", "", "", 0, "", 3)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": None, "email": "", "role": ""})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=None)
    @patch("core.vendas.listar_pedidos_por_loja")
    @patch("core.vendas.list")
    def test_sem_nenhum_filtro_mantem_comportamento_antigo(self, mock_list, mock_por_loja, mock_permitidas, mock_verif):
        """Regressao: sem loja_id/data/status nenhum, continua indo pro
        caminho antigo (list() geral, sem RBAC pq usuario nao restrito)."""
        mock_list.return_value = [{"id": 1}]
        r = self.client.get("/api/vendas/pedidos", headers=self.master)
        self.assertEqual(r.status_code, 200)
        mock_list.assert_called_once_with("pedidos")
        mock_por_loja.assert_not_called()

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3])
    @patch("core.vendas.listar_pedidos_por_loja", return_value=[{"id": 1, "loja_id": 3}])
    def test_sem_loja_id_mas_restrito_ainda_filtra_pelas_permitidas(self, mock_por_loja, mock_permitidas, mock_verif):
        """Sem loja_id explicito na request, mas usuario restrito — o
        caminho RBAC antigo (listar_pedidos_por_loja) continua valendo,
        nao regride pro comportamento pre-Fase-4."""
        r = self.client.get("/api/vendas/pedidos", headers=self.comum)
        self.assertEqual(r.status_code, 200)
        mock_por_loja.assert_called_once_with([3])


class TestVendasListEnriquecidoComItemPrincipal(unittest.TestCase):
    """/api/vendas/pedidos passa a enriquecer cada pedido com item_principal/
    total_itens — confirma que a funcao e' chamada nos 3 caminhos possiveis
    de listagem de pedidos, nao so' que ela funciona isolada (ja coberto em
    test_vendas.py::TestEnriquecerItemPrincipal). Tabelas itens/pagamentos
    nao devem passar por esse enriquecimento (so' faz sentido pra pedidos)."""

    def setUp(self):
        self.client = _app()
        self.master = {"Authorization": f"Bearer {_TEST_TOKEN}"}

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": None, "email": "", "role": ""})
    @patch("core.vendas.listar_filtrado", return_value={"data": [{"id": 1}]})
    @patch("core.vendas.enriquecer_item_principal")
    def test_via_listar_filtrado_enriquece_pedidos(self, mock_enriq, mock_filtrado, mock_verif):
        mock_enriq.return_value = [{"id": 1, "item_principal": "Camiseta", "total_itens": 1}]
        r = self.client.get("/api/vendas/pedidos?dias=7", headers=self.master)
        self.assertEqual(r.status_code, 200)
        mock_enriq.assert_called_once_with([{"id": 1}])
        self.assertEqual(r.get_json()["data"][0]["item_principal"], "Camiseta")

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": None, "email": "", "role": ""})
    @patch("core.vendas.list", return_value=[{"id": 2}])
    @patch("core.vendas.enriquecer_item_principal")
    def test_via_fallback_sem_filtro_enriquece_pedidos(self, mock_enriq, mock_list, mock_verif):
        mock_enriq.return_value = [{"id": 2, "item_principal": "Caneca", "total_itens": 2}]
        r = self.client.get("/api/vendas/pedidos", headers=self.master)
        self.assertEqual(r.status_code, 200)
        mock_enriq.assert_called_once_with([{"id": 2}])

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": None, "email": "", "role": ""})
    @patch("core.vendas.listar_filtrado", return_value={"data": [{"id": 1}]})
    @patch("core.vendas.enriquecer_item_principal")
    def test_itens_nao_passa_por_enriquecimento(self, mock_enriq, mock_filtrado, mock_verif):
        r = self.client.get("/api/vendas/itens?dias=7", headers=self.master)
        self.assertEqual(r.status_code, 200)
        mock_enriq.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
