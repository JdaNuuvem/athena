# Exclusão Forçada de Loja — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que um Admin apague permanentemente uma loja **inativa** que tem dado vinculado (estoque, vendas, PDV, produção, fiscal, etc), depois de ver uma prévia do impacto e confirmar digitando o nome exato da loja — sem alterar em nada o comportamento da exclusão comum (`DELETE /api/lojas/manage/<id>`), que continua bloqueando com 409 por padrão.

**Architecture:** Duas funções novas em `core/lojas.py` (`impacto_exclusao` só-leitura, `excluir_forcado` transacional) reaproveitam a mesma lista ordenada de `(tabela, where_clause)` — a cascata de exclusão é dado, não lógica duplicada. Duas rotas novas em `routes/lojas_manage.py`, gated por uma permissão RBAC dedicada (`lojas.excluir_forcado`, Admin-only). Frontend: um link "Excluir mesmo assim" aparece só quando o 409 padrão bate, a loja está inativa e o usuário tem a permissão; abre um modal com prévia de impacto + confirmação por nome.

**Tech Stack:** Flask + asyncpg (backend, `hermes_agents/`), Next.js + TypeScript (frontend, `web/`), unittest + `unittest.mock` (testes Python).

## Global Constraints

- Toda a cascata de exclusão roda numa única transação (`async with db.acquire() as conn: async with conn.transaction():`) — sucesso total ou rollback total, nunca cascata parcial. Padrão de referência: `core/lojas.py::desvincular_estoque()`.
- `$1` é sempre `id_loja` (int), passado via parametrização do asyncpg — nunca string-interpolado a partir de input do usuário. Os nomes de tabela/coluna interpolados via f-string vêm só da constante `_CASCATA_EXCLUSAO_FORCADA` (hardcoded no código, nunca do usuário) — mesmo padrão já usado em `core/pdv.py::_list()`/`_delete()`.
- `confirmar_nome` é comparado por igualdade exata (`==`), sem `.strip()`/`.lower()` em nenhuma camada (rota nem função core) — um espaço extra ou case diferente precisa reprovar a confirmação de propósito.
- Só loja com `status == "inativa"` pode ser avaliada (`impacto_exclusao`) ou excluída (`excluir_forcado`) via este fluxo. Nunca `ativa`/`em_implantacao`/`bloqueada`.
- `compras_pedidos`, `fin_contas_pagar` (e as filhas de `compras_pedidos`) **nunca** entram na cascata — são dado centralizado (`loja_id` default de "loja principal", não escopo real por loja). Não aparecem nem na prévia nem na exclusão.
- `fiscal_notas_fiscais` (+ filhas `fiscal_nfe_itens`/`fiscal_impostos_nota`) fica no escopo normalmente, sem nenhum bloqueio especial — decisão explícita do usuário ("só avisa, deixa passar"), ao contrário da recomendação original de bloquear.
- Nenhuma das duas rotas novas usa `@requer_acesso_loja` — é ação administrativa central, restrita só pela permissão `lojas.excluir_forcado` (que hoje só o role Admin tem).
- `lojas.excluir_forcado` é concedida automaticamente **só** ao role Admin — mesmo padrão de `lojas.ver_todas` (`core/rbac.py`), com seed inicial (`if count == 0`) **e** fix-up idempotente pra bancos já seedados antes desta permissão existir.

---

### Task 1: `core/lojas.py` — lista da cascata + `impacto_exclusao()` (dry-run)

**Files:**
- Modify: `hermes_agents/core/lojas.py` (inserir depois de `deletar()`, linha 456, antes do comentário `# ── Sync Bling ──` na linha 458)
- Test: `hermes_agents/tests/test_lojas_exclusao_forcada_impacto.py`

**Interfaces:**
- Consumes: `get_db()`, `run_async()`, `log` (já importados em `core/lojas.py:4`); `_log_erro(onde: str, e: Exception)` (`core/lojas.py:43`).
- Produces: constante `_CASCATA_EXCLUSAO_FORCADA: list[tuple[str, str]]` (tabela, where_clause) e `_WHERE_CRM_NEGOCIACOES_VINCULADAS: str` — reaproveitadas pelo Task 2. Função `impacto_exclusao(id_loja: int) -> dict` retornando `{"erro": str}` OU `{"loja": dict, "impacto": dict[str,int], "negociacoes_crm_desvinculadas": int, "total_linhas": int}`.

- [ ] **Step 1: Escrever os testes (vão falhar — a função ainda não existe)**

Criar `hermes_agents/tests/test_lojas_exclusao_forcada_impacto.py`:

