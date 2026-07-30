"""Testes de core/estoque_saldos.py — mover_saldo/saldo isolados, sem
depender do resto do modulo core/estoque.py."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


class FakeDBSaldos:
    """Simula estoque_saldos + estoque_movimentacoes + o efeito do trigger
    de espelho (estoque_lojas.quantidade) em memoria. A correcao real do
    trigger em Postgres precisa ser validada manualmente contra um banco
    real (ver checklist no final da Task 1)."""

    def __init__(self):
        self.saldos = {}  # (sku, loja, tipo) -> float
        self.estoque_lojas = {}  # (sku, loja) -> float (espelho simulado)
        self.movimentacoes = []
        self.catalogo = set()  # skus com linha minima em catalogo_produtos
        self.statements = []  # todo SQL normalizado que passou por execute()
        self.lojas = []  # nomes de loja retornados por `SELECT nome FROM lojas`
        self.backfills = 0

    def set_saldo(self, sku, loja, tipo, qtd):
        self.saldos[(sku, loja, tipo)] = qtd

    async def execute(self, query, *params):
        q = " ".join(query.split())
        self.statements.append(q)
        # Backfill estoque_lojas -> estoque_saldos (INSERT ... SELECT, sem params).
        # Precisa vir ANTES do branch generico de "INSERT INTO estoque_saldos".
        if "INSERT INTO estoque_saldos" in q and "SELECT sku, loja, 'disponivel'" in q:
            self.backfills += 1
            for (sku, loja), qtd in self.estoque_lojas.items():
                self.saldos.setdefault((sku, loja, "disponivel"), qtd)  # ON CONFLICT DO NOTHING
            return "OK"
        if "CREATE TABLE" in q or "ALTER TABLE" in q or "CREATE OR REPLACE FUNCTION" in q \
                or "DROP TRIGGER" in q or "CREATE TRIGGER" in q or q.startswith("DO $$"):
            return "OK"
        if "INSERT INTO catalogo_produtos" in q:
            self.catalogo.add(params[0])
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

    async def fetch(self, query, *params):
        q = " ".join(query.split())
        if "FROM lojas" in q:
            return [{"nome": n} for n in self.lojas]
        return []

    def acquire(self):
        return _FakeAcquireCtx(self)


class _FakeTransactionCtx:
    """Transacao simulada: tira snapshot do estado em memoria na entrada e
    restaura se sair por excecao (ROLLBACK). E' o que permite testar a
    atomicidade das duas pernas de uma transferencia (review final #7)."""

    def __init__(self, fake=None):
        self._fake = fake
        self._snap = None

    async def __aenter__(self):
        if self._fake is not None:
            f = self._fake
            self._snap = (dict(f.saldos), dict(f.estoque_lojas),
                          list(f.movimentacoes), set(f.catalogo))
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None and self._snap is not None:
            f = self._fake
            f.saldos, f.estoque_lojas, f.movimentacoes, f.catalogo = (
                self._snap[0], self._snap[1], self._snap[2], self._snap[3])
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
        return _FakeTransactionCtx(self._fake)

    async def execute(self, query, *params):
        return await self._fake.execute(query, *params)

    async def fetchval(self, query, *params):
        return await self._fake.fetchval(query, *params)

    async def fetch(self, query, *params):
        return await self._fake.fetch(query, *params)


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

    async def test_credito_disponivel_cria_linha_no_catalogo(self):
        """Review final #5: SKU novo criado via entrada/ajuste ficava invisivel
        em toda listagem (estoque_lojas JOIN catalogo_produtos e' INNER)."""
        from core.estoque_saldos import mover_saldo
        mover_saldo("SKU_NOVO", "Loja A", None, "disponivel", 7, "compra", "compra_fornecedor")
        self.assertIn("SKU_NOVO", self.fake.catalogo)

    async def test_credito_em_bucket_nao_disponivel_nao_toca_catalogo(self):
        from core.estoque_saldos import mover_saldo
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 50)
        mover_saldo("SKU1", "Loja A", "disponivel", "transito", 5, "transferencia_saida", "outro")
        self.assertNotIn("SKU1", self.fake.catalogo)


