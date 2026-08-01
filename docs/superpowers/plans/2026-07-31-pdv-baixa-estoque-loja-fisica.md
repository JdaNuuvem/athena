# PDV baixa estoque real da loja física — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `core/pdv.py::realizar_venda()` decrementa estoque real da loja física do caixa ao vender; `cancelar_venda()`/`devolver_item_venda()` restauram automaticamente.

**Architecture:** Reusa `core.estoque.saida_async()`/`entrada_async()` (versões async-native, já existentes, usadas hoje por `core/entidades.py`/`bling_erp.py`/`core.estoque.transferir()`) dentro da MESMA transação que `realizar_venda()`/`cancelar_venda()`/`devolver_item_venda()` já abrem (ou passam a abrir). Loja resolvida de `pdv_caixas.loja_id` → nome via `lojas`. Erro de saldo insuficiente aborta a transação inteira via `SaldoError` (mesmo padrão de `core.estoque.transferir()`).

**Tech Stack:** Python 3.13, asyncpg (via `core.get_db()`/`run_async()`), pytest + `unittest.IsolatedAsyncioTestCase`.

## Global Constraints

- Loja sempre trafega como nome/string pro resolver de estoque, nunca id — mesma convenção do resto do módulo `core.estoque`/`core.estoque_saldos`.
- Estoque insuficiente bloqueia a venda inteira (nenhuma linha em `pdv_vendas`/`pdv_itens`, nenhum estoque alterado) — decisão do usuário, spec `docs/superpowers/specs/2026-07-30-pdv-baixa-estoque-loja-fisica-design.md`.
- Cancelamento e devolução restauram estoque automaticamente — decisão do usuário, mesma spec.
- Motivo novo `"venda_pdv"` cobre a baixa; `"devolucao_cliente"` (já existe em `MOTIVOS_ENTRADA`) cobre toda restauração — nenhum motivo de entrada novo.
- Se o caixa da venda não tiver `loja_id` definido (coluna nula — caixas antigos, ou não configurado), a baixa/restauração de estoque é pulada sem bloquear a operação de PDV (fail-open na resolução de loja, consistente com o padrão já usado em todo `core.lojas`/`core.estoque`; ver nota na Task 2). Isso é uma decisão de implementação desta plan, não coberta explicitamente pela spec.

---

### Task 1: Motivo `venda_pdv` em `core/estoque.py`

**Files:**
- Modify: `hermes_agents/core/estoque.py:21` (`MOTIVOS_SAIDA`), `hermes_agents/core/estoque.py:40-48` (`_MAPA_MOVIMENTO_SAIDA`)
- Test: `hermes_agents/tests/test_estoque_motivos_pdv.py`

**Interfaces:**
- Produces: `"venda_pdv"` em `core.estoque.MOTIVOS_SAIDA`, mapeado em `core.estoque._MAPA_MOVIMENTO_SAIDA["venda_pdv"] == "venda"`. Tasks 3-5 dependem disso.

- [ ] **Step 1: Escrever o teste (RED)**

```python
"""Motivo venda_pdv em MOTIVOS_SAIDA/_MAPA_MOVIMENTO_SAIDA."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMotivoVendaPdv(unittest.TestCase):
    def test_venda_pdv_em_motivos_saida(self):
        from core.estoque import MOTIVOS_SAIDA
        self.assertIn("venda_pdv", MOTIVOS_SAIDA)

    def test_venda_pdv_mapeia_para_tipo_movimento_venda(self):
        from core.estoque import _MAPA_MOVIMENTO_SAIDA
        self.assertEqual(_MAPA_MOVIMENTO_SAIDA.get("venda_pdv"), "venda")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/ -k "TestMotivoVendaPdv" -v`
Expected: FAIL — `"venda_pdv" not in MOTIVOS_SAIDA` (motivo ainda não existe).

- [ ] **Step 3: Implementar**

Em `hermes_agents/core/estoque.py:21`, mudar:

```python
MOTIVOS_SAIDA = ["quebra", "perda", "devolucao_fornecedor", "uso_interno", "furto_identificado", "ajuste_inventario", "outro"]
```

para:

```python
MOTIVOS_SAIDA = ["quebra", "perda", "devolucao_fornecedor", "uso_interno", "furto_identificado", "ajuste_inventario", "venda_pdv", "outro"]
```

Em `hermes_agents/core/estoque.py:40-48`, mudar:

```python
_MAPA_MOVIMENTO_SAIDA = {
    "quebra": "perda",
    "perda": "perda",
    "devolucao_fornecedor": "devolucao",
    "uso_interno": "ajuste",
    "furto_identificado": "roubo",
    "ajuste_inventario": "ajuste",
    "outro": "ajuste",
}
```

para:

```python
_MAPA_MOVIMENTO_SAIDA = {
    "quebra": "perda",
    "perda": "perda",
    "devolucao_fornecedor": "devolucao",
    "uso_interno": "ajuste",
    "furto_identificado": "roubo",
    "ajuste_inventario": "ajuste",
    "venda_pdv": "venda",
    "outro": "ajuste",
}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/ -k "TestMotivoVendaPdv" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/estoque.py hermes_agents/tests/test_estoque_motivos_pdv.py
git commit -m "feat: motivo venda_pdv em MOTIVOS_SAIDA/_MAPA_MOVIMENTO_SAIDA"
```

