"""
Testes de shopee/stock.py — sincronizar_estoque_shopee() (botao "Enviar" da
aba Produtos Shopee).

Contexto: produtos com variacao (has_model=True) gravam anuncio_id no formato
"item_id_model_id" (ver shopee_sync.sync_produtos) em vez de so' o item_id
numerico puro. sincronizar_estoque_shopee() fazia int(anuncio_id) direto, o
que quebra com ValueError para SKUs de variacao — e mesmo corrigindo o parse,
o payload de update_stock precisa do model_id, senao a Shopee rejeita/ignora
o update em item com modelos (nao existe estoque no nivel do item nesse caso).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock
import unittest

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

import shopee.stock as stock


class TestSincronizarEstoqueShopee(unittest.TestCase):

    @patch("shopee.stock.update_stock")
    @patch("shopee.stock.get_shopee_config")
    @patch("shopee.stock.get_db")
    def test_produto_sem_variacao_usa_item_id_direto(self, mock_get_db, mock_cfg, mock_update):
        mock_cfg.return_value = {"shop_id": "1782908877"}
        fake_db = AsyncMock()
        fake_db.fetchrow.return_value = {"anuncio_id": "58259837432"}
        mock_get_db.return_value = fake_db
        mock_update.return_value = {"success": True}

        r = stock.sincronizar_estoque_shopee("SKU-SEM-VAR", 10, loja_id=7)

        mock_update.assert_called_once_with(58259837432, [{"seller_stock": [{"stock": 10}]}], loja_id=7)
        self.assertEqual(r, {"success": True})

    @patch("shopee.stock.update_stock")
    @patch("shopee.stock.get_shopee_config")
    @patch("shopee.stock.get_db")
    def test_produto_com_variacao_inclui_model_id(self, mock_get_db, mock_cfg, mock_update):
        mock_cfg.return_value = {"shop_id": "1782908877"}
        fake_db = AsyncMock()
        fake_db.fetchrow.return_value = {"anuncio_id": "333_1"}
        mock_get_db.return_value = fake_db
        mock_update.return_value = {"success": True}

        r = stock.sincronizar_estoque_shopee("BAR-LAM-MASTER-1UN", 10, loja_id=7)

        mock_update.assert_called_once_with(333, [{"model_id": 1, "seller_stock": [{"stock": 10}]}], loja_id=7)

    @patch("shopee.stock.get_shopee_config")
    @patch("shopee.stock.get_db")
    def test_sku_sem_anuncio_id_retorna_erro(self, mock_get_db, mock_cfg):
        mock_cfg.return_value = {"shop_id": "1782908877"}
        fake_db = AsyncMock()
        fake_db.fetchrow.return_value = None
        mock_get_db.return_value = fake_db

        r = stock.sincronizar_estoque_shopee("SKU-INEXISTENTE", 10, loja_id=7)

        self.assertIn("error", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
