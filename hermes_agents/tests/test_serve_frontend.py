"""
Testes de athena_bridge.py::serve_frontend() — fallback do export estatico
do Next.js para rotas dinamicas (/produtos/<sku>, /lojas/<id>, /agents/<id>).

Contexto: o build (`output: 'export'`) so' gera HTML para o valor
"placeholder" de generateStaticParams — o SKU/ID real e' lido em runtime via
useParams(). Isso funciona quando a navegacao e' client-side (dentro do SPA
ja carregado), mas um F5 ou link direto bate no Flask, que nao achava nem
"<path>.html" nem um diretorio "<path>/index.html" e caia no fallback final
servindo a raiz do app (dashboard/login) em vez da pagina de produto/loja —
o usuario via a tela errada sem nenhum erro visivel.
"""
import sys, os, unittest, tempfile, shutil
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

# Mock DB pool global (mesmo padrao de test_shopee_flow.py) para os imports no
# topo do modulo nao tentarem uma conexao real ao Postgres de producao.
_fake_conn = AsyncMock()
_fake_conn.fetch.return_value = []
_fake_conn.fetchrow.return_value = None
_fake_conn.fetchval.return_value = 0
_fake_conn.execute.return_value = "OK"

async def _mock_create_pool(*a, **kw):
    pool = AsyncMock()
    pool.acquire.return_value = _fake_conn
    return pool

_pool_patcher = patch("asyncpg.create_pool", side_effect=_mock_create_pool)
_pool_patcher.start()

_db_table_patcher = patch("core.config._ensure_db_table", return_value=False)
_db_table_patcher.start()

os.environ.setdefault("ATHENA_TOKEN", "test-token-123")
import athena_bridge
from athena_bridge import app


class TestServeFrontendFallbackRotaDinamica(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()
        modulo_dir = Path(self.tmp_root) / "hermes_agents"
        modulo_dir.mkdir()
        dashboard = modulo_dir / "dashboard"
        dashboard.mkdir()
        (dashboard / "index.html").write_text("RAIZ_DASHBOARD_OU_LOGIN")
        (dashboard / "produtos").mkdir()
        (dashboard / "produtos" / "placeholder.html").write_text("PAGINA_PRODUTO_SKU")
        (dashboard / "produtos" / "novo.html").write_text("PAGINA_PRODUTO_NOVO")
        (dashboard / "lojas").mkdir()
        (dashboard / "lojas" / "placeholder.html").write_text("PAGINA_LOJA_ID")
        self.fake_module_file = str(modulo_dir / "athena_bridge.py")

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_sku_real_serve_pagina_de_produto_nao_a_raiz(self):
        with patch.object(athena_bridge, "__file__", new=self.fake_module_file):
            resp = self.client.get("/produtos/BEM-CALC-AZUL-1UN")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"PAGINA_PRODUTO_SKU", resp.data)
        self.assertNotIn(b"RAIZ_DASHBOARD_OU_LOGIN", resp.data)

    def test_loja_id_real_serve_pagina_de_loja_nao_a_raiz(self):
        with patch.object(athena_bridge, "__file__", new=self.fake_module_file):
            resp = self.client.get("/lojas/42")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"PAGINA_LOJA_ID", resp.data)

    def test_rota_estatica_conhecida_continua_normal(self):
        """/produtos/novo ja tem HTML proprio — nao deve cair no placeholder."""
        with patch.object(athena_bridge, "__file__", new=self.fake_module_file):
            resp = self.client.get("/produtos/novo")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"PAGINA_PRODUTO_NOVO", resp.data)

    def test_path_sem_placeholder_correspondente_cai_na_raiz(self):
        """Segmento sem nenhuma rota dinamica conhecida mantem o comportamento antigo."""
        with patch.object(athena_bridge, "__file__", new=self.fake_module_file):
            resp = self.client.get("/rota-que-nao-existe-em-lugar-nenhum")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"RAIZ_DASHBOARD_OU_LOGIN", resp.data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
