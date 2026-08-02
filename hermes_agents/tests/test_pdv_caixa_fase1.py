"""Fase 1 — contagem de denominacao e conferencia por maquineta no fechamento de caixa."""
import sys, os, unittest, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


class _SpyDB:
    def __init__(self):
        self.queries = []

    async def execute(self, query, *params):
        self.queries.append(" ".join(query.split()))
        return "OK"

    async def fetchval(self, query, *params):
        self.queries.append(" ".join(query.split()))
        return 0

    async def fetchrow(self, query, *params):
        self.queries.append(" ".join(query.split()))
        return None

    async def fetch(self, query, *params):
        self.queries.append(" ".join(query.split()))
        return []


class TestSchemaFase1(unittest.TestCase):
    def test_ensure_tables_cria_contagem_conferencia_e_coluna_maquineta(self):
        import core.pdv as pdv
        spy = _SpyDB()
        # Use AsyncMock to return the spy directly
        async_mock_get_db = AsyncMock(return_value=spy)
        with patch("core.pdv.get_db", async_mock_get_db):
            pdv._ensure_tables()
        joined = " ".join(spy.queries)
        self.assertIn("CREATE TABLE IF NOT EXISTS pdv_caixa_contagem", joined)
        self.assertIn("CREATE TABLE IF NOT EXISTS pdv_caixa_conferencia", joined)
        self.assertIn("ALTER TABLE pdv_pagamentos ADD COLUMN IF NOT EXISTS maquineta", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
