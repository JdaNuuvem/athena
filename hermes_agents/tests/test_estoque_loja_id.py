"""Testes da Fase 3 (migracao aditiva loja-texto -> loja_id FK): core/estoque.py,
core/estoque_transferencias.py, core/estoque_contagem.py e core/entidades.py
continuam gravando a coluna "loja" (texto) — este arquivo garante que a nova
coluna "loja_id" tambem e' preenchida em paralelo (dual-write) e que a
reconciliacao periodica cobre as 5 colunas/tabelas.

Depois do merge com a Fase 1 (saldos segregados), o dual-write mudou de LUGAR,
nao de intencao:
  - estoque_movimentacoes.loja_id: gravado dentro de
    core/estoque_saldos.py::_mover_saldo_async(), o unico escritor daquela
    tabela desde a Fase 1. Vale automaticamente pra entrada/saida/transferir/
    ratear/ajustar_absoluto e pros eventos de core/entidades.py.
  - estoque_lojas.loja_id: gravado pelo trigger de espelho
    fn_espelhar_saldo_disponivel, que resolve o id a partir do nome da loja
    (estoque_lojas virou espelho de estoque_saldos; Python nao escreve mais
    nela diretamente).
  - estoque_transferencias.loja_origem_id/loja_destino_id e
    estoque_contagens.loja_id: continuam sendo dual-write explicito nos
    proprios modulos, porque essas tabelas nao passam por mover_saldo.
"""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


async def _mp(*a, **kw):
    return AsyncMock()


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.estoque as estoque
import core.estoque_saldos as estoque_saldos
import core.estoque_transferencias as estoque_transf
import core.estoque_contagem as estoque_contagem


class FakeDB:
    """Fake minimo cobrindo os padroes de query usados por core/estoque*.py.
    "lojas" e' um dict nome->id simulando a tabela real de lojas.

    Simula tambem o efeito do trigger de espelho: todo INSERT em
    estoque_saldos com tipo='disponivel' propaga (quantidade, loja_id) pra
    estoque_lojas, com loja_id resolvido pelo nome — exatamente o que
    fn_espelhar_saldo_disponivel faz no Postgres."""

    def __init__(self, lojas: dict = None):
        self.lojas = lojas or {"Loja A": 1, "Loja B": 2}
        self.estoque = {}  # (sku, loja) -> {"quantidade":..., "loja_id":...}
        self.saldos = {}  # (sku, loja, tipo) -> float
        self.movimentacoes = []  # params do INSERT em estoque_movimentacoes
        self.contagens = []
        self.transferencias = []
        self.executed = []

    def _norm(self, q):
        return " ".join(q.split())

    def set_saldo(self, sku, loja, tipo, qtd):
        self.saldos[(sku, loja, tipo)] = qtd
        if tipo == "disponivel":
            self.estoque[(sku, loja)] = {"quantidade": qtd, "loja_id": self.lojas.get(loja)}

    async def fetchval(self, query, *params):
        q = self._norm(query)
        if q.startswith("SELECT id FROM lojas WHERE nome"):
            return self.lojas.get(params[0])
        if "SELECT quantidade FROM estoque_saldos" in q:
            sku, loja, tipo = params
            return self.saldos.get((sku, loja, tipo))
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
        if "CREATE TABLE" in q or "ALTER TABLE" in q or "CREATE INDEX" in q \
                or "CREATE OR REPLACE FUNCTION" in q or "DROP TRIGGER" in q \
                or "CREATE TRIGGER" in q or q.startswith("DO $$"):
            return "OK"
        if "INSERT INTO estoque_saldos" in q and "SELECT sku, loja, 'disponivel'" in q:
            return "OK"  # backfill, sem params
        if "INSERT INTO catalogo_produtos" in q:
            return "OK"
        if "INSERT INTO estoque_saldos" in q:
            sku, loja, tipo, qtd = params
            self.saldos[(sku, loja, tipo)] = qtd
            if tipo == "disponivel":
                # trigger fn_espelhar_saldo_disponivel: espelha quantidade E
                # resolve loja_id pelo nome (COALESCE pra nao apagar o que ja
                # estava preenchido quando a loja nao existe em `lojas`).
                anterior = self.estoque.get((sku, loja), {}).get("loja_id")
                self.estoque[(sku, loja)] = {
                    "quantidade": qtd,
                    "loja_id": self.lojas.get(loja) if self.lojas.get(loja) is not None else anterior,
                }
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

    def acquire(self):
        return _FakeAcquireCtx(self)


