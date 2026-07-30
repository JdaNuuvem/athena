# Vínculo de Estoque Física×Virtual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que uma loja `virtual` compartilhe o saldo de estoque de uma loja `fisica` quando um vínculo opcional estiver ativo — saldo único, resolvido de forma transparente em todo ponto do sistema que hoje lê/escreve `estoque_lojas`/`estoque_saldos` por nome de loja.

**Architecture:** Coluna nova `lojas.loja_vinculada_id`. Resolver central `core.lojas._loja_efetiva_async()`/`loja_efetiva()`/`loja_efetiva_sync()` (nome ou id de loja → nome efetivo, com cache em memória, mesmo padrão de `resolver_loja_id()` já existente). Injetado no choke point de escrita/leitura (`core/estoque_saldos.py`) — cobre de graça os 17+ call sites que já passam por `core.estoque.entrada/saida/mover_saldo/saldo`. Os ~11 pontos de SQL cru restantes (9 arquivos) recebem a chamada ao resolver explicitamente.

**Tech Stack:** Flask + asyncpg (maioria) + psycopg2 sync (`routes/estoque.py`, `athena_bridge.py`) no backend, Next.js/TypeScript no frontend.

## Global Constraints

- Spec de referência: `docs/superpowers/specs/2026-07-30-vinculo-estoque-fisica-virtual-design.md`.
- Saldo único compartilhado — nunca dois saldos espelhados/sincronizados.
- 1 física pode ter N virtuais vinculadas; 1 virtual vincula em no máximo 1 física.
- Ativar vínculo: saldo da física vira o compartilhado (linhas antigas da virtual ficam órfãs, não apagadas).
- Desativar vínculo: virtual recebe cópia do saldo compartilhado no momento, física intocada.
- `produtos_loja` (preço/mín/máx/comissão) nunca resolve por vínculo — é sempre por loja, só a quantidade de `estoque_lojas`/`estoque_saldos` resolve.
- O resolver aceita tanto nome de loja quanto id (string de dígitos) — todo call site hoje mistura as duas formas (`loja.isdigit()` já é um padrão existente em vários arquivos).
- Toda função que hoje já engole exceção e retorna vazio/erro genérico continua fazendo isso — o resolver não muda contrato de erro de ninguém.

---

### Task 1: Resolver central em `core/lojas.py`

**Files:**
- Modify: `hermes_agents/core/lojas.py`
- Test: `hermes_agents/tests/test_lojas_vinculo_estoque.py`

**Interfaces:**
- Produces: `async def _loja_efetiva_async(loja) -> str`, `def loja_efetiva(loja: str) -> str` (wrapper sync via `run_async`), `def loja_efetiva_sync(cur, loja: str) -> str` (psycopg2), `def invalidar_cache_loja_efetiva()`. Todas as Tasks seguintes consomem uma dessas três.

- [ ] **Step 1: Escrever o teste (RED)**

```python
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
        db.fetchrow.return_value = {"nome": "Loja Virtual A", "nome_fisica": "Loja Fisica Central"}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async("42"))
        self.assertEqual(resultado, "Loja Fisica Central")

    def test_id_sem_vinculo_resolve_para_o_proprio_nome(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"nome": "Loja Y", "nome_fisica": None}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async("7"))
        self.assertEqual(resultado, "Loja Y")

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
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_lojas_vinculo_estoque.py -v`
Expected: FAIL — `AttributeError: module 'core.lojas' has no attribute '_loja_efetiva_async'` (e `_sync_run` também não existe ainda).

- [ ] **Step 3: Implementar**

Em `hermes_agents/core/lojas.py`, depois de `invalidar_cache_loja_id()`/`resolver_loja_id()` (linha ~78):

```python
_cache_loja_efetiva: dict = {}


def invalidar_cache_loja_efetiva():
    _cache_loja_efetiva.clear()


def _sync_run(coro):
    """Helper de teste — roda uma coroutine isolada sem passar por run_async
    (que abriria um pool asyncpg de verdade). Producao usa loja_efetiva()."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _loja_efetiva_async(loja) -> str:
    """Aceita nome OU id (string de digitos) de loja; devolve sempre o NOME
    efetivo — se for virtual com vinculo ativo, o nome da fisica vinculada;
    senao, o proprio nome (resolvendo id->nome primeiro, se for o caso)."""
    if not loja:
        return loja
    chave = str(loja)
    if chave in _cache_loja_efetiva:
        return _cache_loja_efetiva[chave]
    db = await get_db()
    if chave.isdigit():
        row = await db.fetchrow(
            "SELECT l1.nome, l2.nome AS nome_fisica FROM lojas l1 "
            "LEFT JOIN lojas l2 ON l2.id = l1.loja_vinculada_id "
            "WHERE l1.id = $1", int(chave))
        efetiva = (row["nome_fisica"] or row["nome"]) if row else loja
    else:
        row = await db.fetchrow(
            "SELECT l2.nome FROM lojas l1 JOIN lojas l2 ON l2.id = l1.loja_vinculada_id "
            "WHERE l1.nome = $1 AND l1.tipo = 'virtual' AND l1.loja_vinculada_id IS NOT NULL", chave)
        efetiva = row["nome"] if row else chave
    _cache_loja_efetiva[chave] = efetiva
    return efetiva


def loja_efetiva(loja: str) -> str:
    """Versao sincrona (wrapper sobre run_async) — use em qualquer caller
    que ja tenha so' o nome/id em maos fora de um `async def`."""
    if not loja:
        return loja
    try:
        return run_async(_loja_efetiva_async(loja))
    except Exception as e:
        _log_erro("loja_efetiva", e)
        return loja


def loja_efetiva_sync(cur, loja: str) -> str:
    """Para callers com conexao psycopg2 direta (routes/estoque.py,
    athena_bridge.py) — usa cursor sincrono, mesmo cache compartilhado."""
    if not loja:
        return loja
    chave = str(loja)
    if chave in _cache_loja_efetiva:
        return _cache_loja_efetiva[chave]
    if chave.isdigit():
        cur.execute(
            "SELECT l1.nome, l2.nome AS nome_fisica FROM lojas l1 "
            "LEFT JOIN lojas l2 ON l2.id = l1.loja_vinculada_id "
            "WHERE l1.id = %s", (int(chave),))
        row = cur.fetchone()
        efetiva = (row[1] or row[0]) if row else loja
    else:
        cur.execute(
            "SELECT l2.nome FROM lojas l1 JOIN lojas l2 ON l2.id = l1.loja_vinculada_id "
            "WHERE l1.nome = %s AND l1.tipo = 'virtual' AND l1.loja_vinculada_id IS NOT NULL", (chave,))
        row = cur.fetchone()
        efetiva = row[0] if row else chave
    _cache_loja_efetiva[chave] = efetiva
    return efetiva
```

