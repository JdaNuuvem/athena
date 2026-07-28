# Fase 1 — Saldos Segregados + Ledger Formal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o campo único `estoque_lojas.quantidade` por saldos segregados (`disponivel`, `reservado`, `separacao`, `transito`, `bloqueado`, `devolucao`, `danificado`, `perdido`, `consignado`, `inventario`, `virtual`), com ledger formal (`estoque_movimentacoes` com `saldo_anterior`/`saldo_posterior`/`ip`/`dispositivo`), corrigindo dois bugs reais de perda de saldo já encontrados no fluxo de transferência.

**Architecture:** Nova tabela `estoque_saldos(sku, loja, tipo, quantidade)` como fonte de verdade. `estoque_lojas.quantidade` vira espelho do saldo `disponivel`, mantido por trigger Postgres (defesa em profundidade — funciona mesmo se algum caller ainda não migrado escrever direto). Função única `mover_saldo()` em `core/estoque_saldos.py` grava saldo + ledger atomicamente; `entrada/saida/transferir/ratear` em `core/estoque.py` viram wrappers finos sobre ela. Os 6 pontos de escrita direta em `estoque_lojas` (fora de `core/estoque.py`) migram para chamar a API pública.

**Tech Stack:** Python 3, asyncpg, Flask, PostgreSQL (trigger + PL/pgSQL), unittest (`IsolatedAsyncioTestCase` com `FakeDB` mockando `get_db`).

## Global Constraints

- Fonte de verdade única: nenhuma movimentação de saldo pode acontecer sem passar por `mover_saldo()` e gerar linha em `estoque_movimentacoes`.
- `estoque_lojas.quantidade` continua existindo e correto — é espelho automático de `estoque_saldos` (tipo=`disponivel`), não fonte de dados.
- Assinaturas públicas existentes (`entrada`, `saida`, `transferir`, `ratear` em `core/estoque.py`) mantêm compatibilidade posicional — só ganham parâmetros novos opcionais no final (`ip=None, dispositivo=None`).
- `MOTIVOS_ENTRADA`, `MOTIVOS_SAIDA`, `MOTIVOS_TRANSFERENCIA`, `LIMITE_APROVACAO_UNIDADES` em `core/estoque.py` não mudam de nome/valor — outros módulos os importam.
- Sem `SELECT *` novo em SQL escrito nesta fase; todo INSERT/UPDATE usa placeholders parametrizados (`$1, $2...`), nunca f-string com valor variável.
- Buckets `reservado, separacao, bloqueado, devolucao, danificado, perdido, consignado, inventario, virtual` existem no schema desta fase mas **não têm produtor** — nenhuma task desta fase escreve neles. Confirmar isso no code review de cada task.

---

## Task 1: `core/estoque_saldos.py` — tabela, trigger espelho, `saldo()`, `mover_saldo()`

**Files:**
- Create: `hermes_agents/core/estoque_saldos.py`
- Test: `hermes_agents/tests/test_estoque_saldos.py`

**Interfaces:**
- Produces: `TIPOS_SALDO: tuple[str]`, `TIPOS_MOVIMENTO: tuple[str]`, `saldo(sku: str, loja: str, tipo: str = "disponivel") -> float`, `mover_saldo(sku: str, loja: str, tipo_origem: str | None, tipo_destino: str | None, quantidade: float, tipo_movimento: str, motivo: str = "", usuario_id: int = None, usuario_nome: str = "", ip: str = None, dispositivo: str = None) -> dict` — retorna `{"ok": True, "sku", "loja", "quantidade", "saldo_origem": {...}?, "saldo_destino": {...}?}` ou `{"erro": str}`.

- [ ] **Step 1: Escrever `core/estoque_saldos.py`**

