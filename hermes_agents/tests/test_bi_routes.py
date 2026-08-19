"""Testes de integracao — rotas /api/bi/* exigem bi.ver (o modulo BI inteiro
antes nao existia no backend: as 5 telas do frontend sempre caiam em dado
mockado, silenciosamente, porque /api/bi/* devolvia 404)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

from flask import Flask
from routes.bi import bi_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(bi_bp)
    return app.test_client()


class TestBIExigePermissao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_dashboard_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.bi.dashboard") as mock_dashboard:
            r = self.client.get("/api/bi/dashboard", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_dashboard.assert_not_called()

    def test_dashboard_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(7, "financeiro@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["bi.ver"]), \
             patch("core.bi.dashboard", return_value={"kpis": []}) as mock_dashboard:
            r = self.client.get("/api/bi/dashboard", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_dashboard.assert_called_once()

    def test_todas_as_rotas_exigem_bi_ver(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        rotas = [
            ("GET", "/api/bi/dashboard"), ("GET", "/api/bi/vendas/diarias"),
            ("GET", "/api/bi/vendas/categorias"), ("GET", "/api/bi/indicadores"),
            ("GET", "/api/bi/forecast"), ("GET", "/api/bi/ml/anomalias"),
            ("GET", "/api/bi/ml/segmentos"), ("GET", "/api/bi/ml/recomendacoes"),
            ("GET", "/api/bi/lojas"),
        ]
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]):
            for metodo, rota in rotas:
                r = self.client.open(rota, method=metodo, headers=headers)
                self.assertEqual(r.status_code, 403, f"{rota} deveria exigir bi.ver")


class TestBiLojasRestricaoPorLoja(unittest.TestCase):
    """Achado real (auditoria do modulo BI): /api/bi/lojas chamava
    core.relatorios.dre_por_loja(dias) sem nenhum filtro por loja permitida —
    so' checava a permissao generica bi.ver. Um usuario restrito a lojas
    especificas via usuario_lojas via receita/lucro/margem de TODAS as
    lojas ativas do sistema em BI -&gt; Lojas, vazando dado financeiro de
    lojas que ele nao deveria ver. Mesma classe de bug ja corrigida antes
    em routes/relatorios.py::rel_dre_por_loja (ver
    test_relatorios_rbac_lojas_rotas.py::TestDreLojaRotaComRestricaoDeLoja)
    — essa rota irma usava a MESMA funcao core mas nunca recebeu o fix."""

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def _headers_com_permissao(self):
        token = rbac.gerar_token_sessao(7, "financeiro@x.com", "Financeiro")
        return {"Authorization": f"Bearer {token}"}

    @patch("core.rbac.get_permissoes_por_usuario", return_value=["bi.ver"])
    @patch("core.rbac_lojas.lojas_permitidas", return_value=[3])
    @patch("core.relatorios.dre_por_loja", return_value=[
        {"loja_id": 3, "loja_nome": "Loja A", "lucro": 100},
        {"loja_id": 4, "loja_nome": "Loja B", "lucro": 200},
    ])
    def test_usuario_restrito_ve_so_as_lojas_permitidas(self, mock_dre, mock_permitidas, mock_perm):
        r = self.client.get("/api/bi/lojas", headers=self._headers_com_permissao())
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual([item["loja_id"] for item in data], [3])

    @patch("core.rbac.get_permissoes_por_usuario", return_value=["bi.ver"])
    @patch("core.rbac_lojas.lojas_permitidas", return_value=None)
    @patch("core.relatorios.dre_por_loja", return_value=[
        {"loja_id": 3, "loja_nome": "Loja A", "lucro": 100},
        {"loja_id": 4, "loja_nome": "Loja B", "lucro": 200},
    ])
    def test_usuario_sem_restricao_ve_todas(self, mock_dre, mock_permitidas, mock_perm):
        r = self.client.get("/api/bi/lojas", headers=self._headers_com_permissao())
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(len(data), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