Em `_ensure_table()`, junto dos outros `ALTER TABLE` defensivos (depois da linha do `tipo`, ~linha 105):

```python
        try: await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS loja_vinculada_id INT REFERENCES lojas(id)")
        except Exception as e: _log_erro("ALTER lojas.loja_vinculada_id", e)
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_lojas_vinculo_estoque.py -v`
Expected: PASS (8 testes)

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/lojas.py hermes_agents/tests/test_lojas_vinculo_estoque.py
git commit -m "feat: resolver loja_efetiva (nome/id -> nome resolvido por vinculo)"
```

---

### Task 2: `vincular_estoque()` / `desvincular_estoque()`

**Files:**
- Modify: `hermes_agents/core/lojas.py`
- Test: `hermes_agents/tests/test_lojas_vinculo_estoque.py`

**Interfaces:**
- Consumes: `invalidar_cache_loja_efetiva` (Task 1), `core.estoque.entrada_async`/`saida_async` (já existentes).
- Produces: `def vincular_estoque(loja_virtual_id: int, loja_fisica_id: int) -> dict`, `def desvincular_estoque(loja_virtual_id: int) -> dict`. Task 10 (rota) consome as duas.

- [ ] **Step 1: Escrever o teste (RED)**

Adicionar em `hermes_agents/tests/test_lojas_vinculo_estoque.py`:

```python
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
        db = AsyncMock()
        db.fetchrow.return_value = {"id": 1, "tipo": "virtual", "nome": "Loja Virtual A", "loja_vinculada_id": None}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.desvincular_estoque(1)
        self.assertIn("erro", resultado)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_lojas_vinculo_estoque.py::TestVincularDesvincularEstoque -v`
Expected: FAIL — `AttributeError: module 'core.lojas' has no attribute 'vincular_estoque'`

- [ ] **Step 3: Implementar**

Em `hermes_agents/core/lojas.py`, depois das funções do Task 1:

```python
def vincular_estoque(loja_virtual_id: int, loja_fisica_id: int) -> dict:
    """Ativa o vinculo: saldo da fisica vira o compartilhado. Linhas que a
    virtual tinha em estoque_saldos/estoque_lojas sob o proprio nome ficam
    orfas (nao apagadas — historico preservado), porque leitura/escrita
    passam a resolver pro nome da fisica a partir de agora."""
    async def _go():
        db = await get_db()
        virtual = await db.fetchrow("SELECT id, tipo, nome FROM lojas WHERE id = $1", loja_virtual_id)
        if not virtual:
            return {"erro": "Loja virtual nao encontrada"}
        if virtual["tipo"] != "virtual":
            return {"erro": f"Loja {virtual['nome']} nao e' do tipo virtual"}
        fisica = await db.fetchrow("SELECT id, tipo, nome FROM lojas WHERE id = $1", loja_fisica_id)
        if not fisica:
            return {"erro": "Loja fisica nao encontrada"}
        if fisica["tipo"] != "fisica":
            return {"erro": f"Loja {fisica['nome']} nao e' do tipo fisica"}
        await db.execute("UPDATE lojas SET loja_vinculada_id = $1 WHERE id = $2", loja_fisica_id, loja_virtual_id)
        return {"ok": True, "loja_virtual": virtual["nome"], "loja_fisica": fisica["nome"]}
    try:
        resultado = run_async(_go())
    except Exception as e:
        return {"erro": str(e)}
    if not resultado.get("erro"):
        invalidar_cache_loja_efetiva()
    return resultado


def desvincular_estoque(loja_virtual_id: int) -> dict:
    """Desativa o vinculo: a virtual recebe uma copia do saldo compartilhado
    no momento da desvinculacao (entrada por sku com saldo > 0 na fisica),
    como novo ponto de partida independente. A fisica fica intocada."""
    from core.estoque import entrada as estoque_entrada
    async def _buscar():
        db = await get_db()
        virtual = await db.fetchrow("SELECT id, tipo, nome, loja_vinculada_id FROM lojas WHERE id = $1", loja_virtual_id)
        if not virtual:
            return None, {"erro": "Loja virtual nao encontrada"}
        if not virtual["loja_vinculada_id"]:
            return None, {"erro": f"Loja {virtual['nome']} nao tem vinculo ativo"}
        fisica = await db.fetchrow("SELECT nome FROM lojas WHERE id = $1", virtual["loja_vinculada_id"])
        saldos = await db.fetch(
            "SELECT sku, quantidade FROM estoque_saldos WHERE loja = $1 AND tipo = 'disponivel' AND quantidade > 0",
            fisica["nome"])
        return {"virtual_nome": virtual["nome"], "fisica_nome": fisica["nome"], "saldos": saldos}, None
    try:
        dados, erro = run_async(_buscar())
    except Exception as e:
        return {"erro": str(e)}
    if erro:
        return erro

    async def _limpar_vinculo():
        db = await get_db()
        await db.execute("UPDATE lojas SET loja_vinculada_id = NULL WHERE id = $1", loja_virtual_id)
    try:
        run_async(_limpar_vinculo())
    except Exception as e:
        return {"erro": str(e)}
    invalidar_cache_loja_efetiva()

    copiados = 0
    for s in dados["saldos"]:
        r = estoque_entrada(s["sku"], dados["virtual_nome"], float(s["quantidade"]), "ajuste_inventario")
        if not r.get("erro"):
            copiados += 1
    return {"ok": True, "loja_virtual": dados["virtual_nome"], "loja_fisica": dados["fisica_nome"], "skus_copiados": copiados}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_lojas_vinculo_estoque.py -v`
Expected: PASS (11 testes no total do arquivo)

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/lojas.py hermes_agents/tests/test_lojas_vinculo_estoque.py
git commit -m "feat: vincular_estoque()/desvincular_estoque() entre loja fisica e virtual"
```

