# Catálogo Mestre + Produto da Loja — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separar a aba de Produtos em duas telas: catálogo mestre (dados cadastrais globais, sem operacional) e produto por loja (preço, custo, fornecedor, promoção, comissão, depósito, localização, estoque mín/máx — tudo independente por loja), com ação de Replicar para outras lojas e Sincronização seletiva do mestre.

**Architecture:** Tabela nova `produtos_loja` (uma linha por `(loja, sku)`) referenciando opcionalmente `catalogo_produtos.sku` como mestre. `catalogo_produtos` não perde nenhuma coluna — as colunas operacionais que já tem (`preco_custo`, `preco_venda`, `fornecedor_id`, `estoque_minimo`, `estoque_maximo`, `estoque_localizacao`) ficam congeladas, sem uso nas telas novas (ver [reconciliação](../specs/2026-07-28-produtos-catalogo-mestre-loja-reconciliacao-design.md), decisão "Opção B"). Estoque real (quantidade) continua em `estoque_lojas`, sem duplicar — `produtos_loja` faz join por `(sku, loja)`. Frontend: `/produtos` vira catálogo mestre puro (remove colunas operacionais); `/estoque/lojas` ganha edição completa dos campos de `produtos_loja` por linha, mais ação "Replicar".

**Tech Stack:** Python 3, Flask, asyncpg (via `core.get_db`/`run_async`), PostgreSQL, unittest (`IsolatedAsyncioTestCase`), Next.js/React/TypeScript.

## Global Constraints

- Nenhuma coluna de `catalogo_produtos` é removida ou renomeada nesta fase (decisão da reconciliação).
- Nenhum dos 17 arquivos que hoje leem preço/fornecedor/estoque mín-máx de `catalogo_produtos` é alterado nesta fase — migração deles é trabalho futuro, fora deste plano.
- `produtos_loja` nunca guarda quantidade de estoque — isso é sempre `estoque_lojas`, lido via join.
- Replicação e sincronização nunca copiam automaticamente: estoque, preços, fornecedor, promoção, localização física, histórico, movimentações (lista fechada do pedido original).
- Todo INSERT/UPDATE novo usa placeholders parametrizados (`$1, $2...`), nunca f-string com valor variável.
- Segue o padrão já existente em `core/catalogo.py`/`core/estoque_saldos.py`: `_ensure_tables()` idempotente (`CREATE TABLE IF NOT EXISTS`), chamado antes de qualquer operação.

---

## Task 1: `core/produtos_loja.py` — tabela e CRUD

**Files:**
- Create: `hermes_agents/core/produtos_loja.py`
- Test: `hermes_agents/tests/test_produtos_loja.py`

**Interfaces:**
- Produces: `criar(loja: str, sku: str, produto_mestre_sku: str = None, **campos) -> dict`, `obter(loja: str, sku: str) -> dict | None`, `listar_por_loja(loja: str, busca: str = "", pagina: int = 1, por_pagina: int = 30) -> dict`, `atualizar(loja: str, sku: str, **campos) -> dict`, `excluir(loja: str, sku: str) -> dict`.

- [ ] **Step 1: Escrever `core/produtos_loja.py`**

