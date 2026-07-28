"""Testes da Fase 3 (migracao aditiva loja-texto -> loja_id FK): core/lojas.py,
core/estoque.py, core/estoque_transferencias.py, core/estoque_contagem.py e
core/entidades.py continuam gravando a coluna "loja" (texto) — este arquivo
garante que a nova coluna "loja_id" tambem e' preenchida em paralelo (dual-
write) e que a reconciliacao periodica cobre as 4 tabelas."""
import sys, os, re, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


async def _mp(*a, **kw):
    return AsyncMock()


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.estoque as estoque
import core.estoque_transferencias as estoque_transf
import core.estoque_contagem as estoque_contagem


class FakeDB:
    """Fake minimo cobrindo os padroes de query usados por core/estoque*.py.
    "lojas" e' um dict nome->id simulando a tabela real de lojas."""

    def __init__(self, lojas: dict = None):
        self.lojas = lojas or {"Loja A": 1, "Loja B": 2}
        self.estoque = {}  # (sku, loja) -> {"quantidade":..., "loja_id":...}
        self.movimentacoes = []  # cada item: dict com sku/loja/loja_id/tipo/...
        self.contagens = []
        self.transferencias = []
        self.executed = []

    def _norm(self, q):
        return " ".join(q.split())

    async def fetchval(self, query, *params):
        q = self._norm(query)
        if q.startswith("SELECT id FROM lojas WHERE nome"):
            return self.lojas.get(params[0])
        if q.startswith("SELECT quantidade FROM estoque_lojas"):
            sku, loja = params
            row = self.estoque.get((sku, loja))
            return row["quantidade"] if row else None
        return None

    async def fetchrow(self, query, *params):
        q = self._norm(query)
        if q.startswith("SELECT * FROM estoque_transferencias WHERE id"):
            tid = params[0]
            return next((t for t in self.transferencias if t["id"] == tid), None)
        if q.startswith("INSERT INTO estoque_transferencias"):
            sku, origem, destino, origem_id, destino_id, qtd, motivo, status, uid, uname = params
            row = {"id": len(self.transferencias) + 1, "sku": sku, "loja_origem": origem,
                   "loja_destino": destino, "loja_origem_id": origem_id, "loja_destino_id": destino_id,
                   "quantidade_solicitada": qtd, "motivo": motivo, "status": status}
            self.transferencias.append(row)
            return {"id": row["id"]}
        return None

    async def execute(self, query, *params):
        q = self._norm(query)
        self.executed.append(q)
        if "CREATE TABLE" in q or "ALTER TABLE" in q or "CREATE INDEX" in q:
            return "OK"
        if q.startswith("INSERT INTO estoque_lojas"):
            sku, loja, loja_id, qtd = params[0], params[1], params[2], params[3]
            self.estoque[(sku, loja)] = {"quantidade": qtd, "loja_id": loja_id}
            return "OK"
        if q.startswith("UPDATE estoque_lojas SET quantidade = quantidade -"):
            qtd, sku, loja, loja_id = params
            row = self.estoque.setdefault((sku, loja), {"quantidade": 0, "loja_id": None})
            row["quantidade"] -= qtd
            row["loja_id"] = row["loja_id"] or loja_id
            return "OK"
        if q.startswith("UPDATE estoque_lojas SET quantidade = $1"):
            qtd, sku, loja, loja_id = params
            row = self.estoque.setdefault((sku, loja), {"quantidade": 0, "loja_id": None})
            row["quantidade"] = qtd
            row["loja_id"] = row["loja_id"] or loja_id
            return "OK"
        if q.startswith("INSERT INTO estoque_movimentacoes"):
            self.movimentacoes.append(params)
            return "OK"
        if q.startswith("INSERT INTO estoque_contagens"):
            self.contagens.append(params)
            return "OK"
        if "UPDATE estoque_lojas e SET loja_id" in q:
            return "UPDATE 1"
        if "UPDATE estoque_movimentacoes m SET loja_id" in q:
            return "UPDATE 1"
        if "UPDATE estoque_contagens c SET loja_id" in q:
            return "UPDATE 1"
        if "UPDATE estoque_transferencias t SET loja_origem_id" in q:
            return "UPDATE 1"
        if "UPDATE estoque_transferencias t SET loja_destino_id" in q:
            return "UPDATE 1"
        return "OK"

    async def fetch(self, query, *params):
        return []


