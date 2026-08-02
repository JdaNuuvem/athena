"""Testes — core.shopee_fulfillment (orquestracao Shopee + Bling: vincular
pedido, emitir nota fiscal, baixar PDF, marcar despacho).

A etiqueta/despacho em si (create_shipping_document/mass_ship_order) ja'
existe e e' testada em outro lugar (shopee/logistics.py + rotas dedicadas) —
este modulo so' persiste o vinculo/estado, nao reimplementa a chamada real."""
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

import core.shopee_fulfillment as ful


class TestStatusFulfillment(unittest.TestCase):
    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": "123"})
    @patch("core.shopee_fulfillment.obter_pedido_sincronizado")
    def test_pedido_sem_nenhuma_acao_ainda(self, mock_obter, mock_cfg):
        mock_obter.return_value = {"order_sn": "SN-1", "bling_pedido_id": None,
            "bling_nota_fiscal_id": None, "despachado_em": None, "package_number": None}
        r = ful.status_fulfillment("SN-1", 7)
        self.assertFalse(r["vinculado_bling"])
        self.assertFalse(r["nota_emitida"])
        self.assertFalse(r["despachado"])

    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": "123"})
    @patch("core.shopee_fulfillment.obter_pedido_sincronizado")
    def test_pedido_com_tudo_feito(self, mock_obter, mock_cfg):
        mock_obter.return_value = {"order_sn": "SN-1", "bling_pedido_id": 10,
            "bling_nota_fiscal_id": 20, "despachado_em": "2026-08-02T10:00:00", "package_number": "PKG-1"}
        r = ful.status_fulfillment("SN-1", 7)
        self.assertTrue(r["vinculado_bling"])
        self.assertTrue(r["nota_emitida"])
        self.assertTrue(r["despachado"])
        self.assertEqual(r["bling_pedido_id"], 10)

    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": ""})
    def test_loja_sem_shop_id_retorna_erro(self, mock_cfg):
        r = ful.status_fulfillment("SN-1", 7)
        self.assertIn("erro", r)

    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": "123"})
    @patch("core.shopee_fulfillment.obter_pedido_sincronizado", return_value=None)
    def test_pedido_nao_sincronizado_retorna_erro(self, mock_obter, mock_cfg):
        r = ful.status_fulfillment("SN-X", 7)
        self.assertIn("erro", r)


class TestVincularPedidoBling(unittest.TestCase):
    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": "123"})
    @patch("core.shopee_fulfillment.atualizar_vinculo_pedido", return_value={"ok": True})
    def test_vinculo_manual_nao_busca_automatico(self, mock_atualiza, mock_cfg):
        with patch("core.shopee_fulfillment.buscar_pedido_por_numero_loja") as mock_buscar:
            r = ful.vincular_pedido_bling("SN-1", 7, id_pedido_bling=999)
        mock_buscar.assert_not_called()
        mock_atualiza.assert_called_once_with("SN-1", "123", bling_pedido_id=999)
        self.assertTrue(r["ok"])

    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": "123"})
    @patch("core.shopee_fulfillment.buscar_pedido_por_numero_loja", return_value={"id": 55, "numeroLoja": "SN-1"})
    @patch("core.shopee_fulfillment.atualizar_vinculo_pedido", return_value={"ok": True})
    def test_busca_automatica_por_numero_loja(self, mock_atualiza, mock_buscar, mock_cfg):
        ful.vincular_pedido_bling("SN-1", 7)
        mock_buscar.assert_called_once_with("SN-1")
        mock_atualiza.assert_called_once_with("SN-1", "123", bling_pedido_id=55)

    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": "123"})
    @patch("core.shopee_fulfillment.buscar_pedido_por_numero_loja", return_value=None)
    def test_busca_automatica_sem_match_retorna_erro_claro(self, mock_buscar, mock_cfg):
        r = ful.vincular_pedido_bling("SN-1", 7)
        self.assertIn("erro", r)
        self.assertIn("manual", r["erro"])


