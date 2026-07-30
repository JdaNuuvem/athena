"""Testes de integracao — import de catalogo i9Logic -> catalogo_produtos."""
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

import core.i9logic_catalogo as catalogo_i9logic
from core.i9logic import I9LogicPaginaError


class TestUpsertProduto(unittest.TestCase):
    def test_codproduto_vazio_retorna_erro(self):
        resultado = catalogo_i9logic._upsert_produto({"id": 1, "codproduto": "  "})
        self.assertIn("erro", resultado)

    def test_grava_de_para_automatico_junto_com_upsert(self):
        chamadas_execute = []
        async def _fetchrow(query, *args):
            return {"sku": args[0]}
        async def _execute(query, *args):
            chamadas_execute.append((query, args))
            return "OK"
        class TxMock:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return None
        def _transaction():
            # transaction() returns the context manager object directly
            return TxMock()

        with patch("core.i9logic_catalogo.get_db") as mock_get_db:
            mock_db = AsyncMock(fetchrow=_fetchrow, execute=_execute)
            mock_db.transaction = _transaction
            mock_get_db.return_value = mock_db
            resultado = catalogo_i9logic._upsert_produto(
                {"id": 99, "codproduto": "SKU-99", "descricao": "Teste", "ean": "123",
                 "ncm": "0000", "unidademedida": "UN", "peso": 1})
        self.assertEqual(resultado["sku"], "SKU-99")
        self.assertTrue(any("de_para_i9logic" in q for q, _ in chamadas_execute))
        query_depara, args_depara = next((q, a) for q, a in chamadas_execute if "de_para_i9logic" in q)
        self.assertEqual(args_depara, ("99", "SKU-99"))


class TestUpsertPagina(unittest.TestCase):
    def test_filtra_apenas_ativo_e_emlinha(self):
        """Testa que _upsert_pagina filtra produtos ativo=1 e emlinha=1"""
        chamadas_upsert = []
        async def _upsert_mock(db, produto):
            chamadas_upsert.append(produto.get("codproduto"))
            return {"sku": produto.get("codproduto")}

        pagina = [
            {"id": 1, "codproduto": "ATIVO1", "ativo": "1", "emlinha": "1"},
            {"id": 2, "codproduto": "INATIVO", "ativo": "0", "emlinha": "1"},
            {"id": 3, "codproduto": "FORADELINHA", "ativo": "1", "emlinha": "0"},
        ]

        with patch("core.i9logic_catalogo._upsert_produto_async", side_effect=_upsert_mock), \
             patch("core.i9logic_catalogo.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock()
            importados, erros = catalogo_i9logic._upsert_pagina(pagina)

        self.assertEqual(chamadas_upsert, ["ATIVO1"])
        self.assertEqual(importados, 1)
        self.assertEqual(len(erros), 0)

    def test_produto_malformado_e_pulado_sem_abortar_lote(self):
        """Testa que produtos malformados sao registrados sem abortar o lote"""
        async def _upsert_mock(db, produto):
            if not produto.get("codproduto"):
                return {"erro": "codproduto vazio"}
            return {"sku": produto.get("codproduto")}

        pagina = [
            {"id": 1, "codproduto": "", "ativo": "1", "emlinha": "1"},
            {"id": 2, "codproduto": "OK", "ativo": "1", "emlinha": "1"},
        ]

        with patch("core.i9logic_catalogo._upsert_produto_async", side_effect=_upsert_mock), \
             patch("core.i9logic_catalogo.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock()
            importados, erros = catalogo_i9logic._upsert_pagina(pagina)

        self.assertEqual(importados, 1)
        self.assertEqual(len(erros), 1)
        self.assertIn("codproduto vazio", erros[0]["erro"])

    def test_transacao_atomica_envolvida(self):
        """Testa que _upsert_produto_async usa transaction context manager"""
        chamadas_transaction = []

        class TxMock:
            async def __aenter__(self):
                chamadas_transaction.append("enter")
                return self
            async def __aexit__(self, *args):
                chamadas_transaction.append("exit")
                return None

        def _transaction():
            # transaction() retorna o context manager object
            return TxMock()

        async def _fetchrow(query, *args):
            return {"sku": args[0]}

        async def _execute(query, *args):
            return "OK"

        with patch("core.i9logic_catalogo.get_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.fetchrow = _fetchrow
            mock_db.execute = _execute
            mock_db.transaction = _transaction
            mock_get_db.return_value = mock_db

            import asyncio
            result = asyncio.run(catalogo_i9logic._upsert_produto_async(mock_db,
                {"id": 99, "codproduto": "SKU-99", "descricao": "Teste"}))

        self.assertEqual(result["sku"], "SKU-99")
        self.assertIn("enter", chamadas_transaction)
        self.assertIn("exit", chamadas_transaction)


class TestSincronizarCatalogo(unittest.TestCase):
    def test_sem_base_url_retorna_erro(self):
        with patch("core.i9logic_catalogo.BASE_URL", ""):
            resultado = catalogo_i9logic.sincronizar_catalogo_i9logic()
        self.assertIn("erro", resultado)

    def test_agrega_resultados_de_paginas(self):
        """Testa que sincronizar_catalogo_i9logic agrega importados e erros de multiplas paginas"""
        def _fake_paginar(endpoint, params, on_pagina=None):
            # Simula 2 paginas
            if on_pagina:
                on_pagina([
                    {"id": 1, "codproduto": "P1", "ativo": "1", "emlinha": "1"},
                    {"id": 2, "codproduto": "P2", "ativo": "1", "emlinha": "1"},
                ])
                on_pagina([
                    {"id": 3, "codproduto": "P3", "ativo": "1", "emlinha": "1"},
                ])
            return []

        def _fake_upsert_pagina(pagina):
            # Simula sucesso/erro
            if len(pagina) == 2:
                return 2, []
            else:
                return 1, []

        with patch("core.i9logic_catalogo.BASE_URL", "https://fake"), \
             patch("core.i9logic_catalogo._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_catalogo._upsert_pagina", side_effect=_fake_upsert_pagina):
            resultado = catalogo_i9logic.sincronizar_catalogo_i9logic()

        self.assertEqual(resultado["ok"], True)
        self.assertEqual(resultado["importados"], 3)
        self.assertEqual(len(resultado["erros_registro"]), 0)

    def test_falha_de_pagina_retorna_progresso_parcial(self):
        """Testa que falha de pagina retorna progresso parcial"""
        def _fake_paginar(endpoint, params, on_pagina=None):
            if on_pagina:
                on_pagina([{"id": 1, "codproduto": "P1", "ativo": "1", "emlinha": "1"}])
            raise I9LogicPaginaError(2, Exception("timeout"))

        def _fake_upsert_pagina(pagina):
            return 1, []

        with patch("core.i9logic_catalogo.BASE_URL", "https://fake"), \
             patch("core.i9logic_catalogo._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_catalogo._upsert_pagina", side_effect=_fake_upsert_pagina):
            resultado = catalogo_i9logic.sincronizar_catalogo_i9logic()

        self.assertIn("erro", resultado)
        self.assertEqual(resultado["pagina_falhou"], 2)
        self.assertEqual(resultado["importados_ate_agora"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
