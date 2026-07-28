"""Testes de core/lojas_virtual.py — config de loja virtual (dominio/SEO/
pixels) e delivery (raio/taxa/retirada)."""
import sys, os, re, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


async def _mp(*a, **kw):
    return AsyncMock()


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.lojas as lojas
import core.lojas_virtual as virtual


class FakeDB:
    def __init__(self):
        self.rows = {1: {"id": 1, "nome": "Loja Teste"}}

    async def execute(self, query, *params):
        q = " ".join(query.split())
        if "CREATE TABLE" in q or "ALTER TABLE" in q or "CREATE INDEX" in q:
            return "OK"
        m = re.match(r"UPDATE lojas SET (.+) WHERE id = \$(\d+)$", q)
        if m:
            id_loja = params[int(m.group(2)) - 1]
            if id_loja not in self.rows:
                return "UPDATE 0"
            for atrib in m.group(1).split(","):
                col, ph = [p.strip() for p in atrib.split("=")]
                self.rows[id_loja][col] = params[int(ph.lstrip("$")) - 1]
            return "UPDATE 1"
        return "OK"

    async def fetchval(self, query, *params):
        return 0

    async def fetchrow(self, query, *params):
        return None

    async def fetch(self, query, *params):
        return []


class TestLojasVirtual(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        self._p = patch("core.lojas.get_db", side_effect=_get_db)
        self._p.start()
        lojas._table_ok = True

    def tearDown(self):
        self._p.stop()
        lojas._table_ok = False

    async def test_atualizar_virtual_dominio_e_pixels(self):
        ok = virtual.atualizar_virtual(1, {
            "dominio": "charmenilopolis.com.br", "tema": "clean",
            "pixel_meta": "1234567890", "google_analytics_id": "G-ABC123",
        })
        self.assertTrue(ok)
        row = self.fake.rows[1]
        self.assertEqual(row["dominio"], "charmenilopolis.com.br")
        self.assertEqual(row["pixel_meta"], "1234567890")

    async def test_atualizar_virtual_ignora_campo_delivery(self):
        ok = virtual.atualizar_virtual(1, {"raio_entrega_km": 10})
        self.assertTrue(ok)
        self.assertNotIn("raio_entrega_km", self.fake.rows[1])

    async def test_atualizar_delivery_raio_taxa_e_retirada(self):
        ok = virtual.atualizar_delivery(1, {
            "raio_entrega_km": 8.5, "taxa_entrega": 12.0,
            "tempo_medio_entrega_min": 45, "retirada_loja": True,
        })
        self.assertTrue(ok)
        row = self.fake.rows[1]
        self.assertEqual(row["raio_entrega_km"], 8.5)
        self.assertTrue(row["retirada_loja"])

    async def test_atualizar_delivery_loja_inexistente_retorna_false(self):
        ok = virtual.atualizar_delivery(9999, {"raio_entrega_km": 5})
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