class TestEmitirNotaFiscal(unittest.TestCase):
    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": "123"})
    @patch("core.shopee_fulfillment.obter_pedido_sincronizado")
    def test_sem_vinculo_bling_recusa(self, mock_obter, mock_cfg):
        mock_obter.return_value = {"bling_pedido_id": None, "bling_nota_fiscal_id": None}
        r = ful.emitir_nota_fiscal("SN-1", 7)
        self.assertIn("erro", r)

    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": "123"})
    @patch("core.shopee_fulfillment.obter_pedido_sincronizado")
    def test_nota_ja_emitida_recusa_duplicar(self, mock_obter, mock_cfg):
        mock_obter.return_value = {"bling_pedido_id": 10, "bling_nota_fiscal_id": 20}
        r = ful.emitir_nota_fiscal("SN-1", 7)
        self.assertIn("erro", r)
        self.assertEqual(r["bling_nota_fiscal_id"], 20)

    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": "123"})
    @patch("core.shopee_fulfillment.obter_pedido_sincronizado")
    @patch("core.shopee_fulfillment.emitir_nfe", return_value={"data": {"id": 777}})
    @patch("core.shopee_fulfillment.atualizar_vinculo_pedido", return_value={"ok": True})
    @patch("core.shopee_fulfillment.sincronizar_uma_nota_fiscal", return_value={"nota_id": 1})
    def test_emite_e_grava_vinculo(self, mock_sync, mock_atualiza, mock_emitir, mock_obter, mock_cfg):
        mock_obter.return_value = {"bling_pedido_id": 10, "bling_nota_fiscal_id": None}
        r = ful.emitir_nota_fiscal("SN-1", 7)
        mock_emitir.assert_called_once_with(10)
        mock_atualiza.assert_called_once_with("SN-1", "123", bling_nota_fiscal_id=777)
        mock_sync.assert_called_once_with(777)
        self.assertTrue(r["ok"])
        self.assertEqual(r["bling_nota_fiscal_id"], 777)

    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": "123"})
    @patch("core.shopee_fulfillment.obter_pedido_sincronizado")
    @patch("core.shopee_fulfillment.emitir_nfe", return_value={"error": "pedido ja possui nota"})
    def test_erro_do_bling_propaga(self, mock_emitir, mock_obter, mock_cfg):
        mock_obter.return_value = {"bling_pedido_id": 10, "bling_nota_fiscal_id": None}
        r = ful.emitir_nota_fiscal("SN-1", 7)
        self.assertIn("erro", r)

    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": "123"})
    @patch("core.shopee_fulfillment.obter_pedido_sincronizado")
    @patch("core.shopee_fulfillment.emitir_nfe", return_value={"data": {}})
    def test_resposta_sem_id_reconhecivel_nao_quebra(self, mock_emitir, mock_obter, mock_cfg):
        mock_obter.return_value = {"bling_pedido_id": 10, "bling_nota_fiscal_id": None}
        r = ful.emitir_nota_fiscal("SN-1", 7)
        self.assertIn("erro", r)
        self.assertIn("resposta_bruta", r)


class TestBaixarNotaPdf(unittest.TestCase):
    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": "123"})
    @patch("core.shopee_fulfillment.obter_pedido_sincronizado")
    @patch("core.shopee_fulfillment.get_nfe_pdf_bytes", return_value=(b"%PDF", "application/pdf"))
    def test_baixa_com_nota_vinculada(self, mock_pdf, mock_obter, mock_cfg):
        mock_obter.return_value = {"bling_nota_fiscal_id": 20}
        conteudo, content_type = ful.baixar_nota_pdf("SN-1", 7)
        mock_pdf.assert_called_once_with(20)
        self.assertEqual(conteudo, b"%PDF")

    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": "123"})
    @patch("core.shopee_fulfillment.obter_pedido_sincronizado")
    def test_sem_nota_vinculada_retorna_none(self, mock_obter, mock_cfg):
        mock_obter.return_value = {"bling_nota_fiscal_id": None}
        conteudo, content_type = ful.baixar_nota_pdf("SN-1", 7)
        self.assertIsNone(conteudo)


class TestMarcarDespachado(unittest.TestCase):
    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": "123"})
    @patch("core.shopee_fulfillment.atualizar_vinculo_pedido", return_value={"ok": True})
    def test_grava_despachado_em_e_package_number(self, mock_atualiza, mock_cfg):
        r = ful.marcar_despachado("SN-1", 7, package_number="PKG-1")
        self.assertTrue(r["ok"])
        _, kwargs = mock_atualiza.call_args
        self.assertIn("despachado_em", kwargs)
        self.assertEqual(kwargs["package_number"], "PKG-1")

    @patch("core.shopee_fulfillment.get_shopee_config", return_value={"shop_id": "123"})
    @patch("core.shopee_fulfillment.atualizar_vinculo_pedido", return_value={"ok": True})
    def test_sem_package_number_ainda_grava_despacho(self, mock_atualiza, mock_cfg):
        ful.marcar_despachado("SN-1", 7)
        _, kwargs = mock_atualiza.call_args
        self.assertIn("despachado_em", kwargs)
        self.assertNotIn("package_number", kwargs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