```python
"""Testes de core/lojas.py::impacto_exclusao() — dry-run de contagem por
tabela antes de uma exclusao forcada, sem apagar nada. Ver
docs/superpowers/specs/2026-08-09-exclusao-forcada-loja-design.md."""
import sys, os, unittest
from unittest.mock import patch, AsyncMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.lojas as lojas


class TestImpactoExclusao(unittest.TestCase):
    def test_loja_inexistente_retorna_erro(self):
        db = AsyncMock()
        db.fetchrow.return_value = None
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.impacto_exclusao(999)
        self.assertEqual(resultado, {"erro": "Loja nao encontrada"})

    def test_loja_ativa_retorna_erro_pedindo_desativacao(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"id": 1, "nome": "Loja Ativa", "status": "ativa"}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.impacto_exclusao(1)
        self.assertEqual(resultado, {"erro": "Loja precisa estar inativa antes de avaliar exclusao forcada"})
        db.fetchval.assert_not_called()

    def test_loja_inativa_sem_dado_vinculado_retorna_contagens_zeradas(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"id": 1, "nome": "Loja Teste", "status": "inativa"}
        db.fetchval.return_value = 0
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.impacto_exclusao(1)
        self.assertNotIn("erro", resultado)
        self.assertEqual(resultado["total_linhas"], 0)
        self.assertEqual(resultado["negociacoes_crm_desvinculadas"], 0)
        self.assertEqual(len(resultado["impacto"]), len(lojas._CASCATA_EXCLUSAO_FORCADA))
        self.assertTrue(all(n == 0 for n in resultado["impacto"].values()))

    def test_loja_inativa_com_dado_retorna_contagem_por_tabela(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"id": 1, "nome": "Loja Teste", "status": "inativa"}
        def _fetchval(sql, *params):
            if sql.startswith("SELECT COUNT(*) FROM pdv_caixas WHERE"):
                return 3
            if sql.startswith("SELECT COUNT(*) FROM vendas_pedidos WHERE"):
                return 7
            return 0
        db.fetchval = AsyncMock(side_effect=_fetchval)
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.impacto_exclusao(1)
        self.assertEqual(resultado["impacto"]["pdv_caixas"], 3)
        self.assertEqual(resultado["impacto"]["vendas_pedidos"], 7)
        self.assertEqual(resultado["total_linhas"], 10)

    def test_loja_devolve_dados_completos_da_loja(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"id": 5, "nome": "Loja Charme", "status": "inativa", "tipo": "fisica"}
        db.fetchval.return_value = 0
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.impacto_exclusao(5)
        self.assertEqual(resultado["loja"]["nome"], "Loja Charme")
        self.assertEqual(resultado["loja"]["id"], 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run (de dentro de `hermes_agents/`): `python -m pytest tests/test_lojas_exclusao_forcada_impacto.py -v`
Expected: FAIL com `AttributeError: module 'core.lojas' has no attribute 'impacto_exclusao'` (ou `_CASCATA_EXCLUSAO_FORCADA`).

- [ ] **Step 3: Implementar a constante da cascata + `impacto_exclusao()`**

Em `hermes_agents/core/lojas.py`, inserir o bloco abaixo logo depois do fim de `deletar()` (depois da linha `return {"erro": str(e)}` que fecha `deletar()`, linha 456) e antes do comentário `# ── Sync Bling ──`:

```python
# ── Exclusao forcada (irreversivel) ──
# Cascata completa de tabelas com dado vinculado a uma loja, na ordem
# correta de dependencia (filhas antes de maes) — reaproveitada por
# impacto_exclusao() (so' leitura) e excluir_forcado() (apaga de verdade).
# compras_pedidos/fin_contas_pagar ficam FORA de proposito: seu loja_id e'
# so' um default de "loja principal" (core/compras.py), nao escopo real por
# loja — apagar por loja_id nessas tabelas destruiria dado da empresa
# inteira sempre que a loja-alvo for a principal.
_CASCATA_EXCLUSAO_FORCADA = [
    ("pdv_devolucoes", "venda_id IN (SELECT id FROM pdv_vendas WHERE caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1))"),
    ("pdv_pagamentos", "venda_id IN (SELECT id FROM pdv_vendas WHERE caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1))"),
    ("pdv_itens", "venda_id IN (SELECT id FROM pdv_vendas WHERE caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1))"),
    ("pdv_turnos", "caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1)"),
    ("pdv_caixa_conferencia", "caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1)"),
    ("pdv_caixa_contagem", "caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1)"),
    ("pdv_suprimentos", "caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1)"),
    ("pdv_sangrias", "caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1)"),
    ("pdv_vendas", "caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1)"),
    ("pdv_caixas", "loja_id = $1"),
    ("vendas_pagamentos", "pedido_id IN (SELECT id FROM vendas_pedidos WHERE loja_id = $1)"),
    ("vendas_historico_status", "pedido_id IN (SELECT id FROM vendas_pedidos WHERE loja_id = $1)"),
    ("vendas_itens", "pedido_id IN (SELECT id FROM vendas_pedidos WHERE loja_id = $1)"),
    ("vendas_pedidos", "loja_id = $1"),
    ("fin_cofre_movimentos", "cofre_id IN (SELECT id FROM fin_cofre WHERE loja_id = $1)"),
    ("fin_cofre", "loja_id = $1"),
    ("estoque_lojas", "loja_id = $1"),
    ("estoque_movimentacoes", "loja_id = $1"),
    ("estoque_transferencias", "(loja_origem_id = $1 OR loja_destino_id = $1)"),
    ("estoque_contagens", "loja_id = $1"),
    ("producao_bom", "op_id IN (SELECT id FROM producao_ops WHERE loja_id = $1)"),
    ("producao_apontamentos", "op_id IN (SELECT id FROM producao_ops WHERE loja_id = $1)"),
    ("producao_consumo", "op_id IN (SELECT id FROM producao_ops WHERE loja_id = $1)"),
    ("producao_perdas", "op_id IN (SELECT id FROM producao_ops WHERE loja_id = $1)"),
    ("producao_custos", "op_id IN (SELECT id FROM producao_ops WHERE loja_id = $1)"),
    ("producao_ops", "loja_id = $1"),
    ("chat_conversas", "loja_id = $1"),
    ("shopee_estoque_snapshot", "loja_id = $1"),
    ("fiscal_nfe_itens", "nota_id IN (SELECT id FROM fiscal_notas_fiscais WHERE loja_id = $1)"),
    ("fiscal_impostos_nota", "nota_id IN (SELECT id FROM fiscal_notas_fiscais WHERE loja_id = $1)"),
    ("fiscal_notas_fiscais", "loja_id = $1"),
    ("fin_contas_receber", "loja_id = $1"),
    ("autom_regras_preco", "loja_id = $1"),
]

# crm_negociacoes.pedido_id e' nullable (FK -> vendas_pedidos.id) — a
# negociacao nunca e' apagada, so' perde a referencia ao pedido.
_WHERE_CRM_NEGOCIACOES_VINCULADAS = "pedido_id IN (SELECT id FROM vendas_pedidos WHERE loja_id = $1)"


def impacto_exclusao(id_loja: int) -> dict:
    """Dry-run de excluir_forcado(): conta quantas linhas seriam apagadas em
    cada tabela do escopo, sem apagar nada. So' aceita loja ja inativa —
    mesma trava que excluir_forcado() usa."""
    _ensure_table()
    async def _go():
        db = await get_db()
        loja_row = await db.fetchrow("SELECT * FROM lojas WHERE id = $1", id_loja)
        if not loja_row:
            return {"erro": "Loja nao encontrada"}
        loja = dict(loja_row)
        if loja.get("status") != "inativa":
            return {"erro": "Loja precisa estar inativa antes de avaliar exclusao forcada"}
        impacto = {}
        total = 0
        for tabela, where_clause in _CASCATA_EXCLUSAO_FORCADA:
            n = await db.fetchval(f"SELECT COUNT(*) FROM {tabela} WHERE {where_clause}", id_loja)
            impacto[tabela] = n
            total += n
        negociacoes = await db.fetchval(
            f"SELECT COUNT(*) FROM crm_negociacoes WHERE {_WHERE_CRM_NEGOCIACOES_VINCULADAS}", id_loja)
        return {"loja": loja, "impacto": impacto,
                "negociacoes_crm_desvinculadas": negociacoes, "total_linhas": total}
    try:
        return run_async(_go())
    except Exception as e:
        _log_erro("impacto_exclusao", e)
        return {"erro": str(e)}
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `python -m pytest tests/test_lojas_exclusao_forcada_impacto.py -v`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/lojas.py hermes_agents/tests/test_lojas_exclusao_forcada_impacto.py
git commit -m "feat: adiciona impacto_exclusao() para prever cascata de exclusao forcada de loja"
```

