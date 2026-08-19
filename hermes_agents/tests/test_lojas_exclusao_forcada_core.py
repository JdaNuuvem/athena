"""Testes de core/lojas.py::excluir_forcado() — exclusao permanente de loja
inativa com dado vinculado, numa unica transacao atomica. Padrao de mock
(_mock_conn/_mock_db_com_conn) e' o mesmo de
tests/test_lojas_vinculo_estoque.py::TestVincularDesvincularEstoque."""
import sys, os, unittest
from unittest.mock import patch, AsyncMock, MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.lojas as lojas


def _mock_conn(fetchrow_return=None, execute_return="DELETE 0"):
    conn = AsyncMock()
    conn.fetchrow.return_value = fetchrow_return
    conn.execute.return_value = execute_return
    tx_ctx = AsyncMock(__aenter__=AsyncMock(return_value=None), __aexit__=AsyncMock(return_value=False))
    conn.transaction = MagicMock(return_value=tx_ctx)
    return conn


def _mock_db_com_conn(conn):
    acquire_ctx = AsyncMock(__aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock(return_value=False))
    db = AsyncMock()
    db.acquire = MagicMock(return_value=acquire_ctx)
    return db


class TestExcluirForcado(unittest.TestCase):
    def test_loja_inexistente_retorna_erro_sem_tocar_em_nada(self):
        conn = _mock_conn(fetchrow_return=None)
        db = _mock_db_com_conn(conn)
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.excluir_forcado(999, "Qualquer Nome")
        self.assertEqual(resultado, {"erro": "Loja nao encontrada"})
        conn.execute.assert_not_called()

    def test_loja_ativa_retorna_erro_sem_tocar_em_nada(self):
        conn = _mock_conn(fetchrow_return={"id": 1, "nome": "Loja X", "status": "ativa"})
        db = _mock_db_com_conn(conn)
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.excluir_forcado(1, "Loja X")
        self.assertEqual(resultado, {"erro": "Loja precisa estar inativa antes de forcar exclusao"})
        conn.execute.assert_not_called()

    def test_confirmar_nome_errado_retorna_erro_sem_apagar_nada(self):
        conn = _mock_conn(fetchrow_return={"id": 1, "nome": "Loja X", "status": "inativa"})
        db = _mock_db_com_conn(conn)
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.excluir_forcado(1, "Loja X ")  # espaco extra
        self.assertEqual(resultado, {"erro": "Nome de confirmacao nao confere"})
        conn.execute.assert_not_called()

    def test_sucesso_apaga_na_ordem_certa_e_retorna_contagem(self):
        conn = _mock_conn(fetchrow_return={"id": 1, "nome": "Loja X", "status": "inativa"},
                           execute_return="DELETE 2")
        db = _mock_db_com_conn(conn)
        with patch("core.lojas.get_db", AsyncMock(return_value=db)), \
             patch("core.lojas.invalidar_cache_loja_efetiva") as mock_inv1, \
             patch("core.lojas.invalidar_cache_loja_id") as mock_inv2:
            resultado = lojas.excluir_forcado(1, "Loja X")
        self.assertTrue(resultado.get("ok"))
        self.assertEqual(len(resultado["apagado"]), len(lojas._CASCATA_EXCLUSAO_FORCADA))
        self.assertTrue(all(n == 2 for n in resultado["apagado"].values()))
        sqls = [c.args[0] for c in conn.execute.call_args_list]
        idx_pdv_vendas = next(i for i, s in enumerate(sqls) if s.startswith("DELETE FROM pdv_vendas WHERE"))
        idx_pdv_caixas = next(i for i, s in enumerate(sqls) if s.startswith("DELETE FROM pdv_caixas WHERE"))
        self.assertLess(idx_pdv_vendas, idx_pdv_caixas, "pdv_vendas (filha) precisa vir antes de pdv_caixas (mae)")
        idx_lojas_delete = next(i for i, s in enumerate(sqls) if s.startswith("DELETE FROM lojas WHERE"))
        self.assertEqual(idx_lojas_delete, len(sqls) - 1, "DELETE FROM lojas precisa ser o ultimo passo")
        mock_inv1.assert_called_once()
        mock_inv2.assert_called_once()

    def test_cascata_inclui_tabelas_adicionadas_no_review_final(self):
        """Achado do review final da branch: 4 tabelas faltavam na cascata —
        loja_integracoes/loja_responsaveis/usuario_lojas (ja tinham ON DELETE
        CASCADE, mas ficavam invisiveis na previa/auditoria) e "vendas"
        (tabela legada sem FK, inclusao no escopo real por decisao explicita
        do usuario). Nao basta confiar na asserção de tamanho baseada na
        propria constante — este teste confere os nomes de verdade."""
        conn = _mock_conn(fetchrow_return={"id": 1, "nome": "Loja X", "status": "inativa"},
                           execute_return="DELETE 1")
        db = _mock_db_com_conn(conn)
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.excluir_forcado(1, "Loja X")
        self.assertTrue(resultado.get("ok"))
        sqls = [c.args[0] for c in conn.execute.call_args_list]
        self.assertTrue(any(s.startswith("DELETE FROM vendas WHERE") for s in sqls),
                         "vendas precisa ser apagada na cascata (decisao do usuario)")
        self.assertTrue(any(s.startswith("DELETE FROM usuario_lojas WHERE") for s in sqls),
                         "usuario_lojas precisa ser apagada na cascata (honestidade do preview)")
        self.assertTrue(any(s.startswith("DELETE FROM loja_integracoes WHERE") for s in sqls),
                         "loja_integracoes precisa ser apagada na cascata (honestidade do preview)")
        self.assertTrue(any(s.startswith("DELETE FROM loja_responsaveis WHERE") for s in sqls),
                         "loja_responsaveis precisa ser apagada na cascata (honestidade do preview)")
        self.assertIn("vendas", resultado["apagado"])
        self.assertIn("usuario_lojas", resultado["apagado"])
        self.assertIn("loja_integracoes", resultado["apagado"])
        self.assertIn("loja_responsaveis", resultado["apagado"])

    def test_garante_coluna_pedido_id_antes_de_usar_crm_negociacoes(self):
        """Achado real: crm_negociacoes.pedido_id so' era criado sob demanda
        dentro de ao_converter_negociacao() (core/entidades.py) — se nenhuma
        negociacao jamais foi convertida em producao, a coluna nao existia, e
        excluir_forcado() estourava "column pedido_id does not exist" ao
        tentar excluir uma loja Shopee. O ALTER TABLE IF NOT EXISTS precisa
        rodar ANTES do UPDATE que usa a coluna, dentro da mesma transacao."""
        conn = _mock_conn(fetchrow_return={"id": 1, "nome": "Loja X", "status": "inativa"},
                           execute_return="UPDATE 0")
        db = _mock_db_com_conn(conn)
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.excluir_forcado(1, "Loja X")
        self.assertTrue(resultado.get("ok"))
        sqls = [c.args[0] for c in conn.execute.call_args_list]
        idx_alter = next(i for i, s in enumerate(sqls)
                          if "ALTER TABLE crm_negociacoes ADD COLUMN IF NOT EXISTS pedido_id" in s)
        idx_update = next(i for i, s in enumerate(sqls) if s.startswith("UPDATE crm_negociacoes SET pedido_id"))
        self.assertLess(idx_alter, idx_update, "ALTER precisa rodar antes do UPDATE que usa a coluna")

    def test_negociacoes_crm_sao_desvinculadas_nao_apagadas(self):
        conn = _mock_conn(fetchrow_return={"id": 1, "nome": "Loja X", "status": "inativa"},
                           execute_return="UPDATE 4")
        db = _mock_db_com_conn(conn)
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.excluir_forcado(1, "Loja X")
        self.assertEqual(resultado["negociacoes_crm_desvinculadas"], 4)
        sqls = [c.args[0] for c in conn.execute.call_args_list]
        self.assertTrue(any("UPDATE crm_negociacoes SET pedido_id = NULL" in s for s in sqls))
        self.assertFalse(any("DELETE FROM crm_negociacoes" in s for s in sqls))

    def test_loja_vinculada_por_outra_loja_tem_vinculo_nulificado_sem_apagar_a_vinculadora(self):
        conn = _mock_conn(fetchrow_return={"id": 2, "nome": "Loja Fisica", "status": "inativa"},
                           execute_return="UPDATE 1")
        db = _mock_db_com_conn(conn)
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.excluir_forcado(2, "Loja Fisica")
        self.assertTrue(resultado.get("ok"))
        sqls = [c.args[0] for c in conn.execute.call_args_list]
        self.assertIn("UPDATE lojas SET loja_vinculada_id = NULL WHERE loja_vinculada_id = $1", sqls)
        self.assertIn("UPDATE lojas SET loja_matriz_id = NULL WHERE loja_matriz_id = $1", sqls)
        self.assertFalse(any(s.startswith("DELETE FROM lojas WHERE loja_vinculada_id") for s in sqls),
                          "a loja vinculadora nunca deve ser apagada, so' desvinculada")

    def test_falha_no_meio_da_transacao_faz_rollback_completo(self):
        """Prova de atomicidade REAL (estado em memoria com rollback de
        verdade), mesma tecnica de
        tests/test_lojas_vinculo_estoque.py::_FakeTxLojas."""
        estado = {"lojas": {1: {"id": 1, "nome": "Loja X", "status": "inativa",
                                 "loja_vinculada_id": None, "loja_matriz_id": None}},
                  "deletes": []}

        class _FakeTx:
            def __init__(self, estado): self._estado = estado; self._snap = None
            async def __aenter__(self):
                self._snap = {"lojas": {k: dict(v) for k, v in self._estado["lojas"].items()},
                              "deletes": list(self._estado["deletes"])}
                return self
            async def __aexit__(self, exc_type, exc, tb):
                if exc_type is not None:
                    self._estado["lojas"] = self._snap["lojas"]
                    self._estado["deletes"] = self._snap["deletes"]
                return False

        class _FakeConn:
            def __init__(self, estado): self._estado = estado
            def transaction(self): return _FakeTx(self._estado)
            async def fetchrow(self, query, *params):
                return dict(self._estado["lojas"][params[0]]) if params[0] in self._estado["lojas"] else None
            async def execute(self, query, *params):
                if query.startswith("DELETE FROM producao_custos"):
                    raise Exception("boom - falha simulada no meio da cascata")
                if query.startswith("DELETE FROM") or query.startswith("UPDATE"):
                    self._estado["deletes"].append(query)
                return "DELETE 1"

        class _FakeAcquireCtx:
            def __init__(self, conn): self._conn = conn
            async def __aenter__(self): return self._conn
            async def __aexit__(self, exc_type, exc, tb): return False

        class _FakeDB:
            def __init__(self, estado): self._conn = _FakeConn(estado)
            def acquire(self): return _FakeAcquireCtx(self._conn)

        db = _FakeDB(estado)
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.excluir_forcado(1, "Loja X")
        self.assertIn("erro", resultado)
        self.assertEqual(estado["deletes"], [], "rollback precisa desfazer TODOS os deletes ja executados")
        self.assertIn(1, estado["lojas"], "a loja nao pode ter sido apagada quando a transacao falha no meio")


if __name__ == "__main__":
    unittest.main(verbosity=2)