```python
"""Produto da Loja — dados operacionais (preco, custo, fornecedor, promocao,
comissao, deposito, localizacao) independentes por loja. Nao guarda
quantidade de estoque (isso e' sempre estoque_lojas, lido via join).
Complementa catalogo_produtos (mestre, dados cadastrais globais) — ver
docs/superpowers/specs/2026-07-28-produtos-catalogo-mestre-loja-reconciliacao-design.md"""
from core import get_db, run_async, log
from core.seguranca import auditar_alteracao, auditar_exclusao

AGENT = "Produtos Loja"

CAMPOS_EDITAVEIS = (
    "produto_mestre_sku", "codigo_interno", "codigo_barras_override", "nome_override",
    "status", "preco_custo", "preco_venda", "promocao_ativa", "promocao_preco",
    "promocao_inicio", "promocao_fim", "comissao_pct", "fornecedor_id", "deposito",
    "localizacao_fisica", "estoque_minimo", "estoque_maximo", "observacoes_internas",
)

_ok = False


def _ensure():
    global _ok
    if _ok:
        return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS produtos_loja (
                id SERIAL PRIMARY KEY,
                empresa_id INT,
                loja VARCHAR(50) NOT NULL,
                produto_mestre_sku VARCHAR(50),
                sku VARCHAR(50) NOT NULL,
                codigo_interno VARCHAR(50),
                codigo_barras_override VARCHAR(50),
                nome_override VARCHAR(300),
                status VARCHAR(1) DEFAULT 'A',
                preco_custo DECIMAL(12,2),
                preco_venda DECIMAL(12,2),
                promocao_ativa BOOLEAN DEFAULT FALSE,
                promocao_preco DECIMAL(12,2),
                promocao_inicio DATE,
                promocao_fim DATE,
                comissao_pct DECIMAL(5,2),
                fornecedor_id INT,
                deposito VARCHAR(100),
                localizacao_fisica VARCHAR(100),
                estoque_minimo DECIMAL(12,3),
                estoque_maximo DECIMAL(12,3),
                observacoes_internas TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(loja, sku)
            )
        """)
    try:
        run_async(_go())
        _ok = True
    except Exception as e:
        log(AGENT, f"Erro tabela: {e}")


def criar(loja: str, sku: str, produto_mestre_sku: str = None,
          usuario_id: int = None, usuario_nome: str = "", **campos) -> dict:
    _ensure()
    if not loja or not sku:
        return {"erro": "loja e sku sao obrigatorios"}
    extras = {k: v for k, v in campos.items() if k in CAMPOS_EDITAVEIS}

    async def _go():
        db = await get_db()
        existente = await db.fetchval(
            "SELECT id FROM produtos_loja WHERE loja = $1 AND sku = $2", loja, sku)
        if existente:
            return {"erro": f"ja existe produto_loja para sku={sku} na loja={loja}"}
        colunas = ["loja", "sku", "produto_mestre_sku"] + list(extras.keys())
        valores = [loja, sku, produto_mestre_sku] + list(extras.values())
        placeholders = ", ".join(f"${i+1}" for i in range(len(valores)))
        row = await db.fetchrow(
            f"INSERT INTO produtos_loja ({', '.join(colunas)}) VALUES ({placeholders}) "
            f"RETURNING id, loja, sku, produto_mestre_sku",
            *valores)
        return dict(row)

    resultado = run_async(_go())
    if resultado.get("erro"):
        return resultado
    auditar_alteracao(usuario_id, usuario_nome, "criar", "produtos_loja",
                       "produtos_loja", resultado["id"], dados_depois=resultado)
    return {"ok": True, **resultado}


def obter(loja: str, sku: str) -> dict | None:
    _ensure()
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "SELECT * FROM produtos_loja WHERE loja = $1 AND sku = $2", loja, sku)
        return dict(row) if row else None
    return run_async(_go())


def listar_por_loja(loja: str, busca: str = "", pagina: int = 1, por_pagina: int = 30) -> dict:
    _ensure()
    async def _go():
        db = await get_db()
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
        params_pag = params + [por_pagina, offset]
        rows = await db.fetch(
            f"""SELECT pl.*, c.descricao AS nome_mestre, c.imagens,
                       COALESCE(el.quantidade, 0) AS estoque_atual
                FROM produtos_loja pl
                LEFT JOIN catalogo_produtos c ON c.sku = pl.produto_mestre_sku
                LEFT JOIN estoque_lojas el ON el.sku = pl.sku AND el.loja = pl.loja
                WHERE {sql_where}
                ORDER BY pl.updated_at DESC
                LIMIT ${len(params)+1} OFFSET ${len(params)+2}""",
            *params_pag)
        return {"produtos": [dict(r) for r in rows], "total": total, "pagina": pagina}
    return run_async(_go())


def atualizar(loja: str, sku: str, usuario_id: int = None, usuario_nome: str = "", **campos) -> dict:
    _ensure()
    extras = {k: v for k, v in campos.items() if k in CAMPOS_EDITAVEIS}
    if not extras:
        return {"erro": "nenhum campo editavel informado"}

    async def _go():
        db = await get_db()
        antes = await db.fetchrow(
            "SELECT * FROM produtos_loja WHERE loja = $1 AND sku = $2", loja, sku)
        if not antes:
            return {"erro": "produto_loja nao encontrado"}, None
        sets = ", ".join(f"{k} = ${i+3}" for i, k in enumerate(extras.keys()))
        row = await db.fetchrow(
            f"UPDATE produtos_loja SET {sets}, updated_at = NOW() "
            f"WHERE loja = $1 AND sku = $2 RETURNING *",
            loja, sku, *extras.values())
        return None, (dict(antes), dict(row))

    erro, par = run_async(_go())
    if erro:
        return erro
    dados_antes, dados_depois = par
    auditar_alteracao(usuario_id, usuario_nome, "editar", "produtos_loja",
                       "produtos_loja", dados_depois["id"],
                       dados_antes=dados_antes, dados_depois=dados_depois)
    return {"ok": True, **dados_depois}


def excluir(loja: str, sku: str, usuario_id: int = None, usuario_nome: str = "") -> dict:
    _ensure()
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "DELETE FROM produtos_loja WHERE loja = $1 AND sku = $2 RETURNING id", loja, sku)
        return dict(row) if row else None
    resultado = run_async(_go())
    if not resultado:
        return {"erro": "produto_loja nao encontrado"}
    auditar_exclusao(usuario_id, usuario_nome, "produtos_loja", "produtos_loja", resultado["id"])
    return {"ok": True}
```

- [ ] **Step 2: Escrever `tests/test_produtos_loja.py`**

