"""Testes de integracao — reconciliacao i9Logic."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock, MagicMock

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.i9logic as i9logic


class TestDeParaCRUD(unittest.TestCase):
    def test_criar_mapeamento_tipo_invalido_retorna_erro(self):
        resultado = i9logic.criar_mapeamento("invalido", "1", "SKU-1")
        self.assertIn("erro", resultado)

    def test_criar_mapeamento_produto_grava(self):
        async def _fetchrow(query, *args):
            return {"id": 1, "tipo": args[0], "id_i9logic": args[1], "codigo_athena": args[2]}
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.criar_mapeamento("produto", 29098, "SKU-29098")
        self.assertEqual(resultado["codigo_athena"], "SKU-29098")
        self.assertEqual(resultado["id_i9logic"], "29098")

    def test_buscar_codigo_athena_encontrado(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=AsyncMock(return_value="SKU-29098"))
            resultado = i9logic.buscar_codigo_athena("produto", 29098)
        self.assertEqual(resultado, "SKU-29098")

    def test_buscar_codigo_athena_nao_encontrado_retorna_none(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=AsyncMock(return_value=None))
            resultado = i9logic.buscar_codigo_athena("produto", 999)
        self.assertIsNone(resultado)

    def test_listar_mapeamentos_filtra_por_tipo(self):
        async def _fetch(query, *args):
            self.assertIn("tipo=$1", query)
            self.assertEqual(args[0], "filial")
            return [{"id": 1, "tipo": "filial", "id_i9logic": "63", "codigo_athena": "Loja Matriz"}]
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetch=_fetch)
            resultado = i9logic.listar_mapeamentos("filial")
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["codigo_athena"], "Loja Matriz")
