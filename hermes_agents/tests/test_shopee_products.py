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


if __name__ == "__main__":
    unittest.main(verbosity=2)
