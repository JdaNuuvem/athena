"""Testes de core/lojas.py — resolver de vinculo de estoque fisica x virtual
e vincular_estoque()/desvincular_estoque()."""
import sys, os, unittest
from unittest.mock import patch, AsyncMock, MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.lojas as lojas


class TestLojaEfetivaAsync(unittest.TestCase):
    def setUp(self):
        lojas.invalidar_cache_loja_efetiva()

    def test_loja_sem_vinculo_retorna_o_proprio_nome(self):
        db = AsyncMock()
        db.fetchrow.return_value = None
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async("Loja X"))
        self.assertEqual(resultado, "Loja X")

    def test_loja_virtual_vinculada_resolve_para_fisica(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"nome": "Loja Fisica Central"}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async("Loja Virtual A"))
        self.assertEqual(resultado, "Loja Fisica Central")

    def test_loja_vazia_nao_consulta_banco(self):
        db = AsyncMock()
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async(""))
        self.assertEqual(resultado, "")
        db.fetchrow.assert_not_called()

    def test_id_com_vinculo_resolve_para_nome_da_fisica(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"nome": "Loja Virtual A", "tipo": "virtual", "nome_fisica": "Loja Fisica Central"}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async("42"))
        self.assertEqual(resultado, "Loja Fisica Central")

    def test_id_sem_vinculo_resolve_para_o_proprio_nome(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"nome": "Loja Y", "nome_fisica": None}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async("7"))
        self.assertEqual(resultado, "Loja Y")

    def test_id_fisica_com_loja_vinculada_id_setado_ignora_e_resolve_proprio_nome(self):
        """Regressao: loja fisica (tipo != 'virtual') com loja_vinculada_id
        setado (nao deveria acontecer, mas o resolver nao pode confiar so' na
        escrita) deve resolver pro proprio nome, nunca pro nome "vinculado"."""
        db = AsyncMock()
        db.fetchrow.return_value = {"nome": "Loja Fisica Y", "tipo": "fisica", "nome_fisica": "Loja Vinculada Errada"}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async("99"))
        self.assertEqual(resultado, "Loja Fisica Y")

    def test_cache_evita_segunda_consulta(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"nome": "Loja Fisica Central"}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            lojas._sync_run(lojas._loja_efetiva_async("Loja Virtual A"))
            lojas._sync_run(lojas._loja_efetiva_async("Loja Virtual A"))
        self.assertEqual(db.fetchrow.call_count, 1)


