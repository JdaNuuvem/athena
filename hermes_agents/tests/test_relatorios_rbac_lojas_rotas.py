"""Testes de integracao do RBAC por loja em routes/relatorios.py::/dre-por-loja.

Contexto (achado de auditoria): essa era a unica rota loja-relevante do
arquivo sem @requer_acesso_loja, e dre_por_loja() nunca aceitava loja_id —
sempre devolvia TODAS as lojas ativas, sem respeitar usuario_lojas. Um
usuario restrito a lojas especificas conseguia ver receita/lucro/margem de
lojas que nao devia. Mesmo padrao de test_shopee_rbac_lojas_rotas.py."""
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
from routes.relatorios import relatorios_bp

_DRE_FAKE = [
    {"loja_id": 3, "loja_nome": "Loja Permitida", "lucro": 100.0},
    {"loja_id": 999, "loja_nome": "Loja Fora da Lista", "lucro": 200.0},
]


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(relatorios_bp)
    return app.test_client()


class TestDreLojaRotaComRestricaoDeLoja(unittest.TestCase):
    def setUp(self):
        self.client = _app()
        self.master = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        self.comum = {"Authorization": "Bearer qualquer"}

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    def test_loja_id_fora_da_lista_bloqueia_403(self, mock_permitidas, mock_verif):
        r = self.client.get("/api/relatorios/dre-por-loja?loja_id=999", headers=self.comum)
        self.assertEqual(r.status_code, 403)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    @patch("core.relatorios.dre_por_loja", return_value=_DRE_FAKE)
    def test_loja_id_permitida_filtra_so_essa_loja(self, mock_dre, mock_permitidas, mock_verif):
        r = self.client.get("/api/relatorios/dre-por-loja?loja_id=3", headers=self.comum)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()["data"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["loja_id"], 3)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3])
    @patch("core.relatorios.dre_por_loja", return_value=_DRE_FAKE)
    def test_sem_loja_id_filtra_pelas_permitidas_do_usuario(self, mock_dre, mock_permitidas, mock_verif):
        """Sem loja_id na request, requer_acesso_loja nao filtra nada (rota
        nao-escopada, por design) — o handler precisa filtrar por conta
        propria, senao o usuario ve todas as lojas mesmo estando restrito."""
        r = self.client.get("/api/relatorios/dre-por-loja", headers=self.comum)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()["data"]
        self.assertEqual([item["loja_id"] for item in data], [3])

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": None, "email": "", "role": ""})
    @patch("core.relatorios.dre_por_loja", return_value=_DRE_FAKE)
    def test_token_master_ve_todas_as_lojas(self, mock_dre, mock_verif):
        r = self.client.get("/api/relatorios/dre-por-loja", headers=self.master)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()["data"]
        self.assertEqual(len(data), 2)

    @patch("core.rbac.verificar_token_sessao", return_value={"user_id": 7, "email": "a@b.com", "role": "Vendedor"})
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3, 4])
    @patch("core.relatorios.dre_por_loja", return_value=_DRE_FAKE)
    def test_dias_negativo_ou_absurdo_e_limitado(self, mock_dre, mock_permitidas, mock_verif):
        r = self.client.get("/api/relatorios/dre-por-loja?dias=-5&loja_id=3", headers=self.comum)
        self.assertEqual(r.status_code, 200)
        mock_dre.assert_called_once_with(1)  # clamp pro minimo de 1 dia

        mock_dre.reset_mock()
        r = self.client.get("/api/relatorios/dre-por-loja?dias=99999&loja_id=3", headers=self.comum)
        self.assertEqual(r.status_code, 200)
        mock_dre.assert_called_once_with(365)  # clamp pro maximo de 365 dias


if __name__ == "__main__":
    unittest.main(verbosity=2)