class TestDualWriteEstoque(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        self._p_estoque = patch("core.estoque.get_db", side_effect=_get_db)
        self._p_estoque.start()
        estoque._ok = True

    def tearDown(self):
        self._p_estoque.stop()
        estoque._ok = False

    async def test_entrada_grava_loja_id(self):
        r = estoque.entrada("SKU1", "Loja A", 10, "compra_fornecedor", usuario_id=1, usuario_nome="x")
        self.assertTrue(r.get("ok"))
        self.assertEqual(self.fake.estoque[("SKU1", "Loja A")]["loja_id"], 1)

    async def test_saida_grava_loja_id(self):
        self.fake.estoque[("SKU1", "Loja A")] = {"quantidade": 20, "loja_id": None}
        r = estoque.saida("SKU1", "Loja A", 5, "quebra", usuario_id=1, usuario_nome="x")
        self.assertTrue(r.get("ok"))
        self.assertEqual(self.fake.estoque[("SKU1", "Loja A")]["loja_id"], 1)

    async def test_atualizar_grava_loja_id(self):
        r = estoque.atualizar("SKU1", "Loja B", 30, sync_bling=False)
        self.assertTrue(r.get("ok"))
        self.assertEqual(self.fake.estoque[("SKU1", "Loja B")]["loja_id"], 2)

    async def test_transferir_grava_loja_id_origem_e_destino(self):
        self.fake.estoque[("SKU1", "Loja A")] = {"quantidade": 20, "loja_id": 1}
        r = estoque.transferir("SKU1", "Loja A", "Loja B", 5, "reposicao")
        self.assertTrue(r.get("ok"))
        self.assertEqual(self.fake.estoque[("SKU1", "Loja A")]["loja_id"], 1)
        self.assertEqual(self.fake.estoque[("SKU1", "Loja B")]["loja_id"], 2)

    async def test_entrada_loja_desconhecida_grava_loja_id_none(self):
        """Loja sem correspondencia em "lojas" (nome digitado errado, etc):
        loja_id fica None — nao quebra o fluxo, so' fica pra reconciliacao futura."""
        r = estoque.entrada("SKU1", "Loja Inexistente", 10, "compra_fornecedor")
        self.assertTrue(r.get("ok"))
        self.assertIsNone(self.fake.estoque[("SKU1", "Loja Inexistente")]["loja_id"])

    async def test_reconciliar_loja_id_atualiza_as_4_tabelas(self):
        r = estoque.reconciliar_loja_id()
        self.assertTrue(r["ok"])
        self.assertIn("estoque_lojas", r["resultado"])
        self.assertIn("estoque_movimentacoes", r["resultado"])
        self.assertIn("estoque_contagens", r["resultado"])
        self.assertIn("estoque_transferencias_origem", r["resultado"])
        self.assertIn("estoque_transferencias_destino", r["resultado"])


class TestDualWriteTransferenciasEContagem(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        self._p_transf = patch("core.estoque_transferencias.get_db", side_effect=_get_db)
        self._p_transf.start()
        self._p_contagem = patch("core.estoque_contagem.get_db", side_effect=_get_db)
        self._p_contagem.start()
        self._p_estoque = patch("core.estoque.get_db", side_effect=_get_db)
        self._p_estoque.start()
        estoque_transf._ok = True
        estoque_contagem._ok = True
        estoque._ok = True

    def tearDown(self):
        self._p_transf.stop()
        self._p_contagem.stop()
        self._p_estoque.stop()
        estoque_transf._ok = False
        estoque_contagem._ok = False
        estoque._ok = False

    async def test_solicitar_transferencia_grava_loja_origem_destino_id(self):
        self.fake.estoque[("SKU1", "Loja A")] = {"quantidade": 20, "loja_id": 1}
        r = estoque_transf.solicitar("SKU1", "Loja A", "Loja B", 3, "reposicao_entre_lojas", usuario_id=1, usuario_nome="x")
        self.assertNotIn("erro", r)
        t = self.fake.transferencias[0]
        self.assertEqual(t["loja_origem_id"], 1)
        self.assertEqual(t["loja_destino_id"], 2)

    async def test_registrar_contagem_grava_loja_id(self):
        self.fake.estoque[("SKU1", "Loja A")] = {"quantidade": 10, "loja_id": 1}
        estoque_contagem.registrar("SKU1", "Loja A", 12, usuario_id=1, usuario_nome="x")
        self.assertEqual(len(self.fake.contagens), 1)
        # params: sku, loja, loja_id, quantidade_sistema, quantidade_contada, ...
        self.assertEqual(self.fake.contagens[0][2], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
