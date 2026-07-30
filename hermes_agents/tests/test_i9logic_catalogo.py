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
        with patch("core.i9logic_catalogo.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow, execute=_execute)
            resultado = catalogo_i9logic._upsert_produto(
                {"id": 99, "codproduto": "SKU-99", "descricao": "Teste", "ean": "123",
                 "ncm": "0000", "unidademedida": "UN", "peso": 1})
        self.assertEqual(resultado["sku"], "SKU-99")
        self.assertTrue(any("de_para_i9logic" in q for q, _ in chamadas_execute))
        query_depara, args_depara = next((q, a) for q, a in chamadas_execute if "de_para_i9logic" in q)
        self.assertEqual(args_depara, ("99", "SKU-99"))


class TestSincronizarCatalogo(unittest.TestCase):
    def test_sem_base_url_retorna_erro(self):
        with patch("core.i9logic_catalogo.BASE_URL", ""):
            resultado = catalogo_i9logic.sincronizar_catalogo_i9logic()
        self.assertIn("erro", resultado)

    def test_filtra_apenas_ativo_e_emlinha(self):
        produtos_upsertados = []
        def _fake_upsert(produto):
            produtos_upsertados.append(produto["codproduto"])
            return {"sku": produto["codproduto"]}
        def _fake_paginar(endpoint, params, on_pagina=None):
            pagina = [
                {"id": 1, "codproduto": "ATIVO1", "ativo": "1", "emlinha": "1"},
                {"id": 2, "codproduto": "INATIVO", "ativo": "0", "emlinha": "1"},
                {"id": 3, "codproduto": "FORADELINHA", "ativo": "1", "emlinha": "0"},
            ]
            if on_pagina: on_pagina(pagina)
            return pagina
        with patch("core.i9logic_catalogo.BASE_URL", "https://fake"), \
             patch("core.i9logic_catalogo._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_catalogo._upsert_produto", side_effect=_fake_upsert):
            resultado = catalogo_i9logic.sincronizar_catalogo_i9logic()
        self.assertEqual(produtos_upsertados, ["ATIVO1"])
        self.assertEqual(resultado["importados"], 1)

    def test_produto_malformado_e_pulado_sem_abortar_lote(self):
        def _fake_paginar(endpoint, params, on_pagina=None):
            pagina = [
                {"id": 1, "codproduto": "", "ativo": "1", "emlinha": "1"},
                {"id": 2, "codproduto": "OK", "ativo": "1", "emlinha": "1"},
            ]
            if on_pagina: on_pagina(pagina)
            return pagina
        def _fake_upsert(produto):
            if not produto.get("codproduto"):
                return {"erro": "codproduto vazio"}
            return {"sku": produto["codproduto"]}
        with patch("core.i9logic_catalogo.BASE_URL", "https://fake"), \
             patch("core.i9logic_catalogo._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_catalogo._upsert_produto", side_effect=_fake_upsert):
            resultado = catalogo_i9logic.sincronizar_catalogo_i9logic()
        self.assertEqual(resultado["importados"], 1)
        self.assertEqual(len(resultado["erros_registro"]), 1)

    def test_falha_de_pagina_retorna_progresso_parcial(self):
        def _fake_paginar(endpoint, params, on_pagina=None):
            if on_pagina:
                on_pagina([{"id": 1, "codproduto": "P1", "ativo": "1", "emlinha": "1"}])
            raise I9LogicPaginaError(2, Exception("timeout"))
        with patch("core.i9logic_catalogo.BASE_URL", "https://fake"), \
             patch("core.i9logic_catalogo._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_catalogo._upsert_produto", return_value={"sku": "P1"}):
            resultado = catalogo_i9logic.sincronizar_catalogo_i9logic()
        self.assertIn("erro", resultado)
        self.assertEqual(resultado["pagina_falhou"], 2)
        self.assertEqual(resultado["importados_ate_agora"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