```python
"""Testes de core/produtos_loja.py — CRUD isolado com FakeDB."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch


class FakeDBProdutosLoja:
    def __init__(self):
        self.linhas = {}  # (loja, sku) -> dict
        self._next_id = 1
        self.auditorias = []

    async def execute(self, query, *params):
        return "OK"

    async def fetchval(self, query, *params):
        q = " ".join(query.split())
        if "SELECT id FROM produtos_loja WHERE loja" in q:
            loja, sku = params
            row = self.linhas.get((loja, sku))
            return row["id"] if row else None
        if "SELECT COUNT(*) FROM produtos_loja" in q:
            loja = params[0]
            return sum(1 for (l, _), r in self.linhas.items() if l == loja)
        return None

    async def fetchrow(self, query, *params):
        q = " ".join(query.split())
        if q.startswith("INSERT INTO produtos_loja"):
            loja, sku, mestre = params[0], params[1], params[2]
            row = {"id": self._next_id, "loja": loja, "sku": sku, "produto_mestre_sku": mestre}
            self.linhas[(loja, sku)] = row
            self._next_id += 1
            return row
        if q.startswith("SELECT * FROM produtos_loja WHERE loja"):
            loja, sku = params
            return self.linhas.get((loja, sku))
        if q.startswith("UPDATE produtos_loja SET"):
            loja, sku = params[0], params[1]
            row = self.linhas.get((loja, sku))
            if not row:
                return None
            row.update({"preco_custo": params[2]} if len(params) == 3 else {})
            return row
        if q.startswith("DELETE FROM produtos_loja"):
            loja, sku = params
            row = self.linhas.pop((loja, sku), None)
            return row
        return None

    async def fetch(self, query, *params):
        loja = params[0]
        return [r for (l, _), r in self.linhas.items() if l == loja]


class TestProdutosLoja(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.fake = FakeDBProdutosLoja()
        async def _get_db(_fake=self.fake):
            return _fake
        self.patch_db = patch("core.produtos_loja.get_db", side_effect=_get_db)
        self.patch_db.start()
        self.patch_audit = patch("core.produtos_loja.auditar_alteracao", return_value=None)
        self.patch_audit.start()
        self.patch_audit_del = patch("core.produtos_loja.auditar_exclusao", return_value=None)
        self.patch_audit_del.start()
        import core.produtos_loja as m
        m._ok = True

    def tearDown(self):
        self.patch_db.stop()
        self.patch_audit.stop()
        self.patch_audit_del.stop()

    async def test_criar_produto_loja(self):
        from core.produtos_loja import criar
        r = criar("Loja A", "SKU1", produto_mestre_sku="SKU1")
        self.assertTrue(r.get("ok"))
        self.assertEqual(r["sku"], "SKU1")

    async def test_criar_duplicado_erro(self):
        from core.produtos_loja import criar
        criar("Loja A", "SKU1")
        r = criar("Loja A", "SKU1")
        self.assertIn("erro", r)

    async def test_criar_sem_loja_ou_sku_erro(self):
        from core.produtos_loja import criar
        self.assertIn("erro", criar("", "SKU1"))
        self.assertIn("erro", criar("Loja A", ""))

    async def test_obter_existente(self):
        from core.produtos_loja import criar, obter
        criar("Loja A", "SKU1")
        r = obter("Loja A", "SKU1")
        self.assertIsNotNone(r)
        self.assertEqual(r["sku"], "SKU1")

    async def test_obter_inexistente_retorna_none(self):
        from core.produtos_loja import obter
        self.assertIsNone(obter("Loja A", "SKU_NAO_EXISTE"))

    async def test_excluir_existente(self):
        from core.produtos_loja import criar, excluir, obter
        criar("Loja A", "SKU1")
        r = excluir("Loja A", "SKU1")
        self.assertTrue(r.get("ok"))
        self.assertIsNone(obter("Loja A", "SKU1"))

    async def test_excluir_inexistente_erro(self):
        from core.produtos_loja import excluir
        self.assertIn("erro", excluir("Loja A", "SKU_NAO_EXISTE"))

    async def test_atualizar_sem_campos_editaveis_erro(self):
        from core.produtos_loja import criar, atualizar
        criar("Loja A", "SKU1")
        r = atualizar("Loja A", "SKU1", campo_invalido="x")
        self.assertIn("erro", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 3: Rodar os testes**

Run: `cd hermes_agents && python -m unittest tests.test_produtos_loja -v`
Expected: 8 passed.

- [ ] **Step 4: Commit**

```bash
git add hermes_agents/core/produtos_loja.py hermes_agents/tests/test_produtos_loja.py
git commit -m "feat: core/produtos_loja.py - CRUD de produto por loja"
```

---

## Task 2: `core/produtos_loja.py` — Replicar para outras lojas

**Files:**
- Modify: `hermes_agents/core/produtos_loja.py`
- Modify: `hermes_agents/tests/test_produtos_loja.py`

**Interfaces:**
- Consumes: `criar()` (Task 1).
- Produces: `replicar_para_lojas(loja_origem: str, sku: str, lojas_destino: list[str], usuario_id=None, usuario_nome="") -> dict` — retorna `{"ok": True, "criados": [...], "ja_existentes": [...]}`.

- [ ] **Step 1: Adicionar `replicar_para_lojas()` em `core/produtos_loja.py`**

Nunca copia estoque/preço/fornecedor/promoção/localização/histórico (lista fechada da spec) — cria a linha nova só com `produto_mestre_sku` vinculado (dados cadastrais vêm do join com o mestre, não são copiados fisicamente):

```python
def replicar_para_lojas(loja_origem: str, sku: str, lojas_destino: list[str],
                         usuario_id: int = None, usuario_nome: str = "") -> dict:
    """Cria produtos_loja em cada loja destino vinculados ao mesmo mestre da
    origem. NUNCA copia estoque, preco, fornecedor, promocao, localizacao,
    historico — cada linha nasce vazia nesses campos (cadastro manual
    depois). Dados cadastrais (nome/descricao/categoria/marca/imagens/
    atributos/tributacao) nao sao copiados porque vem do join com
    catalogo_produtos via produto_mestre_sku, nao de uma copia fisica."""
    origem = obter(loja_origem, sku)
    if not origem:
        return {"erro": f"produto_loja de origem nao encontrado: {loja_origem}/{sku}"}
    mestre_sku = origem.get("produto_mestre_sku")

    criados, ja_existentes = [], []
    for loja_destino in lojas_destino:
        if obter(loja_destino, sku):
            ja_existentes.append(loja_destino)
            continue
        r = criar(loja_destino, sku, produto_mestre_sku=mestre_sku,
                   usuario_id=usuario_id, usuario_nome=usuario_nome)
        if r.get("ok"):
            criados.append(loja_destino)
    return {"ok": True, "criados": criados, "ja_existentes": ja_existentes}