---

### Task 2: `core/lojas.py` — `excluir_forcado()` (exclusão transacional)

**Files:**
- Modify: `hermes_agents/core/lojas.py` (inserir logo depois de `impacto_exclusao()`, criada no Task 1)
- Test: `hermes_agents/tests/test_lojas_exclusao_forcada_core.py`

**Interfaces:**
- Consumes: `_CASCATA_EXCLUSAO_FORCADA`, `_WHERE_CRM_NEGOCIACOES_VINCULADAS` (Task 1); `get_db()`, `run_async()`, `_log_erro()`; `invalidar_cache_loja_efetiva()` e `invalidar_cache_loja_id()` (já existem em `core/lojas.py`, usadas por `desvincular_estoque()`/`criar()`).
- Produces: `excluir_forcado(id_loja: int, confirmar_nome: str) -> dict` retornando `{"erro": str}` OU `{"ok": True, "apagado": dict[str,int], "negociacoes_crm_desvinculadas": int}`. Consumida pela rota do Task 3.

- [ ] **Step 1: Escrever os testes (vão falhar — a função ainda não existe)**

Criar `hermes_agents/tests/test_lojas_exclusao_forcada_core.py`:

```python
"""Testes de core/lojas.py::excluir_forcado() — exclusao permanente de loja
inativa com dado vinculado, numa unica transacao atomica. Padrao de mock
(_mock_conn/_mock_db_com_conn) e' o mesmo de
tests/test_lojas_vinculo_estoque.py::TestVincularDesvincularEstoque."""
import sys, os, unittest
from unittest.mock import patch, AsyncMock, MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m pytest tests/test_lojas_exclusao_forcada_core.py -v`
Expected: FAIL com `AttributeError: module 'core.lojas' has no attribute 'excluir_forcado'`.

- [ ] **Step 3: Implementar `excluir_forcado()`**

Em `hermes_agents/core/lojas.py`, inserir logo depois do fim de `impacto_exclusao()` (Task 1):