---

### Task 3: Resolver no choke point de escrita (`core/estoque_saldos.py`)

**Files:**
- Modify: `hermes_agents/core/estoque_saldos.py`
- Test: `hermes_agents/tests/test_estoque_saldos.py` (arquivo já existe — adicionar casos)

**Interfaces:**
- Consumes: `core.lojas.loja_efetiva` (Task 1).
- Produces: nenhuma interface nova — `_mover_saldo_async`/`mover_saldo` continuam com a mesma assinatura, só passam a resolver `loja` internamente antes de gravar.

- [ ] **Step 1: Escrever o teste (RED)**

Adicionar em `hermes_agents/tests/test_estoque_saldos.py` (reaproveitar `FakeDBSaldos` já existente no arquivo — ver classe no topo):

```python
class TestVinculoEstoqueEscrita(unittest.TestCase):
    def test_entrada_em_loja_virtual_vinculada_grava_sob_o_nome_da_fisica(self):
        fake = FakeDBSaldos()
        fake.lojas = ["Loja Fisica Central"]
        with patch("core.estoque_saldos.get_db", AsyncMock(return_value=fake)), \
             patch("core.lojas.loja_efetiva", return_value="Loja Fisica Central") as mock_resolver:
            import core.estoque_saldos as es
            resultado = es.mover_saldo("SKU-1", "Loja Virtual A", None, "disponivel", 10,
                                        "compra", usuario_id=1, usuario_nome="Teste")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertTrue(resultado.get("ok") or "saldo_destino" in resultado)
        self.assertIn(("SKU-1", "Loja Fisica Central", "disponivel"), fake.saldos)
```

Nota pro implementador: `FakeDBSaldos` já existe no arquivo (ver topo) — confirme os nomes exatos dos atributos (`.lojas`, `.saldos`) lendo a classe antes de escrever o teste; ajuste se os nomes reais forem outros.

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_saldos.py::TestVinculoEstoqueEscrita -v`
Expected: FAIL — grava sob "Loja Virtual A", não "Loja Fisica Central" (resolver ainda não chamado).

- [ ] **Step 3: Implementar**

Em `hermes_agents/core/estoque_saldos.py`, no topo do arquivo adicionar o import:

```python
from core.lojas import loja_efetiva as _loja_efetiva_sync_wrapper
```

Em `_mover_saldo_async(conn, sku, loja, ...)` (linha ~227), primeira linha do corpo da função (antes de qualquer uso de `loja`):

```python
    loja = await __import__("core.lojas", fromlist=["_loja_efetiva_async"])._loja_efetiva_async(loja)
```

Substitua o import gambiarra acima por um import limpo no topo do arquivo e uma chamada direta — escreva assim de verdade:

No topo do arquivo (junto de `from core import get_db, run_async, log`):
```python
from core.lojas import _loja_efetiva_async
```

E dentro de `_mover_saldo_async`, primeira linha do corpo:
```python
    loja = await _loja_efetiva_async(loja)
```

Em `mover_saldo(sku, loja, ...)` (a versão síncrona pública, que abre sua própria conexão) — como ela delega pra `_mover_saldo_async` internamente (confirme lendo a função антes de editar — se `mover_saldo` já chama `_mover_saldo_async` dentro do seu próprio `async def _go()`, a resolução do passo anterior já cobre; não duplique a chamada ao resolver).

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_saldos.py -v`
Expected: PASS (todos os testes existentes + o novo, sem regressão)

- [ ] **Step 5: Rodar a suite completa do módulo estoque pra garantir que nenhum outro teste que exercita `mover_saldo`/`entrada`/`saida` quebrou**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_saldos.py tests/test_estoque_seguranca.py tests/test_estoque_loja_id.py tests/test_estoque_movimentacoes_sql.py -v`
Expected: PASS, output pristine

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/estoque_saldos.py hermes_agents/tests/test_estoque_saldos.py
git commit -m "feat: mover_saldo/_mover_saldo_async resolvem loja por vinculo antes de escrever"
```

---

### Task 4: Resolver no choke point de leitura (`core/estoque_saldos.py`)

**Files:**
- Modify: `hermes_agents/core/estoque_saldos.py`
- Test: `hermes_agents/tests/test_estoque_saldos.py`

**Interfaces:**
- Consumes: `_loja_efetiva_async` (Task 3, já importado no arquivo).
- Produces: nenhuma interface nova — `saldo()`/`_saldo_async()` mesma assinatura.

- [ ] **Step 1: Escrever o teste (RED)**

```python
class TestVinculoEstoqueLeitura(unittest.TestCase):
    def test_saldo_de_loja_virtual_vinculada_le_da_fisica(self):
        db = AsyncMock()
        db.fetchval.return_value = 42
        with patch("core.estoque_saldos.get_db", AsyncMock(return_value=db)), \
             patch("core.lojas.loja_efetiva", return_value="Loja Fisica Central"):
            import core.estoque_saldos as es
            resultado = es.saldo("SKU-1", "Loja Virtual A")
        self.assertEqual(resultado, 42.0)
        args = db.fetchval.call_args[0]
        self.assertIn("Loja Fisica Central", args)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_saldos.py::TestVinculoEstoqueLeitura -v`
Expected: FAIL — query roda com "Loja Virtual A", não resolve.

- [ ] **Step 3: Implementar**

Em `_saldo_async(conn, sku, loja, tipo)` (linha ~204) e em `saldo(sku, loja, tipo)` (linha ~212), primeira linha de cada corpo async:

