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
            [{"sku": "SKU1", "shop_id": "222", "estoque": 0}],           # pares (so' tem anuncio na loja 2)
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
    def test_sem_saldo_local_usa_estoque_ja_sincronizado_da_shopee(self, mock_get_db, mock_lojas, mock_efetiva):
        """Achado real: a grade de /estoque/rapido sempre mostrava 0 pra
        qualquer SKU/loja sem registro em estoque_lojas (cadastro manual do
        Athena), mesmo quando a Shopee ja tinha reportado o estoque real via
        sync_produtos (coluna anuncios.estoque, mesmo dado que aparece em
        /integracoes/shopee/produtos). Agora usa esse valor como estoque
        inicial em vez de 0 fabricado."""
        mock_lojas.return_value = [{"id": 1, "nome": "Loja A", "shopee_shop_id": "111", "shopee_shop_name": "Shop A"}]
        mock_efetiva.side_effect = lambda nome: nome

        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"sku": "SKU1", "nome": "Produto 1"}],                          # sku_rows
            [{"sku": "SKU1", "shop_id": "111", "estoque": 42}],              # pares (com estoque da Shopee)
            [],                                                              # saldos: nenhum registro em estoque_lojas
        ]
        mock_get_db.return_value = fake_db

        r = estoque_rapido.listar_grid_estoque_rapido(skus=["SKU1"])

        self.assertEqual(r["produtos"][0]["estoque"], {1: 42.0})

    @patch("shopee.estoque_rapido._loja_efetiva_async", new_callable=AsyncMock)
    @patch("shopee.estoque_rapido.listar_lojas_shopee")
    @patch("shopee.estoque_rapido.get_db")
    def test_com_saldo_local_ignora_estoque_da_shopee(self, mock_get_db, mock_lojas, mock_efetiva):
        """Saldo em estoque_lojas (ajustado manualmente/via ledger) e' a fonte
        de verdade quando existe — o fallback da Shopee so' entra na ausencia
        dele, nao sobrescreve um saldo ja gerenciado pelo Athena."""
        mock_lojas.return_value = [{"id": 1, "nome": "Loja A", "shopee_shop_id": "111", "shopee_shop_name": "Shop A"}]
        mock_efetiva.side_effect = lambda nome: nome

        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"sku": "SKU1", "nome": "Produto 1"}],
            [{"sku": "SKU1", "shop_id": "111", "estoque": 42}],
            [{"sku": "SKU1", "loja": "Loja A", "quantidade": 7}],
        ]
        mock_get_db.return_value = fake_db

        r = estoque_rapido.listar_grid_estoque_rapido(skus=["SKU1"])

        self.assertEqual(r["produtos"][0]["estoque"], {1: 7.0})

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
            [{"sku": "SKU1", "shop_id": "111", "estoque": 0}],     # pares
            [{"sku": "SKU1", "loja": "Loja A", "quantidade": 5}],  # saldos
        ]
        mock_get_db.return_value = fake_db

        r = estoque_rapido.listar_grid_estoque_rapido(busca="SKU1", pagina=1, por_pagina=50)

        self.assertEqual(r["total"], 1)
        self.assertEqual(r["produtos"][0]["estoque"], {1: 5.0})
        fake_db.fetchval.assert_called_once()


