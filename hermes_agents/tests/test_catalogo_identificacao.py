"""Fase 1 do PIM Core: novas colunas de identificacao em catalogo_produtos
devem ser criadas via ALTER TABLE ... IF NOT EXISTS, sem tocar nas colunas
existentes (compatibilidade com os 17 consumidores atuais)."""
import sys, os, unittest, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock, MagicMock

# Patch asyncpg BEFORE pytest imports hermes_agents (which tries to connect to DB)
async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock(
            fetch=AsyncMock(return_value=[]),
            fetchrow=AsyncMock(return_value=None),
            fetchval=AsyncMock(return_value=1),
            execute=AsyncMock(return_value="OK")
        )),
        __aexit__=AsyncMock(return_value=None)
    )
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mock_pool)
patcher.start()
import core.catalogo as catalogo  # import AFTER patch is active

NOVAS_COLUNAS = [
    "classificacao", "nome_reduzido", "nome_impressao", "codigo_interno",
    "codigo_erp", "ex_tipi", "modelo", "linha", "colecao",
]


class TestColunasIdentificacao(unittest.TestCase):
    def test_ensure_tables_cria_novas_colunas(self):
        fake_db = MagicMock()
        fake_db.execute = AsyncMock(return_value="OK")
        fake_db.fetchval = AsyncMock(return_value=1)  # >0 => nao roda migracao de dedup
        fake_db.fetch = AsyncMock(return_value=[])
        fake_db.fetchrow = AsyncMock(return_value=None)

        with patch("core.get_db", new=AsyncMock(return_value=fake_db)):
            importlib.reload(catalogo)

        sql_executado = " ".join(str(c.args[0]) for c in fake_db.execute.call_args_list if c.args)
        for coluna in NOVAS_COLUNAS:
            self.assertIn(f"ADD COLUMN IF NOT EXISTS {coluna}", sql_executado,
                          f"coluna {coluna} nao foi criada")
        # nenhuma coluna existente pode ser removida ou renomeada
        self.assertNotIn("DROP COLUMN", sql_executado)
        self.assertNotIn("RENAME COLUMN", sql_executado)


if __name__ == "__main__":
    unittest.main(verbosity=2)
