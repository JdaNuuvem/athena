"""Testes — Shopee: margem, markup, regras, concorrencia, kits (Fases 1-5)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock

# ── Mock asyncpg ANTES de importar os modulos ──
_fake_db = AsyncMock()
_fake_db.fetchval = AsyncMock(return_value=0)
_fake_db.fetchrow = AsyncMock(return_value=None)
_fake_db.fetch = AsyncMock(return_value=[])
_fake_db.execute = AsyncMock(return_value="OK")
_fake_conn = AsyncMock()
_fake_conn.__aenter__ = AsyncMock(return_value=AsyncMock(
    fetchval=AsyncMock(return_value=0), fetchrow=AsyncMock(return_value=None),
    fetch=AsyncMock(return_value=[]), execute=AsyncMock(return_value="OK"),
    transaction=AsyncMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=None),
        __aexit__=AsyncMock(return_value=None),
    )),
))
_fake_conn.__aexit__ = AsyncMock(return_value=None)
async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = _fake_conn
    return m
patcher = patch("asyncpg.create_pool", side_effect=_mock_pool)
patcher.start()

import core  # noqa
import shopee as s
import core.automacoes as aut

def _stub_run_async(ret):
    """Retorna um mock de run_async que devolve `ret`."""
    return patch("core.run_async", return_value=ret)

class TestMargemProduto(unittest.TestCase):
    """Fase 1 — Alerta de margem negativa."""

    @patch("shopee.pricing.get_config", return_value=None)
    @patch("shopee.pricing.run_async")
    @patch.dict("os.environ", {"SHOPEE_COMISSAO_PCT": "15"})
    def test_margem_com_custo_comissao_e_frete(self, mock_run, mock_cfg):
        mock_run.return_value = 10.0  # custo
        r = s.calcular_margem_produto("SKU1", 45.0)
        self.assertEqual(r["custo"], 10.0)
        self.assertEqual(r["comissao_valor"], 6.75)
        self.assertEqual(r["frete"], 15.0)  # default FactoryConfig.frete_medio_shopee
        self.assertEqual(r["margem_valor"], 13.25)  # 45 - 6.75 - 15 - 10

    @patch("shopee.pricing.get_config", return_value=None)
    @patch.dict("os.environ", {"SHOPEE_COMISSAO_PCT": "12"})
    def test_margem_negativa_bloqueia(self, mock_cfg):
        """Preco = R$18, custo = R$20, comissao = 12%, frete R$15 → prejuizo."""
        with patch("shopee.pricing.run_async", return_value=20.0):
            r = s.calcular_margem_produto("SKU2", 18.0)
        self.assertFalse(r["ok"])
        self.assertIn("PREJUIZO", r["mensagem"])

    def test_margem_sem_custo_avisa(self):
        """Custo = 0 -> avisa mas nao bloqueia."""
        with patch("shopee.pricing.run_async", return_value=0):
            r = s.calcular_margem_produto("SKU3", 50.0)
        self.assertTrue(r["ok"])
        self.assertIn("Custo nao cadastrado", r["mensagem"])


class TestAnalisarConsistenciaPrecos(unittest.TestCase):
    """Fase 5 — Consistencia de preco do mesmo SKU entre lojas proprias
    (nao e' comparacao com concorrentes reais — a API da Shopee nao expoe isso)."""

    def test_consistencia_com_anuncios(self):
        with patch("shopee.concorrencia.run_async", return_value={
            "sku": "SKU1", "preco_nosso": 35.0, "marketplace": "shopee",
            "total_anuncios": 5, "preco_medio": 20.8, "preco_mediano": 20.0,
            "preco_min": 18.0, "preco_max": 24.0, "preco_acima_pct": 68.3,
            "alerta": "critico",
            "mensagem": "Este SKU esta 68.3% acima da media das suas outras lojas (R$ 20.80). 5 anuncios proprios analisados.",
        }):
            r = s.analisar_consistencia_precos("SKU1", 35.0)
        self.assertEqual(r["total_anuncios"], 5)
        self.assertEqual(r["alerta"], "critico")

    def test_consistencia_sem_anuncios(self):
        with patch("shopee.concorrencia.run_async", return_value=None):
            r = s.analisar_consistencia_precos("SKU_NOVO", 50.0)
        self.assertEqual(r["total_anuncios"], 0)
        self.assertIn("nao esta anunciado em nenhuma outra loja", r["mensagem"])


class TestSugerirKits(unittest.TestCase):
    """Fase 5 — Sugestao de kits."""

    def test_kits_sem_dados(self):
        with patch("shopee.kits.run_async", return_value=[]):
            r = s.sugerir_kits(dias=30, min_ocorrencias=2)
        self.assertEqual(r, [])

    def test_kits_com_pares(self):
        kit = [{
            "sku_a": "SKU1", "nome_a": "Produto A",
            "sku_b": "SKU2", "nome_b": "Produto B",
            "qtd_juntos": 5, "confianca_pct": 50.0,
        }]
        with patch("shopee.kits.run_async", return_value=kit):
            r = s.sugerir_kits(dias=90, min_ocorrencias=2)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["sku_a"], "SKU1")
        self.assertEqual(r[0]["confianca_pct"], 50.0)


