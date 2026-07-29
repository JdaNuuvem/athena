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


class TestMatchingAutomatico(unittest.TestCase):
    def test_matching_tipo_invalido_retorna_erro(self):
        resultado = i9logic.executar_matching_automatico("invalido", [])
        self.assertIn("erro", resultado)

    def test_matching_produto_casa_por_sku_igual(self):
        query_capturada = {}
        async def _fetchval(query, *args):
            query_capturada["query"] = query
            if "catalogo_produtos" in query:
                return args[0] if args[0] == "041725" else None
            return None
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=_fetchval, execute=AsyncMock(return_value="OK"))
            resultado = i9logic.executar_matching_automatico(
                "produto", [{"id_i9logic": 29098, "codigo_i9logic": "041725"}])
        self.assertEqual(resultado["casados"], 1)
        self.assertEqual(resultado["nao_casados"], [])
        # Verificar que a query usa igualdade EXATA, nunca fuzzy matching
        self.assertIn("sku=$1", query_capturada["query"].replace(" ", ""))
        self.assertNotIn("ILIKE", query_capturada["query"].upper())
        self.assertNotIn("LIKE", query_capturada["query"].upper())

    def test_matching_produto_nao_casado_vai_pro_relatorio(self):
        async def _fetchval(query, *args):
            return None
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=_fetchval, execute=AsyncMock(return_value="OK"))
            resultado = i9logic.executar_matching_automatico(
                "produto", [{"id_i9logic": 999, "codigo_i9logic": "SKU-INEXISTENTE"}])
        self.assertEqual(resultado["casados"], 0)
        self.assertEqual(len(resultado["nao_casados"]), 1)
        self.assertEqual(resultado["nao_casados"][0]["codigo_i9logic"], "SKU-INEXISTENTE")

    def test_matching_filial_consulta_tabela_lojas(self):
        query_capturada = {}
        async def _fetchval(query, *args):
            query_capturada["query"] = query
            self.assertIn("lojas", query)
            return "Loja Matriz"
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=_fetchval, execute=AsyncMock(return_value="OK"))
            resultado = i9logic.executar_matching_automatico(
                "filial", [{"id_i9logic": 63, "codigo_i9logic": "Loja Matriz"}])
        self.assertEqual(resultado["casados"], 1)
        # Verificar que a query usa igualdade EXATA, nunca fuzzy matching
        self.assertIn("nome=$1", query_capturada["query"].replace(" ", ""))
        self.assertNotIn("ILIKE", query_capturada["query"].upper())
        self.assertNotIn("LIKE", query_capturada["query"].upper())