class TestEnsureBackfill(unittest.IsolatedAsyncioTestCase):
    """Review final #1 e #2: schema bootstrap."""

    def setUp(self):
        self.fake = FakeDBSaldos()
        async def _get_db(_fake=self.fake):
            return _fake
        self.patch = patch("core.estoque_saldos.get_db", side_effect=_get_db)
        self.patch.start()
        import core.estoque_saldos as m
        self._m = m
        self._ok_original = m._ok
        m._ok = False

    def tearDown(self):
        self.patch.stop()
        self._m._ok = self._ok_original

    async def test_backfill_semeia_saldos_a_partir_de_estoque_lojas(self):
        """Sem isto, estoque_saldos nasce vazio e a primeira entrada() grava um
        delta pequeno que o trigger de espelho copia por cima da quantidade
        real em estoque_lojas — destruindo o estoque de producao."""
        self.fake.estoque_lojas[("SKU_LEGADO", "Loja A")] = 400
        await self._m._ensure_async()
        self.assertEqual(self.fake.backfills, 1)
        self.assertEqual(self.fake.saldos[("SKU_LEGADO", "Loja A", "disponivel")], 400)

    async def test_backfill_nao_sobrescreve_saldo_ja_existente(self):
        """ON CONFLICT DO NOTHING => idempotente, roda a cada boot sem estragar."""
        self.fake.estoque_lojas[("SKU_LEGADO", "Loja A")] = 400
        self.fake.saldos[("SKU_LEGADO", "Loja A", "disponivel")] = 123
        await self._m._ensure_async()
        self.assertEqual(self.fake.saldos[("SKU_LEGADO", "Loja A", "disponivel")], 123)

    async def test_alarga_coluna_tipo_de_movimentacoes(self):
        """'transferencia_recebida' tem 22 chars; a coluna em producao e'
        VARCHAR(20) e CREATE TABLE IF NOT EXISTS nao alarga nada."""
        await self._m._ensure_async()
        sql = " || ".join(self.fake.statements)
        self.assertIn("ALTER COLUMN tipo TYPE VARCHAR(30)", sql)
        self.assertIn("character_maximum_length", sql)  # guardado por information_schema
        self.assertTrue(max(len(t) for t in self._m.TIPOS_MOVIMENTO) <= 30)

    async def test_backfill_roda_antes_do_trigger_de_espelho(self):
        """O seed nao pode disparar o espelho de volta na propria fonte."""
        await self._m._ensure_async()
        idx_backfill = next(i for i, q in enumerate(self.fake.statements)
                            if "SELECT sku, loja, 'disponivel'" in q)
        idx_trigger = next(i for i, q in enumerate(self.fake.statements)
                           if q.startswith("CREATE TRIGGER"))
        self.assertLess(idx_backfill, idx_trigger)


class TestRatearIdempotente(unittest.IsolatedAsyncioTestCase):
    """Review final #3: rateio e' SET ABSOLUTO, nao credito. Rodar duas vezes o
    mesmo rateio tem que dar o mesmo estado final, nao o dobro."""

    def setUp(self):
        self.fake = FakeDBSaldos()
        self.fake.lojas = ["Loja A", "Loja B"]
        async def _get_db(_fake=self.fake):
            return _fake
        self.patches = [
            patch("core.estoque_saldos.get_db", side_effect=_get_db),
            patch("core.estoque.get_db", side_effect=_get_db),
        ]
        for p in self.patches:
            p.start()
        import core.estoque_saldos as m
        m._ok = True

    def tearDown(self):
        for p in self.patches:
            p.stop()

    async def test_ratear_duas_vezes_nao_dobra_o_saldo(self):
        from core.estoque import ratear
        r1 = ratear("SKU1", 100, "igual")
        self.assertTrue(r1.get("ok"), r1)
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "disponivel")], 50)
        self.assertEqual(self.fake.saldos[("SKU1", "Loja B", "disponivel")], 50)
        r2 = ratear("SKU1", 100, "igual")
        self.assertTrue(r2.get("ok"), r2)
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "disponivel")], 50)
        self.assertEqual(self.fake.saldos[("SKU1", "Loja B", "disponivel")], 50)

    async def test_ratear_para_menos_debita(self):
        from core.estoque import ratear
        ratear("SKU1", 100, "igual")
        r = ratear("SKU1", 40, "igual")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "disponivel")], 20)
        self.assertEqual(self.fake.saldos[("SKU1", "Loja B", "disponivel")], 20)