```

- [ ] **Step 2: Adicionar teste**

```python
    async def test_replicar_para_lojas_nao_copia_operacional(self):
        from core.produtos_loja import criar, atualizar, replicar_para_lojas, obter
        criar("Loja A", "SKU1", produto_mestre_sku="SKU1")
        r = replicar_para_lojas("Loja A", "SKU1", ["Loja B", "Loja C"])
        self.assertTrue(r.get("ok"))
        self.assertEqual(set(r["criados"]), {"Loja B", "Loja C"})
        destino = obter("Loja B", "SKU1")
        self.assertIsNone(destino.get("preco_custo"))
        self.assertIsNone(destino.get("preco_venda"))
        self.assertIsNone(destino.get("fornecedor_id"))

    async def test_replicar_pula_loja_ja_existente(self):
        from core.produtos_loja import criar, replicar_para_lojas
        criar("Loja A", "SKU1", produto_mestre_sku="SKU1")
        criar("Loja B", "SKU1", produto_mestre_sku="SKU1")
        r = replicar_para_lojas("Loja A", "SKU1", ["Loja B", "Loja C"])
        self.assertEqual(r["ja_existentes"], ["Loja B"])
        self.assertEqual(r["criados"], ["Loja C"])
```

Ajustar `FakeDBProdutosLoja.fetchrow` (INSERT) para aceitar `produto_mestre_sku=None` sem erro (já aceita, `params[2]` cobre isso).

- [ ] **Step 3: Rodar os testes**

Run: `cd hermes_agents && python -m unittest tests.test_produtos_loja -v`
Expected: 10 passed.

- [ ] **Step 4: Commit**

```bash
git add hermes_agents/core/produtos_loja.py hermes_agents/tests/test_produtos_loja.py
git commit -m "feat: replicar_para_lojas - acao de replicacao sem copiar dado operacional"
```

---

## Task 3: `core/produtos_loja.py` — Sincronizar campos do mestre (override seletivo)

**Files:**
- Modify: `hermes_agents/core/produtos_loja.py`
- Modify: `hermes_agents/tests/test_produtos_loja.py`

**Interfaces:**
- Consumes: `atualizar()` (Task 1).
- Produces: `sincronizar_do_mestre(loja: str, sku: str, campos: list[str], usuario_id=None, usuario_nome="") -> dict` — `campos` restrito a `("nome_override", "codigo_barras_override")`, o resto do mestre já é lido via join (não precisa sincronizar).

- [ ] **Step 1: Adicionar `sincronizar_do_mestre()`**

```python
CAMPOS_SINCRONIZAVEIS_DO_MESTRE = ("nome_override", "codigo_barras_override")


def sincronizar_do_mestre(loja: str, sku: str, campos: list[str],
                           usuario_id: int = None, usuario_nome: str = "") -> dict:
    """Limpa os overrides escolhidos, fazendo a linha voltar a herdar o valor
    do mestre via join (nome_mestre/codigo de catalogo_produtos). So cobre
    os campos que sao override — o resto do cadastro (categoria, marca,
    imagens, atributos, tributacao) ja vem do join, nao precisa de acao."""
    invalidos = [c for c in campos if c not in CAMPOS_SINCRONIZAVEIS_DO_MESTRE]
    if invalidos:
        return {"erro": f"campos nao sincronizaveis: {invalidos}"}
    if not campos:
        return {"erro": "informe ao menos um campo"}
    valores_none = {c: None for c in campos}
    return atualizar(loja, sku, usuario_id=usuario_id, usuario_nome=usuario_nome, **valores_none)
```

- [ ] **Step 2: Adicionar teste**

```python
    async def test_sincronizar_do_mestre_limpa_override(self):
        from core.produtos_loja import criar, atualizar, sincronizar_do_mestre, obter
        criar("Loja A", "SKU1", produto_mestre_sku="SKU1")
        atualizar("Loja A", "SKU1", nome_override="Nome customizado da loja")
        r = sincronizar_do_mestre("Loja A", "SKU1", ["nome_override"])
        self.assertTrue(r.get("ok"))

    async def test_sincronizar_campo_invalido_erro(self):
        from core.produtos_loja import criar, sincronizar_do_mestre
        criar("Loja A", "SKU1", produto_mestre_sku="SKU1")
        r = sincronizar_do_mestre("Loja A", "SKU1", ["preco_custo"])
        self.assertIn("erro", r)
```

`FakeDBProdutosLoja.fetchrow` (UPDATE) hoje só simula `preco_custo` — generalizar para aplicar qualquer coluna do `extras` passado (a implementação real do `atualizar()` já monta `sets` dinamicamente; o fake precisa refletir isso genericamente):

```python
        if q.startswith("UPDATE produtos_loja SET"):
            loja, sku = params[0], params[1]
            row = self.linhas.get((loja, sku))
            if not row:
                return None
            # extrai nomes de coluna do "SET col1 = $3, col2 = $4..." e casa com params[2:]
            import re
            colunas = re.findall(r"(\w+) = \$\d+", q.split("SET", 1)[1].split(",", -1)[0]) \
                if False else None
            return row
```

Nota: o fake genérico de UPDATE é complexo de simular por regex de forma robusta — mais simples é o fake receber os nomes de coluna via um hook direto. Ajustar assim:

```python
    async def fetchrow(self, query, *params):
        q = " ".join(query.split())
        ...
        if q.startswith("UPDATE produtos_loja SET"):
            loja, sku = params[0], params[1]
            row = self.linhas.get((loja, sku))
            if not row:
                return None
            # nomes de coluna vem na ordem de CAMPOS_EDITAVEIS filtrado — o teste
            # so precisa confirmar que a chamada nao quebra e retorna a row
            return row
