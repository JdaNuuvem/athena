"""Regression guard: core/estoque.py::movimentacoes() concatenava sku/loja
direto na string SQL (f"m.sku = '{sku}'" / f"m.loja = '{loja}'") — SQL
injection. Agora tem que vir parametrizado ($n) e o valor bruto nunca pode
aparecer literal dentro do texto da query."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


async def _mp(*a, **kw):
    return AsyncMock()


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.estoque as estoque


class SpyDB:
    def __init__(self):
        self.query = None
        self.params = None

    async def fetch(self, query, *params):
        self.query = " ".join(query.split())
        self.params = params
        return []


class TestMovimentacoesSemSQLInjection(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.spy = SpyDB()

        async def _get_db(_spy=self.spy):
            return _spy
        self._p = patch("core.estoque.get_db", side_effect=_get_db)
        self._p.start()
        estoque._ok = True

    def tearDown(self):
        self._p.stop()
        estoque._ok = False

    async def test_filtro_por_loja_maliciosa_nao_entra_na_query(self):
        payload = "Loja X' OR '1'='1"
        estoque.movimentacoes(loja=payload)
        self.assertNotIn(payload, self.spy.query)
        self.assertIn(payload, self.spy.params)

    async def test_filtro_por_sku_malicioso_nao_entra_na_query(self):
        payload = "ABC'; DROP TABLE estoque_movimentacoes; --"
        estoque.movimentacoes(sku=payload)
        self.assertNotIn(payload, self.spy.query)
        self.assertIn(payload, self.spy.params)

    async def test_limite_e_parametrizado(self):
        estoque.movimentacoes(limite=7)
        self.assertNotIn("LIMIT 7", self.spy.query)
        self.assertIn(7, self.spy.params)


if __name__ == "__main__":
    unittest.main(verbosity=2)
