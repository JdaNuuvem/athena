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
    def test_sync_produtos_grava_fichas_tecnicas_antes_de_anuncio(self, mock_get_db, mock_get_items, mock_get_base, mock_cfg):
        """Bug real em producao: anuncios.sku tem FK pra fichas_tecnicas(sku)
        (ver hermes_agents/sql/schema.sql). _upsert_anuncio inseria em anuncios
        ANTES de fichas_tecnicas — pra SKU nunca sincronizado antes (ainda nao
        existe em fichas_tecnicas), o INSERT em anuncios violava a FK e o
        produto nunca gravava. Precisa gravar fichas_tecnicas primeiro."""
        mock_cfg.return_value = {"shop_id": "1782908877"}
        mock_get_items.return_value = {"response": {"item": [{"item_id": 999}], "has_next_page": False, "next_offset": 0}}
        mock_get_base.return_value = {"response": {"item_list": [{
            "item_id": 999, "item_sku": "SKU-NOVO", "item_name": "Produto Nunca Sincronizado",
            "item_status": "NORMAL",
            "price_info": [{"current_price": 15.0}],
            "stock_info_v2": {"summary_info": {"total_available_stock": 3}},
        }]}}
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 1
        mock_get_db.return_value = fake_db

        shopee_sync.run_async(shopee_sync.sync_produtos(loja_id=7))

        chamadas = fake_db.execute.call_args_list
        idx_fichas = next(i for i, c in enumerate(chamadas) if "INSERT INTO fichas_tecnicas" in c.args[0])
        idx_anuncio = next(i for i, c in enumerate(chamadas) if "INSERT INTO anuncios" in c.args[0])
        self.assertLess(idx_fichas, idx_anuncio, "fichas_tecnicas precisa ser gravado antes de anuncios (FK anuncios_sku_fkey)")

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

    @patch("shopee_sync.get_shopee_config")
    @patch("shopee_sync.get_item_base_info")
    @patch("shopee_sync.get_items")
    @patch("shopee_sync.get_db")
    def test_sync_produtos_grava_imagem_do_item(self, mock_get_db, mock_get_items, mock_get_base, mock_cfg):
        """A aba Produtos da Shopee nao mostrava nenhuma foto porque sync_produtos
        nunca lia o campo "image" da resposta do get_item_base_info — a imagem_url
        gravada em anuncios so' vinha (por acaso) do catalogo interno via JOIN."""
        mock_cfg.return_value = {"shop_id": "1782908877"}
        mock_get_items.return_value = {"response": {"item": [{"item_id": 444}], "has_next_page": False, "next_offset": 0}}
        mock_get_base.return_value = {"response": {"item_list": [{
            "item_id": 444, "item_sku": "SKU-FOTO", "item_name": "Produto Com Foto",
            "item_status": "NORMAL",
            "price_info": [{"current_price": 19.9}],
            "stock_info_v2": {"summary_info": {"total_available_stock": 5}},
            "image": {"image_url_list": ["https://cf.shopee.com.br/file/abc123"], "image_id_list": ["abc123"]},
        }]}}
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 1
        mock_get_db.return_value = fake_db

        shopee_sync.run_async(shopee_sync.sync_produtos(loja_id=7))

        insert_call = next(c for c in fake_db.execute.call_args_list if "INSERT INTO anuncios" in c.args[0])
        self.assertIn("https://cf.shopee.com.br/file/abc123", insert_call.args)

    @patch("shopee_sync.get_shopee_config")
    @patch("shopee_sync.get_model_list")
    @patch("shopee_sync.get_item_base_info")
    @patch("shopee_sync.get_items")
    @patch("shopee_sync.get_db")
    def test_sync_produtos_com_variacao_grava_imagem_do_item_pai_em_cada_modelo(self, mock_get_db, mock_get_items, mock_get_base, mock_get_models, mock_cfg):
        """Shopee guarda a foto no nivel do item pai, nao por variacao — cada
        linha de modelo deve herdar essa mesma imagem_url."""
        mock_cfg.return_value = {"shop_id": "1782908877"}
        mock_get_items.return_value = {"response": {"item": [{"item_id": 555}], "has_next_page": False, "next_offset": 0}}
        mock_get_base.return_value = {"response": {"item_list": [{
            "item_id": 555, "item_sku": "BAR-FOTO-MASTER", "item_name": "Lamina Com Foto",
            "item_status": "NORMAL", "has_model": True,
            "price_info": [{"current_price": 0}],
            "image": {"image_url_list": ["https://cf.shopee.com.br/file/pai999"]},
        }]}}
        mock_get_models.return_value = {"response": {"model": [
            {"model_id": 1, "model_name": "1 Unidade", "model_sku": "BAR-FOTO-MASTER-1UN",
             "price_info": [{"current_price": 27.99}],
             "stock_info_v2": {"summary_info": {"total_available_stock": 10}}},
        ]}}
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 1
        mock_get_db.return_value = fake_db

        shopee_sync.run_async(shopee_sync.sync_produtos(loja_id=7))

        insert_call = next(c for c in fake_db.execute.call_args_list if "INSERT INTO anuncios" in c.args[0])
        self.assertIn("https://cf.shopee.com.br/file/pai999", insert_call.args)

    @patch("shopee_sync.get_shopee_config")
    @patch("shopee_sync.get_model_list")
    @patch("shopee_sync.get_item_base_info")
    @patch("shopee_sync.get_items")
    @patch("shopee_sync.get_db")
    def test_sync_produtos_com_variacao_grava_1_linha_por_modelo(self, mock_get_db, mock_get_items, mock_get_base, mock_get_models, mock_cfg):
        """Produto com has_model=True nao tem preco/estoque no nivel do item —
        price_info/stock_info_v2 vem zerados. O preco/estoque real esta em cada
        variacao (model), obtido via get_model_list(). Sem isso, produtos com
        variacao sempre sincronizavam com preco R$ 0,00."""
        mock_cfg.return_value = {"shop_id": "1782908877"}
        mock_get_items.return_value = {"response": {"item": [{"item_id": 333}], "has_next_page": False, "next_offset": 0}}
        mock_get_base.return_value = {"response": {"item_list": [{
            "item_id": 333, "item_sku": "BAR-LAM-MASTER", "item_name": "Lamina Master",
            "item_status": "NORMAL", "has_model": True,
            "price_info": [{"current_price": 0}],
        }]}}
        mock_get_models.return_value = {"response": {"model": [
            {"model_id": 1, "model_name": "1 Unidade", "model_sku": "BAR-LAM-MASTER-1UN",
             "price_info": [{"current_price": 27.99}],
             "stock_info_v2": {"summary_info": {"total_available_stock": 10}}},
            {"model_id": 2, "model_name": "2 Unidades", "model_sku": "BAR-LAM-MASTER-2UN",
             "price_info": [{"current_price": 54.29}],
             "stock_info_v2": {"summary_info": {"total_available_stock": 5}}},
            {"model_id": 3, "model_name": "3 Unidades", "model_sku": "BAR-LAM-MASTER-3UN",
             "price_info": [{"current_price": 79.99}],
             "stock_info_v2": {"summary_info": {"total_available_stock": 3}}},
        ]}}
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 1
        mock_get_db.return_value = fake_db

        r = shopee_sync.run_async(shopee_sync.sync_produtos(loja_id=7))

        self.assertEqual(r["total"], 3)
        mock_get_models.assert_called_once_with(333, loja_id=7)
        inserts = [c for c in fake_db.execute.call_args_list if "INSERT INTO anuncios" in c.args[0]]
        self.assertEqual(len(inserts), 3)
        skus_gravados = {c.args[1] for c in inserts}
        self.assertEqual(skus_gravados, {"BAR-LAM-MASTER-1UN", "BAR-LAM-MASTER-2UN", "BAR-LAM-MASTER-3UN"})
        precos_gravados = {c.args[1]: c.args[5] for c in inserts}
        self.assertEqual(precos_gravados["BAR-LAM-MASTER-2UN"], 54.29)

    @patch("shopee_sync.get_shopee_config")
    @patch("shopee_sync.get_model_list")
    @patch("shopee_sync.get_item_base_info")
    @patch("shopee_sync.get_items")
    @patch("shopee_sync.get_db")
    def test_sync_produtos_com_variacao_remove_registro_orfao_do_item_pai(self, mock_get_db, mock_get_items, mock_get_base, mock_get_models, mock_cfg):
        """Sincronizacoes anteriores a este suporte gravavam o item pai como se
        fosse produto simples (sku=item_sku, preco=0). Ao detectar has_model=True
        agora, precisa remover essa linha orfa (anuncio_id = item_id puro), senao
        ela fica pendurada na listagem mostrando R$ 0,00 pra sempre."""
        mock_cfg.return_value = {"shop_id": "1782908877"}
        mock_get_items.return_value = {"response": {"item": [{"item_id": 333}], "has_next_page": False, "next_offset": 0}}
        mock_get_base.return_value = {"response": {"item_list": [{
            "item_id": 333, "item_sku": "BEM-CALC-UN", "item_name": "Calcanheira",
            "item_status": "NORMAL", "has_model": True,
        }]}}
        mock_get_models.return_value = {"response": {"model": [
            {"model_id": 1, "model_name": "Azul,1UN", "model_sku": "BEM-CALC-AZUL-1UN",
             "price_info": [{"current_price": 15.98}],
             "stock_info_v2": {"summary_info": {"total_available_stock": 0}}},
        ]}}
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 1
        mock_get_db.return_value = fake_db

        shopee_sync.run_async(shopee_sync.sync_produtos(loja_id=7))

        deletes = [c for c in fake_db.execute.call_args_list if "DELETE FROM anuncios" in c.args[0]]
        self.assertEqual(len(deletes), 1)
        self.assertEqual(deletes[0].args[1:], ("1782908877", "333"))

    @patch("shopee_sync.get_shopee_config")
    @patch("shopee_sync.get_model_list")
    @patch("shopee_sync.get_item_base_info")
    @patch("shopee_sync.get_items")
    @patch("shopee_sync.get_db")
    def test_sync_produtos_erro_no_get_model_list_nao_derruba_sync(self, mock_get_db, mock_get_items, mock_get_base, mock_get_models, mock_cfg):
        mock_cfg.return_value = {"shop_id": "1782908877"}
        mock_get_items.return_value = {"response": {"item": [{"item_id": 333}], "has_next_page": False, "next_offset": 0}}
        mock_get_base.return_value = {"response": {"item_list": [{
            "item_id": 333, "item_sku": "X", "item_name": "X", "item_status": "NORMAL", "has_model": True,
        }]}}
        mock_get_models.return_value = {"error": "item_not_found", "message": "item nao encontrado"}
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 1
        mock_get_db.return_value = fake_db

        r = shopee_sync.run_async(shopee_sync.sync_produtos(loja_id=7))

        self.assertEqual(r["total"], 0)
        self.assertEqual(r["erros"], 1)


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

    @patch("shopee_sync.get_shopee_config")
    @patch("shopee_sync.get_db")
    def test_lista_produtos_prefere_imagem_da_shopee_sobre_catalogo_interno(self, mock_get_db, mock_cfg):
        """imagem_url deve vir da propria Shopee (coluna gravada por sync_produtos)
        quando disponivel — o catalogo interno (catalogo_produtos) e' so' fallback
        pra SKUs que a Shopee ainda nao tem foto."""
        mock_cfg.return_value = {"shop_id": "1782908877"}
        fake_db = AsyncMock()
        mock_get_db.return_value = fake_db

        shopee_sync.listar_produtos_sincronizados(7)

        query = fake_db.fetch.call_args.args[0]
        self.assertIn("a.imagem_url", query)
        self.assertIn("COALESCE", query)

    @patch("shopee_sync.get_shopee_config", return_value={})
    def test_loja_sem_shop_id_retorna_vazio(self, mock_cfg):
        r = shopee_sync.listar_produtos_sincronizados(999)
        self.assertEqual(r, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
