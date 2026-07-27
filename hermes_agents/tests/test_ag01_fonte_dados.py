"""Testes — AG-01 (Cacador de Produtos) e' 100% simulado hoje; nenhuma
fonte (Shopee/ML/Amazon/Temu/TikTok/Trends/Pinterest) tem integracao real.
Esses testes garantem que essa limitacao fica explicita nos dados
devolvidos (fonte_dados: "simulada"), em vez de parecer dado real."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import ag_01_cacador as cacador


class TestStatusFonteDados(unittest.TestCase):
    def test_todas_as_fontes_marcadas_como_simuladas(self):
        status = cacador.status_fonte_dados()
        self.assertTrue(all(v == "simulada" for v in status["fontes"].values()))
        self.assertIn("simulado", status["aviso"].lower())

    def test_sete_fontes_documentadas(self):
        self.assertEqual(set(cacador.FONTE_DADOS_STATUS.keys()), {
            "shopee", "mercado_livre", "amazon", "temu", "tiktok_shop", "google_trends", "pinterest",
        })


class TestPesquisarMarketplaceMarcaFonte(unittest.TestCase):
    def test_produtos_simulados_vem_marcados(self):
        with patch.dict(cacador.PRODUTOS_CONFIG, {"mercado_livre": [{"nome": "Produto X", "preco": 50}]}):
            produtos = cacador.pesquisar_marketplace("mercado_livre")
        self.assertEqual(len(produtos), 1)
        self.assertEqual(produtos[0]["fonte_dados"], "simulada")

    def test_modo_api_configurado_nao_muda_o_resultado_mas_avisa(self):
        """Se alguem setar CACADOR_FONTE=api, o comportamento deve continuar
        sendo o simulado (nao ha integracao real) — mas precisa avisar,
        nunca fingir silenciosamente que usou uma API real."""
        with patch.object(cacador, "FONTE_DADOS", "api"), \
             patch.object(cacador, "_avisar_modo_api_nao_implementado") as mock_aviso, \
             patch.dict(cacador.PRODUTOS_CONFIG, {"shopee": [{"nome": "Y", "preco": 10}]}):
            produtos = cacador.pesquisar_marketplace("shopee")
        mock_aviso.assert_called_once_with("shopee")
        self.assertEqual(produtos[0]["fonte_dados"], "simulada")


class TestAnalisarViabilidadePropagaFonte(unittest.TestCase):
    def test_fonte_dados_do_produto_aparece_na_analise(self):
        produto = {"nome": "Organizador Plástico", "preco": 40, "concorrentes": 10, "fonte_dados": "simulada"}
        analise = cacador.analisar_viabilidade(produto)
        self.assertEqual(analise["fonte_dados"], "simulada")


if __name__ == "__main__":
    unittest.main(verbosity=2)
