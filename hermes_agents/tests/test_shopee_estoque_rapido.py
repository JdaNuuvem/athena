"""Testes de shopee/estoque_rapido.py — grid SKU x loja Shopee (aba Estoque
Rapido) e salvamento de 1 celula com sync sincrono pra Shopee."""
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

import shopee.estoque_rapido as estoque_rapido


class TestListarGridEstoqueRapido(unittest.TestCase):

    @patch("shopee.estoque_rapido._loja_efetiva_async", new_callable=AsyncMock)
    @patch("shopee.estoque_rapido.listar_lojas_shopee")
    @patch("shopee.estoque_rapido.get_db")
    def test_grid_resolve_anuncio_ausente_e_loja_vinculada(self, mock_get_db, mock_lojas, mock_efetiva):
        mock_lojas.return_value = [
            {"id": 1, "nome": "Loja A", "shopee_shop_id": "111", "shopee_shop_name": "Shop A"},
            {"id": 2, "nome": "Loja Virtual B", "shopee_shop_id": "222", "shopee_shop_name": "Shop B"},
        ]
        # Loja A nao tem vinculo (efetiva = ela mesma). Loja Virtual B e' vinculada
        # a "Loja Fisica X" — o saldo mora la', nao sob o proprio nome dela.
        mock_efetiva.side_effect = lambda nome: {"Loja A": "Loja A", "Loja Virtual B": "Loja Fisica X"}[nome]

        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"sku": "SKU1", "nome": "Produto 1"}],                      # sku_rows
            [{"sku": "SKU1", "shop_id": "222"}],                         # pares (so' tem anuncio na loja 2)
            [{"sku": "SKU1", "loja": "Loja Fisica X", "quantidade": 25}],  # saldos
        ]
        mock_get_db.return_value = fake_db

        r = estoque_rapido.listar_grid_estoque_rapido(skus=["SKU1"])

        self.assertEqual(r["produtos"], [
            {"sku": "SKU1", "nome": "Produto 1", "estoque": {1: None, 2: 25.0}}
        ])
        self.assertEqual(r["total"], 1)
        fake_db.fetchval.assert_not_called()  # skus= bypassa contagem/paginacao

    @patch("shopee.estoque_rapido.listar_lojas_shopee")
    @patch("shopee.estoque_rapido.get_db")
    def test_sem_lojas_shopee_retorna_vazio(self, mock_get_db, mock_lojas):
        mock_lojas.return_value = []
        fake_db = AsyncMock()
        mock_get_db.return_value = fake_db

        r = estoque_rapido.listar_grid_estoque_rapido(busca="qualquer")

        self.assertEqual(r, {"lojas": [], "produtos": [], "total": 0})
        fake_db.fetch.assert_not_called()

    @patch("shopee.estoque_rapido._loja_efetiva_async", new_callable=AsyncMock)
    @patch("shopee.estoque_rapido.listar_lojas_shopee")
    @patch("shopee.estoque_rapido.get_db")
    def test_busca_com_paginacao_usa_fetchval_para_total(self, mock_get_db, mock_lojas, mock_efetiva):
        mock_lojas.return_value = [{"id": 1, "nome": "Loja A", "shopee_shop_id": "111", "shopee_shop_name": "Shop A"}]
        mock_efetiva.side_effect = lambda nome: nome

        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 1
        fake_db.fetch.side_effect = [
            [{"sku": "SKU1", "nome": "Produto 1"}],                # sku_rows (pagina)
            [{"sku": "SKU1", "shop_id": "111"}],                   # pares
            [{"sku": "SKU1", "loja": "Loja A", "quantidade": 5}],  # saldos
        ]
        mock_get_db.return_value = fake_db

        r = estoque_rapido.listar_grid_estoque_rapido(busca="SKU1", pagina=1, por_pagina=50)

        self.assertEqual(r["total"], 1)
        self.assertEqual(r["produtos"][0]["estoque"], {1: 5.0})
        fake_db.fetchval.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