class TestAtualizarCelulaEstoqueRapido(unittest.TestCase):

    @patch("shopee.estoque_rapido.listar_grid_estoque_rapido")
    @patch("shopee.estoque_rapido.sincronizar_estoque_shopee")
    @patch("shopee.estoque_rapido.ajustar_absoluto")
    @patch("shopee.estoque_rapido.obter")
    def test_sucesso_local_e_shopee(self, mock_obter, mock_ajustar, mock_sync, mock_grid):
        mock_obter.return_value = {"id": 1, "nome": "Loja A"}
        mock_ajustar.return_value = {"ok": True, "sku": "SKU1", "loja": "Loja A", "quantidade": 10, "anterior": 5, "atual": 10}
        mock_sync.return_value = {"success": True}
        mock_grid.return_value = {"produtos": [{"sku": "SKU1", "nome": "Produto 1", "estoque": {1: 10.0}}], "lojas": [], "total": 1}

        r = estoque_rapido.atualizar_celula_estoque_rapido(
            "SKU1", 1, 10, {"user_id": 9, "nome": "Ana"}, "127.0.0.1", "pytest")

        mock_ajustar.assert_called_once_with("SKU1", "Loja A", 10, "ajuste_inventario", 9, "Ana", "127.0.0.1", "pytest")
        mock_sync.assert_called_once_with("SKU1", 10, loja_id=1)
        mock_grid.assert_called_once_with(skus=["SKU1"])
        self.assertEqual(r, {
            "ok": True, "salvo_local": True, "erro_shopee": None,
            "linha": {"sku": "SKU1", "nome": "Produto 1", "estoque": {1: 10.0}},
        })

    @patch("shopee.estoque_rapido.listar_grid_estoque_rapido")
    @patch("shopee.estoque_rapido.sincronizar_estoque_shopee")
    @patch("shopee.estoque_rapido.ajustar_absoluto")
    @patch("shopee.estoque_rapido.obter")
    def test_sucesso_com_envelope_real_da_shopee_open_platform(self, mock_obter, mock_ajustar, mock_sync, mock_grid):
        """A Shopee Open Platform v2 SEMPRE devolve a chave "error" — vazia em
        sucesso, com codigo em falha. Este teste usa o envelope real (nao a
        forma ficticia {"success": True}) pra fixar o contrato: checar so' a
        PRESENCA da chave "error" marcaria isso como falha (bug ja corrigido)."""
        mock_obter.return_value = {"id": 1, "nome": "Loja A"}
        mock_ajustar.return_value = {"ok": True, "sku": "SKU1", "loja": "Loja A", "quantidade": 10, "anterior": 5, "atual": 10}
        mock_sync.return_value = {"error": "", "message": "", "response": {"item_id": 123, "stock_list": []}}
        mock_grid.return_value = {"produtos": [{"sku": "SKU1", "nome": "Produto 1", "estoque": {1: 10.0}}], "lojas": [], "total": 1}

        r = estoque_rapido.atualizar_celula_estoque_rapido(
            "SKU1", 1, 10, {"user_id": 9, "nome": "Ana"}, "127.0.0.1", "pytest")

        self.assertIs(r["ok"], True)
        self.assertIsNone(r["erro_shopee"])
        self.assertEqual(r["salvo_local"], True)

    @patch("shopee.estoque_rapido.ajustar_absoluto")
    @patch("shopee.estoque_rapido.obter")
    def test_loja_nao_encontrada_nao_chama_ajustar(self, mock_obter, mock_ajustar):
        mock_obter.return_value = None

        r = estoque_rapido.atualizar_celula_estoque_rapido(
            "SKU1", 999, 10, {"user_id": 9, "nome": "Ana"})

        self.assertEqual(r, {"ok": False, "erro_local": "Loja 999 nao encontrada"})
        mock_ajustar.assert_not_called()

    @patch("shopee.estoque_rapido.sincronizar_estoque_shopee")
    @patch("shopee.estoque_rapido.ajustar_absoluto")
    @patch("shopee.estoque_rapido.obter")
    def test_falha_local_nao_chama_shopee(self, mock_obter, mock_ajustar, mock_sync):
        mock_obter.return_value = {"id": 1, "nome": "Loja A"}
        mock_ajustar.return_value = {"erro": "saldo negativo nao permitido"}

        r = estoque_rapido.atualizar_celula_estoque_rapido(
            "SKU1", 1, -5, {"user_id": 9, "nome": "Ana"})

        self.assertEqual(r, {"ok": False, "erro_local": "saldo negativo nao permitido"})
        mock_sync.assert_not_called()

    @patch("shopee.estoque_rapido.listar_grid_estoque_rapido")
    @patch("shopee.estoque_rapido.sincronizar_estoque_shopee")
    @patch("shopee.estoque_rapido.ajustar_absoluto")
    @patch("shopee.estoque_rapido.obter")
    def test_sucesso_local_falha_shopee(self, mock_obter, mock_ajustar, mock_sync, mock_grid):
        mock_obter.return_value = {"id": 1, "nome": "Loja A"}
        mock_ajustar.return_value = {"ok": True}
        mock_sync.return_value = {"error": "token expirado"}
        mock_grid.return_value = {"produtos": [{"sku": "SKU1", "nome": "Produto 1", "estoque": {1: 10.0}}]}

        r = estoque_rapido.atualizar_celula_estoque_rapido(
            "SKU1", 1, 10, {"user_id": 9, "nome": "Ana"})

        self.assertEqual(r["ok"], False)
        self.assertEqual(r["salvo_local"], True)
        self.assertEqual(r["erro_shopee"], "token expirado")

    @patch("shopee.estoque_rapido.sincronizar_estoque_shopee")
    @patch("shopee.estoque_rapido.ajustar_absoluto")
    @patch("shopee.estoque_rapido.obter")
    def test_sucesso_local_sincronizar_lanca_excecao(self, mock_obter, mock_ajustar, mock_sync):
        mock_obter.return_value = {"id": 1, "nome": "Loja A"}
        mock_ajustar.return_value = {"ok": True}
        mock_sync.side_effect = Exception("malformed anuncio_id: bad_format")

        r = estoque_rapido.atualizar_celula_estoque_rapido(
            "SKU1", 1, 10, {"user_id": 9, "nome": "Ana"})

        self.assertEqual(r["ok"], False)
        self.assertEqual(r["salvo_local"], True)
        self.assertEqual(r["erro_shopee"], "malformed anuncio_id: bad_format")
        self.assertIsNone(r["linha"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