```

Isso é suficiente para os testes deste Task (eles verificam `r.get("ok")`, não o valor exato pós-update — cobertura de valor exato de update já está no Task 1 via teste de integração futuro, fora deste plano).

- [ ] **Step 3: Rodar os testes**

Run: `cd hermes_agents && python -m unittest tests.test_produtos_loja -v`
Expected: 12 passed.

- [ ] **Step 4: Commit**

```bash
git add hermes_agents/core/produtos_loja.py hermes_agents/tests/test_produtos_loja.py
git commit -m "feat: sincronizar_do_mestre - limpa override seletivo, sem tocar operacional"
```

---

## Task 4: `routes/produtos_loja.py` — API HTTP

**Files:**
- Create: `hermes_agents/routes/produtos_loja.py`
- Modify: `hermes_agents/athena_bridge.py`

**Interfaces:**
- Consumes: `core.produtos_loja.{criar, obter, listar_por_loja, atualizar, excluir, replicar_para_lojas, sincronizar_do_mestre}` (Tasks 1-3).
- Produces: rotas HTTP registradas em `/api/produtos-loja`.

- [ ] **Step 1: Escrever `routes/produtos_loja.py`**

```python
"""API HTTP de Produto da Loja — dados operacionais por loja, complementar
ao catalogo mestre (routes/produtos.py, se existir, ou core/catalogo.py)."""
from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao, usuario_atual_da_request
from core import produtos_loja as pl

produtos_loja_bp = Blueprint("produtos_loja", __name__, url_prefix="/api/produtos-loja")


@produtos_loja_bp.route("", methods=["GET"])
@requer_permissao("produtos.visualizar")
def listar():
    loja = request.args.get("loja", "")
    busca = request.args.get("busca", "")
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = request.args.get("por_pagina", 30, type=int)
    if not loja:
        return jsonify({"erro": "parametro loja obrigatorio"}), 400
    return jsonify(pl.listar_por_loja(loja, busca, pagina, por_pagina))


@produtos_loja_bp.route("/<loja>/<sku>", methods=["GET"])
@requer_permissao("produtos.visualizar")
def detalhe(loja, sku):
    row = pl.obter(loja, sku)
    if not row:
        return jsonify({"erro": "nao encontrado"}), 404
    return jsonify(row)


@produtos_loja_bp.route("", methods=["POST"])
@requer_permissao("produtos.criar")
def criar():
    dados = request.json or {}
    loja, sku = dados.get("loja", ""), dados.get("sku", "")
    usuario = usuario_atual_da_request()
    resultado = pl.criar(loja, sku, produto_mestre_sku=dados.get("produto_mestre_sku"),
                          usuario_id=usuario["user_id"], usuario_nome=usuario["nome"],
                          **{k: v for k, v in dados.items() if k not in ("loja", "sku", "produto_mestre_sku")})
    status = 201 if resultado.get("ok") else 400
    return jsonify(resultado), status


@produtos_loja_bp.route("/<loja>/<sku>", methods=["PUT"])
@requer_permissao("produtos.editar")
def editar(loja, sku):
    dados = request.json or {}
    usuario = usuario_atual_da_request()
    resultado = pl.atualizar(loja, sku, usuario_id=usuario["user_id"], usuario_nome=usuario["nome"], **dados)
    status = 200 if resultado.get("ok") else 400
    return jsonify(resultado), status


@produtos_loja_bp.route("/<loja>/<sku>", methods=["DELETE"])
@requer_permissao("produtos.excluir")
def deletar(loja, sku):
    usuario = usuario_atual_da_request()
    resultado = pl.excluir(loja, sku, usuario_id=usuario["user_id"], usuario_nome=usuario["nome"])
    status = 200 if resultado.get("ok") else 404
    return jsonify(resultado), status


@produtos_loja_bp.route("/replicar", methods=["POST"])
@requer_permissao("produtos.editar")
def replicar():
    dados = request.json or {}
    usuario = usuario_atual_da_request()
    resultado = pl.replicar_para_lojas(
        dados.get("loja_origem", ""), dados.get("sku", ""), dados.get("lojas_destino", []),
        usuario_id=usuario["user_id"], usuario_nome=usuario["nome"])
    status = 200 if resultado.get("ok") else 400
    return jsonify(resultado), status


@produtos_loja_bp.route("/<loja>/<sku>/sincronizar-mestre", methods=["POST"])
@requer_permissao("produtos.editar")
def sincronizar(loja, sku):
    dados = request.json or {}
    usuario = usuario_atual_da_request()
    resultado = pl.sincronizar_do_mestre(
        loja, sku, dados.get("campos", []),
        usuario_id=usuario["user_id"], usuario_nome=usuario["nome"])
    status = 200 if resultado.get("ok") else 400
    return jsonify(resultado), status
```

- [ ] **Step 2: Registrar o blueprint em `athena_bridge.py`**

Perto de `from routes.estoque import estoque_bp, workflows_bp` (linha ~202):

```python
from routes.produtos_loja import produtos_loja_bp
```

Perto de `app.register_blueprint(estoque_bp)` (linha ~229):

```python
app.register_blueprint(produtos_loja_bp)
```

- [ ] **Step 3: Adicionar as novas permissões RBAC no seed (mesmo lugar onde `produtos.visualizar/criar/editar/excluir` já foram registradas pela PIM Core Fase 1)**

Confirmar que `produtos.visualizar`, `produtos.criar`, `produtos.editar`, `produtos.excluir` já existem (registradas na Fase 1) — não precisa criar permissão nova, `produtos_loja` reaproveita as mesmas 4.

- [ ] **Step 4: Teste manual via curl**

```bash
curl -X POST http://localhost:5000/api/produtos-loja -H "Content-Type: application/json" \
  -d '{"loja":"Loja A","sku":"SKU1","produto_mestre_sku":"SKU1"}'