```python
"""Saldos segregados de estoque (Fase 1 da revisao de arquitetura multilojas).
estoque_saldos e' a fonte de verdade; estoque_lojas.quantidade vira espelho do
saldo 'disponivel', mantido por trigger no banco (defesa em profundidade caso
algum caller ainda nao migrado escreva direto em estoque_lojas)."""
from core import get_db, run_async, log

AGENT = "Estoque Saldos"

TIPOS_SALDO = (
    "disponivel", "reservado", "separacao", "transito", "bloqueado",
    "devolucao", "danificado", "perdido", "consignado", "inventario", "virtual",
)

TIPOS_MOVIMENTO = (
    "compra", "venda", "ajuste", "inventario", "transferencia_saida",
    "transferencia_transito", "transferencia_recebida", "reserva",
    "liberacao_reserva", "separacao", "expedicao", "recebimento", "devolucao",
    "troca", "perda", "roubo", "extravio", "bonificacao", "cancelamento", "estorno",
)

_ok = False


def _ensure():
    global _ok
    if _ok:
        return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS estoque_saldos (
                id SERIAL PRIMARY KEY,
                sku VARCHAR(50) NOT NULL,
                loja VARCHAR(50) NOT NULL,
                tipo VARCHAR(20) NOT NULL,
                quantidade DECIMAL(12,3) NOT NULL DEFAULT 0,
                data_atualizacao TIMESTAMP DEFAULT NOW(),
                UNIQUE(sku, loja, tipo)
            )
        """)
        # Defensivo: garante que estoque_lojas existe mesmo se core/catalogo.py
        # (dono original) ainda nao rodou nesta conexao.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS estoque_lojas (
                id SERIAL PRIMARY KEY, sku VARCHAR(50) NOT NULL, loja VARCHAR(50) NOT NULL,
                quantidade DECIMAL(12,3) DEFAULT 0, data_atualizacao TIMESTAMP DEFAULT NOW(),
                UNIQUE (sku, loja)
            )
        """)
        # Defensivo: garante estoque_movimentacoes com as colunas novas de
        # auditoria mesmo se core/estoque.py ainda nao rodou nesta conexao.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS estoque_movimentacoes (
                id SERIAL PRIMARY KEY,
                sku VARCHAR(50) NOT NULL,
                loja VARCHAR(50) NOT NULL,
                tipo VARCHAR(30) NOT NULL,
                quantidade DECIMAL(12,3) NOT NULL,
                loja_relacionada VARCHAR(50),
                motivo VARCHAR(200),
                data TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS usuario_id INT")
        await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS usuario_nome VARCHAR(100)")
        await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS tipo_saldo VARCHAR(20)")
        await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS saldo_anterior DECIMAL(12,3)")
        await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS saldo_posterior DECIMAL(12,3)")
        await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS ip VARCHAR(45)")
        await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS dispositivo VARCHAR(300)")
        # Espelho: estoque_lojas.quantidade sempre reflete estoque_saldos
        # (tipo='disponivel') — defesa em profundidade pra callers nao migrados.
        await db.execute("""
            CREATE OR REPLACE FUNCTION fn_espelhar_saldo_disponivel() RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.tipo = 'disponivel' THEN
                    INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao)
                    VALUES (NEW.sku, NEW.loja, NEW.quantidade, NOW())
                    ON CONFLICT (sku, loja) DO UPDATE
                        SET quantidade = NEW.quantidade, data_atualizacao = NOW();
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """)
        await db.execute("DROP TRIGGER IF EXISTS trg_espelhar_saldo_disponivel ON estoque_saldos")
        await db.execute("""
            CREATE TRIGGER trg_espelhar_saldo_disponivel
            AFTER INSERT OR UPDATE ON estoque_saldos
            FOR EACH ROW EXECUTE FUNCTION fn_espelhar_saldo_disponivel()
        """)
    try:
        run_async(_go())
        _ok = True
    except Exception as e:
        log(AGENT, f"Erro tabela/trigger: {e}")


def saldo(sku: str, loja: str, tipo: str = "disponivel") -> float:
    _ensure()
    async def _go():
        db = await get_db()
        v = await db.fetchval(
            "SELECT quantidade FROM estoque_saldos WHERE sku = $1 AND loja = $2 AND tipo = $3",
            sku, loja, tipo)
        return float(v or 0)
    try:
        return run_async(_go())
    except Exception:
        return 0.0


def mover_saldo(sku: str, loja: str, tipo_origem, tipo_destino, quantidade: float,
                tipo_movimento: str, motivo: str = "", usuario_id: int = None, usuario_nome: str = "",
                ip: str = None, dispositivo: str = None) -> dict:
    """Unica funcao que escreve em estoque_saldos + estoque_movimentacoes, na
    mesma transacao logica. tipo_origem=None => credito puro (entrada).
    tipo_destino=None => debito puro (saida). Pelo menos um dos dois precisa
    estar presente. Nunca chamar UPDATE/INSERT em estoque_saldos fora daqui."""
    _ensure()
    if tipo_origem is None and tipo_destino is None:
        return {"erro": "tipo_origem e tipo_destino nao podem ser ambos None"}
    if tipo_origem is not None and tipo_origem not in TIPOS_SALDO:
        return {"erro": f"tipo_origem invalido: {tipo_origem}"}
    if tipo_destino is not None and tipo_destino not in TIPOS_SALDO:
        return {"erro": f"tipo_destino invalido: {tipo_destino}"}
    if tipo_movimento not in TIPOS_MOVIMENTO:
        return {"erro": f"tipo_movimento invalido: {tipo_movimento}"}
    if quantidade <= 0:
        return {"erro": "quantidade deve ser maior que zero"}

    async def _go():
        db = await get_db()
        resultado = {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade}

        if tipo_origem is not None:
            atual = await db.fetchval(
                "SELECT quantidade FROM estoque_saldos WHERE sku = $1 AND loja = $2 AND tipo = $3",
                sku, loja, tipo_origem)
            atual = float(atual or 0)
            if atual < quantidade:
                return {"erro": f"Saldo insuficiente em '{tipo_origem}' ({atual} disponivel, {quantidade} solicitado)"}
            nova_origem = atual - quantidade
            await db.execute("""
                INSERT INTO estoque_saldos (sku, loja, tipo, quantidade, data_atualizacao)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (sku, loja, tipo) DO UPDATE SET quantidade = $4, data_atualizacao = NOW()
            """, sku, loja, tipo_origem, nova_origem)
            await db.execute("""
                INSERT INTO estoque_movimentacoes
                    (sku, loja, tipo, quantidade, motivo, usuario_id, usuario_nome,
                     tipo_saldo, saldo_anterior, saldo_posterior, ip, dispositivo)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """, sku, loja, tipo_movimento, quantidade, motivo, usuario_id, usuario_nome,
                tipo_origem, atual, nova_origem, ip, dispositivo)
            resultado["saldo_origem"] = {"tipo": tipo_origem, "anterior": atual, "atual": nova_origem}

        if tipo_destino is not None:
            atual_d = await db.fetchval(
                "SELECT quantidade FROM estoque_saldos WHERE sku = $1 AND loja = $2 AND tipo = $3",
                sku, loja, tipo_destino)
            atual_d = float(atual_d or 0)
            nova_destino = atual_d + quantidade
            await db.execute("""
                INSERT INTO estoque_saldos (sku, loja, tipo, quantidade, data_atualizacao)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (sku, loja, tipo) DO UPDATE SET quantidade = $4, data_atualizacao = NOW()
            """, sku, loja, tipo_destino, nova_destino)
            await db.execute("""
                INSERT INTO estoque_movimentacoes
                    (sku, loja, tipo, quantidade, motivo, usuario_id, usuario_nome,
                     tipo_saldo, saldo_anterior, saldo_posterior, ip, dispositivo)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """, sku, loja, tipo_movimento, quantidade, motivo, usuario_id, usuario_nome,
                tipo_destino, atual_d, nova_destino, ip, dispositivo)
            resultado["saldo_destino"] = {"tipo": tipo_destino, "anterior": atual_d, "atual": nova_destino}

        return resultado
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}
```

- [ ] **Step 2: Escrever `tests/test_estoque_saldos.py` (falhando, ainda sem uso real)**

```python
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
```