```python
    loja = await _loja_efetiva_async(loja)
```

(`saldo()` chama `_go()` que já é `async def` — adicione a linha logo após `db = await get_db()`.)

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_saldos.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/estoque_saldos.py hermes_agents/tests/test_estoque_saldos.py
git commit -m "feat: saldo/_saldo_async resolvem loja por vinculo antes de ler"
```

---

### Task 5: `core/estoque.py` — `listar()`, `movimentacoes()`

**Nota:** `sync_bling()` (linha 360) fica FORA desta task — decisão do usuário em 30/07/2026 de não usar o módulo Bling por ora. Não resolver vínculo lá por enquanto; revisitar quando o módulo voltar a ser usado.

**Files:**
- Modify: `hermes_agents/core/estoque.py`
- Test: `hermes_agents/tests/test_estoque_vinculo.py`

**Interfaces:**
- Consumes: `core.lojas._loja_efetiva_async`.

- [ ] **Step 1: Escrever o teste (RED)**

```python
"""Testes de resolucao de vinculo fisica x virtual em core/estoque.py."""
import sys, os, unittest
from unittest.mock import patch, AsyncMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.estoque as estoque


class TestListarResolveVinculo(unittest.TestCase):
    def test_listar_com_loja_nome_resolve_para_fisica(self):
        db = AsyncMock()
        db.fetchval.return_value = 0
        db.fetch.return_value = []
        with patch("core.estoque.get_db", AsyncMock(return_value=db)), \
             patch("core.lojas._loja_efetiva_async", AsyncMock(return_value="Loja Fisica Central")):
            estoque.listar(loja="Loja Virtual A")
        args = db.fetchval.call_args[0]
        self.assertIn("Loja Fisica Central", args)


class TestMovimentacoesResolveVinculo(unittest.TestCase):
    def test_movimentacoes_com_loja_resolve_para_fisica(self):
        db = AsyncMock()
        db.fetch.return_value = []
        with patch("core.estoque.get_db", AsyncMock(return_value=db)), \
             patch("core.lojas._loja_efetiva_async", AsyncMock(return_value="Loja Fisica Central")):
            estoque.movimentacoes(loja="Loja Virtual A")
        args = db.fetch.call_args[0]
        self.assertIn("Loja Fisica Central", args)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_vinculo.py -v`
Expected: FAIL — args não contém "Loja Fisica Central" (ainda usa "Loja Virtual A" direto).

- [ ] **Step 3: Implementar**

Em `hermes_agents/core/estoque.py`, adicionar import no topo:
```python
from core.lojas import _loja_efetiva_async
```

Em `listar()` (linha 55), primeira linha do corpo de `_go()` (após `db = await get_db()`):
```python
        loja_resolvida = await _loja_efetiva_async(loja) if loja and loja != "todas" else loja
```
E usar `loja_resolvida` no lugar de `loja` na chamada `_where_loja_param(loja_resolvida)` (linha 65).

Em `movimentacoes()` (linha 247), primeira linha do corpo de `_go()`:
```python
        loja_resolvida = await _loja_efetiva_async(loja) if loja else loja
```
Usar `loja_resolvida` no `params.append(...)` da linha 258 no lugar de `loja`.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_vinculo.py -v`
Expected: PASS

- [ ] **Step 5: Rodar suite do módulo pra garantir que `listar`/`movimentacoes` continuam corretos pro caso sem vínculo (loja física normal, sem `loja_vinculada_id`)**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_seguranca.py tests/test_estoque_loja_id.py tests/test_estoque_movimentacoes_sql.py -v`
Expected: PASS, output pristine

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/estoque.py hermes_agents/tests/test_estoque_vinculo.py
git commit -m "feat: estoque.listar/movimentacoes resolvem loja por vinculo"
```

---

### Task 6: `core/estoque_analise.py` — giro/ruptura/cobertura

**Files:**
- Modify: `hermes_agents/core/estoque_analise.py`
- Test: `hermes_agents/tests/test_estoque_analise.py`

**Interfaces:**
- Consumes: `core.lojas._loja_efetiva_async`.

- [ ] **Step 1: Escrever o teste (RED)**

Adicionar em `hermes_agents/tests/test_estoque_analise.py`:

```python
class TestGiroResolveVinculo(unittest.TestCase):
    def test_giro_com_loja_virtual_vinculada_consulta_saldo_da_fisica(self):
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                self.assertIn("Loja Fisica Central", params)
                return []
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db, \
             patch("core.lojas._loja_efetiva_async", AsyncMock(return_value="Loja Fisica Central")):
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            analise.giro(loja="Loja Virtual A")
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_analise.py::TestGiroResolveVinculo -v`
Expected: FAIL — `params` contém "Loja Virtual A", não "Loja Fisica Central".

- [ ] **Step 3: Implementar**

Em `hermes_agents/core/estoque_analise.py`, adicionar import no topo:
```python
from core.lojas import _loja_efetiva_async
```

Em `giro()`, `ruptura()` e `cobertura()`, primeira linha do corpo de cada `_go()` (logo após `db = await get_db()`), resolver `loja` UMA vez — o valor resolvido substitui `loja` pro resto da função (todas as queries downstream, tanto a de `estoque_lojas` quanto a de `vendas_pedidos`, já usam essa mesma variável):

```python
        loja = await _loja_efetiva_async(loja) if loja else loja
```

Isso cobre as 3 funções com uma linha cada — nenhuma outra mudança necessária, porque `_filtro_loja`/os blocos `if loja:` já usam a variável `loja` do parâmetro, que passa a estar resolvida a partir dessa linha em diante.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_analise.py -v`
Expected: PASS (todos os testes existentes + o novo)

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/estoque_analise.py hermes_agents/tests/test_estoque_analise.py
git commit -m "feat: giro/ruptura/cobertura resolvem loja por vinculo"
```

---

### Task 7: `core/estoque_aprovacoes.py` + `core/estoque_contagem.py`

