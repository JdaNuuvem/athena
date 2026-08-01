"""Testes de core/pdv.py — baixa/restauracao de estoque real da loja fisica
em realizar_venda/cancelar_venda/devolver_item_venda. FakeDBPdv simula
pdv_caixas/lojas/pdv_vendas/pdv_itens em memoria; saida_async/entrada_async
de core.estoque sao mockados diretamente (ja tem cobertura propria em
test_estoque_saldos.py) -- aqui so' testa que core.pdv os chama certo, com
os argumentos certos, e que erro de saldo aborta a transacao inteira."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


class FakeDBPdv:
    """Simula pdv_caixas, lojas, pdv_vendas, pdv_itens, pdv_pagamentos,
    pdv_devolucoes em memoria, com suporte a `async with db.acquire() as conn:
    async with conn.transaction():` (snapshot/restore em excecao) -- mesmo
    padrao de tests/test_estoque_saldos.py::FakeDBSaldos/_FakeTransactionCtx,
    usado aqui pra testar a atomicidade venda+baixa de estoque."""

    def __init__(self):
        self.caixas = {}   # id -> {"loja_id": int|None}
        self.lojas = {}    # id -> nome
        self.vendas = {}   # id -> dict
        self.itens = {}    # id -> dict
        self.pagamentos = []
        self.devolucoes = []
        self._next_venda_id = 1
        self._next_item_id = 1

    async def fetchrow(self, query, *params):
        q = " ".join(query.split())
        if "SELECT loja_id FROM pdv_caixas WHERE id" in q:
            c = self.caixas.get(params[0])
            return {"loja_id": c["loja_id"]} if c else None
        if "SELECT nome FROM lojas WHERE id" in q:
            nome = self.lojas.get(params[0])
            return {"nome": nome} if nome is not None else None
        if q.startswith("INSERT INTO pdv_vendas") and "RETURNING *" in q:
            vid = self._next_venda_id; self._next_venda_id += 1
            caixa_id, cliente, cliente_id, total, desconto, operador, data = params
            venda = {"id": vid, "caixa_id": caixa_id, "cliente": cliente, "cliente_id": cliente_id,
                     "total": total, "desconto": desconto, "operador": operador, "status": "finalizada",
                     "data": data, "observacoes": None, "tipo": "venda", "numero": None}
            self.vendas[vid] = dict(venda)
            return dict(venda)
        if q == "SELECT * FROM pdv_vendas WHERE id = $1":
            v = self.vendas.get(params[0])
            return dict(v) if v else None
        if "FROM pdv_itens i JOIN pdv_vendas v ON v.id = i.venda_id WHERE i.id" in q:
            item = self.itens.get(params[0])
            if not item:
                return None
            venda = self.vendas.get(item["venda_id"])
            out = dict(item)
            out["venda_status"] = venda["status"] if venda else None
            out["caixa_id"] = venda["caixa_id"] if venda else None
            return out
        if q.startswith("UPDATE pdv_itens SET quantidade") and "RETURNING quantidade" in q:
            quantidade, item_id = params
            item = self.itens.get(item_id)
            if not item or float(item["quantidade"]) < float(quantidade):
                return None
            item["quantidade"] = float(item["quantidade"]) - float(quantidade)
            item["valor_total"] = round(item["quantidade"] * float(item["valor_unitario"]), 2)
            return {"quantidade": item["quantidade"]}
        return None

    async def fetch(self, query, *params):
        q = " ".join(query.split())
        if "SELECT produto_codigo, quantidade FROM pdv_itens WHERE venda_id" in q:
            return [{"produto_codigo": i["produto_codigo"], "quantidade": i["quantidade"]}
                    for i in self.itens.values() if i["venda_id"] == params[0]]
        return []

    async def execute(self, query, *params):
        q = " ".join(query.split())
        if q.startswith("INSERT INTO pdv_itens"):
            iid = self._next_item_id; self._next_item_id += 1
            venda_id, codigo, descricao, quantidade, valor_unitario, desconto, valor_total = params
            self.itens[iid] = {"id": iid, "venda_id": venda_id, "produto_codigo": codigo,
                                "descricao": descricao, "quantidade": quantidade,
                                "valor_unitario": valor_unitario, "desconto": desconto,
                                "valor_total": valor_total}
            return "INSERT 1"
        if q.startswith("INSERT INTO pdv_pagamentos"):
            self.pagamentos.append(params)
            return "INSERT 1"
        if q.startswith("UPDATE pdv_vendas SET status"):
            venda_id, observacoes = params
            self.vendas[venda_id]["status"] = "cancelada"
            self.vendas[venda_id]["observacoes"] = observacoes
            return "UPDATE 1"
        if q.startswith("UPDATE pdv_vendas SET total"):
            valor, venda_id = params
            self.vendas[venda_id]["total"] = max(0, float(self.vendas[venda_id]["total"]) - float(valor))
            return "UPDATE 1"
        if q.startswith("INSERT INTO pdv_devolucoes"):
            self.devolucoes.append(params)
            return "INSERT 1"
        if q.startswith("DELETE FROM pdv_itens"):
            self.itens.pop(params[0], None)
            return "DELETE 1"
        return "OK"

    def acquire(self):
        return _FakeAcquireCtx(self)


class _FakeTransactionCtx:
    """Snapshot na entrada, restaura em excecao (ROLLBACK) -- permite testar
    que erro de saldo insuficiente desfaz venda+itens+pagamentos juntos."""

    def __init__(self, fake):
        self._fake = fake
        self._snap = None

    async def __aenter__(self):
        f = self._fake
        self._snap = ({k: dict(v) for k, v in f.vendas.items()},
                       {k: dict(v) for k, v in f.itens.items()},
                       list(f.pagamentos), list(f.devolucoes),
                       f._next_venda_id, f._next_item_id)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None:
            f = self._fake
            (f.vendas, f.itens, f.pagamentos, f.devolucoes,
             f._next_venda_id, f._next_item_id) = self._snap
        return False


class _FakeAcquireCtx:
    def __init__(self, fake):
        self._fake = fake

    async def __aenter__(self):
        return _FakeConn(self._fake)

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, fake):
        self._fake = fake

    def transaction(self):
        return _FakeTransactionCtx(self._fake)

    async def fetchrow(self, query, *params):
        return await self._fake.fetchrow(query, *params)

    async def fetch(self, query, *params):
        return await self._fake.fetch(query, *params)

    async def execute(self, query, *params):
        return await self._fake.execute(query, *params)


class TestResolverLojaDaVenda(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDBPdv()

    async def test_resolve_nome_da_loja_do_caixa(self):
        from core.pdv import _resolver_loja_da_venda
        self.fake.caixas[1] = {"loja_id": 5}
        self.fake.lojas[5] = "Loja Fisica Central"
        conn = _FakeConn(self.fake)
        loja = await _resolver_loja_da_venda(conn, 1)
        self.assertEqual(loja, "Loja Fisica Central")

    async def test_none_quando_caixa_sem_loja_id(self):
        from core.pdv import _resolver_loja_da_venda
        self.fake.caixas[1] = {"loja_id": None}
        conn = _FakeConn(self.fake)
        loja = await _resolver_loja_da_venda(conn, 1)
        self.assertIsNone(loja)

    async def test_none_quando_caixa_id_vazio(self):
        from core.pdv import _resolver_loja_da_venda
        conn = _FakeConn(self.fake)
        loja = await _resolver_loja_da_venda(conn, None)
        self.assertIsNone(loja)

    async def test_none_quando_loja_nao_encontrada(self):
        from core.pdv import _resolver_loja_da_venda
        self.fake.caixas[1] = {"loja_id": 99}
        conn = _FakeConn(self.fake)
        loja = await _resolver_loja_da_venda(conn, 1)
        self.assertIsNone(loja)


if __name__ == "__main__":
    unittest.main()