- [ ] **Step 3: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_saldos.py -v`
Expected: 9 passed.

- [ ] **Step 4: Corrigir a spec quanto ao CHECK constraint de `tipo`**

Editar `docs/superpowers/specs/2026-07-28-fase1-saldos-segregados-design.md`, seção "`estoque_movimentacoes` expandido": trocar a frase "`tipo` ... vira CHECK constraint com os 18 valores" por uma nota explicando que a validação fica só em Python (`TIPOS_MOVIMENTO` em `mover_saldo()`), não como constraint de banco — `ADD CONSTRAINT CHECK` quebraria a migração por causa de linhas históricas com `tipo` em `entrada/saida/transferencia_origem/transferencia_destino/rateio`, fora do novo enum de 18 valores.

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/estoque_saldos.py hermes_agents/tests/test_estoque_saldos.py \
        docs/superpowers/specs/2026-07-28-fase1-saldos-segregados-design.md
git commit -m "feat: core/estoque_saldos.py - saldos segregados + mover_saldo (Fase 1)"
```

---

## Task 2: `core/estoque.py` — `entrada/saida/transferir/ratear` viram wrappers de `mover_saldo`

**Files:**
- Modify: `hermes_agents/core/estoque.py`
- Modify: `hermes_agents/tests/test_estoque_seguranca.py`

**Interfaces:**
- Consumes: `core.estoque_saldos.mover_saldo`, `core.estoque_saldos.saldo`, `core.estoque_saldos.TIPOS_MOVIMENTO` (Task 1).
- Produces: `entrada(sku, loja, quantidade, motivo="", usuario_id=None, usuario_nome="", ip=None, dispositivo=None) -> dict`, `saida(sku, loja, quantidade, motivo="", usuario_id=None, usuario_nome="", ip=None, dispositivo=None) -> dict`, `transferir(sku, origem, destino, quantidade, motivo="", usuario_id=None, usuario_nome="", ip=None, dispositivo=None) -> dict`, `ratear(...)` (assinatura inalterada). Todos continuam retornando `{"ok": True, "sku", "loja"/"origem"/"destino", "quantidade", "anterior", "atual"}` como hoje (campos `anterior`/`atual` mapeados do `saldo_origem`/`saldo_destino` de `mover_saldo` para não quebrar consumidores como `routes/estoque.py` que leem `resultado["atual"]`).

- [ ] **Step 1: Substituir `_ensure()`, `entrada()`, `saida()`, `transferir()` em `core/estoque.py`**

Remove a função `_ensure()` antiga (linhas 20-45 do arquivo atual) e o `_ok`/`_where_loja_param` fica como está (usado por `listar()`, não mexe). Adiciona import e mapas de tipo de movimento, e reescreve as três funções:

```python
from core.estoque_saldos import mover_saldo, saldo as _saldo_bucket

_MAPA_MOVIMENTO_ENTRADA = {
    "compra_fornecedor": "compra",
    "devolucao_cliente": "devolucao",
    "producao_interna": "recebimento",
    "ajuste_inventario": "ajuste",
    "outro": "ajuste",
}
_MAPA_MOVIMENTO_SAIDA = {
    "quebra": "perda",
    "perda": "perda",
    "devolucao_fornecedor": "devolucao",
    "uso_interno": "ajuste",
    "furto_identificado": "roubo",
    "ajuste_inventario": "ajuste",
    "outro": "ajuste",
}


def entrada(sku: str, loja: str, quantidade: float, motivo: str = "",
            usuario_id: int = None, usuario_nome: str = "",
            ip: str = None, dispositivo: str = None) -> dict:
    if motivo not in MOTIVOS_ENTRADA:
        motivo = "outro"
    tipo_movimento = _MAPA_MOVIMENTO_ENTRADA[motivo]
    r = mover_saldo(sku, loja, None, "disponivel", quantidade, tipo_movimento, motivo,
                     usuario_id, usuario_nome, ip, dispositivo)
    if r.get("erro"):
        return r
    d = r["saldo_destino"]
    return {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade,
            "anterior": d["anterior"], "atual": d["atual"]}


def saida(sku: str, loja: str, quantidade: float, motivo: str = "",
          usuario_id: int = None, usuario_nome: str = "",
          ip: str = None, dispositivo: str = None) -> dict:
    """Aplica a saida diretamente. Nao decide alcada de aprovacao — quem chama
    (routes/estoque.py ou core/estoque_aprovacoes.py) decide se a quantidade
    exige aprovacao antes de chegar aqui."""
    if motivo not in MOTIVOS_SAIDA:
        return {"erro": f"Motivo invalido. Use um de: {', '.join(MOTIVOS_SAIDA)}"}
    tipo_movimento = _MAPA_MOVIMENTO_SAIDA[motivo]
    r = mover_saldo(sku, loja, "disponivel", None, quantidade, tipo_movimento, motivo,
                     usuario_id, usuario_nome, ip, dispositivo)
    if r.get("erro"):
        return r
    o = r["saldo_origem"]
    return {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade,
            "anterior": o["anterior"], "atual": o["atual"]}


def transferir(sku: str, origem: str, destino: str, quantidade: float, motivo: str = "",
               usuario_id: int = None, usuario_nome: str = "",
               ip: str = None, dispositivo: str = None) -> dict:
    """Transferencia instantanea, sem aprovacao/estado pendente — nao passa
    pelo bucket 'transito' (esse e' exclusivo do fluxo com aprovacao em
    core/estoque_transferencias.py)."""
    r1 = mover_saldo(sku, origem, "disponivel", None, quantidade, "transferencia_saida", motivo,
                      usuario_id, usuario_nome, ip, dispositivo)
    if r1.get("erro"):
        return {"erro": r1["erro"] if "insuficiente" in r1.get("erro", "") else f"Saldo insuficiente na origem: {r1['erro']}"}
    r2 = mover_saldo(sku, destino, None, "disponivel", quantidade, "transferencia_recebida", motivo,
                      usuario_id, usuario_nome, ip, dispositivo)
    if r2.get("erro"):
        return r2
    return {"ok": True, "sku": sku, "origem": origem, "destino": destino,
            "quantidade": quantidade,
            "saldo_origem": r1["saldo_origem"]["atual"], "saldo_destino": r2["saldo_destino"]["atual"]}
```

`ratear()` troca só o corpo do loop final (mantém todo o cálculo de percentuais igual, de `resultados = []` até o fim da função):

