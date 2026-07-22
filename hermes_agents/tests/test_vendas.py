"""Testes unitarios — Vendas / Sync de pedidos Bling."""
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

import core.vendas as vendas


class _FakeDBPedidos:
    """Fake DB minimo para testar sincronizar_pedidos_bling sem banco real."""
    def __init__(self, existing_id=None):
        self.existing_id = existing_id
        self.executed = []
        self.deleted_itens_pedido_id = None
        self.deleted_pagamentos_pedido_id = None

    async def fetchval(self, q, *a):
        if "SELECT id FROM vendas_pedidos" in q:
            return self.existing_id
        if "INSERT INTO vendas_pedidos" in q:
            return 88
        return 1

    async def fetchrow(self, q, *a):
        return None

    async def execute(self, q, *a):
        self.executed.append((q, a))
        if "DELETE FROM vendas_itens" in q:
            self.deleted_itens_pedido_id = a[0]
        if "DELETE FROM vendas_pagamentos" in q:
            self.deleted_pagamentos_pedido_id = a[0]


_PEDIDO_DETALHE_MOCK = {
    "id": 555, "numero": "2001", "data": "2026-07-20", "total": 500.0,
    "contato": {"nome": "Cliente X", "numeroDocumento": "11122233344"},
    "situacao": {"id": 15}, "loja": {"id": 1},
    "vendedor": {"contato": {"nome": "Joao Vendedor"}},
    "transporte": {"frete": 25.0, "transportadora": {"nome": "Transportadora ABC"}},
    "itens": [{"codigo": "SKU1", "descricao": "Item 1", "quantidade": 2,
               "valorUnitario": 200.0, "valor": 400.0}],
    "parcelas": [
        {"valor": 250.0, "data": "2026-08-20", "formaPagamento": {"descricao": "Boleto"}},
        {"valor": 250.0, "data": "2026-09-20", "formaPagamento": {"descricao": "Boleto"}},
    ],
}


class TestSincronizarPedidosBling(unittest.TestCase):
    @patch("bling_erp.get_access_token", return_value="")
    def test_sem_token(self, mt):
        r = vendas.sincronizar_pedidos_bling()
        self.assertIn("error", r)

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_pedidos", return_value={"data": []})
    def test_sem_pedidos(self, ml, mt):
        r = vendas.sincronizar_pedidos_bling()
        self.assertEqual(r["sync"], 0)

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_pedidos", return_value={"data": [{"id": 555}]})
    @patch("bling_erp.get_pedido_detalhe", return_value={"data": _PEDIDO_DETALHE_MOCK})
    def test_cria_pedido_com_frete_vendedor_parcelas(self, mdet, ml, mt):
        db = _FakeDBPedidos(existing_id=None)
        async def fake_get_db(): return db
        with patch.object(vendas, "get_db", fake_get_db):
            r = vendas.sincronizar_pedidos_bling()
        self.assertEqual(r["sync"], 1)
        insert_pagamentos = [e for e in db.executed if "INSERT INTO vendas_pagamentos" in e[0]]
        self.assertEqual(len(insert_pagamentos), 2)  # 2 parcelas viram 2 linhas

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_pedidos", return_value={"data": [{"id": 555}]})
    @patch("bling_erp.get_pedido_detalhe", return_value={"data": _PEDIDO_DETALHE_MOCK})
    def test_atualiza_pedido_existente_refaz_itens_e_pagamentos(self, mdet, ml, mt):
        db = _FakeDBPedidos(existing_id=33)
        async def fake_get_db(): return db
        with patch.object(vendas, "get_db", fake_get_db):
            r = vendas.sincronizar_pedidos_bling()
        self.assertEqual(r["sync"], 1)
        self.assertEqual(db.deleted_itens_pedido_id, 33)
        self.assertEqual(db.deleted_pagamentos_pedido_id, 33)

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_pedidos", return_value={"data": [{"id": 555}]})
    @patch("bling_erp.get_pedido_detalhe", return_value={"error": "falhou"})
    def test_fallback_para_resumo_quando_detalhe_falha(self, mdet, ml, mt):
        db = _FakeDBPedidos(existing_id=None)
        async def fake_get_db(): return db
        with patch.object(vendas, "get_db", fake_get_db):
            r = vendas.sincronizar_pedidos_bling()
        self.assertEqual(r["sync"], 1)
        self.assertTrue(any("555" in e for e in r["erros"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
