"""Fase 1 do PIM Core: novas colunas de identificacao em catalogo_produtos
devem ser criadas via ALTER TABLE ... IF NOT EXISTS, sem tocar nas colunas
existentes (compatibilidade com os 17 consumidores atuais)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock, MagicMock

# Criar mock pool ANTES de importar catalogo (que tenta conectar no modulo-level)
async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock(
            fetch=AsyncMock(return_value=[]),
            fetchrow=AsyncMock(return_value=None),
            fetchval=AsyncMock(return_value=1),  # >0 => nao roda migracao de dedup
            execute=AsyncMock(return_value="OK")
        )),
        __aexit__=AsyncMock(return_value=None)
    )
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mock_pool)
patcher.start()
import core.catalogo as catalogo  # importa APOS patch estar ativo

NOVAS_COLUNAS = [
    "classificacao", "nome_reduzido", "nome_impressao", "codigo_interno",
    "codigo_erp", "ex_tipi", "modelo", "linha", "colecao",
]


class TestColunasIdentificacao(unittest.TestCase):
    def test_ensure_tables_cria_novas_colunas(self):
        """Verifica que as 9 novas colunas de identificacao sao criadas via ALTER TABLE,
        sem remover ou renomear colunas existentes."""
        import inspect
        source = inspect.getsource(catalogo._ensure_tables)

        for coluna in NOVAS_COLUNAS:
            self.assertIn(f"ADD COLUMN IF NOT EXISTS {coluna}", source,
                          f"coluna {coluna} nao declarada no source de _ensure_tables")
        # nenhuma coluna existente pode ser removida ou renomeada
        self.assertNotIn("DROP COLUMN", source)
        self.assertNotIn("RENAME COLUMN", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
