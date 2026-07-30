"""
Testes de shopee/products.py — get_item_base_info().

Contexto: item_id_list era serializado com json.dumps(item_ids), produzindo a
string "[123, 456]". A API da Shopee rejeita esse formato com o erro
'strconv.ParseUint: parsing "[123": invalid syntax' — o endpoint espera uma
string de IDs separados por virgula, sem colchetes. Esse bug fazia
sync_produtos() sempre retornar 0 itens (sem erro visivel na tela), mesmo com
produtos reais e ativos na conta — confirmado contra a API real de producao.
Os testes anteriores nunca pegaram isso porque mockavam get_item_base_info()
inteira, sem verificar o parametro real enviado pra _request().
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock
import unittest

# Mock DB pool global (mesmo padrao de test_shopee_flow.py) para os imports no
# topo do modulo nao tentarem uma conexao real ao Postgres de producao.
_fake_conn = AsyncMock()
_fake_conn.fetch.return_value = []
_fake_conn.fetchrow.return_value = None
_fake_conn.fetchval.return_value = 0
_fake_conn.execute.return_value = "OK"

async def _mock_create_pool(*a, **kw):
    pool = AsyncMock()
    pool.acquire.return_value = _fake_conn
    return pool

_pool_patcher = patch("asyncpg.create_pool", side_effect=_mock_create_pool)
_pool_patcher.start()

_db_table_patcher = patch("core.config._ensure_db_table", return_value=False)
_db_table_patcher.start()

import shopee.products as products


class TestGetItemBaseInfo(unittest.TestCase):

    @patch("shopee.products._request")
    def test_item_id_list_e_string_separada_por_virgula(self, mock_request):
        mock_request.return_value = {"response": {"item_list": []}}
        products.get_item_base_info([58258804054, 58260686121, 58257905216], loja_id=7)
        params = mock_request.call_args[0][1]
        self.assertEqual(params["item_id_list"], "58258804054,58260686121,58257905216")
        self.assertNotIn("[", params["item_id_list"])

    @patch("shopee.products._request")
    def test_item_id_list_unico(self, mock_request):
        mock_request.return_value = {"response": {"item_list": []}}
        products.get_item_base_info([58258804054], loja_id=7)
        params = mock_request.call_args[0][1]
        self.assertEqual(params["item_id_list"], "58258804054")


class TestInitTierVariation(unittest.TestCase):
    """Cria a estrutura de variacao (tiers + modelos) de um item. Payload usa
    a chave "model" (nao "model_list") — confirmado nos exemplos oficiais de
    Creating product.md secao 7, diferente de update_tier_variation/add_model
    que usam "model_list"."""

    @patch("shopee.products._request")
    def test_monta_payload_com_chave_model(self, mock_request):
        mock_request.return_value = {"response": {}}
        tier = [{"name": "Cor", "option_list": [{"option": "Azul"}, {"option": "Vermelho"}]}]
        modelos = [
            {"tier_index": [0], "original_price": 15.98, "model_sku": "SKU-AZUL", "normal_stock": 10},
            {"tier_index": [1], "original_price": 15.98, "model_sku": "SKU-VERM", "normal_stock": 5},
        ]
        products.init_tier_variation(58262112365, tier, modelos, loja_id=7)
        endpoint, params = mock_request.call_args[0][:2]
        self.assertEqual(endpoint, "product/init_tier_variation")
        self.assertEqual(params["item_id"], 58262112365)
        self.assertEqual(params["tier_variation"], tier)
        self.assertEqual(params["model"], modelos)
        self.assertNotIn("model_list", params)
        self.assertEqual(mock_request.call_args.kwargs.get("method"), "POST")


class TestAddModel(unittest.TestCase):

    @patch("shopee.products._request")
    def test_monta_payload_com_chave_model_list(self, mock_request):
        mock_request.return_value = {"response": {}}
        novo_modelo = [{"tier_index": [2], "original_price": 15.98, "model_sku": "SKU-VERDE", "normal_stock": 8}]
        products.add_model(58262112365, novo_modelo, loja_id=7)
        endpoint, params = mock_request.call_args[0][:2]
        self.assertEqual(endpoint, "product/add_model")
        self.assertEqual(params["item_id"], 58262112365)
        self.assertEqual(params["model_list"], novo_modelo)


class TestUpdateTierVariation(unittest.TestCase):

    @patch("shopee.products._request")
    def test_preserva_model_id_existentes(self, mock_request):
        mock_request.return_value = {"response": {}}
        tier = [{"name": "Cor", "option_list": [{"option": "Azul"}, {"option": "Preto"}]}]
        mapeamento = [{"tier_index": [0], "model_id": 111}, {"tier_index": [1], "model_id": 222}]
        products.update_tier_variation(58262112365, tier, mapeamento, loja_id=7)
        endpoint, params = mock_request.call_args[0][:2]
        self.assertEqual(endpoint, "product/update_tier_variation")
        self.assertEqual(params["model_list"], mapeamento)


class TestDeleteModel(unittest.TestCase):
    """model_id e' singular, nao uma lista — confirmado contra a API real:
    {"model_id_list": [...]} retorna 'ModelId is required'; so' funciona com
    {"model_id": 111}."""

    @patch("shopee.products._request")
    def test_monta_payload_com_model_id_singular(self, mock_request):
        mock_request.return_value = {"response": {}}
        products.delete_model(58262112365, 111, loja_id=7)
        endpoint, params = mock_request.call_args[0][:2]
        self.assertEqual(endpoint, "product/delete_model")
        self.assertEqual(params["item_id"], 58262112365)
        self.assertEqual(params["model_id"], 111)
        self.assertNotIn("model_id_list", params)


if __name__ == "__main__":
    unittest.main(verbosity=2)
