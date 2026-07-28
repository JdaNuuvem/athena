"""Testes de core/estoque_saldos.py — mover_saldo/saldo isolados, sem
depender do resto do modulo core/estoque.py."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch


class FakeDBSaldos:
    """Simula estoque_saldos + estoque_movimentacoes + o efeito do trigger
    de espelho (estoque_lojas.quantidade) em memoria. A correcao real do
    trigger em Postgres precisa ser validada manualmente contra um banco
    real (ver checklist no final da Task 1)."""

    def __init__(self):
        self.saldos = {}  # (sku, loja, tipo) -> float
        self.estoque_lojas = {}  # (sku, loja) -> float (espelho simulado)
        self.movimentacoes = []

    def set_saldo(self, sku, loja, tipo, qtd):
        self.saldos[(sku, loja, tipo)] = qtd

    async def execute(self, query, *params):
        q = " ".join(query.split())
        if "CREATE TABLE" in q or "ALTER TABLE" in q or "CREATE OR REPLACE FUNCTION" in q \
                or "DROP TRIGGER" in q or "CREATE TRIGGER" in q:
            return "OK"
        if "INSERT INTO estoque_saldos" in q:
            sku, loja, tipo, qtd = params
            self.saldos[(sku, loja, tipo)] = qtd
            if tipo == "disponivel":
                self.estoque_lojas[(sku, loja)] = qtd  # simula o trigger
            return "OK"
        if "INSERT INTO estoque_movimentacoes" in q:
            self.movimentacoes.append(params)
            return "OK"
        return "OK"

    async def fetchval(self, query, *params):
        q = " ".join(query.split())
        if "SELECT quantidade FROM estoque_saldos" in q:
            sku, loja, tipo = params
            return self.saldos.get((sku, loja, tipo))
        return None

    def acquire(self):
        return _FakeAcquireCtx(self)


class _FakeTransactionCtx:
    """No-op transaction context manager — a real Postgres transaction isn't
    meaningful over the in-memory fake, so this just supports `async with`."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeAcquireCtx:
    """Fake `async with db.acquire() as conn:` — yields the same FakeDBSaldos
    instance (it already implements execute/fetchval against the same dicts),
    plus a `.transaction()` no-op."""

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


class TestMoverSaldo(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.fake = FakeDBSaldos()
        async def _get_db(_fake=self.fake):
            return _fake
        self.patch = patch("core.estoque_saldos.get_db", side_effect=_get_db)
        self.patch.start()
        import core.estoque_saldos as m
        m._ok = True

    def tearDown(self):
        self.patch.stop()

    async def test_credito_puro_entrada(self):
        from core.estoque_saldos import mover_saldo
        r = mover_saldo("SKU1", "Loja A", None, "disponivel", 10, "compra", "compra_fornecedor")
        self.assertTrue(r.get("ok"))
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "disponivel")], 10)
        self.assertEqual(self.fake.estoque_lojas[("SKU1", "Loja A")], 10)
        self.assertEqual(len(self.fake.movimentacoes), 1)

    async def test_debito_puro_saida_com_saldo_suficiente(self):
        from core.estoque_saldos import mover_saldo
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 20)
        r = mover_saldo("SKU1", "Loja A", "disponivel", None, 5, "perda", "quebra")
        self.assertTrue(r.get("ok"))
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "disponivel")], 15)

    async def test_debito_com_saldo_insuficiente_nao_grava(self):
        from core.estoque_saldos import mover_saldo
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 3)
        r = mover_saldo("SKU1", "Loja A", "disponivel", None, 5, "perda", "quebra")
        self.assertIn("erro", r)
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "disponivel")], 3)
        self.assertEqual(len(self.fake.movimentacoes), 0)

    async def test_transferencia_com_saldo_insuficiente_nao_grava_nenhum_lado(self):
        """Regression pra fix #1/#2: numa transferencia (origem+destino), se a
        origem nao tem saldo suficiente, a funcao deve retornar erro sem
        escrever nada em nenhum dos dois lados nem em movimentacoes — a
        checagem+escrita da origem e a escrita da destino agora vivem na
        mesma transacao, entao um erro na origem nao pode deixar rastro."""
        from core.estoque_saldos import mover_saldo
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 3)
        r = mover_saldo("SKU1", "Loja A", "disponivel", "transito", 10, "transferencia_saida", "reposicao_entre_lojas")
        self.assertIn("erro", r)
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "disponivel")], 3)
        self.assertNotIn(("SKU1", "Loja A", "transito"), self.fake.saldos)
        self.assertEqual(len(self.fake.movimentacoes), 0)

    async def test_transferencia_disponivel_para_transito(self):
        from core.estoque_saldos import mover_saldo
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 50)
        r = mover_saldo("SKU1", "Loja A", "disponivel", "transito", 10, "transferencia_saida", "reposicao_entre_lojas")
        self.assertTrue(r.get("ok"))
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "disponivel")], 40)
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "transito")], 10)

    async def test_ambos_none_erro(self):
        from core.estoque_saldos import mover_saldo
        r = mover_saldo("SKU1", "Loja A", None, None, 5, "ajuste", "outro")
        self.assertIn("erro", r)

    async def test_tipo_movimento_invalido_erro(self):
        from core.estoque_saldos import mover_saldo
        r = mover_saldo("SKU1", "Loja A", None, "disponivel", 5, "tipo_inventado", "outro")
        self.assertIn("erro", r)

    async def test_tipo_saldo_invalido_erro(self):
        from core.estoque_saldos import mover_saldo
        r = mover_saldo("SKU1", "Loja A", None, "bucket_inventado", 5, "ajuste", "outro")
        self.assertIn("erro", r)

    async def test_quantidade_zero_ou_negativa_erro(self):
        from core.estoque_saldos import mover_saldo
        self.assertIn("erro", mover_saldo("SKU1", "Loja A", None, "disponivel", 0, "ajuste", "outro"))
        self.assertIn("erro", mover_saldo("SKU1", "Loja A", None, "disponivel", -1, "ajuste", "outro"))

    async def test_saldo_le_zero_quando_inexistente(self):
        from core.estoque_saldos import saldo
        self.assertEqual(saldo("SKU_INEXISTENTE", "Loja X"), 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