```python
def excluir_forcado(id_loja: int, confirmar_nome: str) -> dict:
    """Apaga permanentemente uma loja inativa e todo o dado vinculado a ela
    (ver _CASCATA_EXCLUSAO_FORCADA), numa unica transacao. Existe pra quando
    o operador confirma que o historico vinculado e' dado errado/lixo (loja
    de teste), nao venda real que precise ser preservada — a exclusao comum
    (deletar()) continua bloqueando por FK de proposito pra todo o resto."""
    _ensure_table()
    async def _go():
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                loja_row = await conn.fetchrow("SELECT * FROM lojas WHERE id = $1", id_loja)
                if not loja_row:
                    return {"erro": "Loja nao encontrada"}
                loja = dict(loja_row)
                if loja.get("status") != "inativa":
                    return {"erro": "Loja precisa estar inativa antes de forcar exclusao"}
                if confirmar_nome != loja["nome"]:
                    return {"erro": "Nome de confirmacao nao confere"}
                r = await conn.execute(
                    f"UPDATE crm_negociacoes SET pedido_id = NULL WHERE {_WHERE_CRM_NEGOCIACOES_VINCULADAS}", id_loja)
                negociacoes_desvinculadas = int(r.split()[-1])
                apagado = {}
                for tabela, where_clause in _CASCATA_EXCLUSAO_FORCADA:
                    r = await conn.execute(f"DELETE FROM {tabela} WHERE {where_clause}", id_loja)
                    apagado[tabela] = int(r.split()[-1])
                await conn.execute("UPDATE lojas SET loja_vinculada_id = NULL WHERE loja_vinculada_id = $1", id_loja)
                await conn.execute("UPDATE lojas SET loja_matriz_id = NULL WHERE loja_matriz_id = $1", id_loja)
                await conn.execute("DELETE FROM lojas WHERE id = $1", id_loja)
                return {"ok": True, "apagado": apagado,
                        "negociacoes_crm_desvinculadas": negociacoes_desvinculadas}
    try:
        resultado = run_async(_go())
    except Exception as e:
        _log_erro("excluir_forcado", e)
        return {"erro": str(e)}
    if not resultado.get("erro"):
        invalidar_cache_loja_efetiva()
        invalidar_cache_loja_id()
    return resultado
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `python -m pytest tests/test_lojas_exclusao_forcada_core.py -v`
Expected: PASS (7 testes).

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/lojas.py hermes_agents/tests/test_lojas_exclusao_forcada_core.py
git commit -m "feat: adiciona excluir_forcado() para apagar loja inativa com dado vinculado"
```

---

### Task 3: RBAC + rotas + coluna `status` na listagem

**Files:**
- Modify: `hermes_agents/core/rbac.py` (permissão `lojas.excluir_forcado`)
- Modify: `hermes_agents/core/lojas.py` (`listar()` passa a incluir `status`)
- Modify: `hermes_agents/routes/lojas_manage.py` (duas rotas novas)
- Test: `hermes_agents/tests/test_lojas_exclusao_forcada_rotas.py`

**Interfaces:**
- Consumes: `impacto_exclusao()`/`excluir_forcado()` (Tasks 1/2); `requer_permissao(codigo)` (`core/rbac.py:598`); `obter()`/`listar()` (`core/lojas.py`); `auditar_exclusao(modulo, entidade, entidade_id, dados_antes)` (`core/seguranca.py:56`).
- Produces: rotas `GET /api/lojas/manage/<id>/impacto-exclusao` e `POST /api/lojas/manage/<id>/excluir-forcado` (body `{"confirmar_nome": str}`), consumidas pelo Task 4 (`web/src/lib/api.ts`). `listar()` passa a devolver `status` em cada loja, consumido pelo Task 5 (gating do botão no frontend).

- [ ] **Step 1: Escrever os testes (vão falhar — permissão/rotas ainda não existem)**

Criar `hermes_agents/tests/test_lojas_exclusao_forcada_rotas.py`:

```python
"""Testes de integracao — rotas de exclusao forcada de loja
(GET .../impacto-exclusao, POST .../excluir-forcado). Ambas gated so' pela
permissao dedicada lojas.excluir_forcado (Admin-only por padrao), sem
@requer_acesso_loja (acao administrativa central). Padrao _app()/_TEST_TOKEN
e' o mesmo de tests/test_lojas_manage_seguranca.py."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

from flask import Flask
from routes.lojas_manage import lojas_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(lojas_bp)
    return app.test_client()


class TestExclusaoForcadaRotas(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_impacto_exclusao_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["configuracoes.editar"]), \
             patch("core.lojas.impacto_exclusao") as mock_impacto:
            r = self.client.get("/api/lojas/manage/1/impacto-exclusao", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_impacto.assert_not_called()

    def test_impacto_exclusao_com_permissao_libera(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.impacto_exclusao",
                    return_value={"loja": {"id": 1}, "impacto": {}, "total_linhas": 0}) as mock_impacto:
            r = self.client.get("/api/lojas/manage/1/impacto-exclusao", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_impacto.assert_called_once_with(1)

    def test_impacto_exclusao_com_erro_retorna_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.impacto_exclusao", return_value={"erro": "Loja nao encontrada"}):
            r = self.client.get("/api/lojas/manage/999/impacto-exclusao", headers=headers)
        self.assertEqual(r.status_code, 400)

    def test_excluir_forcado_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["configuracoes.excluir"]), \
             patch("core.lojas.excluir_forcado") as mock_excluir:
            r = self.client.post("/api/lojas/manage/1/excluir-forcado",
                                  json={"confirmar_nome": "Loja X"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_excluir.assert_not_called()

    def test_excluir_forcado_com_permissao_libera_e_audita(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.obter", return_value={"id": 1, "nome": "Loja X"}), \
             patch("core.lojas.excluir_forcado",
                   return_value={"ok": True, "apagado": {"pdv_caixas": 2},
                                 "negociacoes_crm_desvinculadas": 0}) as mock_excluir, \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.post("/api/lojas/manage/1/excluir-forcado",
                                  json={"confirmar_nome": "Loja X"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_excluir.assert_called_once_with(1, "Loja X")
        mock_audit.assert_called_once_with(
            "lojas", "manage-forcado", 1,
            {"id": 1, "nome": "Loja X", "apagado": {"pdv_caixas": 2}, "negociacoes_crm_desvinculadas": 0})

    def test_excluir_forcado_com_erro_retorna_400_e_nao_audita(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.obter", return_value={"id": 1, "nome": "Loja X"}), \
             patch("core.lojas.excluir_forcado", return_value={"erro": "Nome de confirmacao nao confere"}), \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.post("/api/lojas/manage/1/excluir-forcado",
                                  json={"confirmar_nome": "Nome Errado"}, headers=headers)
        self.assertEqual(r.status_code, 400)
        mock_audit.assert_not_called()

    def test_excluir_forcado_nao_faz_strip_no_nome_confirmado(self):
        """confirmar_nome precisa chegar exatamente como o body mandou —
        strip() na rota mascararia o caso 'espaco extra' que excluir_forcado()
        precisa reprovar."""
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.obter", return_value={"id": 1, "nome": "Loja X"}), \
             patch("core.lojas.excluir_forcado",
                   return_value={"erro": "Nome de confirmacao nao confere"}) as mock_excluir:
            self.client.post("/api/lojas/manage/1/excluir-forcado",
                              json={"confirmar_nome": "Loja X "}, headers=headers)
        mock_excluir.assert_called_once_with(1, "Loja X ")

    def test_listar_lojas_manage_repassa_status(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.listar",
                   return_value=[{"id": 1, "nome": "Loja X", "status": "inativa", "ativa": False}]):
            r = self.client.get("/api/lojas/manage", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["lojas"][0]["status"], "inativa")

    def test_core_listar_inclui_coluna_status(self):
        import core.lojas as lojas_core
        db = AsyncMock()
        db.fetch.return_value = [{"id": 1, "nome": "Loja X", "ativa": False, "status": "inativa",
                                   "created_at": None, "bling_id": None, "tipo": "fisica",
                                   "shopee_markup_pct": 100, "grupos_publicacao": None,
                                   "shopee_conectado": False}]
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas_core.listar()
        sql = db.fetch.call_args[0][0]
        self.assertIn("status", sql)
        self.assertEqual(resultado[0]["status"], "inativa")


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m pytest tests/test_lojas_exclusao_forcada_rotas.py -v`
Expected: FAIL (rotas retornam 404 — não existem ainda; `test_core_listar_inclui_coluna_status` falha por `assertIn("status", sql)`).

