"""
Testes de shopee/orders.py — sync de pedidos.

Contexto: order/get_order_list e order/get_order_detail sao endpoints GET da
Shopee, nao POST (o codigo antigo forcava POST e a Shopee respondia 404 puro
— confirmado ao vivo contra a loja de producao real, ver commit desta
correcao). Os nomes de parametro tambem estavam errados
(create_time_from/create_time_to nao existem; os reais sao
time_range_field/time_from/time_to, mais um cursor obrigatorio).
order_status so' aceita 1 valor por chamada — CSV de 2+ status e' rejeitado
pela Shopee ("order_status is invalid", confirmado ao vivo) — por isso
get_orders_by_time_range faz uma chamada por status. A Shopee tambem limita
o intervalo a 15 dias por chamada, entao periodos maiores sao quebrados em
janelas de 15 dias automaticamente.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock, MagicMock
import unittest

# Mock DB pool global (mesmo padrao de test_shopee_flow.py) para os imports no
# topo do modulo nao tentarem uma conexao real ao Postgres de producao.
_fake_pool = AsyncMock()
_fake_conn = AsyncMock()
_fake_conn.fetch.return_value = []
_fake_conn.fetchrow.return_value = None
_fake_conn.fetchval.return_value = 0
_fake_conn.execute.return_value = "OK"
_fake_pool.acquire.return_value = _fake_conn


async def _mock_create_pool(*a, **kw):
    pool = AsyncMock()
    pool.acquire.return_value = _fake_conn
    return pool


_pool_patcher = patch("asyncpg.create_pool", side_effect=_mock_create_pool)
_pool_patcher.start()

_db_table_patcher = patch("core.config._ensure_db_table", return_value=False)
_db_table_patcher.start()

import shopee
from shopee import orders as shopee_orders
from core.config import set_config


def _configurar_loja_fake():
    set_config("shopee", "partner_id", "1237336")
    set_config("shopee", "api_key", "chave-secreta-sandbox")
    set_config("shopee", "shop_id", "227748635")
    set_config("shopee", "access_token", "token-sandbox-fake")


class TestParametrosCorretosNaQueryString(unittest.TestCase):
    """Trava a forma exata dos parametros — e' o que estava errado em producao."""

    def setUp(self):
        _configurar_loja_fake()

    @patch("shopee.auth.requests.get")
    def test_get_order_list_usa_get_nao_post(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"response": {"order_list": [], "more": False, "next_cursor": ""}}
        shopee_orders.get_orders_by_time_range(1000, 2000, ["READY_TO_SHIP"])
        self.assertTrue(mock_get.called, "get_order_list precisa ser GET, nao POST")
        params = mock_get.call_args[1]["params"]
        self.assertEqual(params["time_range_field"], "create_time")
        self.assertEqual(params["time_from"], 1000)
        self.assertEqual(params["time_to"], 2000)
        self.assertEqual(params["order_status"], "READY_TO_SHIP")
        self.assertIn("cursor", params)
        self.assertNotIn("create_time_from", params)
        self.assertNotIn("create_time_to", params)

    @patch("shopee.auth.requests.get")
    def test_get_order_detail_usa_get_e_csv(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"response": {"order_list": []}}
        shopee_orders.get_order_detail("SN1,SN2")
        self.assertTrue(mock_get.called, "get_order_detail precisa ser GET, nao POST")
        params = mock_get.call_args[1]["params"]
        self.assertEqual(params["order_sn_list"], "SN1,SN2")
        self.assertIsInstance(params["order_sn_list"], str)