class TestTransferirAtomica(unittest.IsolatedAsyncioTestCase):
    """Review final #7: as duas pernas de transferir() rodam na mesma
    transacao. Antes, se a segunda falhasse, a origem ficava debitada e
    ninguem creditado — perda silenciosa de estoque."""

    def setUp(self):
        self.fake = FakeDBSaldos()
        async def _get_db(_fake=self.fake):
            return _fake
        self.patches = [
            patch("core.estoque_saldos.get_db", side_effect=_get_db),
            patch("core.estoque.get_db", side_effect=_get_db),
        ]
        for p in self.patches:
            p.start()
        import core.estoque_saldos as m
        m._ok = True

    def tearDown(self):
        for p in self.patches:
            p.stop()

    async def test_transferencia_feliz(self):
        from core.estoque import transferir
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 30)
        r = transferir("SKU1", "Loja A", "Loja B", 10, "reposicao_entre_lojas")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "disponivel")], 20)
        self.assertEqual(self.fake.saldos[("SKU1", "Loja B", "disponivel")], 10)

    async def test_falha_no_credito_do_destino_faz_rollback_da_origem(self):
        from core.estoque import transferir
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 30)
        original_execute = self.fake.execute

        async def _execute(query, *params):
            q = " ".join(query.split())
            if "INSERT INTO estoque_saldos" in q and params and params[1] == "Loja B":
                raise RuntimeError("boom no destino")
            return await original_execute(query, *params)

        self.fake.execute = _execute
        r = transferir("SKU1", "Loja A", "Loja B", 10, "reposicao_entre_lojas")
        self.assertIn("erro", r)
        # Rollback: a origem NAO pode ter sido debitada.
        self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "disponivel")], 30)
        self.assertNotIn(("SKU1", "Loja B", "disponivel"), self.fake.saldos)
        self.assertEqual(len(self.fake.movimentacoes), 0)

    async def test_origem_sem_saldo_nao_credita_destino(self):
        from core.estoque import transferir
        self.fake.set_saldo("SKU1", "Loja A", "disponivel", 3)
        r = transferir("SKU1", "Loja A", "Loja B", 10, "reposicao_entre_lojas")
        self.assertIn("erro", r)
        self.assertNotIn(("SKU1", "Loja B", "disponivel"), self.fake.saldos)
        self.assertEqual(len(self.fake.movimentacoes), 0)