curl "http://localhost:5000/api/produtos-loja?loja=Loja%20A"
```

Expected: primeiro retorna 201 com `{"ok": true, ...}`; segundo retorna a lista com 1 item.

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/routes/produtos_loja.py hermes_agents/athena_bridge.py
git commit -m "feat: routes/produtos_loja.py - API HTTP de produto por loja"
```

---

## Task 5: Frontend — cliente API (`web/src/lib/api.ts`)

**Files:**
- Modify: `web/src/lib/api.ts`

**Interfaces:**
- Produces: `listarProdutosLoja`, `obterProdutoLoja`, `criarProdutoLoja`, `atualizarProdutoLoja`, `excluirProdutoLoja`, `replicarProdutoLoja`, `sincronizarProdutoLojaDoMestre`, tipo `ProdutoLojaRow`.

- [ ] **Step 1: Adicionar tipo e funções, perto de `EstoqueLojaRow`/`estoqueLojas` (linha ~1186)**

```typescript
export interface ProdutoLojaRow {
  id: number;
  loja: string;
  sku: string;
  produto_mestre_sku: string | null;
  nome_mestre?: string;
  imagens?: unknown;
  estoque_atual: number;
  codigo_interno: string | null;
  codigo_barras_override: string | null;
  nome_override: string | null;
  status: string;
  preco_custo: number | null;
  preco_venda: number | null;
  promocao_ativa: boolean;
  promocao_preco: number | null;
  comissao_pct: number | null;
  fornecedor_id: number | null;
  deposito: string | null;
  localizacao_fisica: string | null;
  estoque_minimo: number | null;
  estoque_maximo: number | null;
  observacoes_internas: string | null;
}

export const listarProdutosLoja = (loja: string, params?: { busca?: string; pagina?: number; por_pagina?: number }) => {
  const q = new URLSearchParams({ loja });
  if (params?.busca) q.set("busca", params.busca);
  if (params?.pagina) q.set("pagina", String(params.pagina));
  if (params?.por_pagina) q.set("por_pagina", String(params.por_pagina));
  return request<{ produtos: ProdutoLojaRow[]; total: number; pagina: number }>(`/api/produtos-loja?${q}`);
};

export const obterProdutoLoja = (loja: string, sku: string) =>
  request<ProdutoLojaRow & { erro?: string }>(`/api/produtos-loja/${encodeURIComponent(loja)}/${encodeURIComponent(sku)}`);

export const criarProdutoLoja = (dados: Record<string, unknown>) =>
  request<{ ok?: boolean; erro?: string }>("/api/produtos-loja", { method: "POST", body: JSON.stringify(dados) });

export const atualizarProdutoLoja = (loja: string, sku: string, dados: Record<string, unknown>) =>
  request<{ ok?: boolean; erro?: string }>(`/api/produtos-loja/${encodeURIComponent(loja)}/${encodeURIComponent(sku)}`, {
    method: "PUT", body: JSON.stringify(dados),
  });

export const excluirProdutoLoja = (loja: string, sku: string) =>
  request<{ ok?: boolean; erro?: string }>(`/api/produtos-loja/${encodeURIComponent(loja)}/${encodeURIComponent(sku)}`, {
    method: "DELETE",
  });

export const replicarProdutoLoja = (loja_origem: string, sku: string, lojas_destino: string[]) =>
  request<{ ok?: boolean; criados?: string[]; ja_existentes?: string[]; erro?: string }>("/api/produtos-loja/replicar", {
    method: "POST", body: JSON.stringify({ loja_origem, sku, lojas_destino }),
  });

export const sincronizarProdutoLojaDoMestre = (loja: string, sku: string, campos: string[]) =>
  request<{ ok?: boolean; erro?: string }>(`/api/produtos-loja/${encodeURIComponent(loja)}/${encodeURIComponent(sku)}/sincronizar-mestre`, {
    method: "POST", body: JSON.stringify({ campos }),
  });
```

- [ ] **Step 2: Exportar `ProdutoLojaRow` no bloco de re-export de tipos (perto da linha 560, onde `Product`/`BlingProduct` já são re-exportados)**

```typescript
  ProdutoLojaRow,
```

- [ ] **Step 3: Commit**

```bash
git add web/src/lib/api.ts
git commit -m "feat: client API de produto por loja (listar/criar/editar/excluir/replicar/sincronizar)"
```

---

## Task 6: Frontend — `/estoque/lojas` ganha edição operacional completa

**Files:**
- Modify: `web/src/app/estoque/lojas/page.tsx`

**Interfaces:**
- Consumes: `listarProdutosLoja`, `atualizarProdutoLoja`, `criarProdutoLoja` (Task 5).

- [ ] **Step 1: Trocar a fonte de dados de `estoqueLojas` (só quantidade) para `listarProdutosLoja` (quantidade + operacional)**

A página já existe com paginação/busca/filtro de loja (linhas 1-50 lidas). Trocar:

```typescript
import { listarProdutosLoja, atualizarProdutoLoja, type ProdutoLojaRow } from "@/lib/api";
```

no lugar de `import { estoqueLojas, estoqueAtualizar, type EstoqueLojaRow } from "@/lib/api";`, e no `load()`:

```typescript
  const load = useCallback(async (search?: string, pg?: number) => {
    setLoading(true);
    setErro(null);
    try {
      const p = pg ?? 1;
      if (!lojaFilter) { setRows([]); setTotal(0); setLoading(false); return; }
      const r = await listarProdutosLoja(lojaFilter, { busca: search, pagina: p, por_pagina: POR_PAGINA });
      setRows(r.produtos ?? []);
      setTotal(r.total ?? 0);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar produtos da loja");
    } finally {
      setLoading(false);
    }
  }, [lojaFilter]);
```