**Files:**
- Modify: `hermes_agents/core/estoque_aprovacoes.py`, `hermes_agents/core/estoque_contagem.py`
- Test: `hermes_agents/tests/test_estoque_vinculo.py`

**Interfaces:**
- Consumes: `core.lojas._loja_efetiva_async`.

- [ ] **Step 1: Escrever o teste (RED)**

Adicionar em `hermes_agents/tests/test_estoque_vinculo.py`:

```python
class TestAprovacoesResolveVinculo(unittest.TestCase):
    def test_solicitar_resolve_loja_antes_de_checar_saldo(self):
        db = AsyncMock()
        db.fetchval.return_value = 5
        db.fetchrow.return_value = {"id": 1}
        with patch("core.estoque_aprovacoes.get_db", AsyncMock(return_value=db)), \
             patch("core.lojas._loja_efetiva_async", AsyncMock(return_value="Loja Fisica Central")):
            import core.estoque_aprovacoes as aprov
            aprov._ok = True  # pula _ensure() (CREATE TABLE) no teste
            aprov.solicitar("SKU-1", "Loja Virtual A", 3, "quebra")
        args = db.fetchval.call_args[0]
        self.assertIn("Loja Fisica Central", args)


class TestContagemResolveVinculo(unittest.TestCase):
    def test_sugestoes_resolve_loja(self):
        db = AsyncMock()
        db.fetch.return_value = []
        with patch("core.estoque_contagem.get_db", AsyncMock(return_value=db)), \
             patch("core.lojas._loja_efetiva_async", AsyncMock(return_value="Loja Fisica Central")):
            import core.estoque_contagem as contagem
            contagem._ok = True
            contagem.sugestoes(loja="Loja Virtual A")
        args = db.fetch.call_args[0]
        self.assertIn("Loja Fisica Central", args)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_vinculo.py -v`
Expected: FAIL nos 2 novos testes.

- [ ] **Step 3: Implementar**

Em `hermes_agents/core/estoque_aprovacoes.py`, adicionar import e resolver em `solicitar()` (linha 42-49), primeira linha do `_go()` interno:
```python
from core.lojas import _loja_efetiva_async
```
```python
    async def _go():
        db = await get_db()
        loja_resolvida = await _loja_efetiva_async(loja)
        atual = await db.fetchval(
            "SELECT quantidade FROM estoque_lojas WHERE sku = $1 AND loja = $2", sku, loja_resolvida)
```
E usar `loja_resolvida` no `INSERT INTO estoque_aprovacoes` logo abaixo (linha 60-64) no lugar de `loja` — mantém a pendência registrada já com o nome efetivo, coerente com o que vai ser aplicado quando aprovada.

Em `hermes_agents/core/estoque_contagem.py`, adicionar import e resolver em `sugestoes()` (linha 42) e `registrar()` (linha 80), mesma técnica — primeira linha do `_go()`:
```python
from core.lojas import _loja_efetiva_async
```
```python
        loja_resolvida = await _loja_efetiva_async(loja) if loja else loja
```
Substituir `loja` por `loja_resolvida` em todo o resto de cada função (WHERE de `sugestoes`, e o `SELECT quantidade`/`INSERT INTO estoque_contagens` de `registrar`).

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_vinculo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/estoque_aprovacoes.py hermes_agents/core/estoque_contagem.py hermes_agents/tests/test_estoque_vinculo.py
git commit -m "feat: estoque_aprovacoes.solicitar e estoque_contagem resolvem loja por vinculo"
```

---

### Task 8: `core/produtos_loja.py` + `core/relatorios.py` + `core/repositories_postgres.py`

**Files:**
- Modify: `hermes_agents/core/produtos_loja.py`, `hermes_agents/core/relatorios.py`, `hermes_agents/core/repositories_postgres.py`
- Test: `hermes_agents/tests/test_estoque_vinculo.py`

**Interfaces:**
- Consumes: `core.lojas._loja_efetiva_async`.

- [ ] **Step 1: Escrever o teste (RED)**

```python
class TestProdutosLojaResolveVinculo(unittest.TestCase):
    def test_listar_por_loja_join_estoque_usa_loja_resolvida(self):
        db = AsyncMock()
        db.fetchval.return_value = 0
        db.fetch.return_value = []
        with patch("core.produtos_loja.get_db", AsyncMock(return_value=db)), \
             patch("core.lojas._loja_efetiva_async", AsyncMock(return_value="Loja Fisica Central")):
            import core.produtos_loja as pl
            pl.listar_por_loja("Loja Virtual A")
        args = db.fetch.call_args[0]
        self.assertIn("Loja Fisica Central", args)
        # pl.loja no WHERE continua sendo o nome literal da virtual — config independente.
        self.assertIn("Loja Virtual A", args)


class TestRelatoriosResolveVinculo(unittest.TestCase):
    def test_estoque_resolve_loja_id_por_vinculo(self):
        db = AsyncMock()
        db.fetchval.return_value = 0
        with patch("core.relatorios.get_db", AsyncMock(return_value=db)), \
             patch("core.lojas.loja_efetiva", return_value="Loja Fisica Central"):
            import core.relatorios as relatorios
            relatorios.estoque(loja_id=5)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_vinculo.py -v`
Expected: FAIL nos 2 novos testes.

- [ ] **Step 3: Implementar**

`hermes_agents/core/produtos_loja.py::listar_por_loja()` (linha 108) — resolver só o nome usado no JOIN com `estoque_lojas`, mantendo `pl.loja = $1` como o nome literal da loja pedida (config de produto continua por loja, não por vínculo):

```python
async def _go():
    db = await get_db()
    from core.lojas import _loja_efetiva_async
    loja_estoque = await _loja_efetiva_async(loja)
    where = ["pl.loja = $1"]
    params = [loja]
    if busca:
        where.append(f"(pl.sku ILIKE ${len(params)+1} OR c.descricao ILIKE ${len(params)+1})")
        params.append(f"%{busca}%")
    sql_where = " AND ".join(where)
    total = await db.fetchval(
        f"SELECT COUNT(*) FROM produtos_loja pl "
        f"LEFT JOIN catalogo_produtos c ON c.sku = pl.produto_mestre_sku "
        f"WHERE {sql_where}", *params)
    offset = (pagina - 1) * por_pagina
    idx_loja_estoque = len(params) + 1
    params_pag = params + [loja_estoque, por_pagina, offset]
    rows = await db.fetch(
        f"""SELECT pl.*, c.descricao AS nome_mestre, c.imagens,
                   COALESCE(el.quantidade, 0) AS estoque_atual
            FROM produtos_loja pl
            LEFT JOIN catalogo_produtos c ON c.sku = pl.produto_mestre_sku
            LEFT JOIN estoque_lojas el ON el.sku = pl.sku AND el.loja = ${idx_loja_estoque}
            WHERE {sql_where}
            ORDER BY pl.updated_at DESC, pl.id DESC
            LIMIT ${idx_loja_estoque+1} OFFSET ${idx_loja_estoque+2}""",
        *params_pag)
    return {"produtos": [dict(r) for r in rows], "total": total, "pagina": pagina}