class TestListarLojasShopee(unittest.TestCase):
    """Fase 2 — Listagem de lojas."""

    def test_listar_lojas(self):
        lojas = [{"id": 1, "nome": "Loja A", "shopee_shop_id": "111",
                   "shopee_access_token": "t1", "shopee_shop_name": "Loja A Shopee",
                   "ativa": True, "shopee_markup_pct": 110}]
        with patch("shopee.stores.run_async", return_value=lojas):
            r = s.listar_todas_lojas_shopee()
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["shopee_markup_pct"], 110)


class TestTransferirProdutos(unittest.TestCase):
    """Fase 1+3 — Replicacao."""

    def test_transferir_sem_produtos(self):
        with patch("shopee.replication.configurado", return_value=True):
            with patch("shopee.products.get_items", return_value={"response": {"item_list": []}}):
                r = s.transferir_produtos_para_loja(1, 2)
        self.assertIn("Nenhum produto", r.get("mensagem", ""))

    def test_transferir_com_erro_api(self):
        with patch("shopee.replication.configurado", return_value=True):
            with patch("shopee.replication.get_items", return_value={"response": {"item_list": [{"item_id": 1}]}}):
                with patch("shopee.replication.get_item_base_info", return_value={"response": {"item_list": [{
                    "item_id": 1, "item_name": "Teste", "item_sku": "SKU1",
                    "category_id": 100, "price_info": [{"current_price": 50}],
                    "weight": 0.5, "attribute_list": [], "logistic_info": [{"logistic_id": 1}],
                    "image": {"image_id_list": ["https://img.com/1.jpg"]},
                    "dimension": {"package_length": 10, "package_width": 10, "package_height": 10},
                }]}}):
                    with patch("shopee.replication.run_async", return_value=100):
                        with patch("shopee.replication.upload_image", return_value={"response": {"image_id": "img_123"}}):
                            with patch("shopee.replication.add_item", return_value={"error": "API Error"}):
                                r = s.transferir_produtos_para_loja(1, 2)
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["sucesso"], 0)
        self.assertGreater(len(r["erros"]), 0)


class TestRegrasPreco(unittest.TestCase):
    """Fase 3 — Regras de desconto/markup."""

    def test_sem_regras_ativas(self):
        with patch("core.automacoes.run_async", return_value={"preco_original": 100.0, "preco_final": 100.0, "regras_aplicadas": []}):
            r = aut.aplicar_regras_preco("SKU1", 100.0)
        self.assertEqual(r["preco_final"], 100.0)

    def test_desconto_manual(self):
        result = {"preco_original": 100.0, "preco_final": 90.0, "regras_aplicadas": [
            {"nome": "Desconto 10%", "ajuste_pct": -10.0, "tipo": "desconto"},
        ]}
        with patch("core.automacoes.run_async", return_value=result):
            r = aut.aplicar_regras_preco("SKU1", 100.0)
        self.assertEqual(r["preco_final"], 90.0)
        self.assertEqual(len(r["regras_aplicadas"]), 1)

    def test_markup_e_desconto_combinados(self):
        result = {"preco_original": 100.0, "preco_final": 108.0, "regras_aplicadas": [
            {"nome": "Markup 20%", "ajuste_pct": 20.0, "tipo": "markup"},
            {"nome": "Desconto 10%", "ajuste_pct": -10.0, "tipo": "desconto"},
        ]}
        with patch("core.automacoes.run_async", return_value=result):
            r = aut.aplicar_regras_preco("SKU1", 100.0)
        self.assertEqual(r["preco_final"], 108.0)
        self.assertEqual(len(r["regras_aplicadas"]), 2)


class TestDispararWebhooks(unittest.TestCase):
    """Fase 2 — Webhook dispatcher."""

    def test_sem_webhooks(self):
        with patch("core.automacoes.run_async", return_value={"disparados": 0, "resultados": []}):
            r = aut.disparar_webhooks("venda.criada")
        self.assertEqual(r["disparados"], 0)

    def test_dispara_webhook_com_template(self):
        result = {"evento": "venda.criada", "disparados": 1, "resultados": [
            {"id": 1, "nome": "Hook1", "url": "http://t", "status": 200},
        ]}
        with patch("core.automacoes.run_async", return_value=result):
            r = aut.disparar_webhooks("venda.criada", {"venda_id": "42"})
        self.assertEqual(r["disparados"], 1)
        self.assertEqual(r["resultados"][0]["status"], 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