---

### Task 2: Helper `_resolver_loja_da_venda()` + infraestrutura de teste

**Files:**
- Modify: `hermes_agents/core/pdv.py` (import no topo + função nova, antes de `abrir_caixa()` na linha 411)
- Test: `hermes_agents/tests/test_pdv_estoque.py` (novo arquivo — `FakeDBPdv` reusado pelas Tasks 3-5)

**Interfaces:**
- Consumes: nada de tasks anteriores (independente de Task 1 no código, mas roda depois por ordem lógica).
- Produces: `async def _resolver_loja_da_venda(conn, caixa_id) -> str | None` em `core.pdv`. Tasks 3-5 chamam esta função com o `conn` já aberto na própria transação.

- [ ] **Step 1: Escrever o teste (RED)**

Criar `hermes_agents/tests/test_pdv_estoque.py`:

```python
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
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/ -k "TestResolverLojaDaVenda" -v`
Expected: FAIL — `ImportError: cannot import name '_resolver_loja_da_venda' from 'core.pdv'` (função ainda não existe).

- [ ] **Step 3: Implementar**

Em `hermes_agents/core/pdv.py:2`, mudar:

```python
from core import get_db, run_async, log, hoje
import hashlib, hmac, os as _os
```

para:

```python
from core import get_db, run_async, log, hoje
from core.estoque import saida_async, entrada_async
from core.estoque_saldos import SaldoError, _ensure_async as _ensure_saldos_async
import hashlib, hmac, os as _os
```

Em `hermes_agents/core/pdv.py`, imediatamente antes de `def abrir_caixa(...)` (linha 411), adicionar:

```python
async def _resolver_loja_da_venda(conn, caixa_id):
    """Resolve o nome da loja fisica de uma venda a partir do caixa_id
    (pdv_caixas.loja_id -> lojas.nome). Retorna None se o caixa nao tiver
    loja_id definido ou a loja nao existir -- fail-open: quem chama decide
    pular a baixa/restauracao de estoque nesse caso, sem bloquear a operacao
    de PDV por falta de configuracao de loja no caixa (caixas antigos podem
    nao ter loja_id setado)."""
    if not caixa_id:
        return None
    caixa = await conn.fetchrow("SELECT loja_id FROM pdv_caixas WHERE id = $1", caixa_id)
    if not caixa or not caixa["loja_id"]:
        return None
    loja_row = await conn.fetchrow("SELECT nome FROM lojas WHERE id = $1", caixa["loja_id"])
    return loja_row["nome"] if loja_row else None
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/ -k "TestResolverLojaDaVenda" -v`
Expected: PASS (4 testes)

- [ ] **Step 5: Rodar suite completa (garantir que o import novo não quebra nada)**