- [ ] **Step 3: Adicionar a permissão `lojas.excluir_forcado` em `core/rbac.py`**

Em `hermes_agents/core/rbac.py`, dentro de `_ensure_tables()`, logo depois da linha do seed inicial de `lojas.ver_todas` (linha 176):

```python
            await db.execute("INSERT INTO rbac_permissoes (codigo,descricao,modulo,acao) VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING", "lojas.ver_todas", "Ver todas as lojas (ignora restricao de usuario_lojas)", "lojas", "ver_todas")
            await db.execute("INSERT INTO rbac_permissoes (codigo,descricao,modulo,acao) VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING", "lojas.excluir_forcado", "Excluir loja com dado vinculado (irreversivel)", "lojas", "excluir_forcado")
```

E logo depois do fix-up idempotente de `lojas.ver_todas` (linhas 198-211, terminando em `log(AGENT, f"Fix-up lojas.ver_todas falhou: {e}")`), adicionar um fix-up equivalente:

```python
        # Fix-up idempotente: garante que "lojas.excluir_forcado" exista e
        # esteja no Admin mesmo em bancos onde o seed de roles ja rodou antes
        # dela existir — mesmo padrao do fix-up de "lojas.ver_todas" acima.
        try:
            await db.execute("INSERT INTO rbac_permissoes (codigo,descricao,modulo,acao) VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING",
                              "lojas.excluir_forcado", "Excluir loja com dado vinculado (irreversivel)", "lojas", "excluir_forcado")
            admin_role = await db.fetchrow("SELECT id FROM rbac_roles WHERE nome = 'Admin'")
            perm_excluir_forcado = await db.fetchrow("SELECT id FROM rbac_permissoes WHERE codigo = 'lojas.excluir_forcado'")
            if admin_role and perm_excluir_forcado:
                await db.execute("INSERT INTO rbac_role_permissoes (role_id,permissao_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                                  admin_role["id"], perm_excluir_forcado["id"])
        except Exception as e:
            log(AGENT, f"Fix-up lojas.excluir_forcado falhou: {e}")
```

- [ ] **Step 4: Incluir `status` em `core/lojas.py::listar()`**

Em `hermes_agents/core/lojas.py`, dentro de `listar()`, trocar:

```python
        rows = await db.fetch(
            "SELECT id, nome, ativa, created_at, bling_id, tipo, "
            "shopee_markup_pct, grupos_publicacao, (shopee_shop_id IS NOT NULL) AS shopee_conectado "
            "FROM lojas ORDER BY id")
```

por:

```python
        rows = await db.fetch(
            "SELECT id, nome, ativa, status, created_at, bling_id, tipo, "
            "shopee_markup_pct, grupos_publicacao, (shopee_shop_id IS NOT NULL) AS shopee_conectado "
            "FROM lojas ORDER BY id")
```

- [ ] **Step 5: Adicionar as duas rotas em `routes/lojas_manage.py`**

Em `hermes_agents/routes/lojas_manage.py`, inserir depois da rota `deletar_loja_manage` (antes de `@lojas_bp.route("/manage/<int:id>/vinculo-estoque", ...)`):

