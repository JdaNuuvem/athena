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


if __name__ == "__main__":
    unittest.main(verbosity=2)