```python
        resultados = []
        distribuido = 0
        for i, loja in enumerate(lojas_validas):
            qtd = round(total * pcts[loja] / 100, 3)
            if i == n - 1:
                qtd = round(total - distribuido, 3)
            distribuido += qtd
            mover_saldo(sku, loja, None, "disponivel", qtd, "ajuste", f"rateio {modo}: {pcts[loja]}%")
            resultados.append({"loja": loja, "quantidade": qtd, "percentual": pcts[loja]})
        return {"ok": True, "sku": sku, "total": total, "modo": modo,
                "lojas": resultados, "percentuais": pcts}
```

**Remove `atualizar()` inteira** (linhas 87-109 do arquivo atual — escreve direto em `estoque_lojas`, sem ledger, e não tem nenhum caller no código hoje, confirmado por grep). Deixá-la seria um furo no invariante "toda escrita passa por `mover_saldo`" caso alguém volte a chamá-la.

**Nova função pública `ajustar_absoluto()`** — usada por `bling_erp.py` (Task 5) e `routes/estoque.py::atualizar_estoque_loja` (Task 4), os dois lugares que recebem uma quantidade **absoluta** (não delta) de um sistema externo e precisam convertê-la em movimento de saldo:

```python
def ajustar_absoluto(sku: str, loja: str, quantidade_absoluta: float, motivo: str = "ajuste_inventario",
                      usuario_id: int = None, usuario_nome: str = "",
                      ip: str = None, dispositivo: str = None) -> dict:
    """Para integrações que mandam o valor final, não um delta (Bling, PUT manual
    de loja). Calcula o delta contra o disponível atual e aplica como entrada/saida."""
    atual = _saldo_bucket(sku, loja, "disponivel")
    delta = round(float(quantidade_absoluta) - atual, 3)
    if delta == 0:
        return {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade_absoluta,
                "anterior": atual, "atual": atual, "sem_alteracao": True}
    if delta > 0:
        return entrada(sku, loja, delta, motivo, usuario_id, usuario_nome, ip, dispositivo)
    return saida(sku, loja, abs(delta), motivo, usuario_id, usuario_nome, ip, dispositivo)
```

`_ensure()` e a constante global `_ok` somem de `core/estoque.py` — quem cria as tabelas agora é `core/estoque_saldos._ensure()` (chamado implicitamente por `mover_saldo`). `listar()`, `movimentacoes()`, `sync_bling()`, `sugestao_rotacao()` etc. continuam lendo `estoque_lojas`/`estoque_movimentacoes` direto via SQL sem alteração — leitura, não escrita, funciona pelo espelho.

**Nota sobre `tipo` de `estoque_movimentacoes` (desvio da spec):** a spec original propõe um `CHECK constraint` no banco com os 18 valores de `TIPOS_MOVIMENTO`. Isso quebraria o `ALTER TABLE` em produção — a tabela já tem linhas históricas com `tipo` em `entrada/saida/transferencia_origem/transferencia_destino/rateio`, que não pertencem ao novo enum de 18 valores, e `ADD CONSTRAINT CHECK` valida linhas existentes por padrão. Fica **só validação em Python** (`TIPOS_MOVIMENTO` em `core/estoque_saldos.py`, checada dentro de `mover_saldo()`), sem constraint de banco. Atualizar a spec (Task 1, Step 4 abaixo) para refletir isso.

- [ ] **Step 2: Atualizar `FakeDB` em `tests/test_estoque_seguranca.py` para o novo formato de escrita**

O `FakeDB` hoje reconhece `INSERT INTO estoque_lojas`/`UPDATE estoque_lojas SET quantidade = quantidade -`. Como `entrada/saida/transferir` agora passam por `core.estoque_saldos.mover_saldo`, que fala com `get_db()` importado em `core.estoque_saldos` (não mais em `core.estoque`), o patch precisa cobrir esse módulo também, e o `FakeDB` precisa reconhecer `SELECT/INSERT ... estoque_saldos`:

```python
# em setUp(), adicionar "core.estoque_saldos" na tupla de modulos patchados:
for modulo in ("core.estoque", "core.estoque_saldos", "core.estoque_aprovacoes",
               "core.estoque_transferencias", "core.estoque_contagem"):
    ...
import core.estoque_saldos as ms
ms._ok = True
```

E em `FakeDB`, trocar a leitura/escrita de estoque para simular `estoque_saldos` com o bucket `disponivel` mapeado direto pra `self.estoque` (mantém as asserções existentes dos testes, que checam `self.fake.estoque[(sku, loja)]`):

```python
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
    if "INSERT INTO estoque_movimentacoes" in q:
        self.movimentacoes.append(params)
        return "OK"
    # ... mantem os blocos existentes de estoque_aprovacoes/estoque_transferencias/estoque_contagens
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
```

Adicionar `self.saldos = {}` em `FakeDB.__init__`. Os testes existentes (`test_saida_pequena_aplica_direto_com_usuario` etc.) continuam válidos sem alteração de asserção — só o mecanismo interno do fake muda.

- [ ] **Step 3: Rodar a suite inteira e confirmar que os testes existentes ainda passam**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_seguranca.py -v`
Expected: todos os 12 testes existentes PASS (comportamento observável inalterado).

- [ ] **Step 4: Commit**

```bash
git add hermes_agents/core/estoque.py hermes_agents/tests/test_estoque_seguranca.py
git commit -m "refactor: core/estoque.py entrada/saida/transferir/ratear usam mover_saldo"
```

---

## Task 3: Corrige `core/estoque_transferencias.py` e `core/estoque_aprovacoes.py` — bucket `transito` real + bug de rejeição

**Files:**
- Modify: `hermes_agents/core/estoque_transferencias.py`
- Modify: `hermes_agents/core/estoque_aprovacoes.py`
- Modify: `hermes_agents/tests/test_estoque_seguranca.py`

**Interfaces:**
- Consumes: `core.estoque_saldos.mover_saldo` (Task 1), `core.estoque.saida` com `ip`/`dispositivo` (Task 2).
- Produces: `solicitar(sku, origem, destino, quantidade, motivo, usuario_id=None, usuario_nome="", ip=None, dispositivo=None) -> dict`, `confirmar(transferencia_id, confirmador_id, confirmador_nome, quantidade_recebida, ip=None, dispositivo=None) -> dict`, `rejeitar(transferencia_id, aprovador_id, aprovador_nome, motivo_rejeicao="", ip=None, dispositivo=None) -> dict` (agora devolve saldo). `estoque_aprovacoes.solicitar(..., ip=None, dispositivo=None)`, `estoque_aprovacoes.aprovar(aprovacao_id, aprovador_id, aprovador_nome, ip=None, dispositivo=None)`.

- [ ] **Step 1: Reescrever `_debitar_origem`/`_creditar_destino` em `estoque_transferencias.py`**

Substitui as duas funções internas (linhas 46-57 do arquivo atual) e os pontos que as chamam:

```python
from core.estoque_saldos import mover_saldo