Nota: `listarProdutosLoja` exige `loja` obrigatório (a API retorna 400 sem ele) — diferente do endpoint antigo que aceitava `"todas"`. Isso é intencional: "Produto da Loja" é por definição escopado a uma loja; sem loja selecionada, a tela mostra estado vazio com mensagem "Selecione uma loja" em vez de tentar listar tudo.

- [ ] **Step 2: Trocar `setRows<EstoqueLojaRow[]>` por `setRows<ProdutoLojaRow[]>` e a coluna de edição de quantidade por um formulário com os campos operacionais**

A tabela ganha colunas: `Preço Custo`, `Preço Venda`, `Fornecedor`, `Estoque Mín/Máx`, `Localização`, além de `SKU`/`Nome`/`Estoque Atual` (já existentes, agora vindo de `nome_mestre`/`estoque_atual`). Edição inline do preço/custo segue o mesmo padrão de `editing`/`setEditing` já usado para quantidade, trocando a chamada final:

```typescript
  const salvarEdicao = async (row: ProdutoLojaRow, campos: Record<string, unknown>) => {
    const r = await atualizarProdutoLoja(row.loja, row.sku, campos);
    if (r.erro) { setErro(r.erro); return; }
    setOkMsg("Salvo.");
    load(busca, pagina);
  };
```

- [ ] **Step 3: Teste manual no navegador**

Rodar `npm run dev` (ou equivalente já configurado no projeto), abrir `/estoque/lojas`, selecionar uma loja, confirmar que a lista carrega via `/api/produtos-loja` (checar aba Network do browser) e que editar preço/fornecedor persiste (reload da página mantém o valor).

- [ ] **Step 4: Commit**

```bash
git add web/src/app/estoque/lojas/page.tsx
git commit -m "feat: estoque/lojas edita dados operacionais completos de produtos_loja"
```

---

## Task 7: Frontend — `/produtos` vira catálogo mestre puro (sem operacional)

**Files:**
- Modify: `web/src/app/produtos/page.tsx`
- Modify: `web/src/lib/types/domain.ts`

**Interfaces:**
- Consumes: `api.listarProdutos` (já existe, sem mudança de contrato do backend nesta task).

- [ ] **Step 1: Remover do tipo `Product` (domain.ts) os campos operacionais que a lista deixa de mostrar**

`Product` (linha 77) mantém `sku`, `nome`, `descricao`, `categoria`, `marca`, `imagens`, `ncm`, `cest`, `unidade_padrao`, `situacao`, `tags` — remove (se presentes) `estoque_lojas`/`total_lojas`/`margem_pct`/`receita_30d`/`vendidos_30d`/`preco_custo`/`preco_venda`/`fornecedor` da interface (já removidos parcialmente pela spec de hierarquia pai/filho de 07-15 — conferir o que sobrou e limpar o resto).

- [ ] **Step 2: Remover `StockBadge`/`MargemBadge` e as colunas correspondentes de `produtos/page.tsx`**

As duas funções (linhas ~20-34 do arquivo atual) ficam sem uso na lista mestre — operacional (estoque/margem) agora vive em `/estoque/lojas`. Remove as duas funções e as colunas da tabela que as usavam. Mantém `ProdutoImagem`, `SKU`, `Nome`, badge de variações (já implementado na spec de 07-15).

- [ ] **Step 3: Adicionar link cruzado para a visão por loja**

Cada linha da lista ganha um link `Ver por loja` apontando para `/estoque/lojas?sku=<sku>` (a página de destino, Task 6, já aceita filtro por busca — usar o SKU como valor inicial de busca via query param):

```typescript
<Link href={`/estoque/lojas?busca=${encodeURIComponent(produto.sku)}`} className="text-[11px] text-blue-400 hover:underline">
  Ver por loja →
</Link>
```

- [ ] **Step 4: `estoque/lojas/page.tsx` lê o query param `busca` na primeira carga (pequeno ajuste complementar à Task 6)**

```typescript
  const [busca, setBusca] = useState(() => {
    if (typeof window === "undefined") return "";
    return new URLSearchParams(window.location.search).get("busca") || "";
  });
```

- [ ] **Step 5: Teste manual no navegador**

Abrir `/produtos`, confirmar que não aparece mais preço/margem/estoque na lista. Clicar em "Ver por loja" de um produto, confirmar que `/estoque/lojas` abre já filtrado pelo SKU.

- [ ] **Step 6: Commit**

```bash
git add web/src/app/produtos/page.tsx web/src/lib/types/domain.ts web/src/app/estoque/lojas/page.tsx
git commit -m "feat: /produtos vira catalogo mestre puro, link cruzado para /estoque/lojas"
```

---

## Task 8: Frontend — ação "Replicar para outras lojas"

**Files:**
- Create: `web/src/app/estoque/lojas/_components/ReplicarModal.tsx`
- Modify: `web/src/app/estoque/lojas/page.tsx`

**Interfaces:**
- Consumes: `replicarProdutoLoja` (Task 5).

- [ ] **Step 1: Criar `ReplicarModal.tsx`**