```python
@lojas_bp.route("/manage/<int:id>/impacto-exclusao", methods=["GET"])
def lojas_impacto_exclusao(id):
    @requer_permissao("lojas.excluir_forcado")
    def _go():
        from core.lojas import impacto_exclusao
        resultado = impacto_exclusao(id)
        if resultado.get("erro"):
            return jsonify(resultado), 400
        return jsonify(resultado)
    return _go()


@lojas_bp.route("/manage/<int:id>/excluir-forcado", methods=["POST"])
def lojas_excluir_forcado(id):
    data = request.json or {}
    confirmar_nome = data.get("confirmar_nome", "")

    @requer_permissao("lojas.excluir_forcado")
    def _go():
        from core.lojas import excluir_forcado, obter
        from core.seguranca import auditar_exclusao
        dados_antes = obter(id)
        resultado = excluir_forcado(id, confirmar_nome)
        if resultado.get("erro"):
            return jsonify(resultado), 400
        auditar_exclusao("lojas", "manage-forcado", id,
                          {**(dados_antes or {}), "apagado": resultado.get("apagado", {}),
                           "negociacoes_crm_desvinculadas": resultado.get("negociacoes_crm_desvinculadas", 0)})
        return jsonify(resultado)
    return _go()
```

- [ ] **Step 6: Rodar os testes e confirmar que passam**

Run: `python -m pytest tests/test_lojas_exclusao_forcada_rotas.py -v`
Expected: PASS (9 testes).

- [ ] **Step 7: Rodar a suíte completa do backend pra checar regressão**

Run (de dentro de `hermes_agents/`): `python -m pytest --ignore=test_fase2.py --ignore=test_fase3.py --ignore=test_fase_multiloja.py -q`
Expected: só as 8 falhas pré-existentes e não-relacionadas já conhecidas (`test_all_endpoints.py::TestRHEndpoints::test_dashboard`/`test_list`, `test_compras_seguranca.py` ×5, `test_rbac_lojas_rotas.py` ×1) — nenhuma falha nova.

- [ ] **Step 8: Commit**

```bash
git add hermes_agents/core/rbac.py hermes_agents/core/lojas.py hermes_agents/routes/lojas_manage.py hermes_agents/tests/test_lojas_exclusao_forcada_rotas.py
git commit -m "feat: adiciona permissao lojas.excluir_forcado e rotas de exclusao forcada de loja"
```

---

### Task 4: `web/src/lib/api.ts` — funções e tipos novos

**Files:**
- Modify: `web/src/lib/api.ts`

**Interfaces:**
- Consumes: rotas do Task 3 (`GET /api/lojas/manage/<id>/impacto-exclusao`, `POST /api/lojas/manage/<id>/excluir-forcado`); helper `request<T>()` já existente (`web/src/lib/api.ts:32`).
- Produces: `api.lojasImpactoExclusaoForcada(id: number): Promise<ImpactoExclusaoForcadaLoja>`, `api.lojasExcluirForcado(id: number, confirmarNome: string): Promise<ResultadoExclusaoForcada>` — consumidas pelo Task 5. Tipos exportados `ImpactoExclusaoForcadaLoja`, `ResultadoExclusaoForcada`.

- [ ] **Step 1: Adicionar os tipos novos**

Em `web/src/lib/api.ts`, logo depois da linha `export type TipoLoja = "fisica" | "virtual" | "hibrida" | "marketplace";` (linha 80), inserir:

```typescript

export interface ImpactoExclusaoForcadaLoja {
  loja: { id: number; nome: string; status?: string; [key: string]: unknown };
  impacto: Record<string, number>;
  negociacoes_crm_desvinculadas: number;
  total_linhas: number;
}

export interface ResultadoExclusaoForcada {
  ok: boolean;
  apagado: Record<string, number>;
  negociacoes_crm_desvinculadas: number;
}
```

- [ ] **Step 2: Adicionar as duas funções no objeto `api`**

Logo depois da linha `lojasDeletar: (id: number) => request<{ success: boolean }>(\`/api/lojas/manage/${id}\`, { method: "DELETE" }),` (linha 649), inserir:

```typescript
  lojasImpactoExclusaoForcada: (id: number) =>
    request<ImpactoExclusaoForcadaLoja>(`/api/lojas/manage/${id}/impacto-exclusao`),
  lojasExcluirForcado: (id: number, confirmarNome: string) =>
    request<ResultadoExclusaoForcada>(`/api/lojas/manage/${id}/excluir-forcado`, {
      method: "POST",
      body: JSON.stringify({ confirmar_nome: confirmarNome }),
    }),
```

- [ ] **Step 3: Checar tipos**

Run (de dentro de `web/`): `npx tsc --noEmit`
Expected: 0 erros novos (o projeto não tem suíte de testes automatizados no frontend — checagem de tipos é a verificação disponível pra este arquivo isolado).

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/api.ts
git commit -m "feat: adiciona funcoes de API para exclusao forcada de loja"
```

---

### Task 5: `web/src/app/lojas/page.tsx` — fluxo de UI

**Files:**
- Modify: `web/src/app/lojas/page.tsx`

**Interfaces:**
- Consumes: `api.lojasImpactoExclusaoForcada`, `api.lojasExcluirForcado`, `ImpactoExclusaoForcadaLoja` (Task 4); `useAuth()` de `@/lib/auth` (`hasPermission(code: string): boolean`, mesmo padrão de `web/src/app/estoque/discrepancias/_components/DivergenciaSaldo.tsx:23`).
- Produces: nada consumido por outra task — é a ponta final do fluxo.

- [ ] **Step 1: Importar `useAuth` e o tipo novo, adicionar `status` na interface `Loja`**

Em `web/src/app/lojas/page.tsx`, trocar:

```typescript
import { api, type TipoLoja } from "@/lib/api";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";
import Icon from "@/app/_components/Icon";