```

`hermes_agents/core/relatorios.py::_loja_where_estoque(loja_id)` (linha 18) — resolve o id pro nome efetivo antes de montar o SQL:

```python
def _loja_where_estoque(loja_id):
    """WHERE clause suffix for estoque_lojas, maps loja_id -> loja nome efetivo (resolve vinculo)."""
    if not loja_id: return ""
    from core.lojas import loja_efetiva
    nome_efetivo = loja_efetiva(str(loja_id))
    nome_escapado = nome_efetivo.replace("'", "''")
    return f" AND e.loja = '{nome_escapado}'"
```

Nota: as demais `_loja_where_*` (Bling/PDV) desta mesma função-helper usam `loja_id` direto contra `vendas_pedidos.loja_id`/`pdv_caixas.loja_id` (FK real, não nome) — essas NÃO precisam de resolução, porque a venda ficou registrada na loja física de verdade (quem vendeu), não na virtual. Só o filtro de `estoque_lojas` (que é por nome de loja) precisa resolver.

`hermes_agents/core/repositories_postgres.py::PostgresEstoqueRepository.buscar_quantidade()` (linha 153):

```python
    async def buscar_quantidade(self, sku: str, loja: str) -> int:
        async def _go():
            db = await get_db()
            from core.lojas import _loja_efetiva_async
            loja_resolvida = await _loja_efetiva_async(loja)
            r = await db.fetchval("SELECT SUM(quantidade) FROM estoque_lojas WHERE sku = $1 AND loja = $2", sku, loja_resolvida)
            return int(r or 0)
        try: return run_async(_go())
        except Exception: return 0
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_vinculo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/produtos_loja.py hermes_agents/core/relatorios.py hermes_agents/core/repositories_postgres.py hermes_agents/tests/test_estoque_vinculo.py
git commit -m "feat: produtos_loja/relatorios/repositories_postgres resolvem loja por vinculo"
```

---

### Task 9: `routes/estoque.py` + `athena_bridge.py` (psycopg2 sync)

**Files:**
- Modify: `hermes_agents/routes/estoque.py`, `hermes_agents/athena_bridge.py`
- Test: `hermes_agents/tests/test_estoque_vinculo_rotas.py`

**Interfaces:**
- Consumes: `core.lojas.loja_efetiva_sync` (Task 1).

- [ ] **Step 1: Escrever o teste (RED)**

```python
"""Smoke test — rotas sync (psycopg2) resolvem loja por vinculo antes de filtrar."""
import sys, os, unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEstoquePorLojaResolveVinculo(unittest.TestCase):
    def test_filtro_de_loja_usa_nome_resolvido(self):
        from flask import Flask
        from routes.estoque import estoque_bp
        app = Flask(__name__)
        app.register_blueprint(estoque_bp)
        client = app.test_client()

        conn = MagicMock()
        cur = conn.cursor.return_value
        cur.fetchone.side_effect = [(0,)]
        cur.fetchall.return_value = []
        cur.description = []

        with patch("routes.estoque._db_sync", return_value=conn), \
             patch("core.lojas.loja_efetiva_sync", return_value="Loja Fisica Central") as mock_resolver, \
             patch("core.rbac.usuario_atual_da_request", return_value={"user_id": 1}), \
             patch("core.rbac_lojas.lojas_permitidas", return_value=None):
            r = client.get("/api/estoque/lojas?loja=Loja Virtual A")
        self.assertEqual(r.status_code, 200)
        mock_resolver.assert_called_once()
        executado = cur.execute.call_args_list[0][0][0]
        self.assertIn("Loja Fisica Central", cur.execute.call_args_list[0][0][1])
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_vinculo_rotas.py -v`
Expected: FAIL — resolver não é chamado ainda, filtro usa "Loja Virtual A" direto.

- [ ] **Step 3: Implementar**

Em `hermes_agents/routes/estoque.py::estoque_por_loja()`, o bloco atual (linhas 45-59) é:

```python
        if loja and loja != "todas":
            if loja.isdigit():
                where.append("e.loja = (SELECT nome FROM lojas WHERE id = %s)")
                params.append(int(loja))
            else:
                where.append("e.loja = %s")
                params.append(loja)
        else:
            permitidas = lojas_permitidas(usuario_atual_da_request().get("user_id"))
            if permitidas is not None:
                where.append("e.loja_id = ANY(%s)")
                params.append(permitidas)
```

Substituir por (o resolver já trata id ou nome internamente e sempre devolve um nome, então o `if loja.isdigit(): ... else: ...` deixa de ser necessário):

```python
        if loja and loja != "todas":
            from core.lojas import loja_efetiva_sync
            loja = loja_efetiva_sync(cur, loja)
            where.append("e.loja = %s")
            params.append(loja)
        else:
            permitidas = lojas_permitidas(usuario_atual_da_request().get("user_id"))
            if permitidas is not None:
                where.append("e.loja_id = ANY(%s)")
                params.append(permitidas)