class _FakeTransactionCtx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
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
        return _FakeTransactionCtx()

    async def execute(self, query, *params):
        return await self._fake.execute(query, *params)

    async def fetchval(self, query, *params):
        return await self._fake.fetchval(query, *params)

    async def fetchrow(self, query, *params):
        return await self._fake.fetchrow(query, *params)

    async def fetch(self, query, *params):
        return await self._fake.fetch(query, *params)


# Posicoes (0-indexed) dos params do INSERT em estoque_movimentacoes feito por
# core/estoque_saldos.py::_mover_saldo_async:
#   (sku, loja, loja_id, tipo, quantidade, motivo, usuario_id, usuario_nome,
#    tipo_saldo, saldo_anterior, saldo_posterior, ip, dispositivo)
MOV_SKU, MOV_LOJA, MOV_LOJA_ID = 0, 1, 2


class TestDualWriteEstoque(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        self._patches = [
            patch("core.estoque.get_db", side_effect=_get_db),
            patch("core.estoque_saldos.get_db", side_effect=_get_db),
        ]
        for p in self._patches:
            p.start()
        estoque_saldos._ok = True

    def tearDown(self):
        for p in self._patches:
            p.stop()
        estoque_saldos._ok = False

    def _movs_de(self, loja):
        return [m for m in self.fake.movimentacoes if m[MOV_LOJA] == loja]

    async def test_entrada_grava_loja_id(self):
        r = estoque.entrada("SKU1", "Loja A", 10, "compra_fornecedor", usuario_id=1, usuario_nome="x")
        self.assertTrue(r.get("ok"), r)
        # ledger (fonte do dual-write desde a Fase 1)
        self.assertEqual(self._movs_de("Loja A")[0][MOV_LOJA_ID], 1)
        # espelho estoque_lojas, alimentado pelo trigger
        self.assertEqual(self.fake.estoque[("SKU1", "Loja A")]["loja_id"], 1)

    async def test_saida_grava_loja_id(self):
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 20)
        r = estoque.saida("SKU1", "Loja A", 5, "quebra", usuario_id=1, usuario_nome="x")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(self._movs_de("Loja A")[0][MOV_LOJA_ID], 1)
        self.assertEqual(self.fake.estoque[("SKU1", "Loja A")]["loja_id"], 1)

    async def test_ajustar_absoluto_grava_loja_id(self):
        """Substituiu `atualizar()` (removida na Fase 1: era SET absoluto por
        SQL cru em estoque_lojas). Mesmo contrato de dual-write."""
        r = estoque.ajustar_absoluto("SKU1", "Loja B", 30)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(self._movs_de("Loja B")[0][MOV_LOJA_ID], 2)
        self.assertEqual(self.fake.estoque[("SKU1", "Loja B")]["loja_id"], 2)

    async def test_transferir_grava_loja_id_origem_e_destino(self):
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 20)
        r = estoque.transferir("SKU1", "Loja A", "Loja B", 5, "reposicao_entre_lojas")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(self._movs_de("Loja A")[0][MOV_LOJA_ID], 1)
        self.assertEqual(self._movs_de("Loja B")[0][MOV_LOJA_ID], 2)
        self.assertEqual(self.fake.estoque[("SKU1", "Loja A")]["loja_id"], 1)
        self.assertEqual(self.fake.estoque[("SKU1", "Loja B")]["loja_id"], 2)

    async def test_ratear_grava_loja_id(self):
        self.fake.lojas = {"Loja A": 1, "Loja B": 2}
        r = estoque.ratear("SKU1", 100, "igual", lojas=["Loja A", "Loja B"])
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(self._movs_de("Loja A")[0][MOV_LOJA_ID], 1)
        self.assertEqual(self._movs_de("Loja B")[0][MOV_LOJA_ID], 2)

    async def test_entrada_loja_desconhecida_grava_loja_id_none(self):
        """Loja sem correspondencia em "lojas" (nome digitado errado, etc):
        loja_id fica None — nao quebra o fluxo, so' fica pra reconciliacao futura."""
        r = estoque.entrada("SKU1", "Loja Inexistente", 10, "compra_fornecedor")
        self.assertTrue(r.get("ok"), r)
        self.assertIsNone(self._movs_de("Loja Inexistente")[0][MOV_LOJA_ID])
        self.assertIsNone(self.fake.estoque[("SKU1", "Loja Inexistente")]["loja_id"])

    async def test_reconciliar_loja_id_atualiza_as_4_tabelas(self):
        r = estoque.reconciliar_loja_id()
        self.assertTrue(r["ok"])
        self.assertIn("estoque_lojas", r["resultado"])
        self.assertIn("estoque_movimentacoes", r["resultado"])
        self.assertIn("estoque_contagens", r["resultado"])
        self.assertIn("estoque_transferencias_origem", r["resultado"])
        self.assertIn("estoque_transferencias_destino", r["resultado"])