interface Loja { id: number; nome: string; ativa: boolean; bling_id?: number; bling_descricao?: string; shopee_markup_pct?: number; grupos_publicacao?: string; tipo?: TipoLoja; }
```

por:

```typescript
import { api, type TipoLoja, type ImpactoExclusaoForcadaLoja } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";
import Icon from "@/app/_components/Icon";

interface Loja { id: number; nome: string; ativa: boolean; status?: string; bling_id?: number; bling_descricao?: string; shopee_markup_pct?: number; grupos_publicacao?: string; tipo?: TipoLoja; }

const MENSAGEM_EXCLUSAO_BLOQUEADA =
  "Nao e possivel excluir: existem dados vinculados a esta loja (estoque, vendas, caixas, etc). Desative-a em vez de excluir.";

type ExclusaoForcadaState = {
  lojaId: number; nome: string; modalAberto: boolean;
  impacto: ImpactoExclusaoForcadaLoja | null; carregandoImpacto: boolean;
  nomeDigitado: string; excluindo: boolean; erro: string;
};
```

- [ ] **Step 2: Trocar `deletar(id)` por `deletar(l)` e adicionar o estado/handlers de exclusão forçada**

Trocar:

```typescript
export default function LojasPage() {
  const [lojas, setLojas] = useState<Loja[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [erro, setErro] = useState("");
  const [modal, setModal] = useState<{ open: boolean; nome: string; markup: number; grupos: string; tipo: TipoLoja; editId?: number }>({ open: false, nome: "", markup: 100, grupos: "", tipo: "fisica" });

  const carregar = () => {
    api.lojasManage()
      .then(d => setLojas(d.lojas || []))
      .finally(() => setLoading(false));
  };

  useEffect(() => { carregar(); }, []);

  const salvar = async () => {
    const nome = modal.nome.trim();
    if (!nome) return;
    if (modal.editId) await api.lojasAtualizar(modal.editId, nome, modal.markup, modal.grupos || undefined, modal.tipo);
    else await api.lojasCriar(nome, modal.tipo);
    setModal({ open: false, nome: "", markup: 100, grupos: "", tipo: "fisica" });
    carregar();
  };

  const deletar = async (id: number) => {
    if (!confirm("Tem certeza que deseja excluir esta loja?")) return;
    setErro("");
    try {
      await api.lojasDeletar(id);
      carregar();
    } catch (e) {
      setErro((e as Error).message);
    }
  };
```

por:

```typescript
export default function LojasPage() {
  const { hasPermission } = useAuth();
  const [lojas, setLojas] = useState<Loja[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [erro, setErro] = useState("");
  const [modal, setModal] = useState<{ open: boolean; nome: string; markup: number; grupos: string; tipo: TipoLoja; editId?: number }>({ open: false, nome: "", markup: 100, grupos: "", tipo: "fisica" });
  const [exclusaoForcada, setExclusaoForcada] = useState<ExclusaoForcadaState | null>(null);

  const carregar = () => {
    api.lojasManage()
      .then(d => setLojas(d.lojas || []))
      .finally(() => setLoading(false));
  };

  useEffect(() => { carregar(); }, []);

  const salvar = async () => {
    const nome = modal.nome.trim();
    if (!nome) return;
    if (modal.editId) await api.lojasAtualizar(modal.editId, nome, modal.markup, modal.grupos || undefined, modal.tipo);
    else await api.lojasCriar(nome, modal.tipo);
    setModal({ open: false, nome: "", markup: 100, grupos: "", tipo: "fisica" });
    carregar();
  };

  const deletar = async (l: Loja) => {
    if (!confirm("Tem certeza que deseja excluir esta loja?")) return;
    setErro("");
    setExclusaoForcada(null);
    try {
      await api.lojasDeletar(l.id);
      carregar();
    } catch (e) {
      const mensagem = (e as Error).message;
      setErro(mensagem);
      if (mensagem === MENSAGEM_EXCLUSAO_BLOQUEADA && l.status === "inativa" && hasPermission("lojas.excluir_forcado")) {
        setExclusaoForcada({ lojaId: l.id, nome: l.nome, modalAberto: false,
          impacto: null, carregandoImpacto: false, nomeDigitado: "", excluindo: false, erro: "" });
      }
    }
  };

  const abrirExclusaoForcada = async () => {
    if (!exclusaoForcada) return;
    setExclusaoForcada(p => p && { ...p, modalAberto: true, carregandoImpacto: true });
    try {
      const impacto = await api.lojasImpactoExclusaoForcada(exclusaoForcada.lojaId);
      setExclusaoForcada(p => p && { ...p, impacto, carregandoImpacto: false });
    } catch (e) {
      setExclusaoForcada(p => p && { ...p, carregandoImpacto: false, erro: (e as Error).message });
    }
  };

  const confirmarExclusaoForcada = async () => {
    if (!exclusaoForcada) return;
    setExclusaoForcada(p => p && { ...p, excluindo: true, erro: "" });
    try {
      await api.lojasExcluirForcado(exclusaoForcada.lojaId, exclusaoForcada.nomeDigitado);
      setExclusaoForcada(null);
      setErro("");
      carregar();
    } catch (e) {
      setExclusaoForcada(p => p && { ...p, excluindo: false, erro: (e as Error).message });
    }
  };
```

- [ ] **Step 3: Atualizar o botão "Excluir" do card e o texto de erro pra oferecer "Excluir mesmo assim"**

Trocar:

```typescript
          {erro && <p className="text-xs text-red-400 mt-1">{erro}</p>}
```

por:

```typescript
          {erro && (
            <p className="text-xs text-red-400 mt-1">
              {erro}
              {exclusaoForcada && !exclusaoForcada.modalAberto && (
                <button onClick={abrirExclusaoForcada} className="ml-2 underline hover:text-red-300">
                  Excluir mesmo assim
                </button>
              )}
            </p>
          )}
```

E trocar:

```typescript
                <button
                  onClick={() => deletar(l.id)}
                  className="text-xs text-red-400 hover:text-red-300"
                >Excluir</button>
```

por:

```typescript
                <button
                  onClick={() => deletar(l)}
                  className="text-xs text-red-400 hover:text-red-300"
                >Excluir</button>
```

- [ ] **Step 4: Adicionar o modal de confirmação**

Logo antes do `</div>` final que fecha o componente (depois do bloco `{modal.open && (...)}`), inserir:

```typescript
      {exclusaoForcada?.modalAberto && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setExclusaoForcada(null)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-6 w-[420px]" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-red-400 mb-1">Excluir &quot;{exclusaoForcada.nome}&quot; permanentemente</h3>
            <p className="text-[10px] text-neutral-500 mb-4">Esta ação apaga todo o histórico vinculado a esta loja e não pode ser desfeita.</p>
            {exclusaoForcada.carregandoImpacto ? (
              <p className="text-xs text-neutral-400">Calculando impacto...</p>
            ) : exclusaoForcada.impacto ? (
              <div className="max-h-48 overflow-y-auto text-[10px] text-neutral-400 space-y-0.5 mb-4 border border-neutral-700 rounded p-2">
                {Object.entries(exclusaoForcada.impacto.impacto).filter(([, n]) => n > 0).map(([tabela, n]) => (
                  <div key={tabela} className="flex justify-between"><span>{tabela}</span><span>{n}</span></div>
                ))}
                <div className="flex justify-between font-semibold text-neutral-300 pt-1 border-t border-neutral-700">
                  <span>Total de linhas</span><span>{exclusaoForcada.impacto.total_linhas}</span>
                </div>
              </div>
            ) : null}
            {exclusaoForcada.erro && <p className="text-xs text-red-400 mb-2">{exclusaoForcada.erro}</p>}
            <label className="text-xs text-neutral-400 block mb-1">Digite &quot;{exclusaoForcada.nome}&quot; para confirmar:</label>
            <input
              type="text"
              value={exclusaoForcada.nomeDigitado}
              onChange={e => setExclusaoForcada(p => p && { ...p, nomeDigitado: e.target.value })}
              className="w-full bg-neutral-700 border border-neutral-600 rounded px-3 py-2 text-xs text-neutral-200 mb-4 focus:outline-none focus:border-red-500"
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setExclusaoForcada(null)} className="text-xs px-3 py-1.5 rounded-lg text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button
                onClick={confirmarExclusaoForcada}
                disabled={exclusaoForcada.nomeDigitado !== exclusaoForcada.nome || exclusaoForcada.excluindo}
                className="text-xs px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 disabled:opacity-40 disabled:cursor-not-allowed text-white"
              >{exclusaoForcada.excluindo ? "Excluindo..." : "Excluir permanentemente"}</button>
            </div>
          </div>
        </div>
      )}
```

- [ ] **Step 5: Checar tipos**

Run (de dentro de `web/`): `npx tsc --noEmit`
Expected: 0 erros.

- [ ] **Step 6: Verificação manual no navegador**

Sem backend local disponível nesta sessão — pedir ao usuário pra confirmar em produção (depois do deploy) que: (a) "Excluir mesmo assim" só aparece pra loja **inativa** com a permissão `lojas.excluir_forcado`; (b) o botão "Excluir permanentemente" fica desabilitado até o nome digitado bater exatamente (inclusive espaço/maiúscula); (c) um erro do backend aparece dentro do modal sem fechá-lo; (d) sucesso fecha o modal, some a loja da lista e limpa a mensagem de erro anterior.

- [ ] **Step 7: Commit**

```bash
git add web/src/app/lojas/page.tsx
git commit -m "feat: adiciona fluxo de exclusao forcada de loja na tela /lojas"
```

---

## Self-Review (feito pelo autor do plano)

**Cobertura da spec:** pré-requisito de loja inativa (Tasks 1/2), permissão dedicada Admin-only com seed + fix-up (Task 3), confirmação por nome exato sem strip (Tasks 2/3), prévia obrigatória (Tasks 1/4/5), atomicidade em transação única com prova de rollback real (Task 2), auditoria reaproveitando `auditar_exclusao` com contagens (Task 3), `compras_pedidos`/`fin_contas_pagar` fora de escopo (constante do Task 1, comentário explícito), `fiscal_notas_fiscais` sem bloqueio especial (Task 1, sem trava dedicada) — todas as decisões da spec revisada têm task correspondente.

**Placeholders:** nenhum "TBD"/"implementar depois" — todo código dos Steps é completo e literal, incluindo os 33 pares `(tabela, where_clause)` da cascata.

**Consistência de tipos:** `_CASCATA_EXCLUSAO_FORCADA`/`_WHERE_CRM_NEGOCIACOES_VINCULADAS` (Task 1) são os mesmos nomes usados em Task 2; `impacto_exclusao`/`excluir_forcado` (Tasks 1/2) são os mesmos nomes importados nas rotas (Task 3); `ImpactoExclusaoForcadaLoja`/`ResultadoExclusaoForcada`/`lojasImpactoExclusaoForcada`/`lojasExcluirForcado` (Task 4) são os mesmos nomes usados no Task 5; o campo `status` adicionado em `listar()` (Task 3) é o mesmo lido em `l.status` no Task 5.