```

Em `hermes_agents/athena_bridge.py::listar_produtos()` (linha ~1602-1610), o filtro por id de loja física precisa resolver pro nome efetivo antes de usar no `EXISTS`:

```python
        if loja:
            if loja.isdigit():
                from core.lojas import loja_efetiva_sync
                nome_efetivo = loja_efetiva_sync(cur, loja)
                where.append("EXISTS(SELECT 1 FROM estoque_lojas e WHERE e.sku = c.sku AND e.loja = %s)")
                params.append(nome_efetivo)
            else:
                # Marketplace: filtra via anuncios
                where.append("EXISTS(SELECT 1 FROM anuncios a WHERE a.sku=c.sku AND a.marketplace=%s)")
                params.append(loja)
```

(Trocou o `EXISTS(...JOIN lojas l...)` original por uma resolução em Python + filtro direto em `estoque_lojas.loja` — mais simples e já usa o nome efetivo.)

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_vinculo_rotas.py -v`
Expected: PASS

- [ ] **Step 5: Rodar suite completa do backend pra garantir zero regressão em todo o módulo estoque/lojas**

Run: `cd hermes_agents && python -m pytest -q --ignore=test_fase2.py --ignore=test_fase3.py --ignore=test_fase_multiloja.py`
Expected: todos os testes passam (baseline + todos os novos desta e das tasks anteriores)

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/estoque.py hermes_agents/athena_bridge.py hermes_agents/tests/test_estoque_vinculo_rotas.py
git commit -m "feat: rotas sync (estoque_por_loja, listar_produtos) resolvem loja por vinculo"
```

---

### Task 10: Rota de ativar/desativar vínculo

**Files:**
- Modify: `hermes_agents/routes/lojas_manage.py`
- Test: `hermes_agents/tests/test_lojas_vinculo_rotas.py`

**Interfaces:**
- Consumes: `core.lojas.vincular_estoque`/`desvincular_estoque` (Task 2).
- Produces: `PUT /api/lojas/manage/<id>/vinculo-estoque` com body `{"loja_fisica_id": number | null}`. Task 11 (frontend) consome esta rota.

- [ ] **Step 1: Escrever o teste (RED)**

```python
"""Smoke test da rota de vinculo de estoque fisica x virtual."""
import sys, os, unittest
from unittest.mock import patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRotaVinculoEstoque(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        from routes.lojas_manage import lojas_bp
        app = Flask(__name__)
        app.register_blueprint(lojas_bp)
        self.client = app.test_client()

    def test_put_com_loja_fisica_id_vincula(self):
        with patch("core.lojas.vincular_estoque", return_value={"ok": True, "loja_virtual": "A", "loja_fisica": "B"}), \
             patch("core.rbac.requer_permissao", lambda p: (lambda f: f)):
            r = self.client.put("/api/lojas/manage/1/vinculo-estoque", json={"loja_fisica_id": 2})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])

    def test_put_sem_loja_fisica_id_desvincula(self):
        with patch("core.lojas.desvincular_estoque", return_value={"ok": True, "loja_virtual": "A", "loja_fisica": "B", "skus_copiados": 3}), \
             patch("core.rbac.requer_permissao", lambda p: (lambda f: f)):
            r = self.client.put("/api/lojas/manage/1/vinculo-estoque", json={"loja_fisica_id": None})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_lojas_vinculo_rotas.py -v`
Expected: FAIL — `404 Not Found` (rota não existe).

- [ ] **Step 3: Implementar**

Em `hermes_agents/routes/lojas_manage.py`, depois de `atualizar_loja_manage()`:

```python
@lojas_bp.route("/manage/<int:id>/vinculo-estoque", methods=["PUT"])
def vincular_estoque_loja(id):
    from core.lojas import vincular_estoque, desvincular_estoque
    from core.seguranca import auditar_alteracao
    data = request.json or {}
    loja_fisica_id = data.get("loja_fisica_id")

    @requer_permissao("configuracoes.editar")
    def _go():
        if loja_fisica_id:
            resultado = vincular_estoque(id, int(loja_fisica_id))
        else:
            resultado = desvincular_estoque(id)
        if resultado.get("erro"):
            return jsonify(resultado), 400
        auditar_alteracao("editar", "lojas", "vinculo_estoque", id, dados_antes=None, dados_depois=resultado)
        return jsonify(resultado)
    return _go()
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_lojas_vinculo_rotas.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/routes/lojas_manage.py hermes_agents/tests/test_lojas_vinculo_rotas.py
git commit -m "feat: rota PUT /api/lojas/manage/<id>/vinculo-estoque"
```

---

### Task 11: Frontend — cliente `api.ts` + seção na aba Virtual/Delivery

**Files:**
- Modify: `web/src/lib/api.ts`, `web/src/app/lojas/[id]/_components/VirtualDeliveryTab.tsx`

**Interfaces:**
- Consumes: rota da Task 10.
- Produces: `api.lojasVincularEstoque(id, lojaFisicaId)`.

- [ ] **Step 1: Adicionar a função no cliente**

Em `web/src/lib/api.ts`, no objeto `api`, junto de `lojasVirtualAtualizar`/`lojasDeliveryAtualizar` (buscar pelo nome pra achar o lugar certo):

```typescript
  lojasVincularEstoque: (id: number, lojaFisicaId: number | null) =>
    request<{ ok?: boolean; erro?: string; loja_virtual?: string; loja_fisica?: string; skus_copiados?: number }>(
      `/api/lojas/manage/${id}/vinculo-estoque`,
      { method: "PUT", body: JSON.stringify({ loja_fisica_id: lojaFisicaId }) },
    ),
