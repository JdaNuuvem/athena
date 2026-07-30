"""
Testes de shopee_sync.py — persistencia de produtos sincronizados (tabela
anuncios) e leitura desses dados para a aba "Produtos" da Shopee.

Contexto: sync_all_items() (usado antes por essa rota) buscava produtos na
Shopee mas nunca persistia nada — o botao "Sincronizar" mostrava a contagem
e descartava os dados. sync_produtos() ja gravava em anuncios/fichas_tecnicas,
mas nunca guardava o estoque (variavel calculada e nunca usada). Corrigido
para gravar estoque e exposto listar_produtos_sincronizados() para a UI.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock
import unittest

# Mock DB pool global (mesmo padrao de test_shopee_flow.py) para os imports no
# topo do modulo (core.lojas._ensure_shopee_cols roda no import) nao tentarem
# uma conexao real ao Postgres de producao.
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

import shopee_sync


class TestSyncProdutosGravaEstoque(unittest.TestCase):

    @patch("shopee_sync.get_shopee_config")
    @patch("shopee_sync.get_item_base_info")
    @patch("shopee_sync.get_items")
    @patch("shopee_sync.get_db")
    def test_sync_produtos_grava_estoque_no_insert(self, mock_get_db, mock_get_items, mock_get_base, mock_cfg):
        mock_cfg.return_value = {"shop_id": "1782908877"}
        mock_get_items.return_value = {"response": {"item": [{"item_id": 111}], "has_next_page": False, "next_offset": 0}}
        mock_get_base.return_value = {"response": {"item_list": [{
            "item_id": 111, "item_sku": "SKU-1", "item_name": "Produto Teste",
            "item_status": "NORMAL",
            "price_info": [{"current_price": 49.9}],
            "stock_info_v2": {"summary_info": {"total_available_stock": 25}},
        }]}}
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 1
        mock_get_db.return_value = fake_db

        r = shopee_sync.run_async(shopee_sync.sync_produtos(loja_id=7))

        self.assertEqual(r["total"], 1)
        self.assertEqual(r["erros"], 0)
        insert_call = next(c for c in fake_db.execute.call_args_list if "INSERT INTO anuncios" in c.args[0])
        self.assertIn(25, insert_call.args)
        self.assertIn("SKU-1", insert_call.args)

    @patch("shopee_sync.get_shopee_config")
    @patch("shopee_sync.get_item_base_info")
    @patch("shopee_sync.get_items")
    @patch("shopee_sync.get_db")
    def test_sync_produtos_sem_estoque_grava_zero(self, mock_get_db, mock_get_items, mock_get_base, mock_cfg):
        mock_cfg.return_value = {"shop_id": "1782908877"}
        mock_get_items.return_value = {"response": {"item": [{"item_id": 222}], "has_next_page": False, "next_offset": 0}}
        mock_get_base.return_value = {"response": {"item_list": [{
            "item_id": 222, "item_sku": "SKU-2", "item_name": "Sem stock_info_v2",
            "item_status": "NORMAL",
            "price_info": [{"current_price": 10.0}],
        }]}}
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 1
        mock_get_db.return_value = fake_db

        r = shopee_sync.run_async(shopee_sync.sync_produtos(loja_id=7))

        self.assertEqual(r["total"], 1)
        insert_call = next(c for c in fake_db.execute.call_args_list if "INSERT INTO anuncios" in c.args[0])
        self.assertIn(0, insert_call.args)

    @patch("shopee_sync.get_shopee_config")
    @patch("shopee_sync.get_item_base_info")
    @patch("shopee_sync.get_items")
    @patch("shopee_sync.get_db")
    def test_sync_produtos_pagina_com_mais_de_50_itens_fatia_lotes(self, mock_get_db, mock_get_items, mock_get_base, mock_cfg):
        """get_item_base_info rejeita mais de 50 IDs por chamada ('value must
        contain between 1 and 50 items, inclusive') — get_items traz ate 100
        por pagina, entao sync_produtos precisa fatiar em lotes de 50."""
        mock_cfg.return_value = {"shop_id": "1782908877"}
        items_pagina = [{"item_id": i} for i in range(1, 76)]  # 75 itens numa so pagina
        mock_get_items.return_value = {"response": {"item": items_pagina, "has_next_page": False, "next_offset": 0}}

        def fake_get_base_info(ids, loja_id=None):
            self.assertLessEqual(len(ids), 50)
            return {"response": {"item_list": [{
                "item_id": i, "item_sku": f"SKU-{i}", "item_name": f"Produto {i}",
                "item_status": "NORMAL", "price_info": [{"current_price": 10.0}],
                "stock_info_v2": {"summary_info": {"total_available_stock": 1}},
            } for i in ids]}}
        mock_get_base.side_effect = fake_get_base_info

        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 1
        mock_get_db.return_value = fake_db

        r = shopee_sync.run_async(shopee_sync.sync_produtos(loja_id=7))

        self.assertEqual(r["total"], 75)
        self.assertEqual(mock_get_base.call_count, 2)  # lotes de 50 + 25


class TestListarProdutosSincronizados(unittest.TestCase):

    @patch("shopee_sync.get_shopee_config")
    @patch("shopee_sync.get_db")
    def test_lista_produtos_da_loja(self, mock_get_db, mock_cfg):
        mock_cfg.return_value = {"shop_id": "1782908877"}
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "SKU-1", "titulo": "Produto Teste", "preco": 49.9, "estoque": 25,
             "status": "normal", "anuncio_id": "111", "ultima_atualizacao": None},
        ]
        mock_get_db.return_value = fake_db

        r = shopee_sync.listar_produtos_sincronizados(7)

        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["sku"], "SKU-1")
        self.assertEqual(r[0]["estoque"], 25)

    @patch("shopee_sync.get_shopee_config", return_value={})
    def test_loja_sem_shop_id_retorna_vazio(self, mock_cfg):
        r = shopee_sync.listar_produtos_sincronizados(999)
        self.assertEqual(r, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
