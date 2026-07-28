"""Testes de integracao dos controles de seguranca de estoque:
rastreabilidade por usuario, alcada de aprovacao (saida/transferencia >10un),
confirmacao de transferencia em duas pontas, contagem ciclica com ajuste automatico."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


class FakeDB:
    """Fake minimo que reconhece as queries exatas usadas pelos modulos de
    estoque — nao e' um SQL engine generico, so' cobre os padroes escritos
    para essa feature."""

    def __init__(self):
        self.estoque = {}  # (sku, loja) -> float
        self.saldos = {}  # (sku, loja, tipo) -> float
        self.produtos = {}  # sku -> {"descricao":..., "preco_custo":...}
        self.aprovacoes = []
        self.transferencias = []
        self.contagens = []
        self.movimentacoes = []

    def set_estoque(self, sku, loja, qtd):
        self.estoque[(sku, loja)] = qtd
        self.saldos[(sku, loja, "disponivel")] = qtd

    def set_saldo(self, sku, loja, tipo="disponivel", qtd=0):
        self.saldos[(sku, loja, tipo)] = qtd
        if tipo == "disponivel":
            self.estoque[(sku, loja)] = qtd

    def acquire(self):
        return _FakeAcquireCtx(self)

    async def execute(self, query, *params):
        q = " ".join(query.split())
        if "ALTER TABLE" in q or "CREATE TABLE" in q or "CREATE INDEX" in q \
                or "CREATE OR REPLACE FUNCTION" in q or "DROP TRIGGER" in q or "CREATE TRIGGER" in q:
            return "OK"
        if "INSERT INTO estoque_saldos" in q:
            sku, loja, tipo, qtd = params
            self.saldos[(sku, loja, tipo)] = qtd
            if tipo == "disponivel":
                self.estoque[(sku, loja)] = qtd
            return "OK"
        if "INSERT INTO estoque_lojas" in q:
            sku, loja, qtd = params[0], params[1], params[2]
            self.estoque[(sku, loja)] = qtd
        elif "UPDATE estoque_lojas SET quantidade = quantidade -" in q:
            qtd, sku, loja = params[0], params[1], params[2]
            self.estoque[(sku, loja)] = self.estoque.get((sku, loja), 0) - qtd
        elif "UPDATE estoque_lojas SET quantidade = $1" in q:
            qtd, sku, loja = params[0], params[1], params[2]
            self.estoque[(sku, loja)] = qtd
        elif "INSERT INTO estoque_movimentacoes" in q:
            self.movimentacoes.append(params)
        elif "UPDATE estoque_aprovacoes SET status = 'aprovada'" in q:
            aprovador_id, aprovador_nome, aid = params
            for a in self.aprovacoes:
                if a["id"] == aid:
                    a["status"] = "aprovada"; a["usuario_aprovador_id"] = aprovador_id; a["usuario_aprovador_nome"] = aprovador_nome
        elif "UPDATE estoque_aprovacoes SET status = 'rejeitada'" in q:
            aprovador_id, aprovador_nome, motivo, aid = params
            for a in self.aprovacoes:
                if a["id"] == aid:
                    a["status"] = "rejeitada"; a["motivo_rejeicao"] = motivo
        elif "UPDATE estoque_transferencias SET status = 'em_transito'" in q:
            aprovador_id, aprovador_nome, tid = params
            for t in self.transferencias:
                if t["id"] == tid:
                    t["status"] = "em_transito"; t["usuario_aprovador_id"] = aprovador_id; t["usuario_aprovador_nome"] = aprovador_nome
        elif "UPDATE estoque_transferencias SET status = 'rejeitada'" in q:
            aprovador_id, aprovador_nome, motivo, tid = params
            for t in self.transferencias:
                if t["id"] == tid:
                    t["status"] = "rejeitada"
        elif "UPDATE estoque_transferencias SET status = $1" in q:
            status, qtd_recebida, confirmador_id, confirmador_nome, tid = params
            for t in self.transferencias:
                if t["id"] == tid:
                    t["status"] = status; t["quantidade_recebida"] = qtd_recebida
        return "OK"

    async def fetchval(self, query, *params):
        q = " ".join(query.split())
        if "SELECT quantidade FROM estoque_saldos" in q:
            sku, loja, tipo = params
            return self.saldos.get((sku, loja, tipo))
        if "SELECT quantidade FROM estoque_lojas" in q:
            sku, loja = params
            return self.estoque.get((sku, loja))
        if "SELECT COUNT(*) FROM rbac_permissoes" in q:
            return 1
        return None

    async def fetchrow(self, query, *params):
        q = " ".join(query.split())
        if "INSERT INTO estoque_aprovacoes" in q:
            sku, loja, qtd, motivo, uid, uname = params
            row = {"id": len(self.aprovacoes) + 1, "tipo": "saida", "sku": sku, "loja": loja,
                   "quantidade": qtd, "motivo": motivo, "status": "pendente",
                   "usuario_solicitante_id": uid, "usuario_solicitante_nome": uname}
            self.aprovacoes.append(row)
            return row
        if "FROM estoque_aprovacoes WHERE id" in q:
            (aid,) = params
            return next((a for a in self.aprovacoes if a["id"] == aid), None)
        if "INSERT INTO estoque_transferencias" in q:
            sku, origem, destino, qtd, motivo, status, uid, uname = params
            row = {"id": len(self.transferencias) + 1, "sku": sku, "loja_origem": origem,
                   "loja_destino": destino, "quantidade_solicitada": qtd, "motivo": motivo,
                   "status": status, "usuario_solicitante_id": uid, "usuario_solicitante_nome": uname,
                   "quantidade_recebida": None}
            self.transferencias.append(row)
            return row
        if "FROM estoque_transferencias WHERE id" in q:
            (tid,) = params
            return next((t for t in self.transferencias if t["id"] == tid), None)
        return None

    async def fetch(self, query, *params):
        return []


class _FakeTransactionCtx:
    """No-op transaction context manager — a real Postgres transaction isn't
    meaningful over the in-memory fake, so this just supports `async with`."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeAcquireCtx:
    """Fake `async with db.acquire() as conn:` — yields a `_FakeConn` that
    proxies execute/fetchval back to the same FakeDB instance, plus a
    `.transaction()` no-op. Needed because core.estoque_saldos.mover_saldo
    (called by entrada/saida/transferir/ratear) does its writes inside
    `async with db.acquire() as conn: async with conn.transaction(): ...`."""

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