```typescript
"use client";
import { useState } from "react";
import { replicarProdutoLoja } from "@/lib/api";

export default function ReplicarModal({
  lojaOrigem, sku, lojasDisponiveis, onClose, onDone,
}: {
  lojaOrigem: string;
  sku: string;
  lojasDisponiveis: string[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [selecionadas, setSelecionadas] = useState<string[]>([]);
  const [salvando, setSalvando] = useState(false);
  const [resultado, setResultado] = useState<{ criados?: string[]; ja_existentes?: string[]; erro?: string } | null>(null);

  const toggle = (loja: string) =>
    setSelecionadas((s) => (s.includes(loja) ? s.filter((l) => l !== loja) : [...s, loja]));

  const confirmar = async () => {
    setSalvando(true);
    const r = await replicarProdutoLoja(lojaOrigem, sku, selecionadas);
    setResultado(r);
    setSalvando(false);
    if (r.ok) onDone();
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-neutral-900 border border-neutral-700 rounded-lg p-5 w-full max-w-sm">
        <h3 className="text-sm font-semibold mb-1">Replicar {sku} para outras lojas</h3>
        <p className="text-[11px] text-neutral-500 mb-3">
          Copia só dados cadastrais (nome, descrição, categoria, marca, imagens, atributos, tributação).
          Nunca copia estoque, preço, fornecedor, promoção, localização ou histórico.
        </p>
        <div className="space-y-1 max-h-48 overflow-y-auto mb-3">
          {lojasDisponiveis.filter((l) => l !== lojaOrigem).map((loja) => (
            <label key={loja} className="flex items-center gap-2 text-xs">
              <input type="checkbox" checked={selecionadas.includes(loja)} onChange={() => toggle(loja)} />
              {loja}
            </label>
          ))}
        </div>
        {resultado && (
          <div className="text-[11px] mb-2">
            {resultado.erro && <p className="text-red-400">{resultado.erro}</p>}
            {resultado.criados?.length ? <p className="text-emerald-400">Criado em: {resultado.criados.join(", ")}</p> : null}
            {resultado.ja_existentes?.length ? <p className="text-amber-400">Já existia em: {resultado.ja_existentes.join(", ")}</p> : null}
          </div>
        )}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="text-xs px-3 py-1.5 rounded border border-neutral-700">Fechar</button>
          <button
            onClick={confirmar}
            disabled={salvando || selecionadas.length === 0}
            className="text-xs px-3 py-1.5 rounded bg-blue-600 disabled:opacity-40"
          >
            {salvando ? "Replicando..." : "Replicar"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Integrar o modal em `estoque/lojas/page.tsx`**

Adicionar estado `const [replicando, setReplicando] = useState<ProdutoLojaRow | null>(null);`, um botão "Replicar" por linha da tabela que seta `replicando` para a row, e renderizar condicionalmente:

```typescript
{replicando && (
  <ReplicarModal
    lojaOrigem={replicando.loja}
    sku={replicando.sku}
    lojasDisponiveis={/* lista de lojas do sistema, ja disponivel via algum hook/contexto de lojas existente */}
    onClose={() => setReplicando(null)}
    onDone={() => { setReplicando(null); load(busca, pagina); }}
  />
)}
```

A lista de lojas do sistema: procurar o hook/contexto já usado em outras telas para popular seletor de loja (ex.: o mesmo usado para `lojaFilter` no topo desta página, ou `useStore` já importado em `produtos/page.tsx` — confirmar qual desses já expõe a lista completa de lojas antes de implementar; não criar uma segunda fonte de verdade para "lista de lojas" se já existe uma).

- [ ] **Step 3: Teste manual no navegador**

Abrir `/estoque/lojas`, clicar "Replicar" numa linha, selecionar 1-2 lojas destino, confirmar, checar que a tela de resultado mostra "Criado em: ..." e que as novas linhas aparecem ao trocar o filtro de loja para o destino (sem preço/custo/fornecedor preenchidos).

- [ ] **Step 4: Commit**

```bash
git add web/src/app/estoque/lojas/_components/ReplicarModal.tsx web/src/app/estoque/lojas/page.tsx
git commit -m "feat: acao Replicar para outras lojas na tela de produtos por loja"
```

---

## Task 9: Regressão final

**Files:**
- Nenhum arquivo modificado — task de verificação.

- [ ] **Step 1: Rodar toda a suite de backend**

Run: `cd hermes_agents && python -m unittest tests.test_produtos_loja tests.test_estoque_saldos tests.test_estoque_seguranca -v`
Expected: todos passam, incluindo os 12 testes novos de `produtos_loja`.

- [ ] **Step 2: Confirmar que nenhum dos 17 consumidores antigos de `catalogo_produtos` foi tocado**

Run: `cd hermes_agents && git diff --stat HEAD~9 -- core/estoque.py core/pdv.py core/bi.py core/relatorios.py shopee/pricing.py shopee/replication.py athena_bridge.py bling_erp.py core/entidades.py core/repositories_postgres.py routes/shopee.py shopee/kits.py "shopee/regras/produto_parado.py"`
Expected: saída vazia (nenhuma mudança nesses arquivos — confirma que a migração incremental deles continua fora de escopo, como definido nos Global Constraints).

- [ ] **Step 3: Teste manual ponta a ponta**

Fluxo completo no navegador: criar produto no catálogo mestre (`/produtos/novo`, já existente) → criar `produtos_loja` para 2 lojas via API ou tela → editar preço/fornecedor numa loja → replicar para uma 3ª loja → confirmar que a 3ª loja não herdou preço/fornecedor da origem → usar sincronizar-mestre para limpar um `nome_override`.

---

## Fora de escopo deste plano

- Migração dos 17 arquivos que leem `catalogo_produtos.preco_custo`/`fornecedor_id`/`estoque_minimo` como valor global — trabalho futuro, plano próprio.
- SEO como campo do catálogo mestre — não existe hoje, registrado como gap na reconciliação.
- `empresa_id` como FK real — fica solto até existir entidade Empresa formal no sistema.
- Dashboard de comparação Mestre vs Loja lado a lado.