class TestVinculoEstoqueEscrita(unittest.TestCase):
    """Task 3: _mover_saldo_async precisa resolver `loja` (virtual com
    vinculo ativo -> nome da fisica vinculada) ANTES de qualquer leitura/
    escrita de saldo — esse e' o unico choke point de escrita do modulo, todo
    write-path (mover_saldo/entrada/saida/transferencia/rateio/...) passa por
    aqui, entao vira vinculo-aware automaticamente.

    O resolver em si (core.lojas._loja_efetiva_async) ja' tem cobertura
    propria nos testes da Task 1 — aqui o alvo e' so' confirmar que
    _mover_saldo_async CHAMA o resolver com o nome bruto recebido e usa o
    valor DEVOLVIDO por ele (nao o original) em toda escrita subsequente.

    Importante: o patch abaixo mira `core.estoque_saldos._loja_efetiva_async`
    (o NOME importado dentro deste modulo via `from core.lojas import
    _loja_efetiva_async`), nao `core.lojas._loja_efetiva_async` — com
    `from ... import ...`, o modulo que consome fica com sua propria
    referencia ao objeto funcao; patchar so' o modulo de origem nao
    intercepta a chamada feita a partir daqui."""

    def setUp(self):
        self.fake = FakeDBSaldos()
        async def _get_db(_fake=self.fake):
            return _fake
        self.patch_db = patch("core.estoque_saldos.get_db", side_effect=_get_db)
        self.patch_db.start()
        import core.estoque_saldos as m
        m._ok = True

    def tearDown(self):
        self.patch_db.stop()

    def test_entrada_em_loja_virtual_vinculada_grava_sob_o_nome_da_fisica(self):
        from core.estoque_saldos import mover_saldo
        with patch("core.estoque_saldos._loja_efetiva_async",
                    AsyncMock(return_value="Loja Fisica Central")) as mock_resolver:
            resultado = mover_saldo("SKU-1", "Loja Virtual A", None, "disponivel", 10,
                                     "compra", usuario_id=1, usuario_nome="Teste")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertTrue(resultado.get("ok"), resultado)
        self.assertIn(("SKU-1", "Loja Fisica Central", "disponivel"), self.fake.saldos)
        self.assertNotIn(("SKU-1", "Loja Virtual A", "disponivel"), self.fake.saldos)

    def test_loja_sem_vinculo_passa_pelo_resolver_e_grava_sob_o_proprio_nome(self):
        """Regression: loja fisica (ou virtual sem vinculo) precisa continuar
        gravando sob o proprio nome — o resolver so' troca quando ha' vinculo
        ativo; aqui o fake devolve o mesmo nome recebido, como o resolver real
        faz pra esse caso (ver core/lojas.py::_loja_efetiva_async)."""
        from core.estoque_saldos import mover_saldo
        with patch("core.estoque_saldos._loja_efetiva_async",
                    AsyncMock(side_effect=lambda loja: loja)) as mock_resolver:
            resultado = mover_saldo("SKU-1", "Loja A", None, "disponivel", 10,
                                     "compra", usuario_id=1, usuario_nome="Teste")
        mock_resolver.assert_called_once_with("Loja A")
        self.assertTrue(resultado.get("ok"), resultado)
        self.assertIn(("SKU-1", "Loja A", "disponivel"), self.fake.saldos)

    def test_resolver_indisponivel_nao_derruba_a_escrita_grava_sob_nome_original(self):
        """Regression descoberta ao rodar a suite completa (Step 5): o
        resolver real (core.lojas._loja_efetiva_async) abre sua PROPRIA
        conexao via get_db(), independente do `conn` que _mover_saldo_async
        ja tem aberto. Testes de OUTROS modulos (test_estoque_seguranca.py,
        test_estoque_loja_id.py, ...) so' fakeiam core.estoque_saldos.get_db/
        core.estoque.get_db, nao core.lojas.get_db — entao, sem uma defesa
        aqui, uma excecao (DB indisponivel) OU um fake/mock alheio que nao
        cobre essa query especifica derrubava a movimentacao inteira (ou,
        pior, gravava sob um valor corrompido). O guard em
        _mover_saldo_async precisa tratar um resolver que EXPLODE como um
        no-op — grava sob o nome original, exatamente como antes do vinculo
        existir — em vez de propagar o erro pra fora de mover_saldo()."""
        from core.estoque_saldos import mover_saldo
        with patch("core.estoque_saldos._loja_efetiva_async",
                    AsyncMock(side_effect=RuntimeError("DB indisponivel"))) as mock_resolver:
            resultado = mover_saldo("SKU-1", "Loja A", None, "disponivel", 10,
                                     "compra", usuario_id=1, usuario_nome="Teste")
        mock_resolver.assert_called_once_with("Loja A")
        self.assertTrue(resultado.get("ok"), resultado)
        self.assertIn(("SKU-1", "Loja A", "disponivel"), self.fake.saldos)

    def test_resolver_devolve_valor_nao_string_e_ignorado_grava_sob_nome_original(self):
        """Mesma regression acima, outra face dela: quando o resolver NAO
        levanta excecao mas devolve algo que nao e' um nome de loja valido
        (ex.: um Mock, se algum outro teste na mesma sessao deixar
        asyncpg.create_pool monkeypatchado globalmente sem dar stop()), o
        guard deve ignorar o valor e manter o nome original — nunca gravar
        estoque sob uma chave corrompida."""
        from core.estoque_saldos import mover_saldo
        with patch("core.estoque_saldos._loja_efetiva_async",
                    AsyncMock(return_value=object())) as mock_resolver:
            resultado = mover_saldo("SKU-1", "Loja A", None, "disponivel", 10,
                                     "compra", usuario_id=1, usuario_nome="Teste")
        mock_resolver.assert_called_once_with("Loja A")
        self.assertTrue(resultado.get("ok"), resultado)
        self.assertIn(("SKU-1", "Loja A", "disponivel"), self.fake.saldos)


if __name__ == "__main__":
    unittest.main(verbosity=2)