class TestFluxoEstoqueSeguranca(unittest.IsolatedAsyncioTestCase):
    """Usa IsolatedAsyncioTestCase + patch direto em core.get_db (importado por
    nome em cada modulo) para testar o fluxo completo end-to-end."""

    def setUp(self):
        self.fake = FakeDB()
        self._patches = []
        for modulo in ("core.estoque", "core.estoque_saldos", "core.estoque_aprovacoes",
                       "core.estoque_transferencias", "core.estoque_contagem"):
            async def _get_db(_fake=self.fake):
                return _fake
            p = patch(f"{modulo}.get_db", side_effect=_get_db)
            p.start()
            self._patches.append(p)
        import core.estoque_saldos as ms
        ms._ok = True  # pula _ensure() (CREATE TABLE/trigger real) — fake ja "tem" as tabelas
        import core.estoque_aprovacoes as ma
        ma._ok = True
        import core.estoque_transferencias as mt
        mt._ok = True
        import core.estoque_contagem as mc
        mc._ok = True

    def tearDown(self):
        for p in self._patches:
            p.stop()

    async def test_saida_pequena_aplica_direto_com_usuario(self):
        from core.estoque import saida
        self.fake.set_estoque("SKU1", "Loja A", 100)
        r = saida("SKU1", "Loja A", 5, "quebra", usuario_id=7, usuario_nome="joao")
        self.assertTrue(r.get("ok"))
        self.assertEqual(self.fake.estoque[("SKU1", "Loja A")], 95)
        self.assertEqual(len(self.fake.movimentacoes), 1)
        # usuario_id e usuario_nome sao os params 5 e 6 (0-indexed) do INSERT em
        # estoque_movimentacoes feito por core.estoque_saldos.mover_saldo:
        # (sku, loja, tipo, quantidade, motivo, usuario_id, usuario_nome,
        #  tipo_saldo, saldo_anterior, saldo_posterior, ip, dispositivo)
        self.assertEqual(self.fake.movimentacoes[0][5], 7)
        self.assertEqual(self.fake.movimentacoes[0][6], "joao")

    async def test_saida_grande_fica_pendente_nao_aplica(self):
        from core.estoque_aprovacoes import precisa_aprovacao, solicitar
        self.fake.set_estoque("SKU1", "Loja A", 100)
        self.assertTrue(precisa_aprovacao(15))
        r = solicitar("SKU1", "Loja A", 15, "perda", usuario_id=7, usuario_nome="joao")
        self.assertTrue(r.get("pendente"))
        self.assertEqual(self.fake.estoque[("SKU1", "Loja A")], 100)  # nao debitou ainda

    async def test_aprovar_saida_pendente_aplica_e_debita(self):
        from core.estoque_aprovacoes import solicitar, aprovar
        self.fake.set_estoque("SKU1", "Loja A", 100)
        r = solicitar("SKU1", "Loja A", 15, "perda", usuario_id=7, usuario_nome="joao")
        aid = r["aprovacao_id"]
        r2 = aprovar(aid, aprovador_id=1, aprovador_nome="gerente")
        self.assertTrue(r2.get("ok"))
        self.assertEqual(self.fake.estoque[("SKU1", "Loja A")], 85)
        self.assertEqual(self.fake.aprovacoes[0]["status"], "aprovada")

    async def test_rejeitar_saida_nao_debita(self):
        from core.estoque_aprovacoes import solicitar, rejeitar
        self.fake.set_estoque("SKU1", "Loja A", 100)
        r = solicitar("SKU1", "Loja A", 15, "perda", usuario_id=7, usuario_nome="joao")
        aid = r["aprovacao_id"]
        r2 = rejeitar(aid, aprovador_id=1, aprovador_nome="gerente", motivo_rejeicao="parece erro")
        self.assertTrue(r2.get("ok"))
        self.assertEqual(self.fake.estoque[("SKU1", "Loja A")], 100)
        self.assertEqual(self.fake.aprovacoes[0]["status"], "rejeitada")

    async def test_motivo_invalido_rejeitado(self):
        from core.estoque import saida
        self.fake.set_estoque("SKU1", "Loja A", 100)
        r = saida("SKU1", "Loja A", 5, "motivo_qualquer_texto_livre", usuario_id=7, usuario_nome="joao")
        self.assertIn("erro", r)

    async def test_transferencia_pequena_debita_origem_fica_em_transito(self):
        from core.estoque_transferencias import solicitar
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 50)
        r = solicitar("SKU1", "Loja A", "Loja B", 5, "reposicao_entre_lojas", usuario_id=1, usuario_nome="op")
        self.assertEqual(r["status"], "em_transito")
        self.assertFalse(r["pendente_aprovacao"])
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "disponivel")], 45)
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "transito")], 5)

    async def test_transferencia_grande_fica_pendente_aprovacao(self):
        from core.estoque_transferencias import solicitar
        self.fake.set_estoque("SKU1", "Loja A", 50)
        r = solicitar("SKU1", "Loja A", "Loja B", 20, "reposicao_entre_lojas", usuario_id=1, usuario_nome="op")
        self.assertEqual(r["status"], "pendente_aprovacao")
        self.assertEqual(self.fake.estoque[("SKU1", "Loja A")], 50)  # nao debitou ainda

    async def test_transferencia_grande_pendente_nao_debita_nada_ainda(self):
        from core.estoque_transferencias import solicitar
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 50)
        r = solicitar("SKU1", "Loja A", "Loja B", 20, "reposicao_entre_lojas", usuario_id=1, usuario_nome="op")
        self.assertEqual(r["status"], "pendente_aprovacao")
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "disponivel")], 50)  # nao debitou - so' debita ao aprovar
        self.assertEqual(self.fake.saldos.get(("SKU1", "Loja A", "transito")), None)

    async def test_aprovar_transferencia_pendente_debita_disponivel_credita_transito(self):
        from core.estoque_transferencias import solicitar, aprovar
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 50)
        r = solicitar("SKU1", "Loja A", "Loja B", 20, "reposicao_entre_lojas", usuario_id=1, usuario_nome="op")
        tid = r["transferencia_id"]
        r2 = aprovar(tid, aprovador_id=9, aprovador_nome="gerente")
        self.assertTrue(r2.get("ok"))
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "disponivel")], 30)
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "transito")], 20)

    async def test_confirmar_transferencia_debita_transito_origem_credita_disponivel_destino(self):
        from core.estoque_transferencias import solicitar, confirmar
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 50)
        r = solicitar("SKU1", "Loja A", "Loja B", 5, "reposicao_entre_lojas", usuario_id=1, usuario_nome="op")
        tid = r["transferencia_id"]
        r2 = confirmar(tid, confirmador_id=2, confirmador_nome="loja_b_op", quantidade_recebida=5)
        self.assertEqual(r2["status"], "confirmada")
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "transito")], 0)
        self.assertEqual(self.fake.saldos[("SKU1", "Loja B", "disponivel")], 5)

    async def test_confirmar_transferencia_credita_destino(self):
        from core.estoque_transferencias import solicitar, confirmar
        self.fake.set_estoque("SKU1", "Loja A", 50)
        r = solicitar("SKU1", "Loja A", "Loja B", 5, "reposicao_entre_lojas", usuario_id=1, usuario_nome="op")
        tid = r["transferencia_id"]
        r2 = confirmar(tid, confirmador_id=2, confirmador_nome="loja_b_op", quantidade_recebida=5)
        self.assertEqual(r2["status"], "confirmada")
        self.assertFalse(r2["discrepancia"])
        self.assertEqual(self.fake.estoque[("SKU1", "Loja B")], 5)

    async def test_confirmar_transferencia_com_quantidade_diferente_marca_discrepancia(self):
        from core.estoque_transferencias import solicitar, confirmar
        self.fake.set_estoque("SKU1", "Loja A", 50)
        r = solicitar("SKU1", "Loja A", "Loja B", 10, "reposicao_entre_lojas", usuario_id=1, usuario_nome="op")
        tid = r["transferencia_id"]
        r2 = confirmar(tid, confirmador_id=2, confirmador_nome="loja_b_op", quantidade_recebida=8)
        self.assertEqual(r2["status"], "com_discrepancia")
        self.assertTrue(r2["discrepancia"])
        self.assertEqual(self.fake.estoque[("SKU1", "Loja B")], 8)  # credita o que REALMENTE chegou

    async def test_contagem_diferenca_positiva_aplica_entrada(self):
        from core.estoque_contagem import registrar
        self.fake.set_estoque("SKU1", "Loja A", 10)
        r = registrar("SKU1", "Loja A", 12, usuario_id=1, usuario_nome="op")
        self.assertEqual(r["ajuste_status"], "aplicado")
        self.assertEqual(self.fake.estoque[("SKU1", "Loja A")], 12)

    async def test_contagem_diferenca_negativa_pequena_aplica_saida(self):
        from core.estoque_contagem import registrar
        self.fake.set_estoque("SKU1", "Loja A", 10)
        r = registrar("SKU1", "Loja A", 7, usuario_id=1, usuario_nome="op")
        self.assertEqual(r["ajuste_status"], "aplicado")
        self.assertEqual(self.fake.estoque[("SKU1", "Loja A")], 7)

    async def test_contagem_diferenca_negativa_grande_fica_pendente(self):
        from core.estoque_contagem import registrar
        self.fake.set_estoque("SKU1", "Loja A", 100)
        r = registrar("SKU1", "Loja A", 50, usuario_id=1, usuario_nome="op")  # falta 50un
        self.assertEqual(r["ajuste_status"], "pendente_aprovacao")
        self.assertEqual(self.fake.estoque[("SKU1", "Loja A")], 100)  # nao debitou ainda


if __name__ == "__main__":
    unittest.main(verbosity=2)