Run: `cd hermes_agents && python -m pytest -q --ignore=test_fase2.py --ignore=test_fase3.py --ignore=test_fase_multiloja.py`
Expected: mesma contagem de passed do baseline + 4 novos, 0 failed (exceto o flaky conhecido `test_all_endpoints.py::TestShopeeEndpoints::test_auth_url`, que passa isolado).

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/pdv.py hermes_agents/tests/test_pdv_estoque.py
git commit -m "feat: resolve loja fisica da venda a partir de pdv_caixas.loja_id"
```

---

### Task 3: `realizar_venda()` decrementa estoque por item

**Files:**
- Modify: `hermes_agents/core/pdv.py::realizar_venda()` (linhas 721-762)
- Test: `hermes_agents/tests/test_pdv_estoque.py` (adiciona classe nova)

**Interfaces:**
- Consumes: `_resolver_loja_da_venda(conn, caixa_id)` (Task 2), `saida_async(conn, sku, loja, quantidade, motivo, usuario_id=None, usuario_nome="", ...)` (`core.estoque`, já existe), `SaldoError` (`core.estoque_saldos`, já existe).
- Produces: nada de que outras tasks dependam (cancelar_venda/devolver_item_venda usam `entrada_async` diretamente, não passam por `realizar_venda`).

- [ ] **Step 1: Escrever o teste (RED)**

Adicionar ao final de `hermes_agents/tests/test_pdv_estoque.py` (antes de `if __name__ == "__main__":`):

```python
class TestRealizarVendaBaixaEstoque(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDBPdv()
        self.fake.caixas[1] = {"loja_id": 5}
        self.fake.lojas[5] = "Loja Fisica Central"
        async def _get_db(_fake=self.fake):
            return _fake
        self.patch_db = patch("core.pdv.get_db", side_effect=_get_db)
        self.patch_db.start()
        self.patch_ensure = patch("core.pdv._ensure_saldos_async", new=AsyncMock(return_value=None))
        self.patch_ensure.start()

    def tearDown(self):
        self.patch_db.stop()
        self.patch_ensure.stop()

    async def test_venda_com_estoque_suficiente_decrementa_cada_item(self):
        from core.pdv import realizar_venda
        chamadas = []
        async def fake_saida(conn, sku, loja, quantidade, motivo, usuario_id=None, usuario_nome="", ip=None, dispositivo=None):
            chamadas.append((sku, loja, quantidade, motivo))
            return {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade, "anterior": 10, "atual": 10 - quantidade}
        with patch("core.pdv.saida_async", side_effect=fake_saida):
            r = realizar_venda(1, itens=[
                {"codigo": "SKU1", "descricao": "Produto 1", "quantidade": 2, "valor_unitario": 10.0},
                {"codigo": "SKU2", "descricao": "Produto 2", "quantidade": 1, "valor_unitario": 5.0},
            ], pagamentos=[{"forma": "dinheiro", "valor": 25.0}], operador="Joao", operador_id=1)
        self.assertNotIn("error", r)
        self.assertEqual(sorted(chamadas), sorted([
            ("SKU1", "Loja Fisica Central", 2, "venda_pdv"),
            ("SKU2", "Loja Fisica Central", 1, "venda_pdv"),
        ]))
        self.assertEqual(len(self.fake.vendas), 1)
        self.assertEqual(len(self.fake.itens), 2)

    async def test_item_sem_saldo_suficiente_desfaz_venda_inteira(self):
        from core.pdv import realizar_venda
        async def fake_saida(conn, sku, loja, quantidade, motivo, usuario_id=None, usuario_nome="", ip=None, dispositivo=None):
            if sku == "SKU2":
                return {"erro": "Saldo insuficiente em 'disponivel' (0 disponivel, 1 solicitado)"}
            return {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade, "anterior": 10, "atual": 10 - quantidade}
        with patch("core.pdv.saida_async", side_effect=fake_saida):
            r = realizar_venda(1, itens=[
                {"codigo": "SKU1", "descricao": "Produto 1", "quantidade": 2, "valor_unitario": 10.0},
                {"codigo": "SKU2", "descricao": "Produto 2", "quantidade": 1, "valor_unitario": 5.0},
            ], pagamentos=[{"forma": "dinheiro", "valor": 25.0}], operador="Joao", operador_id=1)
        self.assertIn("error", r)
        self.assertIn("SKU2", r["error"])
        self.assertEqual(len(self.fake.vendas), 0)
        self.assertEqual(len(self.fake.itens), 0)
        self.assertEqual(len(self.fake.pagamentos), 0)

    async def test_caixa_sem_loja_id_nao_bloqueia_venda_nem_baixa_estoque(self):
        from core.pdv import realizar_venda
        self.fake.caixas[1] = {"loja_id": None}
        with patch("core.pdv.saida_async", new=AsyncMock()) as mock_saida:
            r = realizar_venda(1, itens=[
                {"codigo": "SKU1", "descricao": "Produto 1", "quantidade": 2, "valor_unitario": 10.0},
            ], pagamentos=[{"forma": "dinheiro", "valor": 20.0}], operador="Joao", operador_id=1)
        self.assertNotIn("error", r)
        mock_saida.assert_not_called()
        self.assertEqual(len(self.fake.vendas), 1)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/ -k "TestRealizarVendaBaixaEstoque" -v`
Expected: FAIL — `test_venda_com_estoque_suficiente_decrementa_cada_item` falha porque `chamadas` fica vazio (`saida_async` ainda não é chamado dentro de `realizar_venda`); `test_item_sem_saldo_suficiente_desfaz_venda_inteira` falha porque a venda é criada normalmente (sem checar saldo).

- [ ] **Step 3: Implementar**

Em `hermes_agents/core/pdv.py:721-748`, mudar `realizar_venda()` de:

```python
def realizar_venda(caixa_id: int, itens: list, pagamentos: list, cliente="", cliente_id=None, operador="", operador_id=None,
                    desconto=0.0, gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    total_itens = sum((i.get("quantidade",1) or 1) * (i.get("valor_unitario",0) or 0) - (i.get("desconto",0) or 0) for i in itens)
    total = round(total_itens - desconto, 2)

    erro = _validar_desconto_operador(operador_id, itens, desconto, total_itens, gerente_pin_id, pin, codigo_barras)
    if erro: return erro

    # ponytail: transacao atomica — se item/pgto falhar, venda inteira rollback
    async def _go():
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow("""INSERT INTO pdv_vendas (caixa_id, cliente, cliente_id, total, desconto, operador, data)
                    VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *""",
                    caixa_id, cliente, cliente_id, total, desconto, operador, hoje())
                vid = row["id"]
                for item in itens:
                    item_desconto = item.get("desconto",0) or 0
                    item_total = round((item.get("quantidade",1) or 1) * (item.get("valor_unitario",0) or 0) - item_desconto, 2)
                    await conn.execute("INSERT INTO pdv_itens (venda_id, produto_codigo, descricao, quantidade, valor_unitario, desconto, valor_total) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                        vid, item.get("codigo",""), item.get("descricao",""),
                        item.get("quantidade",1), item.get("valor_unitario",0),
                        item_desconto, item_total)
                for pg in pagamentos:
                    await conn.execute("INSERT INTO pdv_pagamentos (venda_id, forma, valor, parcelas) VALUES ($1,$2,$3,$4)",
                        vid, pg.get("forma","dinheiro"), pg.get("valor",total), pg.get("parcelas",1))
                return {"venda": dict(row), "total": total}
    result = run_async(_go())
```

para:

```python
def realizar_venda(caixa_id: int, itens: list, pagamentos: list, cliente="", cliente_id=None, operador="", operador_id=None,
                    desconto=0.0, gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    total_itens = sum((i.get("quantidade",1) or 1) * (i.get("valor_unitario",0) or 0) - (i.get("desconto",0) or 0) for i in itens)
    total = round(total_itens - desconto, 2)

    erro = _validar_desconto_operador(operador_id, itens, desconto, total_itens, gerente_pin_id, pin, codigo_barras)
    if erro: return erro

    # ponytail: transacao atomica — se item/pgto/baixa-de-estoque falhar, venda inteira rollback
    async def _go():
        await _ensure_saldos_async()
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                loja = await _resolver_loja_da_venda(conn, caixa_id)
                row = await conn.fetchrow("""INSERT INTO pdv_vendas (caixa_id, cliente, cliente_id, total, desconto, operador, data)
                    VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *""",
                    caixa_id, cliente, cliente_id, total, desconto, operador, hoje())
                vid = row["id"]
                for item in itens:
                    item_desconto = item.get("desconto",0) or 0
                    item_total = round((item.get("quantidade",1) or 1) * (item.get("valor_unitario",0) or 0) - item_desconto, 2)
                    await conn.execute("INSERT INTO pdv_itens (venda_id, produto_codigo, descricao, quantidade, valor_unitario, desconto, valor_total) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                        vid, item.get("codigo",""), item.get("descricao",""),
                        item.get("quantidade",1), item.get("valor_unitario",0),
                        item_desconto, item_total)
                    if loja:
                        sku = item.get("codigo","")
                        r = await saida_async(conn, sku, loja, item.get("quantidade",1) or 1, "venda_pdv",
                                              usuario_id=operador_id, usuario_nome=operador)
                        if r.get("erro"):
                            raise SaldoError(f"Estoque insuficiente para {sku}: {r['erro']}")
                for pg in pagamentos:
                    await conn.execute("INSERT INTO pdv_pagamentos (venda_id, forma, valor, parcelas) VALUES ($1,$2,$3,$4)",
                        vid, pg.get("forma","dinheiro"), pg.get("valor",total), pg.get("parcelas",1))
                return {"venda": dict(row), "total": total}
    try:
        result = run_async(_go())
    except SaldoError as e:
        return {"error": str(e)}
```

Nota: a linha `result = run_async(_go())` original não estava dentro de um `try` — o restante da função (disparo de webhook + `return result`) continua igual, só precisa ficar fora do novo bloco `try/except SaldoError`, no mesmo nível de indentação de antes. Conferir que o corpo abaixo (linhas 750-762 originais: `if result and not result.get("error"): ... return result`) permanece inalterado e no mesmo nível do `try` acima, não dentro dele.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/ -k "TestRealizarVendaBaixaEstoque" -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Rodar suite completa**

Run: `cd hermes_agents && python -m pytest -q --ignore=test_fase2.py --ignore=test_fase3.py --ignore=test_fase_multiloja.py`
Expected: 0 failed (exceto o flaky conhecido).

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/pdv.py hermes_agents/tests/test_pdv_estoque.py
git commit -m "feat: realizar_venda decrementa estoque real da loja fisica do caixa"
```

---

### Task 4: `cancelar_venda()` restaura estoque de todos os itens

**Files:**
- Modify: `hermes_agents/core/pdv.py::cancelar_venda()` (linhas 581-597)
- Test: `hermes_agents/tests/test_pdv_estoque.py` (adiciona classe nova)

**Interfaces:**
- Consumes: `_resolver_loja_da_venda(conn, caixa_id)` (Task 2), `entrada_async(conn, sku, loja, quantidade, motivo, usuario_id=None, usuario_nome="", ...)` (`core.estoque`, já existe), `SaldoError` (Task 3 já importou; aqui é reusado).

- [ ] **Step 1: Escrever o teste (RED)**

Adicionar ao final de `hermes_agents/tests/test_pdv_estoque.py`:

```python
class TestCancelarVendaRestauraEstoque(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDBPdv()
        self.fake.caixas[1] = {"loja_id": 5}
        self.fake.lojas[5] = "Loja Fisica Central"
        self.fake.vendas[10] = {"id": 10, "caixa_id": 1, "cliente": "", "cliente_id": None,
                                 "total": 25.0, "desconto": 0, "operador": "Joao", "status": "finalizada",
                                 "data": "2026-07-31", "observacoes": None, "tipo": "venda", "numero": None}
        self.fake.itens[1] = {"id": 1, "venda_id": 10, "produto_codigo": "SKU1", "descricao": "Produto 1",
                               "quantidade": 2, "valor_unitario": 10.0, "desconto": 0, "valor_total": 20.0}
        self.fake.itens[2] = {"id": 2, "venda_id": 10, "produto_codigo": "SKU2", "descricao": "Produto 2",
                               "quantidade": 1, "valor_unitario": 5.0, "desconto": 0, "valor_total": 5.0}
        async def _get_db(_fake=self.fake):
            return _fake
        self.patch_db = patch("core.pdv.get_db", side_effect=_get_db)
        self.patch_db.start()
        self.patch_autoriza = patch("core.pdv._autorizar_gerencial",
                                     return_value={"ok": True, "id": 9, "nome": "Gerente", "role": "gerente"})
        self.patch_autoriza.start()

    def tearDown(self):
        self.patch_db.stop()
        self.patch_autoriza.stop()

    async def test_cancelar_restaura_quantidade_de_todos_os_itens(self):
        from core.pdv import cancelar_venda
        chamadas = []
        async def fake_entrada(conn, sku, loja, quantidade, motivo, usuario_id=None, usuario_nome="", ip=None, dispositivo=None):
            chamadas.append((sku, loja, quantidade, motivo))
            return {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade, "anterior": 0, "atual": quantidade}
        with patch("core.pdv.entrada_async", side_effect=fake_entrada):
            r = cancelar_venda(10, motivo="Cliente desistiu", operador_id=9)
        self.assertTrue(r.get("success"))
        self.assertEqual(sorted(chamadas), sorted([
            ("SKU1", "Loja Fisica Central", 2, "devolucao_cliente"),
            ("SKU2", "Loja Fisica Central", 1, "devolucao_cliente"),
        ]))
        self.assertEqual(self.fake.vendas[10]["status"], "cancelada")

    async def test_venda_ja_cancelada_nao_restaura_de_novo(self):
        from core.pdv import cancelar_venda
        self.fake.vendas[10]["status"] = "cancelada"
        with patch("core.pdv.entrada_async", new=AsyncMock()) as mock_entrada:
            r = cancelar_venda(10, motivo="tentativa dupla", operador_id=9)
        self.assertIn("error", r)
        mock_entrada.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

(Este bloco `if __name__ == "__main__":` substitui o que já estava no final do arquivo desde a Task 2 — mover, não duplicar.)

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/ -k "TestCancelarVendaRestauraEstoque" -v`
Expected: FAIL — `test_cancelar_restaura_quantidade_de_todos_os_itens` falha porque `chamadas` fica vazio (`entrada_async` ainda não é chamado dentro de `cancelar_venda`).

- [ ] **Step 3: Implementar**

Em `hermes_agents/core/pdv.py:581-597`, mudar `cancelar_venda()` de:

```python
def cancelar_venda(venda_id: int, motivo: str = "", operador: str = "", operador_id: int = None, senha: str = "",
                    gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    autorizador = _autorizar_gerencial(operador_id, senha, gerente_pin_id, pin, codigo_barras, _ROLES_GERENCIAIS)
    if autorizador.get("error"): return autorizador
    operador_registro = autorizador.get("nome") or operador
    async def _go():
        db = await get_db()
        venda = await db.fetchrow("SELECT * FROM pdv_vendas WHERE id = $1", venda_id)
        if not venda: return {"error": "Venda nao encontrada"}
        if venda["status"] == "cancelada": return {"error": "Venda ja cancelada"}
        await db.execute("UPDATE pdv_vendas SET status = 'cancelada', observacoes = $2 WHERE id = $1", venda_id, f"Cancelada: {motivo}" if motivo else "Cancelada")
        # Registrar devolucao
        await db.execute("INSERT INTO pdv_devolucoes (venda_id, motivo, valor, operador) VALUES ($1,$2,$3,$4)",
            venda_id, motivo, float(venda["total"] or 0), operador_registro)
        return {"success": True, "venda_id": venda_id}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}
```

para:

```python
def cancelar_venda(venda_id: int, motivo: str = "", operador: str = "", operador_id: int = None, senha: str = "",
                    gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    autorizador = _autorizar_gerencial(operador_id, senha, gerente_pin_id, pin, codigo_barras, _ROLES_GERENCIAIS)
    if autorizador.get("error"): return autorizador
    operador_registro = autorizador.get("nome") or operador
    async def _go():
        await _ensure_saldos_async()
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                venda = await conn.fetchrow("SELECT * FROM pdv_vendas WHERE id = $1", venda_id)
                if not venda: return {"error": "Venda nao encontrada"}
                if venda["status"] == "cancelada": return {"error": "Venda ja cancelada"}
                itens = await conn.fetch("SELECT produto_codigo, quantidade FROM pdv_itens WHERE venda_id = $1", venda_id)
                loja = await _resolver_loja_da_venda(conn, venda["caixa_id"])
                if loja:
                    for item in itens:
                        r = await entrada_async(conn, item["produto_codigo"], loja, item["quantidade"], "devolucao_cliente",
                                                usuario_id=autorizador.get("id"), usuario_nome=operador_registro)
                        if r.get("erro"):
                            raise SaldoError(f"Erro ao restaurar estoque de {item['produto_codigo']}: {r['erro']}")
                await conn.execute("UPDATE pdv_vendas SET status = 'cancelada', observacoes = $2 WHERE id = $1", venda_id, f"Cancelada: {motivo}" if motivo else "Cancelada")
                # Registrar devolucao
                await conn.execute("INSERT INTO pdv_devolucoes (venda_id, motivo, valor, operador) VALUES ($1,$2,$3,$4)",
                    venda_id, motivo, float(venda["total"] or 0), operador_registro)
                return {"success": True, "venda_id": venda_id}
    try: return run_async(_go())
    except SaldoError as e: return {"error": str(e)}
    except Exception as e: return {"error": str(e)}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/ -k "TestCancelarVendaRestauraEstoque" -v`
Expected: PASS (2 testes)

- [ ] **Step 5: Rodar suite completa**

Run: `cd hermes_agents && python -m pytest -q --ignore=test_fase2.py --ignore=test_fase3.py --ignore=test_fase_multiloja.py`
Expected: 0 failed (exceto o flaky conhecido).

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/pdv.py hermes_agents/tests/test_pdv_estoque.py
git commit -m "feat: cancelar_venda restaura estoque de todos os itens da venda"
```

---

### Task 5: `devolver_item_venda()` restaura quantidade parcial

**Files:**
- Modify: `hermes_agents/core/pdv.py::devolver_item_venda()` (linhas 599-637)
- Test: `hermes_agents/tests/test_pdv_estoque.py` (adiciona classe nova)

**Interfaces:**
- Consumes: `_resolver_loja_da_venda(conn, caixa_id)` (Task 2), `entrada_async(...)` (`core.estoque`), `SaldoError`.

- [ ] **Step 1: Escrever o teste (RED)**

Adicionar ao final de `hermes_agents/tests/test_pdv_estoque.py` (antes de `if __name__ == "__main__":`):

```python
class TestDevolverItemVendaRestauraParcial(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDBPdv()
        self.fake.caixas[1] = {"loja_id": 5}
        self.fake.lojas[5] = "Loja Fisica Central"
        self.fake.vendas[10] = {"id": 10, "caixa_id": 1, "cliente": "", "cliente_id": None,
                                 "total": 30.0, "desconto": 0, "operador": "Joao", "status": "finalizada",
                                 "data": "2026-07-31", "observacoes": None, "tipo": "venda", "numero": None}
        self.fake.itens[1] = {"id": 1, "venda_id": 10, "produto_codigo": "SKU1", "descricao": "Produto 1",
                               "quantidade": 5, "valor_unitario": 6.0, "desconto": 0, "valor_total": 30.0}
        async def _get_db(_fake=self.fake):
            return _fake
        self.patch_db = patch("core.pdv.get_db", side_effect=_get_db)
        self.patch_db.start()
        self.patch_autoriza = patch("core.pdv._autorizar_gerencial",
                                     return_value={"ok": True, "id": 9, "nome": "Gerente", "role": "gerente"})
        self.patch_autoriza.start()

    def tearDown(self):
        self.patch_db.stop()
        self.patch_autoriza.stop()

    async def test_devolve_so_quantidade_parcial_mantendo_resto_decrementado(self):
        from core.pdv import devolver_item_venda
        chamadas = []
        async def fake_entrada(conn, sku, loja, quantidade, motivo, usuario_id=None, usuario_nome="", ip=None, dispositivo=None):
            chamadas.append((sku, loja, quantidade, motivo))
            return {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade, "anterior": 0, "atual": quantidade}
        with patch("core.pdv.entrada_async", side_effect=fake_entrada):
            r = devolver_item_venda(1, quantidade=2, motivo="Defeito", operador_id=9)
        self.assertTrue(r.get("success"))
        self.assertEqual(chamadas, [("SKU1", "Loja Fisica Central", 2, "devolucao_cliente")])
        self.assertEqual(self.fake.itens[1]["quantidade"], 3)

    async def test_devolucao_total_remove_item_e_restaura_tudo(self):
        from core.pdv import devolver_item_venda
        chamadas = []
        async def fake_entrada(conn, sku, loja, quantidade, motivo, usuario_id=None, usuario_nome="", ip=None, dispositivo=None):
            chamadas.append((sku, loja, quantidade, motivo))
            return {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade, "anterior": 0, "atual": quantidade}
        with patch("core.pdv.entrada_async", side_effect=fake_entrada):
            r = devolver_item_venda(1, quantidade=5, motivo="Defeito", operador_id=9)
        self.assertTrue(r.get("success"))
        self.assertEqual(chamadas, [("SKU1", "Loja Fisica Central", 5, "devolucao_cliente")])
        self.assertNotIn(1, self.fake.itens)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/ -k "TestDevolverItemVendaRestauraParcial" -v`
Expected: FAIL — `chamadas` fica vazio (`entrada_async` ainda não é chamado dentro de `devolver_item_venda`).

- [ ] **Step 3: Implementar**

Em `hermes_agents/core/pdv.py:599-637`, mudar `devolver_item_venda()` de:

```python
def devolver_item_venda(item_id: int, quantidade: float, motivo: str = "", operador: str = "", operador_id: int = None, senha: str = "",
                         gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    """Devolucao parcial: remove qtd de um item da venda, ajusta total, registra devolucao.
    Exige autorizacao gerencial (senha do proprio gerente logado, PIN ou
    codigo de barras de um gerente chamado ao caixa) — cancelamento/devolucao
    e' forma comum de fraude ("desconta" a venda depois que o cliente ja
    pagou e saiu)."""
    autorizador = _autorizar_gerencial(operador_id, senha, gerente_pin_id, pin, codigo_barras, _ROLES_GERENCIAIS)
    if autorizador.get("error"): return autorizador
    operador_registro = autorizador.get("nome") or operador
    if quantidade is None or quantidade <= 0:
        return {"error": "Quantidade a devolver deve ser maior que zero"}
    async def _go():
        db = await get_db()
        item = await db.fetchrow("SELECT i.*, v.status AS venda_status FROM pdv_itens i JOIN pdv_vendas v ON v.id = i.venda_id WHERE i.id = $1", item_id)
        if not item: return {"error": "Item nao encontrado"}
        if item["venda_status"] == "cancelada": return {"error": "Venda ja cancelada"}
        valor_unitario = float(item["valor_unitario"] or 0)
        valor_devolvido = round(quantidade * valor_unitario, 2)
        # UPDATE atomico: a condicao "quantidade >= $1" no WHERE garante que a checagem de
        # estoque disponivel e' feita no mesmo statement que o decremento, evitando que duas
        # devolucoes concorrentes do mesmo item leiam a mesma quantidade e se sobrescrevam.
        atualizado = await db.fetchrow("""
            UPDATE pdv_itens SET quantidade = quantidade - $1,
                valor_total = ROUND((quantidade - $1) * valor_unitario, 2)
            WHERE id = $2 AND quantidade >= $1
            RETURNING quantidade
        """, quantidade, item_id)
        if not atualizado:
            return {"error": f"Quantidade insuficiente (max: {item['quantidade']})"}
        if float(atualizado["quantidade"]) <= 0:
            await db.execute("DELETE FROM pdv_itens WHERE id = $1", item_id)
        await db.execute("UPDATE pdv_vendas SET total = GREATEST(0, total - $1) WHERE id = $2", valor_devolvido, item["venda_id"])
        await db.execute("INSERT INTO pdv_devolucoes (venda_id, motivo, valor, operador) VALUES ($1,$2,$3,$4)",
            item["venda_id"], f"Item #{item_id}: {motivo}" if motivo else f"Devolucao parcial item #{item_id}",
            valor_devolvido, operador_registro)
        return {"success": True, "item_id": item_id, "quantidade_devolvida": quantidade, "valor_devolvido": valor_devolvido}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}
```

para:

```python
def devolver_item_venda(item_id: int, quantidade: float, motivo: str = "", operador: str = "", operador_id: int = None, senha: str = "",
                         gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    """Devolucao parcial: remove qtd de um item da venda, ajusta total, registra devolucao,
    restaura a quantidade devolvida no estoque real da loja fisica.
    Exige autorizacao gerencial (senha do proprio gerente logado, PIN ou
    codigo de barras de um gerente chamado ao caixa) — cancelamento/devolucao
    e' forma comum de fraude ("desconta" a venda depois que o cliente ja
    pagou e saiu)."""
    autorizador = _autorizar_gerencial(operador_id, senha, gerente_pin_id, pin, codigo_barras, _ROLES_GERENCIAIS)
    if autorizador.get("error"): return autorizador
    operador_registro = autorizador.get("nome") or operador
    if quantidade is None or quantidade <= 0:
        return {"error": "Quantidade a devolver deve ser maior que zero"}
    async def _go():
        await _ensure_saldos_async()
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                item = await conn.fetchrow(
                    "SELECT i.*, v.status AS venda_status, v.caixa_id FROM pdv_itens i JOIN pdv_vendas v ON v.id = i.venda_id WHERE i.id = $1", item_id)
                if not item: return {"error": "Item nao encontrado"}
                if item["venda_status"] == "cancelada": return {"error": "Venda ja cancelada"}
                valor_unitario = float(item["valor_unitario"] or 0)
                valor_devolvido = round(quantidade * valor_unitario, 2)
                # UPDATE atomico: a condicao "quantidade >= $1" no WHERE garante que a checagem de
                # estoque disponivel e' feita no mesmo statement que o decremento, evitando que duas
                # devolucoes concorrentes do mesmo item leiam a mesma quantidade e se sobrescrevam.
                atualizado = await conn.fetchrow("""
                    UPDATE pdv_itens SET quantidade = quantidade - $1,
                        valor_total = ROUND((quantidade - $1) * valor_unitario, 2)
                    WHERE id = $2 AND quantidade >= $1
                    RETURNING quantidade
                """, quantidade, item_id)
                if not atualizado:
                    return {"error": f"Quantidade insuficiente (max: {item['quantidade']})"}
                if float(atualizado["quantidade"]) <= 0:
                    await conn.execute("DELETE FROM pdv_itens WHERE id = $1", item_id)
                await conn.execute("UPDATE pdv_vendas SET total = GREATEST(0, total - $1) WHERE id = $2", valor_devolvido, item["venda_id"])
                await conn.execute("INSERT INTO pdv_devolucoes (venda_id, motivo, valor, operador) VALUES ($1,$2,$3,$4)",
                    item["venda_id"], f"Item #{item_id}: {motivo}" if motivo else f"Devolucao parcial item #{item_id}",
                    valor_devolvido, operador_registro)
                loja = await _resolver_loja_da_venda(conn, item["caixa_id"])
                if loja:
                    r = await entrada_async(conn, item["produto_codigo"], loja, quantidade, "devolucao_cliente",
                                            usuario_id=autorizador.get("id"), usuario_nome=operador_registro)
                    if r.get("erro"):
                        raise SaldoError(f"Erro ao restaurar estoque de {item['produto_codigo']}: {r['erro']}")
                return {"success": True, "item_id": item_id, "quantidade_devolvida": quantidade, "valor_devolvido": valor_devolvido}
    try: return run_async(_go())
    except SaldoError as e: return {"error": str(e)}
    except Exception as e: return {"error": str(e)}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/ -k "TestDevolverItemVendaRestauraParcial" -v`
Expected: PASS (2 testes)

- [ ] **Step 5: Rodar suite completa**

Run: `cd hermes_agents && python -m pytest -q --ignore=test_fase2.py --ignore=test_fase3.py --ignore=test_fase_multiloja.py`
Expected: 0 failed (exceto o flaky conhecido).

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/pdv.py hermes_agents/tests/test_pdv_estoque.py
git commit -m "feat: devolver_item_venda restaura quantidade parcial no estoque real"
```

---

### Task 6: Validação final

**Files:** nenhum novo — só execução.

- [ ] **Step 1: Suite completa do backend**

Run: `cd hermes_agents && python -m pytest -q --ignore=test_fase2.py --ignore=test_fase3.py --ignore=test_fase_multiloja.py`
Expected: 100% passando (exceto o flaky conhecido `test_all_endpoints.py::TestShopeeEndpoints::test_auth_url`, que passa isolado — confirmar rodando-o sozinho se aparecer como falha na suite completa).

- [ ] **Step 2: Smoke manual do fluxo completo (documentar no report, não é passo automatizado)**

Requer banco Postgres real (não disponível em todos os ambientes de execução deste plano — documentar essa limitação se não for possível executar). Se houver acesso:
1. Criar/usar um caixa com `loja_id` apontando pra uma loja física com estoque conhecido de 1 SKU (ex.: 10 unidades).
2. `realizar_venda()` desse caixa vendendo 3 unidades do SKU — confirmar que `estoque_lojas`/`estoque_saldos` da loja física caem pra 7.
3. Tentar vender mais unidades do que o saldo restante permite — confirmar que a venda inteira é rejeitada (nenhuma linha em `pdv_vendas`/`pdv_itens`, estoque continua em 7).
4. `cancelar_venda()` da venda de 3 unidades — confirmar que o estoque volta a 10.
5. Nova venda de 3 unidades, depois `devolver_item_venda()` devolvendo só 1 — confirmar que o estoque fica em 8 (10 - 3 + 1), não em 10.

- [ ] **Step 3: Commit final (se sobrar algo solto)**

```bash
git status
# se houver mudanca residual (ex.: ajuste de import esquecido), commitar normalmente
```

---

## Self-Review

**Cobertura da spec:** atomicidade na mesma transação (Tasks 3-5, via `db.acquire()`/`conn.transaction()` já existente ou adicionado), estoque insuficiente bloqueia a venda inteira via `SaldoError` (Task 3), cancelamento restaura tudo (Task 4), devolução parcial restaura só a parte devolvida (Task 5), loja resolvida de `pdv_caixas.loja_id` → nome (Task 2), motivo `venda_pdv` novo em `MOTIVOS_SAIDA`/`_MAPA_MOVIMENTO_SAIDA` (Task 1), motivo `devolucao_cliente` reusado sem mudança (já existia). Validação final (Task 6). Sem lacuna.

**Fora de escopo confirmado, não endereçado neste plano** (registrado na spec, não pedido pelo usuário): `core/pdv.py::buscar_produtos()` mostra estoque somado de todas as lojas, não o saldo da loja do caixa vendendo; loja virtual (spec separada); vínculo físico×virtual na baixa de PDV — quando a loja física da venda estiver vinculada a uma virtual, `saida_async`/`entrada_async` já resolvem automaticamente pro saldo compartilhado via `core.lojas._loja_efetiva_async` (Tasks 1-9 do plano `2026-07-30-vinculo-estoque-fisica-virtual.md`, já mergeado em master) — nenhuma mudança adicional necessária aqui, a integração já é automática pela camada de baixo.

**Nota de implementação, não desvio de spec:** a spec não decide o que fazer quando `pdv_caixas.loja_id` é nulo. Decisão desta plan (documentada em Global Constraints e no docstring de `_resolver_loja_da_venda`): pular a baixa/restauração de estoque sem bloquear a operação de PDV — fail-open, consistente com o padrão já usado em todo `core.lojas`/`core.estoque` (Tasks 3-9 do plano de vínculo). Reconsiderar se o usuário quiser bloquear vendas de caixas sem loja configurada.

**Consistência de tipos:** `_resolver_loja_da_venda(conn, caixa_id) -> str | None` usado identicamente nas Tasks 3, 4 e 5. `saida_async`/`entrada_async` chamados com a mesma assinatura posicional `(conn, sku, loja, quantidade, motivo, usuario_id=..., usuario_nome=...)` em todas as tasks — conferido contra a assinatura real em `core/estoque.py:148` e `:167`.

**Risco identificado para o implementador da Task 2:** o `FakeDBPdv` cobre só as queries exatas que as Tasks 3-5 emitem (texto fixado nesta plan) — se o implementador mudar o SQL literal de qualquer INSERT/UPDATE/SELECT ao implementar, precisa atualizar o branch correspondente no fake, senão o teste falha silenciosamente com `None`/lista vazia em vez do erro esperado.
