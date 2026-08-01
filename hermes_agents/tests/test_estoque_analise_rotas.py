"""Smoke test das rotas /api/estoque/analise/* — confirma que o blueprint
esta registrado e devolve JSON valido (core ja e' testado em
test_estoque_analise.py; aqui so' testa o fio rota -> core -> jsonify)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

# O pytest trata hermes_agents/ como um Package (tem __init__.py) e importa
# esse __init__.py antes de rodar o primeiro teste do diretorio, o que em
# cascata importa ag_01_cacador -> core.memory, que abre uma conexao real
# via asyncpg.create_pool no import. Mesmo padrao ja usado em
# test_estoque_analise.py: mocka asyncpg antes de qualquer import de rota.
async def _mock_create_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"),
    )), __aexit__=AsyncMock(return_value=None))
    return m

patch("asyncpg.create_pool", side_effect=_mock_create_pool).start()


class TestRotasAnalise(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        from routes.estoque import estoque_bp
        app = Flask(__name__)
        app.register_blueprint(estoque_bp)
        self.client = app.test_client()

    def test_giro_retorna_200_e_chave_data(self):
        with patch("core.estoque_analise.giro", return_value=[{"sku": "A"}]):
            r = self.client.get("/api/estoque/analise/giro")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"data": [{"sku": "A"}]})

    def test_ruptura_retorna_200_e_chave_data(self):
        with patch("core.estoque_analise.ruptura", return_value=[]):
            r = self.client.get("/api/estoque/analise/ruptura?loja=Principal")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"data": []})

    def test_cobertura_retorna_200_e_chave_data(self):
        with patch("core.estoque_analise.cobertura", return_value=[{"sku": "B"}]):
            r = self.client.get("/api/estoque/analise/cobertura")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"data": [{"sku": "B"}]})