class TestTriggerEspelhoCarregaLojaId(unittest.IsolatedAsyncioTestCase):
    """Fase 1 x Fase 3: estoque_saldos nao tem loja_id (a chave e' sku+loja+
    tipo), entao o trigger de espelho precisa resolver loja_id pelo nome ao
    escrever em estoque_lojas. Sem isso toda linha espelhada nasceria com
    loja_id NULL e o filtro de RBAC por loja (`e.loja_id = ANY(...)`) deixaria
    de enxergar esse estoque."""

    def setUp(self):
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        self.patch = patch("core.estoque_saldos.get_db", side_effect=_get_db)
        self.patch.start()
        self._ok_original = estoque_saldos._ok
        estoque_saldos._ok = False

    def tearDown(self):
        self.patch.stop()
        estoque_saldos._ok = self._ok_original

    async def test_funcao_do_trigger_resolve_e_preserva_loja_id(self):
        await estoque_saldos._ensure_async()
        fn = next(q for q in self.fake.executed
                  if "CREATE OR REPLACE FUNCTION fn_espelhar_saldo_disponivel" in q)
        self.assertIn("INSERT INTO estoque_lojas (sku, loja, loja_id, quantidade, data_atualizacao)", fn)
        self.assertIn("SELECT id FROM lojas WHERE nome = NEW.loja", fn)
        # COALESCE: nome de loja desconhecido nao pode APAGAR um loja_id ja
        # preenchido pelo dual-write ou pela reconciliacao periodica.
        self.assertIn("COALESCE(EXCLUDED.loja_id, estoque_lojas.loja_id)", fn)

    async def test_ensure_garante_colunas_loja_id_defensivamente(self):
        await estoque_saldos._ensure_async()
        sql = " || ".join(self.fake.executed)
        self.assertIn("ALTER TABLE estoque_lojas ADD COLUMN IF NOT EXISTS loja_id", sql)
        self.assertIn("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS loja_id", sql)


class TestDualWriteTransferenciasEContagem(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        self._patches = [
            patch("core.estoque_transferencias.get_db", side_effect=_get_db),
            patch("core.estoque_contagem.get_db", side_effect=_get_db),
            patch("core.estoque.get_db", side_effect=_get_db),
            patch("core.estoque_saldos.get_db", side_effect=_get_db),
        ]
        for p in self._patches:
            p.start()
        estoque_transf._ok = True
        estoque_contagem._ok = True
        estoque_saldos._ok = True

    def tearDown(self):
        for p in self._patches:
            p.stop()
        estoque_transf._ok = False
        estoque_contagem._ok = False
        estoque_saldos._ok = False

    async def test_solicitar_transferencia_grava_loja_origem_destino_id(self):
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 20)
        r = estoque_transf.solicitar("SKU1", "Loja A", "Loja B", 3, "reposicao_entre_lojas",
                                     usuario_id=1, usuario_nome="x")
        self.assertNotIn("erro", r)
        t = self.fake.transferencias[0]
        self.assertEqual(t["loja_origem_id"], 1)
        self.assertEqual(t["loja_destino_id"], 2)

    async def test_registrar_contagem_grava_loja_id(self):
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 10)
        estoque_contagem.registrar("SKU1", "Loja A", 12, usuario_id=1, usuario_nome="x")
        self.assertEqual(len(self.fake.contagens), 1)
        # params: sku, loja, loja_id, quantidade_sistema, quantidade_contada, ...
        self.assertEqual(self.fake.contagens[0][2], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