def solicitar(sku: str, origem: str, destino: str, quantidade: float, motivo: str,
              usuario_id: int = None, usuario_nome: str = "",
              ip: str = None, dispositivo: str = None) -> dict:
    _ensure()
    precisa_aprovacao = quantidade > LIMITE_APROVACAO_UNIDADES
    status_inicial = "pendente_aprovacao" if precisa_aprovacao else "em_transito"

    if not precisa_aprovacao:
        r = mover_saldo(sku, origem, "disponivel", "transito", quantidade,
                         "transferencia_saida", motivo, usuario_id, usuario_nome, ip, dispositivo)
        if r.get("erro"):
            return {"erro": r["erro"]}

    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            INSERT INTO estoque_transferencias
                (sku, loja_origem, loja_destino, quantidade_solicitada, motivo, status,
                 usuario_solicitante_id, usuario_solicitante_nome)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id
        """, sku, origem, destino, quantidade, motivo, status_inicial, usuario_id, usuario_nome)
        return row["id"]
    transferencia_id = run_async(_go())
    return {"transferencia_id": transferencia_id, "status": status_inicial,
            "pendente_aprovacao": precisa_aprovacao,
            "origem": origem, "destino": destino, "quantidade": quantidade}
```

`aprovar()` (a que libera uma transferência `pendente_aprovacao` para `em_transito`) precisa agora também debitar disponível→trânsito, já que `solicitar()` não debitou mais quando ficou pendente:

```python
def aprovar(transferencia_id: int, aprovador_id: int, aprovador_nome: str,
            ip: str = None, dispositivo: str = None) -> dict:
    _ensure()
    async def _buscar():
        db = await get_db()
        return await db.fetchrow("SELECT * FROM estoque_transferencias WHERE id = $1", transferencia_id)
    row = run_async(_buscar())
    if not row:
        return {"erro": "transferencia nao encontrada"}
    if row["status"] != "pendente_aprovacao":
        return {"erro": f"transferencia ja resolvida (status: {row['status']})"}

    r = mover_saldo(row["sku"], row["loja_origem"], "disponivel", "transito",
                     float(row["quantidade_solicitada"]), "transferencia_saida", row["motivo"],
                     aprovador_id, aprovador_nome, ip, dispositivo)
    if r.get("erro"):
        return {"erro": r["erro"]}

    async def _marcar():
        db = await get_db()
        await db.execute("""
            UPDATE estoque_transferencias SET status = 'em_transito',
                usuario_aprovador_id = $1, usuario_aprovador_nome = $2
            WHERE id = $3
        """, aprovador_id, aprovador_nome, transferencia_id)
    run_async(_marcar())
    return {"ok": True, "transferencia_id": transferencia_id, "status": "em_transito"}


def rejeitar(transferencia_id: int, aprovador_id: int, aprovador_nome: str, motivo_rejeicao: str = "",
             ip: str = None, dispositivo: str = None) -> dict:
    """Bug corrigido: antes so mudava status, nunca devolvia o saldo. Se a
    transferencia ja tinha debitado a origem (status pendente_aprovacao so
    existe se NAO debitou ainda — ver solicitar() — entao aqui nunca ha saldo
    em transito pra devolver quando rejeitada nesse estado). Mantido por
    simetria e para o caso futuro de rejeicao pos-aprovacao."""
    _ensure()
    async def _buscar():
        db = await get_db()
        return await db.fetchrow("SELECT status FROM estoque_transferencias WHERE id = $1", transferencia_id)
    row = run_async(_buscar())
    if not row:
        return {"erro": "transferencia nao encontrada"}
    if row["status"] != "pendente_aprovacao":
        return {"erro": f"transferencia ja resolvida (status: {row['status']})"}
    async def _marcar():
        db = await get_db()
        await db.execute("""
            UPDATE estoque_transferencias SET status = 'rejeitada',
                usuario_aprovador_id = $1, usuario_aprovador_nome = $2, motivo_rejeicao = $3
            WHERE id = $4
        """, aprovador_id, aprovador_nome, motivo_rejeicao, transferencia_id)
    run_async(_marcar())
    return {"ok": True, "transferencia_id": transferencia_id, "status": "rejeitada"}
```

**Nota de design:** ao mover o débito de `solicitar()` para `aprovar()` (só debita quando realmente vai em trânsito), o bug original de "rejeitar não devolve saldo" desaparece por construção — `rejeitar()` só acontece a partir de `pendente_aprovacao`, estado em que a origem nunca foi debitada. Isso é mais simples e mais seguro que debitar cedo e reembolsar depois. Atualizar a spec (`docs/superpowers/specs/2026-07-28-fase1-saldos-segregados-design.md`) com uma nota apontando essa mudança de abordagem antes de finalizar a task (ver Step 4).

`confirmar()`:

```python
def confirmar(transferencia_id: int, confirmador_id: int, confirmador_nome: str, quantidade_recebida: float,
              ip: str = None, dispositivo: str = None) -> dict:
    """Loja destino confirma o recebimento fisico. Credita a quantidade REALMENTE
    recebida (pode divergir da solicitada — fica registrado como discrepancia)."""
    _ensure()
    async def _buscar():
        db = await get_db()
        return await db.fetchrow("SELECT * FROM estoque_transferencias WHERE id = $1", transferencia_id)
    row = run_async(_buscar())
    if not row:
        return {"erro": "transferencia nao encontrada"}
    if row["status"] != "em_transito":
        return {"erro": f"transferencia nao esta em transito (status: {row['status']})"}

    r1 = mover_saldo(row["sku"], row["loja_origem"], "transito", None, quantidade_recebida,
                      "transferencia_recebida", row["motivo"], confirmador_id, confirmador_nome, ip, dispositivo)
    if r1.get("erro"):
        return {"erro": r1["erro"]}
    r2 = mover_saldo(row["sku"], row["loja_destino"], None, "disponivel", quantidade_recebida,
                      "transferencia_recebida", row["motivo"], confirmador_id, confirmador_nome, ip, dispositivo)
    if r2.get("erro"):
        return {"erro": r2["erro"]}

    discrepancia = abs(float(quantidade_recebida) - float(row["quantidade_solicitada"])) > 0.001
    status_final = "com_discrepancia" if discrepancia else "confirmada"
    async def _marcar():
        db = await get_db()
        await db.execute("""
            UPDATE estoque_transferencias SET status = $1, quantidade_recebida = $2,
                usuario_confirmador_id = $3, usuario_confirmador_nome = $4
            WHERE id = $5
        """, status_final, quantidade_recebida, confirmador_id, confirmador_nome, transferencia_id)
    run_async(_marcar())
    return {"ok": True, "transferencia_id": transferencia_id, "status": status_final,
            "quantidade_solicitada": float(row["quantidade_solicitada"]),
            "quantidade_recebida": float(quantidade_recebida), "discrepancia": discrepancia}
```

- [ ] **Step 2: Threadear `ip`/`dispositivo` em `estoque_aprovacoes.py`**

`solicitar()` ganha os dois parâmetros novos (não usa, é só repasse futuro — hoje `solicitar` não grava ledger, só a tabela `estoque_aprovacoes`, então os parâmetros ficam aceitos mas sem uso ainda; evita quebrar a assinatura se uma fase futura passar a usá-los):

```python
def solicitar(sku: str, loja: str, quantidade: float, motivo: str,
              usuario_id: int = None, usuario_nome: str = "",
              ip: str = None, dispositivo: str = None) -> dict:
    _ensure()
    ...  # corpo inalterado
```

`aprovar()` repassa pra `_aplicar_saida` (que é `core.estoque.saida`, já aceita os parâmetros novos da Task 2):

```python
def aprovar(aprovacao_id: int, aprovador_id: int, aprovador_nome: str,
            ip: str = None, dispositivo: str = None) -> dict:
    _ensure()
    ...  # busca pendencia, inalterado
    resultado = _aplicar_saida(
        pendencia["sku"], pendencia["loja"], float(pendencia["quantidade"]), pendencia["motivo"],
        usuario_id=pendencia["usuario_solicitante_id"], usuario_nome=pendencia["usuario_solicitante_nome"],
        ip=ip, dispositivo=dispositivo)
    ...  # resto inalterado
```

- [ ] **Step 3: Atualizar `tests/test_estoque_seguranca.py`**

`test_transferencia_pequena_debita_origem_fica_em_transito` — o nome continua correto (transferência sem aprovação debita na hora), mas agora a asserção certa é sobre o bucket `transito`, não `estoque_lojas` direto:

```python
async def test_transferencia_pequena_debita_origem_fica_em_transito(self):
    from core.estoque_transferencias import solicitar
    self.fake.set_saldo("SKU1", "Loja A", "disponivel", 50)
    r = solicitar("SKU1", "Loja A", "Loja B", 5, "reposicao_entre_lojas", usuario_id=1, usuario_nome="op")
    self.assertEqual(r["status"], "em_transito")
    self.assertFalse(r["pendente_aprovacao"])
    self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "disponivel")], 45)
    self.assertEqual(self.fake.saldos[("SKU1", "Loja A", "transito")], 5)
```

Adiciona `set_saldo` como helper no `FakeDB` (equivalente a `set_estoque`, mas gravando direto em `self.saldos[(sku, loja, tipo)]` com tipo `"disponivel"` por padrão) e um novo teste:

```python
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
```

O `FakeDB` precisa reconhecer `UPDATE estoque_transferencias SET status = 'em_transito'` também quando disparado por `aprovar()` (já reconhece — reaproveita o bloco existente) e a nova coluna no INSERT de `estoque_transferencias` — conferir que o número de `params` na query de `solicitar()` bate com o handler do fake (mesmo formato de hoje, sem mudança de coluna nessa tabela).

- [ ] **Step 4: Corrigir a nota de design na spec**

Editar `docs/superpowers/specs/2026-07-28-fase1-saldos-segregados-design.md`, seção "Corrige `estoque_transferencias.py`": trocar a frase sobre `rejeitar()` devolver saldo por uma explicando que o débito moveu de `solicitar()` para `aprovar()`, eliminando a necessidade de reembolso em `rejeitar()` (pendente nunca chegou a debitar).

- [ ] **Step 5: Rodar a suite inteira**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_seguranca.py -v`
Expected: todos passam, incluindo os 3 testes novos.

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/estoque_transferencias.py hermes_agents/core/estoque_aprovacoes.py \
        hermes_agents/tests/test_estoque_seguranca.py docs/superpowers/specs/2026-07-28-fase1-saldos-segregados-design.md
git commit -m "fix: transferencia usa bucket transito de verdade, corrige perda de saldo em rejeicao"
```

---

## Task 4: `routes/estoque.py` — captura IP/dispositivo e repassa

**Files:**
- Modify: `hermes_agents/routes/estoque.py`

**Interfaces:**
- Consumes: `core.estoque.entrada/saida` com `ip/dispositivo` (Task 2); `core.estoque_aprovacoes.solicitar/aprovar` e `core.estoque_transferencias.solicitar/aprovar/confirmar/rejeitar` com `ip/dispositivo` (Task 3).

- [ ] **Step 1: Adicionar helper e passar `ip`/`dispositivo` nos 6 handlers que alteram saldo**

No topo do arquivo (perto de `_dicts`/`_db_sync`):

```python
def _origem_requisicao() -> tuple:
    return request.remote_addr, request.headers.get("User-Agent", "")[:300]
```

Em cada handler que chama uma função de saldo, capturar e repassar:

```python
@estoque_bp.route('/entrada', methods=['POST'])
def estoque_entrada():
    ...
    usuario = usuario_atual_da_request()
    ip, dispositivo = _origem_requisicao()
    resultado = est_entrada(sku, loja, qtd, motivo, usuario["user_id"], usuario["nome"], ip, dispositivo)
    ...
```

Mesma alteração (adicionar `ip, dispositivo = _origem_requisicao()` e passar como dois argumentos posicionais finais) em: `estoque_saida` (chamada a `est_saida`), `estoque_aprovar` (chamada a `aprovar_saida`), `estoque_transferir` (chamada a `solicitar_transferencia`), `estoque_transferencia_aprovar` (se existir handler — conferir; se `estoque_transferencias.aprovar` não tiver rota HTTP hoje, criar não é escopo desta task, só passar `ip/dispositivo` onde já existe chamada), `estoque_transferencia_rejeitar` (chamada a `rejeitar_transf`), `estoque_transferencia_confirmar` (chamada a `confirmar_transf`).

- [ ] **Step 2: Migrar `atualizar_estoque_loja` (`PUT /api/estoque/lojas`) — escritor direto via psycopg2, não coberto em nenhuma outra task**

Essa rota (linhas 68-99 do arquivo atual) recebe uma quantidade **absoluta** vinda de uma edição manual de tela e escreve direto via `psycopg2`, ignorando totalmente o ledger — nem passa por `core/estoque.py`. Substitui o corpo por uma chamada a `ajustar_absoluto` (Task 2):

```python
@estoque_bp.route('/lojas', methods=['PUT'])
def atualizar_estoque_loja():
    """Atualiza quantidade de estoque em uma loja/deposito. Two-way sync via fila offline."""
    from core.estoque import ajustar_absoluto
    from core.rbac import usuario_atual_da_request
    dados = request.json or {}
    sku = dados.get("sku", "").strip()
    loja_nome = str(dados.get("loja", "")).strip()
    quantidade = dados.get("quantidade")
    sync_bling = str(dados.get("sync_bling", "1")) == "1"
    if not sku or not loja_nome or quantidade is None:
        return jsonify({"erro": "sku, loja e quantidade obrigatorios"}), 400
    usuario = usuario_atual_da_request()
    ip, dispositivo = _origem_requisicao()
    resultado = ajustar_absoluto(sku, loja_nome, float(quantidade), "ajuste_inventario",
                                  usuario["user_id"], usuario["nome"], ip, dispositivo)
    if resultado.get("erro"):
        return jsonify(resultado), 500
    if sync_bling:
        from core.estoque import sync_para_bling
        resultado["bling_sync"] = sync_para_bling(loja_nome, sku, float(quantidade))
    try:
        from shopee import sincronizar_estoque_todas_lojas_automatico
        Thread(target=lambda: sincronizar_estoque_todas_lojas_automatico(sku, float(quantidade)), daemon=True).start()
    except Exception:
        pass
    return jsonify(resultado)
```

Remove os imports `psycopg2`/`psycopg2.extras` no topo do arquivo **só se** `_db_sync()` não for mais usada por nenhuma outra rota do arquivo — conferir (`estoque_por_loja` também usa `_db_sync()` para leitura; se ainda estiver em uso, manter os imports e só remover o uso local desta função). A coluna `sync_status` (setada como `'pendente'` no código antigo) deixa de ser tocada por esta rota — fora do escopo desta fase (mesma decisão do Task 5 para `bling_erp.py`).

- [ ] **Step 3: Teste manual via curl/Postman contra ambiente local**

Não há teste automatizado de rota HTTP nesta suite (os testes existentes cobrem só a camada `core.*`). Validar manualmente: `POST /estoque/entrada` com um usuário autenticado, depois `SELECT ip, dispositivo FROM estoque_movimentacoes ORDER BY id DESC LIMIT 1` e confirmar que `ip` não é NULL.

- [ ] **Step 4: Rodar a suite de regressão completa (garante que nada em `core.*` quebrou com a mudança de assinatura)**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_seguranca.py tests/test_estoque_saldos.py -v`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/routes/estoque.py
git commit -m "feat: routes/estoque.py captura ip/dispositivo do request para o ledger"
```

---

## Task 5: Migra `bling_erp.py` — sync de saldo do Bling para a API nova

**Files:**
- Modify: `hermes_agents/bling_erp.py`

**Interfaces:**
- Consumes: `core.estoque.ajustar_absoluto(sku, loja, quantidade_absoluta, motivo="ajuste_inventario", usuario_id=None, usuario_nome="", ip=None, dispositivo=None) -> dict` (Task 2).

- [ ] **Step 1: Substituir o `INSERT INTO estoque_lojas ... ON CONFLICT` (linha ~748-752) por uma chamada a `ajustar_absoluto`**

Contexto atual: a função recebe `saldo` (quantidade absoluta vinda do Bling, não um delta) e escreve direto via `INSERT ... ON CONFLICT`. `ajustar_absoluto` (Task 2) já encapsula a conversão absoluto→delta e a decisão entrada/saida — reaproveita em vez de duplicar aqui:

```python
from core.estoque import ajustar_absoluto

...
resultado = ajustar_absoluto(sku, loja_nome, float(saldo), "ajuste_inventario")
if resultado.get("erro"):
    log(AGENT, f"sync_bling: erro ao ajustar {sku}/{loja_nome} para {saldo}: {resultado['erro']}")
```

Remove o `INSERT INTO estoque_lojas` cru e a variável `sync_status` (a coluna `sync_status` em `estoque_lojas` — usada por `routes/estoque.py:status_sync_sku`/`processar_fila_sync` — fica fora do escopo desta fase; se `sync_status` precisar continuar sendo setada, manter um `UPDATE estoque_lojas SET sync_status = 'ok' WHERE sku = $1 AND loja = $2` separado, sem tocar `quantidade`).

- [ ] **Step 2: Rodar a suite de regressão**

Run: `cd hermes_agents && python -m pytest tests/ -v -k "estoque"`
Expected: todos passam (esta mudança não tem teste dedicado hoje — cobertura fica na regressão geral).

- [ ] **Step 3: Commit**

```bash
git add hermes_agents/bling_erp.py
git commit -m "refactor: bling_erp.py sync de estoque usa mover_saldo em vez de SQL direto"
```

---

## Task 6: Migra `core/entidades.py` — 3 pontos de escrita direta + remove interpolação f-string

**Files:**
- Modify: `hermes_agents/core/entidades.py`

**Interfaces:**
- Consumes: `core.estoque.entrada`, `core.estoque.saida` (Task 2).

- [ ] **Step 1: Substituir as 3 ocorrências de `INSERT INTO estoque_lojas ... f"..."` (linhas ~242, ~299, ~337, ~352 — são 4 ocorrências, não 3; conferir contagem exata no arquivo antes de editar)**

Padrão de cada uma: linha 242 é uma saída (sinal negativo, `LOJA_PRINCIPAL`), linha 299 é entrada (`LOJA_PRINCIPAL`), linha 337 é entrada (`LOJA_PRODUCAO`), linha 352 é saída (`LOJA_PRODUCAO`, consumo de componente). Substituir cada bloco:

```python
# antes (linha ~242):
await db.execute(f"INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao) VALUES ($1, '{LOJA_PRINCIPAL}', -$2, NOW()) ON CONFLICT (sku, loja) DO UPDATE SET quantidade = estoque_lojas.quantidade - $2, data_atualizacao = NOW()", sku, qtd)

# depois:
from core.estoque import saida as _estoque_saida
_estoque_saida(sku, LOJA_PRINCIPAL, qtd, "uso_interno")
```

```python
# antes (linha ~299 e ~337, entrada):
await db.execute(f"INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao) VALUES ($1, '{LOJA_PRINCIPAL}', $2, NOW()) ON CONFLICT (sku, loja) DO UPDATE SET quantidade = estoque_lojas.quantidade + $2, data_atualizacao = NOW()", sku, qtd)

# depois:
from core.estoque import entrada as _estoque_entrada
_estoque_entrada(sku, LOJA_PRINCIPAL, qtd, "producao_interna")  # ou LOJA_PRODUCAO, conforme o bloco
```

```python
# antes (linha ~352, saida de componente):
await db.execute(f"INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao) VALUES ($1, '{LOJA_PRODUCAO}', -$2, NOW()) ON CONFLICT (sku, loja) DO UPDATE SET quantidade = estoque_lojas.quantidade - $2, data_atualizacao = NOW()", csku, cqtd)

# depois:
_estoque_saida(csku, LOJA_PRODUCAO, cqtd, "uso_interno")
```

Isso elimina a interpolação f-string de `LOJA_PRINCIPAL`/`LOJA_PRODUCAO` (agora vão como parâmetro de função Python normal, não dentro do SQL) e move as 4 escritas para passar pelo ledger. Os blocos continuam dentro dos `try/except` existentes de cada seção (`resultados[...] = "erro: {e}"` etc.) — `entrada()`/`saida()` retornam dict com `"erro"` em vez de lançar exceção, então trocar o padrão de erro local: `res = _estoque_entrada(...); if res.get("erro"): resultados[...] = f"erro: {res['erro']}"`.

- [ ] **Step 2: Rodar a suite de regressão**

Run: `cd hermes_agents && python -m pytest tests/ -v -k "estoque"`
Expected: todos passam.

- [ ] **Step 3: Commit**

```bash
git add hermes_agents/core/entidades.py
git commit -m "refactor: core/entidades.py usa core.estoque entrada/saida, remove f-string em SQL"
```

---

## Task 7: Regressão final — confirma que não sobrou escrita direta em `estoque_lojas`

**Files:**
- Nenhum arquivo modificado — task de verificação.

- [ ] **Step 1: Grep de confirmação**

Run: `cd hermes_agents && grep -rn "UPDATE estoque_lojas\|INSERT INTO estoque_lojas" --include="*.py" .`

Expected: só aparecem `core/catalogo.py` (CREATE TABLE, não escreve linha), `core/estoque_saldos.py` (CREATE TABLE defensivo, não escreve linha), e o `fn_espelhar_saldo_disponivel` embutido como string SQL dentro de `core/estoque_saldos.py` (o `INSERT INTO estoque_lojas` do trigger). Nenhuma outra ocorrência fora dessas.

- [ ] **Step 2: Rodar a suite completa do projeto**

Run: `cd hermes_agents && python -m pytest tests/ -v`
Expected: todos os testes passam, sem exceção.

- [ ] **Step 3: Validação manual do trigger contra Postgres real (staging/local, fora do CI)**

Não automatizado nesta suite (o `FakeDB` não executa SQL real, só simula o efeito esperado do trigger em memória — ver nota na Task 1). Rodar manualmente contra um banco real:

```sql
-- 1. Forçar a criacao do schema chamando qualquer funcao de core.estoque (ex: via python -c "from core.estoque import entrada; entrada('SKU_TESTE','Loja Teste', 1, 'compra_fornecedor')")
-- 2. Escrever DIRETO em estoque_saldos, contornando core/estoque_saldos.py, para provar que o trigger funciona independente do caller Python:
INSERT INTO estoque_saldos (sku, loja, tipo, quantidade) VALUES ('SKU_TESTE', 'Loja Teste', 'disponivel', 42)
ON CONFLICT (sku, loja, tipo) DO UPDATE SET quantidade = 42;
-- 3. Conferir que o espelho atualizou:
SELECT quantidade FROM estoque_lojas WHERE sku = 'SKU_TESTE' AND loja = 'Loja Teste';
-- Esperado: 42
```

- [ ] **Step 4: Commit final (se o Step 1 encontrar algo, corrigir antes; senão, nada para commitar)**

Se o grep do Step 1 não encontrar nenhuma ocorrência fora do esperado, esta task não gera commit — é só o checkpoint de que a Fase 1 está completa.
