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
        self.executed.append((q, a))
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


class _FakeDBPedidosShopee:
    """Fake DB pra sincronizar_pedidos_shopee — le' de shopee_pedidos_sincronizados
    (ja baixado localmente pelo sync da aba Pedidos) em vez de rechamar a API Shopee,
    o que deixava vendas_pedidos incompleto (achado real: so' 182 de 788 pedidos
    ja sincronizados chegavam la', por causa do limite de 200/chamada + rebusca
    redundante). DRE por Loja soma frete de vendas_pedidos — sem gravar o frete
    real da Shopee aqui, todo pedido Shopee entrava com frete=0, subestimando
    custo/superestimando lucro pra lojas virtuais."""
    def __init__(self, pedidos, itens_por_pedido=None, existing_id=None):
        self.pedidos = pedidos
        self.itens_por_pedido = itens_por_pedido or {}
        self.existing_id = existing_id
        self.executed = []

    async def fetch(self, q, *a):
        if "FROM shopee_pedidos_sincronizados" in q:
            return self.pedidos
        if "FROM shopee_pedidos_itens" in q:
            return self.itens_por_pedido.get(a[0], [])
        return []

    async def fetchval(self, q, *a):
        self.executed.append((q, a))
        if "SELECT id FROM vendas_pedidos" in q:
            return self.existing_id
        if "INSERT INTO vendas_pedidos" in q:
            return 88
        return None

    async def fetchrow(self, q, *a):
        return None

    async def execute(self, q, *a):
        self.executed.append((q, a))


from datetime import datetime as _datetime

_PEDIDO_SHOPEE_MOCK = {
    "id": 1, "order_sn": "SN1", "status": "COMPLETED",
    "create_time": _datetime(2026, 7, 20),
    "total_amount": 150.0, "frete": 18.5,
    "recipient_nome": "Cliente Y", "buyer_username": "cliente_y",
    "loja_id_resolvida": 7,
}


class TestSincronizarPedidosShopee(unittest.TestCase):
    @patch("core.lojas.obter_credenciais_shopee", return_value={"shopee_shop_id": "999"})
    def test_grava_frete_do_pedido_shopee(self, mcred):
        db = _FakeDBPedidosShopee(pedidos=[_PEDIDO_SHOPEE_MOCK], existing_id=None)
        async def fake_get_db(): return db
        with patch.object(vendas, "get_db", fake_get_db):
            r = vendas.sincronizar_pedidos_shopee(dias=7, loja_id=7)
        self.assertEqual(r["sync"], 1)
        insert = next(e for e in db.executed if "INSERT INTO vendas_pedidos" in e[0])
        self.assertIn(18.5, insert[1])

    @patch("core.lojas.obter_credenciais_shopee", return_value={"shopee_shop_id": "999"})
    def test_atualiza_pedido_existente_tambem_grava_frete(self, mcred):
        db = _FakeDBPedidosShopee(pedidos=[_PEDIDO_SHOPEE_MOCK], existing_id=33)
        async def fake_get_db(): return db
        with patch.object(vendas, "get_db", fake_get_db):
            r = vendas.sincronizar_pedidos_shopee(dias=7, loja_id=7)
        self.assertEqual(r["sync"], 1)
        update = next(e for e in db.executed if "UPDATE vendas_pedidos" in e[0])
        self.assertIn(18.5, update[1])


class _FakeDBQuery:
    """Fake DB minimo que so' grava as queries+args executadas, pra inspecionar
    SQL/params — usado pra testar o filtro de loja_id em dashboard()/_list_filtered()."""
    def __init__(self, fetchval=0, fetch=None):
        self.executed = []
        self._fetchval = fetchval
        self._fetch = fetch if fetch is not None else []

    async def fetchval(self, q, *a):
        self.executed.append((q, a))
        return self._fetchval

    async def fetch(self, q, *a):
        self.executed.append((q, a))
        return self._fetch

    async def fetchrow(self, q, *a):
        return None

    async def execute(self, q, *a):
        self.executed.append((q, a))
        return "OK"