class TestLojaEfetivaSync(unittest.TestCase):
    def setUp(self):
        lojas.invalidar_cache_loja_efetiva()

    def test_cursor_sync_resolve_vinculo(self):
        cur = MagicMock()
        cur.fetchone.return_value = ("Loja Fisica Central",)
        resultado = lojas.loja_efetiva_sync(cur, "Loja Virtual A")
        self.assertEqual(resultado, "Loja Fisica Central")

    def test_cursor_sync_sem_vinculo_retorna_proprio_nome(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        resultado = lojas.loja_efetiva_sync(cur, "Loja X")
        self.assertEqual(resultado, "Loja X")

    def test_cursor_sync_id_virtual_com_vinculo_resolve_para_fisica(self):
        cur = MagicMock()
        cur.fetchone.return_value = ("Loja Virtual A", "virtual", "Loja Fisica Central")
        resultado = lojas.loja_efetiva_sync(cur, "42")
        self.assertEqual(resultado, "Loja Fisica Central")

    def test_cursor_sync_id_sem_vinculo_resolve_proprio_nome(self):
        cur = MagicMock()
        cur.fetchone.return_value = ("Loja Y", "fisica", None)
        resultado = lojas.loja_efetiva_sync(cur, "7")
        self.assertEqual(resultado, "Loja Y")

    def test_cursor_sync_id_fisica_com_loja_vinculada_id_setado_ignora_e_resolve_proprio_nome(self):
        """Regressao (mesmo caso do async acima): loja fisica com
        loja_vinculada_id setado nao deve resolver pro nome "vinculado"."""
        cur = MagicMock()
        cur.fetchone.return_value = ("Loja Fisica Y", "fisica", "Loja Vinculada Errada")
        resultado = lojas.loja_efetiva_sync(cur, "99")
        self.assertEqual(resultado, "Loja Fisica Y")


def _mock_conn(fetchrow_side_effect=None, fetch_return_value=None):
    """AsyncMock de uma conexao asyncpg (fetchrow/fetch/execute) + o
    `.transaction()` dela — usado pelos testes de desvincular_estoque, que
    roda tudo (leitura + limpeza do vinculo + copia por sku) numa unica
    conexao/transacao (fix pos-review de atomicidade/vazamento de pool).
    `.acquire()`/`.transaction()` sao chamados SEM await no codigo real
    (mesmo padrao de core/estoque.py::transferir()), entao precisam ser
    MagicMock (sync) — o auto-child de um AsyncMock seria AsyncMock e
    quebraria o `async with x() as y:` sem await antes do `x()`."""
    conn = AsyncMock()
    if fetchrow_side_effect is not None:
        conn.fetchrow.side_effect = fetchrow_side_effect
    if fetch_return_value is not None:
        conn.fetch.return_value = fetch_return_value
    conn.execute.return_value = "OK"
    tx_ctx = AsyncMock(__aenter__=AsyncMock(return_value=None), __aexit__=AsyncMock(return_value=False))
    conn.transaction = MagicMock(return_value=tx_ctx)
    return conn


def _mock_db_com_conn(conn):
    """AsyncMock de um pool cujo `.acquire()` devolve `conn` via `async with`."""
    acquire_ctx = AsyncMock(__aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock(return_value=False))
    db = AsyncMock()
    db.acquire = MagicMock(return_value=acquire_ctx)
    return db


class _FakeTxLojas:
    """Transacao simulada com rollback REAL: tira snapshot do dict `lojas`
    na entrada e restaura se sair por excecao. Mesma tecnica de
    tests/test_estoque_saldos.py::_FakeTransactionCtx (usada la' pra provar
    a atomicidade de transferir()) — aqui prova que uma falha no meio do
    loop de copia de desvincular_estoque desfaz o UPDATE que ja tinha
    limpado loja_vinculada_id."""
    def __init__(self, estado):
        self._estado = estado
        self._snap = None

    async def __aenter__(self):
        self._snap = {k: dict(v) for k, v in self._estado["lojas"].items()}
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self._estado["lojas"] = self._snap
        return False


class _FakeConnLojas:
    def __init__(self, estado):
        self._estado = estado

    def transaction(self):
        return _FakeTxLojas(self._estado)

    async def fetchrow(self, query, *params):
        q = " ".join(query.split())
        if "loja_vinculada_id FROM lojas" in q:
            row = self._estado["lojas"].get(params[0])
            return dict(row) if row else None
        if "SELECT nome FROM lojas" in q:
            row = self._estado["lojas"].get(params[0])
            return {"nome": row["nome"]} if row else None
        return None

    async def fetch(self, query, *params):
        return list(self._estado["saldos_fisica"])

    async def execute(self, query, *params):
        q = " ".join(query.split())
        if "loja_vinculada_id = NULL" in q:
            self._estado["lojas"][params[0]]["loja_vinculada_id"] = None
        return "OK"


class _FakeAcquireCtxLojas:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeDBLojas:
    """Fake do pool asyncpg com estado real em memoria (nao so' registra
    chamadas) — precisa disso pra verificar que o ROLLBACK de fato desfez
    a escrita, nao so' que uma excecao foi levantada."""
    def __init__(self, estado):
        self._conn = _FakeConnLojas(estado)

    def acquire(self):
        return _FakeAcquireCtxLojas(self._conn)


class TestVincularDesvincularEstoque(unittest.TestCase):
    def setUp(self):
        lojas.invalidar_cache_loja_efetiva()

    def test_vincular_rejeita_se_virtual_nao_e_tipo_virtual(self):
        db = AsyncMock()
        db.fetchrow.side_effect = [
            {"id": 1, "tipo": "fisica", "nome": "Loja A"},  # loja "virtual" informada
            {"id": 2, "tipo": "fisica", "nome": "Loja B"},
        ]
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.vincular_estoque(1, 2)
        self.assertIn("erro", resultado)

    def test_vincular_rejeita_se_fisica_nao_e_tipo_fisica(self):
        db = AsyncMock()
        db.fetchrow.side_effect = [
            {"id": 1, "tipo": "virtual", "nome": "Loja Virtual A"},
            {"id": 2, "tipo": "virtual", "nome": "Loja Virtual B"},
        ]
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.vincular_estoque(1, 2)
        self.assertIn("erro", resultado)

    def test_desvincular_sem_vinculo_ativo_retorna_erro(self):
        conn = _mock_conn(fetchrow_side_effect=[
            {"id": 1, "tipo": "virtual", "nome": "Loja Virtual A", "loja_vinculada_id": None},
        ])
        db = _mock_db_com_conn(conn)
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.desvincular_estoque(1)
        self.assertIn("erro", resultado)

    def test_vincular_sucesso_grava_vinculo_e_invalida_cache(self):
        db = AsyncMock()
        db.fetchrow.side_effect = [
            {"id": 1, "tipo": "virtual", "nome": "Loja Virtual A"},
            {"id": 2, "tipo": "fisica", "nome": "Loja Fisica B"},
        ]
        lojas._cache_loja_efetiva["algo"] = "valor_stale"
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.vincular_estoque(1, 2)
        self.assertTrue(resultado.get("ok"))
        self.assertEqual(resultado["loja_virtual"], "Loja Virtual A")
        self.assertEqual(resultado["loja_fisica"], "Loja Fisica B")
        db.execute.assert_called_once_with(
            "UPDATE lojas SET loja_vinculada_id = $1 WHERE id = $2", 2, 1)
        self.assertEqual(lojas._cache_loja_efetiva, {})

    def test_desvincular_sucesso_copia_saldos_por_sku_e_limpa_vinculo(self):
        conn = _mock_conn(
            fetchrow_side_effect=[
                {"id": 1, "tipo": "virtual", "nome": "Loja Virtual A", "loja_vinculada_id": 2},
                {"nome": "Loja Fisica B"},
            ],
            fetch_return_value=[
                {"sku": "SKU1", "quantidade": 10},
                {"sku": "SKU2", "quantidade": 5},
            ],
        )
        db = _mock_db_com_conn(conn)
        lojas._cache_loja_efetiva["algo"] = "valor_stale"
        with patch("core.lojas.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque.entrada_async", AsyncMock(return_value={"ok": True})) as mock_entrada:
            resultado = lojas.desvincular_estoque(1)
        self.assertTrue(resultado.get("ok"))
        self.assertEqual(resultado["loja_virtual"], "Loja Virtual A")
        self.assertEqual(resultado["loja_fisica"], "Loja Fisica B")
        self.assertEqual(resultado["skus_copiados"], 2)
        # entrada_async precisa reaproveitar a MESMA conexao (conn) da
        # transacao — e' isso que elimina o vazamento de um pool por sku.
        mock_entrada.assert_any_call(conn, "SKU1", "Loja Virtual A", 10.0, "ajuste_inventario")
        mock_entrada.assert_any_call(conn, "SKU2", "Loja Virtual A", 5.0, "ajuste_inventario")
        limpa_calls = [c for c in conn.execute.call_args_list
                       if "loja_vinculada_id = NULL" in c.args[0]]
        self.assertEqual(len(limpa_calls), 1)
        self.assertEqual(limpa_calls[0].args[1], 1)
        self.assertEqual(lojas._cache_loja_efetiva, {})

    def test_desvincular_falha_no_meio_do_loop_reverte_transacao_e_mantem_vinculo(self):
        """Fix pos-review (atomicidade): antes, uma falha no meio do loop de
        copia deixava o vinculo ja limpo com so' parte dos saldos copiados —
        uma nova tentativa esbarrava em "sem vinculo ativo", sem jeito de
        retomar. Agora tudo roda numa transacao so': uma falha em qualquer
        sku reverte TUDO (inclusive o UPDATE que tinha acabado de limpar
        loja_vinculada_id), e uma nova tentativa funciona normalmente."""
        estado = {
            "lojas": {
                1: {"id": 1, "tipo": "virtual", "nome": "Loja Virtual A", "loja_vinculada_id": 2},
                2: {"id": 2, "tipo": "fisica", "nome": "Loja Fisica B", "loja_vinculada_id": None},
            },
            "saldos_fisica": [
                {"sku": "SKU1", "quantidade": 10},
                {"sku": "SKU2", "quantidade": 5},
            ],
        }
        db = _FakeDBLojas(estado)

        with patch("core.lojas.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque.entrada_async", AsyncMock(side_effect=[{"ok": True}, {"erro": "boom"}])):
            resultado = lojas.desvincular_estoque(1)
        self.assertIn("erro", resultado)
        self.assertIn("SKU2", resultado["erro"])
        # Rollback real: o vinculo continua ativo (2), NAO None.
        self.assertEqual(estado["lojas"][1]["loja_vinculada_id"], 2)

        # Prova final: uma nova tentativa (sem a falha) tem que funcionar —
        # confirma que o estado ficou de fato utilizavel pra retry.
        with patch("core.lojas.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque.entrada_async", AsyncMock(return_value={"ok": True})):
            resultado2 = lojas.desvincular_estoque(1)
        self.assertTrue(resultado2.get("ok"), resultado2)
        self.assertEqual(resultado2["skus_copiados"], 2)
        self.assertIsNone(estado["lojas"][1]["loja_vinculada_id"])