class TestUmStatusPorChamada(unittest.TestCase):
    """A Shopee rejeita CSV de multiplos status num so' get_order_list —
    confirmado ao vivo (order.error_param: order_status is invalid)."""

    def setUp(self):
        _configurar_loja_fake()

    @patch("shopee.auth.requests.get")
    def test_multiplos_status_faz_uma_chamada_por_status(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.side_effect = [
            {"response": {"order_list": [{"order_sn": "A"}], "more": False, "next_cursor": ""}},
            {"response": {"order_list": [{"order_sn": "B"}], "more": False, "next_cursor": ""}},
        ]
        r = shopee_orders.get_orders_by_time_range(1000, 2000, ["READY_TO_SHIP", "PROCESSED"])
        self.assertEqual(mock_get.call_count, 2)
        status_chamados = [c[1]["params"]["order_status"] for c in mock_get.call_args_list]
        self.assertEqual(status_chamados, ["READY_TO_SHIP", "PROCESSED"])
        self.assertEqual(len(r["response"]["order_list"]), 2)

    @patch("shopee.auth.requests.get")
    def test_para_na_primeira_chamada_com_erro(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"error": "order.order_list_invalid_time", "message": "..."}
        r = shopee_orders.get_orders_by_time_range(1000, 2000, ["READY_TO_SHIP", "PROCESSED"])
        self.assertEqual(r.get("error"), "order.order_list_invalid_time")
        self.assertEqual(mock_get.call_count, 1, "nao deveria continuar chamando apos erro")


class TestJanelaDe15Dias(unittest.TestCase):
    """A Shopee limita o intervalo a 15 dias por chamada — periodos maiores
    precisam ser quebrados em janelas, senao a Shopee responde
    order.order_list_invalid_time."""

    def setUp(self):
        _configurar_loja_fake()

    @patch("shopee.auth.requests.get")
    def test_periodo_30_dias_quebra_em_multiplas_janelas_validas(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"response": {"order_list": [], "more": False, "next_cursor": ""}}
        trinta_dias = 30 * 86400
        shopee_orders.get_orders_by_time_range(0, trinta_dias, ["READY_TO_SHIP"])
        self.assertGreater(mock_get.call_count, 1, "30 dias tem que quebrar em mais de 1 chamada")
        janelas = [c[1]["params"] for c in mock_get.call_args_list]
        for j in janelas:
            self.assertLessEqual(j["time_to"] - j["time_from"], 15 * 86400, "nenhuma janela pode passar de 15 dias")
        self.assertEqual(janelas[0]["time_from"], 0)
        self.assertEqual(janelas[-1]["time_to"], trinta_dias)
        for anterior, atual in zip(janelas, janelas[1:]):
            self.assertEqual(anterior["time_to"], atual["time_from"], "janelas tem que ser contiguas, sem furo nem sobreposicao")

    @patch("shopee.auth.requests.get")
    def test_periodo_7_dias_uma_janela_so(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"response": {"order_list": [], "more": False, "next_cursor": ""}}
        shopee_orders.get_orders_by_time_range(0, 7 * 86400, ["READY_TO_SHIP"])
        self.assertEqual(mock_get.call_count, 1)


class TestPaginacaoPorCursor(unittest.TestCase):

    def setUp(self):
        _configurar_loja_fake()

    @patch("shopee.auth.requests.get")
    def test_segue_next_cursor_ate_more_false(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.side_effect = [
            {"response": {"order_list": [{"order_sn": "A"}], "more": True, "next_cursor": "cursor2"}},
            {"response": {"order_list": [{"order_sn": "B"}], "more": False, "next_cursor": ""}},
        ]
        r = shopee_orders.get_orders_by_time_range(0, 86400, ["READY_TO_SHIP"])
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(mock_get.call_args_list[0][1]["params"]["cursor"], "")
        self.assertEqual(mock_get.call_args_list[1][1]["params"]["cursor"], "cursor2")
        self.assertEqual(len(r["response"]["order_list"]), 2)


class TestListarPedidosShopeeDetalhado(unittest.TestCase):

    def setUp(self):
        _configurar_loja_fake()

    @patch("shopee.orders.get_order_detail")
    @patch("shopee.orders.obter_pedidos_shopee")
    def test_junta_resumo_com_detalhe(self, mock_resumo, mock_detalhe):
        mock_resumo.return_value = {"response": {"order_list": [
            {"order_sn": "SN1", "order_status": "READY_TO_SHIP", "create_time": 100},
        ]}}
        mock_detalhe.return_value = {"response": {"order_list": [
            {"order_sn": "SN1", "buyer_username": "cliente1", "total_amount": 99.9,
             "recipient_address": {"name": "Fulano"},
             "item_list": [{"item_sku": "SKU1", "item_name": "Produto 1", "model_quantity_purchased": 2, "model_original_price": 49.95}]},
        ]}}
        r = shopee.listar_pedidos_shopee_detalhado(dias=7, loja_id=7)
        self.assertEqual(len(r["pedidos"]), 1)
        pedido = r["pedidos"][0]
        self.assertEqual(pedido["order_sn"], "SN1")
        self.assertEqual(pedido["buyer_username"], "cliente1")
        self.assertEqual(pedido["recipient_nome"], "Fulano")
        self.assertEqual(pedido["itens"][0]["sku"], "SKU1")
        # detalhe chamado com CSV, nao lista
        detalhe_args = mock_detalhe.call_args[0]
        self.assertIsInstance(detalhe_args[0], str)
        self.assertEqual(detalhe_args[0], "SN1")

    @patch("shopee.orders.obter_pedidos_shopee")
    def test_erro_no_resumo_propaga_sem_chamar_detalhe(self, mock_resumo):
        mock_resumo.return_value = {"error": "order.order_list_invalid_time", "message": "..."}
        r = shopee.listar_pedidos_shopee_detalhado(dias=30, loja_id=7)
        self.assertEqual(r.get("error"), "order.order_list_invalid_time")

    @patch("shopee.orders.obter_pedidos_shopee")
    def test_lista_vazia_nao_erro(self, mock_resumo):
        mock_resumo.return_value = {"response": {"order_list": []}}
        r = shopee.listar_pedidos_shopee_detalhado(dias=7, loja_id=7)
        self.assertEqual(r, {"pedidos": []})


if __name__ == "__main__":
    unittest.main(verbosity=2)