class TestDashboardFiltroLoja(unittest.TestCase):
    """dashboard() ignorava loja_id inteiramente — todas as 8 queries somavam
    vendas de TODAS as lojas, mesmo com uma loja selecionada no frontend."""

    def test_sem_loja_id_nao_filtra_nenhuma_query(self):
        db = _FakeDBQuery()
        async def fake_get_db(): return db
        with patch.object(vendas, "get_db", fake_get_db):
            vendas.dashboard(dias=30)
        self.assertEqual(len(db.executed), 8)
        for q, a in db.executed:
            self.assertIn(None, a, f"query deveria receber loja_id=None: {q}")

    def test_com_loja_id_filtra_todas_as_8_queries(self):
        db = _FakeDBQuery()
        async def fake_get_db(): return db
        with patch.object(vendas, "get_db", fake_get_db):
            vendas.dashboard(dias=30, loja_id=7)
        self.assertEqual(len(db.executed), 8)
        for q, a in db.executed:
            self.assertIn("loja_id", q, f"query nao tem clausula de loja_id: {q}")
            self.assertIn(7, a, f"query nao recebeu loja_id=7: {q}")


class TestListarFiltradoLoja(unittest.TestCase):
    """_list_filtered()/listar_filtrado() ignoravam loja_id — o parametro nem
    existia. Filtro so' se aplica a vendas_pedidos (unica tabela com a coluna)."""

    def test_filtra_por_loja_em_pedidos(self):
        db = _FakeDBQuery(fetch=[])
        async def fake_get_db(): return db
        with patch.object(vendas, "get_db", fake_get_db):
            vendas.listar_filtrado("pedidos", status="aberto", loja_id=7)
        q, a = db.executed[0]
        self.assertIn("loja_id = $2", q)
        self.assertEqual(a, ("aberto", 7))

    def test_nao_filtra_itens_por_loja_mesmo_se_passado(self):
        """vendas_itens nao tem coluna loja_id — passar loja_id nao deve
        gerar SQL invalido, so' deve ser ignorado silenciosamente."""
        db = _FakeDBQuery(fetch=[])
        async def fake_get_db(): return db
        with patch.object(vendas, "get_db", fake_get_db):
            vendas.listar_filtrado("itens", loja_id=7)
        q, a = db.executed[0]
        self.assertNotIn("loja_id", q)
        self.assertEqual(a, ())


class TestEnriquecerItemPrincipal(unittest.TestCase):
    """enriquecer_item_principal() acrescenta item_principal (descricao do
    item de maior valor_total) e total_itens (contagem) a cada pedido, sem
    tocar em vendas_pedidos — so' consulta vendas_itens."""

    def test_sem_pedidos_retorna_lista_vazia(self):
        self.assertEqual(vendas.enriquecer_item_principal([]), [])

    def test_adiciona_item_principal_e_total_itens(self):
        class _FakeDBItens:
            async def fetch(self, q, *a):
                if "DISTINCT ON" in q:
                    return [
                        {"pedido_id": 1, "descricao": "Produto Caro"},
                        {"pedido_id": 2, "descricao": "Produto Unico"},
                    ]
                if "COUNT(*)" in q:
                    return [{"pedido_id": 1, "qtd": 3}, {"pedido_id": 2, "qtd": 1}]
                return []
        db = _FakeDBItens()
        async def fake_get_db(): return db
        pedidos = [{"id": 1, "cliente": "A"}, {"id": 2, "cliente": "B"}]
        with patch.object(vendas, "get_db", fake_get_db):
            resultado = vendas.enriquecer_item_principal(pedidos)
        self.assertEqual(resultado[0]["item_principal"], "Produto Caro")
        self.assertEqual(resultado[0]["total_itens"], 3)
        self.assertEqual(resultado[1]["item_principal"], "Produto Unico")
        self.assertEqual(resultado[1]["total_itens"], 1)

    def test_pedido_sem_item_correspondente_fica_com_none_e_zero(self):
        """Nao deveria acontecer na pratica (todo pedido tem >=1 item), mas
        a funcao nao pode quebrar se a busca por id nao achar nada."""
        class _FakeDBVazio:
            async def fetch(self, q, *a):
                return []
        db = _FakeDBVazio()
        async def fake_get_db(): return db
        pedidos = [{"id": 99, "cliente": "Sem Itens"}]
        with patch.object(vendas, "get_db", fake_get_db):
            resultado = vendas.enriquecer_item_principal(pedidos)
        self.assertIsNone(resultado[0]["item_principal"])
        self.assertEqual(resultado[0]["total_itens"], 0)

    def test_erro_de_query_devolve_pedidos_sem_os_campos_novos(self):
        class _FakeDBErro:
            async def fetch(self, q, *a):
                raise Exception("boom")
        db = _FakeDBErro()
        async def fake_get_db(): return db
        pedidos = [{"id": 1, "cliente": "A"}]
        with patch.object(vendas, "get_db", fake_get_db):
            resultado = vendas.enriquecer_item_principal(pedidos)
        self.assertEqual(resultado, [{"id": 1, "cliente": "A"}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