```

- [ ] **Step 2: Adicionar a seção no componente**

Em `web/src/app/lojas/[id]/_components/VirtualDeliveryTab.tsx`, o componente recebe `loja: Record<string, unknown> | null` já com `tipo`/`loja_vinculada_id` (vem do backend via `obter()`, que já faz `SELECT *`). Adicionar estado e handler, e uma seção nova antes de "Loja virtual":

```tsx
  const [lojasFisicas, setLojasFisicas] = useState<{ id: number; nome: string }[]>([]);
  const [lojaFisicaSelecionada, setLojaFisicaSelecionada] = useState<string>("");
  const [vinculoMsg, setVinculoMsg] = useState("");
  const [vinculoErro, setVinculoErro] = useState("");
  const [salvandoVinculo, setSalvandoVinculo] = useState(false);

  useEffect(() => {
    api.lojas().then((r) => {
      const fisicas = (r.data ?? r ?? []).filter((l: Record<string, unknown>) => l.tipo === "fisica");
      setLojasFisicas(fisicas as { id: number; nome: string }[]);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    setLojaFisicaSelecionada(loja?.loja_vinculada_id ? String(loja.loja_vinculada_id) : "");
  }, [loja]);

  const salvarVinculo = async () => {
    setSalvandoVinculo(true); setVinculoErro(""); setVinculoMsg("");
    try {
      const lojaFisicaId = lojaFisicaSelecionada ? Number(lojaFisicaSelecionada) : null;
      const r = await api.lojasVincularEstoque(id, lojaFisicaId);
      if (r.erro) { setVinculoErro(r.erro); return; }
      setVinculoMsg(lojaFisicaId ? `Vinculado a ${r.loja_fisica}` : `Desvinculado (${r.skus_copiados ?? 0} SKUs copiados)`);
      setTimeout(() => setVinculoMsg(""), 3500);
    } catch (e) {
      setVinculoErro(e instanceof Error ? e.message : "Erro ao salvar vinculo");
    } finally {
      setSalvandoVinculo(false);
    }
  };
```

Nota pro implementador: confirme o formato real de retorno de `api.lojas()` (pode ser `{data: [...]}` ou array direto — olhe outras chamadas no mesmo arquivo `api.ts` que já usam `api.lojas()` pra saber o shape exato) antes de escrever o `.then()` acima; ajuste `r.data ?? r ?? []` se o formato for outro. JSX da seção (adicionar dentro do `<div className="space-y-4">` de retorno, antes do `<Section title="Loja virtual"...`):

```tsx
      <Section title="Vinculo de estoque com loja fisica" onSave={salvarVinculo} saving={salvandoVinculo} msg={vinculoMsg}>
        {vinculoErro && <p className="text-xs text-red-400 mb-2">{vinculoErro}</p>}
        <label className="block text-xs text-neutral-400 mb-1">Loja fisica vinculada</label>
        <select
          className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-sm"
          value={lojaFisicaSelecionada}
          onChange={(e) => setLojaFisicaSelecionada(e.target.value)}
        >
          <option value="">Nenhuma (estoque independente)</option>
          {lojasFisicas.map((l) => (
            <option key={l.id} value={l.id}>{l.nome}</option>
          ))}
        </select>
      </Section>
```

- [ ] **Step 3: Verificar tipos**

Run: `cd web && npx tsc --noEmit`
Expected: sem erro novo em `api.ts` ou `VirtualDeliveryTab.tsx`.

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/api.ts "web/src/app/lojas/[id]/_components/VirtualDeliveryTab.tsx"
git commit -m "feat: UI de vinculo de estoque na aba Virtual/Delivery de lojas"
```

---

### Task 12: Validação final

**Files:** nenhum novo — só execução.

- [ ] **Step 1: Suite completa do backend**

Run: `cd hermes_agents && python -m pytest -q --ignore=test_fase2.py --ignore=test_fase3.py --ignore=test_fase_multiloja.py`
Expected: 100% passando, sem regressão em nenhum teste pré-existente (produtos, lojas, PDV, compras, etc — o resolver toca em muitos módulos, essa é a rede de segurança).

- [ ] **Step 2: Build do frontend**

Run: `cd web && npm run build`
Expected: build limpo.

- [ ] **Step 3: Smoke manual do fluxo completo (documentar no report, não é passo automatizado)**

Anotar no report final: criar 1 loja física com saldo, 1 loja virtual sem saldo, vincular via API, confirmar que `GET /api/estoque/lojas?loja=<nome da virtual>` retorna o mesmo saldo da física; desvincular, confirmar que a virtual mantém uma cópia do saldo e a física continua com o dela.

- [ ] **Step 4: Commit final (se sobrar algo solto)**

```bash
git status
# se houver mudanca residual (ex.: ajuste de import esquecido), commitar normalmente
```

---

## Self-Review

**Cobertura da spec:** saldo único compartilhado (Tasks 3-4, escrita/leitura no choke point), cardinalidade 1 física→N virtuais e restrição de tipo (Task 2), física vira saldo compartilhado ao vincular / cópia ao desvincular (Task 2), `produtos_loja` fica sempre independente — só o JOIN de estoque resolve (Task 8), migração completa dos ~11 pontos de leitura crua enumerados na spec (Tasks 5-9), UI (Task 11), validação final (Task 12). Sem lacuna.

**Nota de implementação, não desvio de spec:** a spec original apontava o resolver para `core/estoque_saldos.py`; ao ler o código real (`core/lojas.py::resolver_loja_id`), a spec foi corrigida ANTES desta etapa de plano — `loja_efetiva`/`loja_efetiva_sync` moram em `core/lojas.py` (mesmo padrão de cache já existente), `core/estoque_saldos.py` só importa e chama. A spec já reflete isso — sem contradição a resolver aqui.

**Consistência de tipos:** `_loja_efetiva_async(loja) -> str`, `loja_efetiva(loja: str) -> str`, `loja_efetiva_sync(cur, loja: str) -> str` — mesmos três nomes usados em todas as Tasks 3-9, conferido contra as assinaturas definidas na Task 1.

**Risco identificado para o implementador da Task 3:** o teste de exemplo usa `FakeDBSaldos` (já existe em `test_estoque_saldos.py`) mas o plano não teve acesso à leitura completa dessa classe — o implementador deve ler a classe primeiro e ajustar nomes de atributo se necessário (`.lojas`, `.saldos`) antes de finalizar o teste, exatamente como a nota inline no Step 1 da Task 3 já avisa.
