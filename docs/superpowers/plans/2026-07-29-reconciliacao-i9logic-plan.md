# Reconciliação Físico x Contábil — Ponte i9Logic → Athena — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir a ponte de migração/coexistência com o sistema legado i9Logic: coletar os saldos físico e contábil por produto/filial via API, usar o físico como semente confiável pro saldo Athena (Fase 1), e manter monitoramento contínuo de divergência entre os dois sistemas enquanto ambos operam em paralelo — sem nunca ajustar saldo automaticamente.

**Architecture:** Módulo novo `hermes_agents/core/i9logic.py` concentra toda a lógica (de-para de identidade, client HTTP paginado com rate limit, staging table de snapshot, classificação de divergência, job de coleta, seed inicial), seguindo o padrão já usado no projeto de "um arquivo por integração externa" (`bling_erp.py`). Rotas REST em `hermes_agents/routes/i9logic.py`, expondo o job de coleta como endpoint (`POST /coletar`) disparado externamente (n8n), não integrado ao `core/scheduler.py` — esse scheduler roda um único thread compartilhado com jobs rápidos (5min-1h); o job de coleta do i9Logic dorme ~2,5s entre cada chamada pra respeitar rate limit (30 req/min), levando minutos por filial, o que bloquearia todos os outros jobs se dividisse o mesmo thread.

**Tech Stack:** Python 3.13 / Flask / asyncpg / `requests` (client HTTP síncrono, mesmo padrão de `bling_erp.py`), seguindo convenções já estabelecidas em `core/estoque.py`/`core/estoque_saldos.py`/`core/config.py`.

## Global Constraints

- Spec de referência: `docs/superpowers/specs/2026-07-28-reconciliacao-fisico-contabil-i9logic-design.md`.
- **Físico (`tipoestoque=1`) semeia `estoque_saldos`. Contábil (`tipoestoque=2`) nunca vira bucket** — só existe como sinal de auditoria (divergência). Nenhum `tipo` novo em `TIPOS_SALDO` (`core/estoque_saldos.py`).
- **Nenhum ajuste automático de saldo.** Toda decisão sobre divergência é manual, e quando aplicada passa pelo ledger formal (`core.estoque.entrada()`/`ajustar_absoluto()`), nunca UPDATE direto em `estoque_saldos`/`estoque_lojas`.
- **Matching de-para é só igualdade textual exata** (`codproduto` i9Logic == `sku` Athena; nome de filial i9Logic == nome de loja Athena). Sem matching fuzzy. Não-casados viram relatório pra revisão humana.
- **Rate limit da API i9Logic: 30 req/min por credencial (fixo).** A rotina de paginação usa sleep de 2,5s entre chamadas (24 req/min, margem de segurança) — nunca ultrapassar isso, mesmo em filial com muitas páginas.
- **Limiar de alerta de divergência:** `abs(divergencia) <= 0.5` → sem ação; `abs(divergencia) >= 5` OU `abs(divergencia)/max(qtd_fisico,1) >= 0.10` → alerta; caso contrário → só registrado (sem alerta ativo).
- **Assunção sobre o formato da resposta JSON da API i9Logic** (não especificado no spec com payload exato): cada página retorna `{"data": [{"idproduto": int, "codproduto": str, "qtd": float}, ...], "total": int}`. Se o formato real divergir ao integrar de verdade, ajustar `_paginar_estoques` (Task 3) — os testes usam mock, então a suíte não trava por isso, mas o comportamento em produção depende de checar isso contra a API real antes de rodar o job de coleta de verdade.
- Todo texto de identificador/variável em português, seguindo a convenção já estabelecida no restante de `core/estoque.py`, `core/chat.py`, `bling_erp.py`.
- Backend: rodar `python -m pytest hermes_agents/tests/test_i9logic.py -v` a partir da raiz do repositório após cada task, e a suíte completa `python -m pytest hermes_agents/tests/ -q` na Task 9.

---

### Task 1: De-para de identidade — tabela + CRUD

**Files:**
- Create: `hermes_agents/core/i9logic.py`
- Modify: `hermes_agents/athena_bridge.py` (nenhuma mudança nesta task — o registro de blueprint só acontece na Task 8; mencionado aqui só pra contexto de onde a app inicializa)
- Test: `hermes_agents/tests/test_i9logic.py` (novo)

**Interfaces:**
- Produces: `core.i9logic.criar_mapeamento(tipo: str, id_i9logic, codigo_athena: str) -> dict`, `core.i9logic.buscar_codigo_athena(tipo: str, id_i9logic) -> str | None`, `core.i9logic.listar_mapeamentos(tipo: str = None) -> list[dict]`. Usadas pelas Tasks 2, 4, 6.

- [ ] **Step 1: Escrever os testes que falham**

Criar `hermes_agents/tests/test_i9logic.py`:

```python
"""Testes de integracao — reconciliacao i9Logic."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock, MagicMock

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.i9logic as i9logic


class TestDeParaCRUD(unittest.TestCase):
    def test_criar_mapeamento_tipo_invalido_retorna_erro(self):
        resultado = i9logic.criar_mapeamento("invalido", "1", "SKU-1")
        self.assertIn("erro", resultado)

    def test_criar_mapeamento_produto_grava(self):
        async def _fetchrow(query, *args):
            return {"id": 1, "tipo": args[0], "id_i9logic": args[1], "codigo_athena": args[2]}
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.criar_mapeamento("produto", 29098, "SKU-29098")
        self.assertEqual(resultado["codigo_athena"], "SKU-29098")
        self.assertEqual(resultado["id_i9logic"], "29098")

    def test_buscar_codigo_athena_encontrado(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=AsyncMock(return_value="SKU-29098"))
            resultado = i9logic.buscar_codigo_athena("produto", 29098)
        self.assertEqual(resultado, "SKU-29098")

    def test_buscar_codigo_athena_nao_encontrado_retorna_none(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=AsyncMock(return_value=None))
            resultado = i9logic.buscar_codigo_athena("produto", 999)
        self.assertIsNone(resultado)

    def test_listar_mapeamentos_filtra_por_tipo(self):
        async def _fetch(query, *args):
            self.assertIn("tipo=$1", query)
            self.assertEqual(args[0], "filial")
            return [{"id": 1, "tipo": "filial", "id_i9logic": "63", "codigo_athena": "Loja Matriz"}]
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetch=_fetch)
            resultado = i9logic.listar_mapeamentos("filial")
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["codigo_athena"], "Loja Matriz")
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.i9logic'` (o módulo ainda não existe).

- [ ] **Step 3: Criar o módulo com tabelas + CRUD de de-para**

Criar `hermes_agents/core/i9logic.py`:

```python
"""Reconciliacao Fisico x Contabil — Ponte i9Logic -> Athena.

De-para de identidade, client HTTP paginado (respeitando rate limit), staging
table de snapshot, classificacao de divergencia, job de coleta e seed inicial.
Fisico (tipoestoque=1) semeia estoque_saldos (Fase 1); contabil (tipoestoque=2)
nunca vira bucket, so' serve como sinal de auditoria. Nenhum ajuste automatico
de saldo — toda decisao sobre divergencia e' manual."""
import os, time, requests
from datetime import datetime
from core import get_db, run_async, log
from core.config import get_config

AGENT = "I9Logic Reconciliacao"

BASE_URL = os.environ.get("I9LOGIC_BASE_URL") or get_config("i9logic", "base_url") or ""
RATE_LIMIT_SLEEP_SEGUNDOS = 2.5  # ~24 req/min, margem sob o limite de 30/min da API
PER_PAGE_PADRAO = 200

LIMIAR_ALERTA_ABSOLUTO = 5
LIMIAR_ALERTA_PERCENTUAL = 0.10
TOLERANCIA_ZERO = 0.5


def _api_key() -> str:
    return os.environ.get("I9LOGIC_API_KEY") or get_config("i9logic", "api_key") or ""


def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS de_para_i9logic (
            id SERIAL PRIMARY KEY,
            tipo VARCHAR(10) NOT NULL,
            id_i9logic VARCHAR(50) NOT NULL,
            codigo_athena VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (tipo, id_i9logic)
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS i9logic_estoque_snapshot (
            id SERIAL PRIMARY KEY,
            idproduto_i9logic INT NOT NULL,
            codproduto_i9logic VARCHAR(50),
            sku_athena VARCHAR(50),
            filial_i9logic INT NOT NULL,
            loja_athena VARCHAR(50),
            qtd_fisico DECIMAL(12,3),
            qtd_contabil DECIMAL(12,3),
            divergencia DECIMAL(12,3) GENERATED ALWAYS AS (qtd_contabil - qtd_fisico) STORED,
            data_coleta TIMESTAMP DEFAULT NOW(),
            revisado BOOLEAN DEFAULT FALSE,
            UNIQUE(idproduto_i9logic, filial_i9logic, data_coleta)
        )""")
    try:
        run_async(_go())
        log(AGENT, "Tabelas i9logic seeded")
    except Exception as e:
        log(AGENT, f"Erro tabelas i9logic: {e}")

_ensure_tables()

# ── De-para de identidade ──

def criar_mapeamento(tipo: str, id_i9logic, codigo_athena: str) -> dict:
    """Cria ou atualiza (upsert) o de-para entre um id interno do i9Logic e o
    codigo correspondente no Athena. tipo: 'produto' (id_i9logic=idproduto,
    codigo_athena=sku) ou 'filial' (id_i9logic=id da filial, codigo_athena=
    nome da loja)."""
    if tipo not in ("produto", "filial"):
        return {"erro": f"tipo invalido: {tipo}. Use 'produto' ou 'filial'"}
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "INSERT INTO de_para_i9logic (tipo, id_i9logic, codigo_athena) VALUES ($1,$2,$3) "
            "ON CONFLICT (tipo, id_i9logic) DO UPDATE SET codigo_athena=$3 RETURNING *",
            tipo, str(id_i9logic), codigo_athena)
        return dict(row)
    try: return run_async(_go())
    except Exception as e: return {"erro": str(e)}


def buscar_codigo_athena(tipo: str, id_i9logic):
    async def _go():
        db = await get_db()
        return await db.fetchval(
            "SELECT codigo_athena FROM de_para_i9logic WHERE tipo=$1 AND id_i9logic=$2",
            tipo, str(id_i9logic))
    try: return run_async(_go())
    except Exception: return None


def listar_mapeamentos(tipo: str = None) -> list:
    async def _go():
        db = await get_db()
        if tipo:
            rows = await db.fetch("SELECT * FROM de_para_i9logic WHERE tipo=$1 ORDER BY id", tipo)
        else:
            rows = await db.fetch("SELECT * FROM de_para_i9logic ORDER BY tipo, id")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception: return []
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/i9logic.py hermes_agents/tests/test_i9logic.py
git commit -m "feat: de-para de identidade i9Logic (produto/filial) - tabela + CRUD"
```

---

### Task 2: De-para — matching automático + relatório de não-casados

**Files:**
- Modify: `hermes_agents/core/i9logic.py`
- Test: `hermes_agents/tests/test_i9logic.py`

**Interfaces:**
- Consumes: nada de tasks anteriores além da tabela `de_para_i9logic` (Task 1) e tabelas já existentes `catalogo_produtos`/`lojas`.
- Produces: `core.i9logic.executar_matching_automatico(tipo: str, pares_i9logic: list[dict]) -> dict` — cada item de `pares_i9logic` é `{"id_i9logic": ..., "codigo_i9logic": ...}`. Retorno: `{"ok": True, "casados": int, "nao_casados": list[dict]}` ou `{"erro": str}`.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `hermes_agents/tests/test_i9logic.py`:

```python
class TestMatchingAutomatico(unittest.TestCase):
    def test_matching_tipo_invalido_retorna_erro(self):
        resultado = i9logic.executar_matching_automatico("invalido", [])
        self.assertIn("erro", resultado)

    def test_matching_produto_casa_por_sku_igual(self):
        async def _fetchval(query, *args):
            if "catalogo_produtos" in query:
                return args[0] if args[0] == "041725" else None
            return None
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=_fetchval, execute=AsyncMock(return_value="OK"))
            resultado = i9logic.executar_matching_automatico(
                "produto", [{"id_i9logic": 29098, "codigo_i9logic": "041725"}])
        self.assertEqual(resultado["casados"], 1)
        self.assertEqual(resultado["nao_casados"], [])

    def test_matching_produto_nao_casado_vai_pro_relatorio(self):
        async def _fetchval(query, *args):
            return None
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=_fetchval, execute=AsyncMock(return_value="OK"))
            resultado = i9logic.executar_matching_automatico(
                "produto", [{"id_i9logic": 999, "codigo_i9logic": "SKU-INEXISTENTE"}])
        self.assertEqual(resultado["casados"], 0)
        self.assertEqual(len(resultado["nao_casados"]), 1)
        self.assertEqual(resultado["nao_casados"][0]["codigo_i9logic"], "SKU-INEXISTENTE")

    def test_matching_filial_consulta_tabela_lojas(self):
        async def _fetchval(query, *args):
            self.assertIn("lojas", query)
            return "Loja Matriz"
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=_fetchval, execute=AsyncMock(return_value="OK"))
            resultado = i9logic.executar_matching_automatico(
                "filial", [{"id_i9logic": 63, "codigo_i9logic": "Loja Matriz"}])
        self.assertEqual(resultado["casados"], 1)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v -k TestMatchingAutomatico`
Expected: FAIL — `AttributeError: module 'core.i9logic' has no attribute 'executar_matching_automatico'`.

- [ ] **Step 3: Implementar o matching automático**

Em `hermes_agents/core/i9logic.py`, ao final da seção `# ── De-para de identidade ──` (depois de `listar_mapeamentos`), adicionar:

```python
def executar_matching_automatico(tipo: str, pares_i9logic: list) -> dict:
    """pares_i9logic: [{"id_i9logic": ..., "codigo_i9logic": ...}, ...] vindos da
    API i9Logic (codproduto pra tipo='produto', nome da filial pra tipo='filial').
    Casa por igualdade textual exata contra catalogo_produtos.sku ou lojas.nome —
    NUNCA matching fuzzy. O que nao casar vai pro relatorio de nao_casados pra
    revisao humana, sem tentativa de match aproximado."""
    if tipo not in ("produto", "filial"):
        return {"erro": f"tipo invalido: {tipo}. Use 'produto' ou 'filial'"}
    async def _go():
        db = await get_db()
        casados, nao_casados = [], []
        for par in pares_i9logic:
            codigo = par.get("codigo_i9logic", "")
            if tipo == "produto":
                existe = await db.fetchval("SELECT sku FROM catalogo_produtos WHERE sku=$1", codigo)
            else:
                existe = await db.fetchval("SELECT nome FROM lojas WHERE nome=$1", codigo)
            if existe:
                await db.execute(
                    "INSERT INTO de_para_i9logic (tipo, id_i9logic, codigo_athena) VALUES ($1,$2,$3) "
                    "ON CONFLICT (tipo, id_i9logic) DO UPDATE SET codigo_athena=$3",
                    tipo, str(par["id_i9logic"]), codigo)
                casados.append({"id_i9logic": par["id_i9logic"], "codigo_athena": codigo})
            else:
                nao_casados.append(par)
        return casados, nao_casados
    try:
        casados, nao_casados = run_async(_go())
    except Exception as e:
        return {"erro": str(e)}
    return {"ok": True, "casados": len(casados), "nao_casados": nao_casados}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v`
Expected: PASS (todos os testes do arquivo, incluindo os da Task 1).

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/i9logic.py hermes_agents/tests/test_i9logic.py
git commit -m "feat: matching automatico de de-para i9Logic (igualdade exata + relatorio de nao-casados)"
```

---

### Task 3: Client HTTP i9Logic — paginação completa respeitando rate limit

**Files:**
- Modify: `hermes_agents/core/i9logic.py`
- Test: `hermes_agents/tests/test_i9logic.py`

**Interfaces:**
- Produces: `core.i9logic._paginar_estoques(filial_id_i9logic: int, tipoestoque: int) -> list[dict]` — cada item `{"idproduto": int, "codproduto": str, "qtd": float}`. Usada pela Task 6.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `hermes_agents/tests/test_i9logic.py`:

```python
class TestPaginarEstoques(unittest.TestCase):
    def _resposta(self, pagina, total, por_pagina=200):
        inicio = (pagina - 1) * por_pagina
        fim = min(inicio + por_pagina, total)
        dados = [{"idproduto": i, "codproduto": f"COD-{i}", "qtd": 10} for i in range(inicio, fim)]
        resp = MagicMock()
        resp.json.return_value = {"data": dados, "total": total}
        resp.raise_for_status.return_value = None
        return resp

    def test_pagina_completa_sem_duplicar_mais_de_200_registros(self):
        total = 450  # 3 paginas: 200, 200, 50
        def _get(url, params=None, headers=None, timeout=None):
            return self._resposta(params["page"], total)
        with patch("core.i9logic.requests.get", side_effect=_get), \
             patch("core.i9logic.time.sleep") as mock_sleep:
            resultado = i9logic._paginar_estoques(63, 1)
        self.assertEqual(len(resultado), total)
        ids = [r["idproduto"] for r in resultado]
        self.assertEqual(len(ids), len(set(ids)), "nao deve haver idproduto duplicado entre paginas")
        self.assertEqual(mock_sleep.call_count, 2)  # dorme entre paginas 1-2 e 2-3, nao depois da ultima
        mock_sleep.assert_called_with(i9logic.RATE_LIMIT_SLEEP_SEGUNDOS)

    def test_pagina_unica_nao_dorme(self):
        def _get(url, params=None, headers=None, timeout=None):
            return self._resposta(params["page"], 50)
        with patch("core.i9logic.requests.get", side_effect=_get), \
             patch("core.i9logic.time.sleep") as mock_sleep:
            resultado = i9logic._paginar_estoques(63, 2)
        self.assertEqual(len(resultado), 50)
        mock_sleep.assert_not_called()

    def test_paginacao_passa_tipoestoque_e_filial_corretos(self):
        chamadas = []
        def _get(url, params=None, headers=None, timeout=None):
            chamadas.append(params)
            return self._resposta(params["page"], 10)
        with patch("core.i9logic.requests.get", side_effect=_get), \
             patch("core.i9logic.time.sleep"):
            i9logic._paginar_estoques(63, 2)
        self.assertEqual(chamadas[0]["filial"], 63)
        self.assertEqual(chamadas[0]["tipoestoque"], 2)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v -k TestPaginarEstoques`
Expected: FAIL — `AttributeError: module 'core.i9logic' has no attribute '_paginar_estoques'`.

- [ ] **Step 3: Implementar o client paginado**

Em `hermes_agents/core/i9logic.py`, depois da seção de de-para (depois de `executar_matching_automatico`), adicionar:

```python
# ── Client HTTP (paginacao + rate limit) ──

def _paginar_estoques(filial_id_i9logic: int, tipoestoque: int) -> list:
    """Pagina o catalogo inteiro da filial pro tipo de estoque pedido
    (1=fisico, 2=contabil), respeitando o rate limit de 30 req/min via sleep
    de RATE_LIMIT_SLEEP_SEGUNDOS entre chamadas (nao dorme apos a ultima
    pagina). Retorna todos os registros de todas as paginas, sem duplicar."""
    registros = []
    pagina = 1
    while True:
        resp = requests.get(
            f"{BASE_URL}/v1/produtos_estoques",
            params={"filial": filial_id_i9logic, "tipoestoque": tipoestoque,
                     "page": pagina, "per_page": PER_PAGE_PADRAO},
            headers={"Authorization": f"Bearer {_api_key()}"},
            timeout=30,
        )
        resp.raise_for_status()
        dados = resp.json()
        pagina_registros = dados.get("data", [])
        registros.extend(pagina_registros)
        total = dados.get("total", len(registros))
        if pagina * PER_PAGE_PADRAO >= total or not pagina_registros:
            break
        pagina += 1
        time.sleep(RATE_LIMIT_SLEEP_SEGUNDOS)
    return registros
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v`
Expected: PASS (todos os testes do arquivo).

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/i9logic.py hermes_agents/tests/test_i9logic.py
git commit -m "feat: client HTTP i9Logic - paginacao completa respeitando rate limit de 30 req/min"
```

---

### Task 4: Snapshot — tabela (já criada na Task 1) + gravação resolvendo de-para

**Files:**
- Modify: `hermes_agents/core/i9logic.py`
- Test: `hermes_agents/tests/test_i9logic.py`

**Interfaces:**
- Consumes: tabela `i9logic_estoque_snapshot` (já criada em `_ensure_tables`, Task 1), tabela `de_para_i9logic` (Task 1).
- Produces: `core.i9logic.gravar_snapshot(idproduto_i9logic: int, codproduto_i9logic: str, filial_i9logic: int, qtd_fisico: float, qtd_contabil: float, data_coleta: datetime = None) -> dict`. Usada pela Task 6.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `hermes_agents/tests/test_i9logic.py`:

```python
class TestGravarSnapshot(unittest.TestCase):
    def test_grava_resolvendo_sku_e_loja_via_depara(self):
        chamadas_fetchval = []
        async def _fetchval(query, *args):
            chamadas_fetchval.append((query, args))
            if "tipo='produto'" in query:
                return "SKU-29098"
            if "tipo='filial'" in query:
                return "Loja Matriz"
            return None
        async def _fetchrow(query, *args):
            return {"id": 1, "idproduto_i9logic": args[0], "codproduto_i9logic": args[1],
                    "sku_athena": args[2], "filial_i9logic": args[3], "loja_athena": args[4],
                    "qtd_fisico": args[5], "qtd_contabil": args[6], "divergencia": args[6] - args[5]}
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=_fetchval, fetchrow=_fetchrow)
            resultado = i9logic.gravar_snapshot(29098, "041725", 63, 165, 348)
        self.assertEqual(resultado["sku_athena"], "SKU-29098")
        self.assertEqual(resultado["loja_athena"], "Loja Matriz")
        self.assertEqual(resultado["divergencia"], 183)

    def test_grava_com_athena_nulo_quando_sem_depara(self):
        async def _fetchval(query, *args):
            return None
        async def _fetchrow(query, *args):
            return {"id": 1, "idproduto_i9logic": args[0], "codproduto_i9logic": args[1],
                    "sku_athena": args[2], "filial_i9logic": args[3], "loja_athena": args[4],
                    "qtd_fisico": args[5], "qtd_contabil": args[6]}
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=_fetchval, fetchrow=_fetchrow)
            resultado = i9logic.gravar_snapshot(999, "SEM-DEPARA", 1, 10, 10)
        self.assertIsNone(resultado["sku_athena"])
        self.assertIsNone(resultado["loja_athena"])
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v -k TestGravarSnapshot`
Expected: FAIL — `AttributeError: module 'core.i9logic' has no attribute 'gravar_snapshot'`.

- [ ] **Step 3: Implementar `gravar_snapshot`**

Em `hermes_agents/core/i9logic.py`, depois da seção de client HTTP (depois de `_paginar_estoques`), adicionar:

```python
# ── Snapshot (staging) ──

def gravar_snapshot(idproduto_i9logic: int, codproduto_i9logic: str, filial_i9logic: int,
                     qtd_fisico: float, qtd_contabil: float, data_coleta: datetime = None) -> dict:
    """Resolve sku_athena/loja_athena via de-para no momento da gravacao; grava
    nulo se nao encontrar mapeamento — nao perde o dado bruto coletado esperando
    resolucao manual do de-para. data_coleta explicito (nao so' o DEFAULT NOW()
    da coluna) permite que o job de coleta (Task 6) marque todas as linhas de
    uma mesma corrida com o MESMO instante, mesmo gravando fora de uma unica
    transacao — necessario pra 'uma linha por corrida completa' do spec."""
    async def _go():
        db = await get_db()
        sku_athena = await db.fetchval(
            "SELECT codigo_athena FROM de_para_i9logic WHERE tipo='produto' AND id_i9logic=$1",
            str(idproduto_i9logic))
        loja_athena = await db.fetchval(
            "SELECT codigo_athena FROM de_para_i9logic WHERE tipo='filial' AND id_i9logic=$1",
            str(filial_i9logic))
        row = await db.fetchrow("""
            INSERT INTO i9logic_estoque_snapshot
                (idproduto_i9logic, codproduto_i9logic, sku_athena, filial_i9logic, loja_athena,
                 qtd_fisico, qtd_contabil, data_coleta)
            VALUES ($1,$2,$3,$4,$5,$6,$7,COALESCE($8, NOW()))
            ON CONFLICT (idproduto_i9logic, filial_i9logic, data_coleta) DO UPDATE
                SET qtd_fisico=$6, qtd_contabil=$7
            RETURNING *
        """, idproduto_i9logic, codproduto_i9logic, sku_athena, filial_i9logic, loja_athena,
            qtd_fisico, qtd_contabil, data_coleta)
        return dict(row)
    try: return run_async(_go())
    except Exception as e: return {"erro": str(e)}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v`
Expected: PASS (todos os testes do arquivo).

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/i9logic.py hermes_agents/tests/test_i9logic.py
git commit -m "feat: gravar_snapshot resolve sku/loja Athena via de-para no momento da gravacao"
```

---

### Task 5: Classificação de divergência + listagem de revisão + comparação com Athena

**Files:**
- Modify: `hermes_agents/core/i9logic.py`
- Test: `hermes_agents/tests/test_i9logic.py`

**Interfaces:**
- Consumes: `core.estoque_saldos.saldo(sku, loja, tipo)` e `core.estoque.ajustar_absoluto(sku, loja, quantidade_absoluta, motivo, usuario_id, usuario_nome)` (já existentes).
- Produces: `core.i9logic.classificar_divergencia(qtd_fisico: float, qtd_comparacao: float) -> str` (`"sem_acao"` | `"registrado"` | `"alerta"`), `core.i9logic.listar_itens_para_revisao(revisado: bool = False) -> list[dict]`, `core.i9logic.marcar_revisado(snapshot_id: int) -> dict`, `core.i9logic.aplicar_ajuste_divergencia(snapshot_id: int, usuario_id: int = None, usuario_nome: str = "") -> dict`, `core.i9logic.comparar_com_athena(sku: str, loja: str) -> dict`. Usadas pela Task 8 (rotas).

Nota de cobertura do spec: a seção "Regra de decisão sobre divergência" descreve 3 desfechos possíveis por item — contar fisicamente (fora do escopo desta ponte, é ação humana externa), **ajustar manualmente via `ajustar_absoluto()` com motivo `ajuste_inventario`** (rastreável — vira linha real em `estoque_movimentacoes`), ou aceitar a divergência como conhecida (só marca revisado, sem tocar saldo). Os dois últimos precisam de função própria cada um — `marcar_revisado` (aceitar) e `aplicar_ajuste_divergencia` (ajustar) — não é a mesma coisa, e um item resolvido por "ajustar" também fica `revisado=TRUE` ao final (não precisa das duas chamadas separadas).

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `hermes_agents/tests/test_i9logic.py`:

```python
class TestClassificarDivergencia(unittest.TestCase):
    def test_sem_divergencia_e_sem_acao(self):
        self.assertEqual(i9logic.classificar_divergencia(100, 100), "sem_acao")

    def test_divergencia_dentro_da_tolerancia_e_sem_acao(self):
        self.assertEqual(i9logic.classificar_divergencia(100, 100.5), "sem_acao")

    def test_divergencia_pequena_e_so_registrada(self):
        # divergencia = 2, abaixo do limiar absoluto (5) e percentual (10% de 100 = 10)
        self.assertEqual(i9logic.classificar_divergencia(100, 102), "registrado")

    def test_divergencia_exatamente_no_limiar_absoluto_e_alerta(self):
        # divergencia = 5, >= LIMIAR_ALERTA_ABSOLUTO
        self.assertEqual(i9logic.classificar_divergencia(100, 105), "alerta")

    def test_divergencia_exatamente_no_limiar_percentual_e_alerta(self):
        # fisico=10, divergencia=1 -> 1/10 = 10% exato, mas abs(1) < 5 -> ainda alerta pelo percentual
        self.assertEqual(i9logic.classificar_divergencia(10, 11), "alerta")

    def test_divergencia_grande_bate_os_dois_limiares_e_alerta(self):
        self.assertEqual(i9logic.classificar_divergencia(165, 348), "alerta")

    def test_qtd_fisico_zero_usa_base_minima_um_no_percentual(self):
        # fisico=0, comparacao=3 -> divergencia=3, abaixo do absoluto (5); percentual usa
        # max(0,1)=1 como base -> 3/1 = 300% -> alerta
        self.assertEqual(i9logic.classificar_divergencia(0, 3), "alerta")


class TestListarERevisar(unittest.TestCase):
    def test_listar_itens_para_revisao_filtra_por_tolerancia(self):
        async def _fetch(query, *args):
            self.assertEqual(args[0], False)
            return [{"id": 1, "divergencia": 183}]
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetch=_fetch)
            resultado = i9logic.listar_itens_para_revisao()
        self.assertEqual(len(resultado), 1)

    def test_marcar_revisado_nao_encontrado_retorna_erro(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=AsyncMock(return_value=None))
            resultado = i9logic.marcar_revisado(999)
        self.assertIn("erro", resultado)

    def test_marcar_revisado_encontrado_retorna_ok(self):
        async def _fetchrow(query, *args):
            return {"id": args[0], "revisado": True}
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.marcar_revisado(1)
        self.assertTrue(resultado["ok"])


class TestAplicarAjusteDivergencia(unittest.TestCase):
    def test_snapshot_nao_encontrado_retorna_erro(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=AsyncMock(return_value=None))
            resultado = i9logic.aplicar_ajuste_divergencia(999)
        self.assertIn("erro", resultado)

    def test_snapshot_sem_depara_resolvido_retorna_erro(self):
        async def _fetchrow(query, *args):
            return {"id": 1, "sku_athena": None, "loja_athena": None, "qtd_fisico": 165}
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.aplicar_ajuste_divergencia(1)
        self.assertIn("erro", resultado)

    def test_ajusta_via_ajustar_absoluto_e_marca_revisado(self):
        chamadas = {"n": 0}
        async def _fetchrow(query, *args):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                return {"id": 1, "sku_athena": "SKU-29098", "loja_athena": "Loja Matriz", "qtd_fisico": 165}
            return {"id": 1, "revisado": True}
        with patch("core.i9logic.get_db") as mock_get_db, \
             patch("core.estoque.ajustar_absoluto", return_value={"ok": True, "atual": 165}) as mock_ajustar:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.aplicar_ajuste_divergencia(1, usuario_id=1, usuario_nome="Ana")
        mock_ajustar.assert_called_once_with(
            "SKU-29098", "Loja Matriz", 165.0, motivo="ajuste_inventario", usuario_id=1, usuario_nome="Ana")
        self.assertTrue(resultado["ok"])

    def test_ajustar_absoluto_com_erro_nao_marca_revisado(self):
        async def _fetchrow(query, *args):
            return {"id": 1, "sku_athena": "SKU-X", "loja_athena": "Loja Y", "qtd_fisico": 165}
        with patch("core.i9logic.get_db") as mock_get_db, \
             patch("core.estoque.ajustar_absoluto", return_value={"erro": "falha simulada"}):
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.aplicar_ajuste_divergencia(1)
        self.assertIn("erro", resultado)


class TestCompararComAthena(unittest.TestCase):
    def test_sem_snapshot_retorna_erro(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=AsyncMock(return_value=None))
            resultado = i9logic.comparar_com_athena("SKU-X", "Loja Y")
        self.assertIn("erro", resultado)

    def test_com_snapshot_calcula_divergencia_contra_saldo_athena(self):
        async def _fetchrow(query, *args):
            return {"qtd_fisico": 100, "data_coleta": "2026-07-29T00:00:00"}
        with patch("core.i9logic.get_db") as mock_get_db, \
             patch("core.estoque_saldos.saldo", return_value=95.0):
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.comparar_com_athena("SKU-X", "Loja Y")
        self.assertEqual(resultado["disponivel_athena"], 95.0)
        self.assertEqual(resultado["qtd_fisico_i9logic"], 100.0)
        self.assertEqual(resultado["divergencia"], -5.0)
        self.assertEqual(resultado["classificacao"], "alerta")
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v -k "ClassificarDivergencia or ListarERevisar or AplicarAjusteDivergencia or CompararComAthena"`
Expected: FAIL — `AttributeError` (funções ainda não existem).

- [ ] **Step 3: Implementar classificação, listagem, ajuste e comparação**

Em `hermes_agents/core/i9logic.py`, depois da seção de snapshot (depois de `gravar_snapshot`), adicionar:

```python
# ── Divergencia: classificacao, listagem, comparacao com Athena ──

def classificar_divergencia(qtd_fisico: float, qtd_comparacao: float) -> str:
    """qtd_comparacao e' o contabil (i9Logic isolado, modo seed/auditoria) ou o
    disponivel do Athena (modo monitoramento continuo) — a mesma regra de
    classificacao serve pros dois casos, so' muda o que se compara contra o
    fisico. Nunca ajusta nada sozinho, so' classifica pra fila de revisao."""
    divergencia = abs(float(qtd_comparacao) - float(qtd_fisico))
    if divergencia <= TOLERANCIA_ZERO:
        return "sem_acao"
    base = max(float(qtd_fisico), 1)
    if divergencia >= LIMIAR_ALERTA_ABSOLUTO or (divergencia / base) >= LIMIAR_ALERTA_PERCENTUAL:
        return "alerta"
    return "registrado"


def listar_itens_para_revisao(revisado: bool = False) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch(
            "SELECT * FROM i9logic_estoque_snapshot WHERE revisado=$1 AND ABS(divergencia) > $2 "
            "ORDER BY ABS(divergencia) DESC", revisado, TOLERANCIA_ZERO)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception: return []


def marcar_revisado(snapshot_id: int) -> dict:
    """Resolve o item como 'aceitar a divergencia como conhecida' — so' marca
    revisado, nunca toca saldo. Pro caminho que ajusta saldo de verdade, ver
    aplicar_ajuste_divergencia()."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "UPDATE i9logic_estoque_snapshot SET revisado=TRUE WHERE id=$1 RETURNING *", snapshot_id)
        return dict(row) if row else None
    try:
        r = run_async(_go())
        return {"ok": True, "snapshot": r} if r else {"erro": "snapshot nao encontrado"}
    except Exception as e: return {"erro": str(e)}


def aplicar_ajuste_divergencia(snapshot_id: int, usuario_id: int = None, usuario_nome: str = "") -> dict:
    """Resolve o item como 'ajustar manualmente' (spec): aplica o fisico
    coletado como quantidade absoluta via core.estoque.ajustar_absoluto() —
    passa pelo ledger formal do Athena (Fase 1), motivo fixo 'ajuste_inventario'
    (nao da' pra colar o id do snapshot dentro do motivo — e' um enum validado
    contra MOTIVOS_ENTRADA/MOTIVOS_SAIDA, nao texto livre). Rastreabilidade fica
    por correlacao de tempo entre estoque_movimentacoes e este snapshot, mais o
    proprio snapshot_id que o chamador ja tinha na mao pra disparar isto.
    So' marca revisado=TRUE se o ajuste realmente aplicar sem erro."""
    async def _buscar():
        db = await get_db()
        return await db.fetchrow(
            "SELECT sku_athena, loja_athena, qtd_fisico FROM i9logic_estoque_snapshot WHERE id=$1",
            snapshot_id)
    try:
        snap = run_async(_buscar())
    except Exception as e:
        return {"erro": str(e)}
    if not snap:
        return {"erro": "snapshot nao encontrado"}
    if not snap["sku_athena"] or not snap["loja_athena"]:
        return {"erro": "snapshot sem de-para resolvido (sku_athena/loja_athena nulos) - resolva o de-para antes de ajustar"}
    from core.estoque import ajustar_absoluto
    resultado = ajustar_absoluto(
        snap["sku_athena"], snap["loja_athena"], float(snap["qtd_fisico"] or 0),
        motivo="ajuste_inventario", usuario_id=usuario_id, usuario_nome=usuario_nome)
    if resultado.get("erro"):
        return resultado
    marcado = marcar_revisado(snapshot_id)
    return {"ok": True, "ajuste": resultado, "snapshot": marcado.get("snapshot")}


def comparar_com_athena(sku: str, loja: str) -> dict:
    """Modo monitoramento continuo (spec): compara o disponivel atual do Athena
    contra o fisico mais recente coletado do i9Logic pro mesmo sku/loja."""
    from core.estoque_saldos import saldo
    async def _go():
        db = await get_db()
        return await db.fetchrow("""
            SELECT qtd_fisico, data_coleta FROM i9logic_estoque_snapshot
            WHERE sku_athena=$1 AND loja_athena=$2 ORDER BY data_coleta DESC LIMIT 1
        """, sku, loja)
    try:
        ultimo = run_async(_go())
    except Exception as e:
        return {"erro": str(e)}
    if not ultimo:
        return {"erro": "sem snapshot para este sku/loja"}
    disponivel_athena = saldo(sku, loja, "disponivel")
    qtd_fisico = float(ultimo["qtd_fisico"] or 0)
    return {
        "sku": sku, "loja": loja,
        "disponivel_athena": disponivel_athena,
        "qtd_fisico_i9logic": qtd_fisico,
        "divergencia": round(disponivel_athena - qtd_fisico, 3),
        "classificacao": classificar_divergencia(qtd_fisico, disponivel_athena),
        "data_coleta": ultimo["data_coleta"],
    }
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v`
Expected: PASS (todos os testes do arquivo).

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/i9logic.py hermes_agents/tests/test_i9logic.py
git commit -m "feat: classificacao de divergencia (limiar absoluto/percentual), fila de revisao e comparacao com Athena"
```

---

### Task 6: Job de coleta — orquestra client + de-para + snapshot por filial

**Files:**
- Modify: `hermes_agents/core/i9logic.py`
- Test: `hermes_agents/tests/test_i9logic.py`

**Interfaces:**
- Consumes: `_paginar_estoques` (Task 3), `gravar_snapshot` (Task 4), `listar_mapeamentos` (Task 1).
- Produces: `core.i9logic.executar_coleta_filial(filial_id_i9logic: int) -> dict`, `core.i9logic.executar_coleta_todas_filiais() -> dict`. Usadas pela Task 8 (rota `/coletar`).

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `hermes_agents/tests/test_i9logic.py`:

```python
class TestExecutarColeta(unittest.TestCase):
    def test_coleta_filial_pareia_fisico_e_contabil_por_idproduto(self):
        def _paginar(filial, tipoestoque):
            if tipoestoque == 1:
                return [{"idproduto": 1, "codproduto": "A", "qtd": 10},
                        {"idproduto": 2, "codproduto": "B", "qtd": 20}]
            return [{"idproduto": 1, "codproduto": "A", "qtd": 15},
                    {"idproduto": 2, "codproduto": "B", "qtd": 20}]
        gravados = []
        def _gravar(idproduto, codproduto, filial, qtd_fisico, qtd_contabil, data_coleta=None):
            gravados.append((idproduto, qtd_fisico, qtd_contabil))
            return {"ok": True}
        with patch("core.i9logic._paginar_estoques", side_effect=_paginar), \
             patch("core.i9logic.gravar_snapshot", side_effect=_gravar):
            resultado = i9logic.executar_coleta_filial(63)
        self.assertEqual(resultado["fisicos"], 2)
        self.assertEqual(resultado["gravados"], 2)
        self.assertIn((1, 10, 15), gravados)
        self.assertIn((2, 20, 20), gravados)

    def test_coleta_filial_usa_mesmo_data_coleta_pra_todas_as_linhas(self):
        def _paginar(filial, tipoestoque):
            return [{"idproduto": 1, "codproduto": "A", "qtd": 10}]
        datas_usadas = []
        def _gravar(idproduto, codproduto, filial, qtd_fisico, qtd_contabil, data_coleta=None):
            datas_usadas.append(data_coleta)
            return {"ok": True}
        with patch("core.i9logic._paginar_estoques", side_effect=_paginar), \
             patch("core.i9logic.gravar_snapshot", side_effect=_gravar):
            i9logic.executar_coleta_filial(63)
        self.assertIsNotNone(datas_usadas[0])

    def test_coleta_todas_filiais_itera_mapeamentos(self):
        with patch("core.i9logic.listar_mapeamentos", return_value=[
                {"id_i9logic": "63", "codigo_athena": "Loja Matriz"},
                {"id_i9logic": "64", "codigo_athena": "Loja Filial"}]), \
             patch("core.i9logic.executar_coleta_filial", return_value={"ok": True, "gravados": 5}) as mock_coleta:
            resultado = i9logic.executar_coleta_todas_filiais()
        self.assertEqual(resultado["filiais_processadas"], 2)
        self.assertEqual(mock_coleta.call_count, 2)
        mock_coleta.assert_any_call(63)
        mock_coleta.assert_any_call(64)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v -k TestExecutarColeta`
Expected: FAIL — `AttributeError: module 'core.i9logic' has no attribute 'executar_coleta_filial'`.

- [ ] **Step 3: Implementar o job de coleta**

Em `hermes_agents/core/i9logic.py`, depois da seção de divergência (depois de `comparar_com_athena`), adicionar:

```python
# ── Job de coleta ──

def executar_coleta_filial(filial_id_i9logic: int) -> dict:
    """Coleta fisico e contabil da filial inteira, pareia por idproduto, e grava
    cada par no snapshot com o MESMO data_coleta (uma corrida = um instante),
    resolvendo sku_athena/loja_athena via de-para em cada gravacao."""
    inicio_corrida = datetime.now()
    fisicos = _paginar_estoques(filial_id_i9logic, 1)
    contabeis = _paginar_estoques(filial_id_i9logic, 2)
    contabil_por_produto = {r["idproduto"]: r for r in contabeis}
    gravados, erros = 0, 0
    for f in fisicos:
        idproduto = f["idproduto"]
        c = contabil_por_produto.get(idproduto, {})
        r = gravar_snapshot(
            idproduto, f.get("codproduto"), filial_id_i9logic,
            f.get("qtd", 0), c.get("qtd", 0), data_coleta=inicio_corrida)
        if r.get("erro"): erros += 1
        else: gravados += 1
    return {"ok": True, "filial": filial_id_i9logic, "fisicos": len(fisicos),
            "contabeis": len(contabeis), "gravados": gravados, "erros": erros,
            "data_coleta": inicio_corrida}


def executar_coleta_todas_filiais() -> dict:
    """Roda executar_coleta_filial pra cada filial ja mapeada em de_para_i9logic
    (tipo='filial'). Filial sem de-para nao entra — nao ha id_i9logic resolvido
    sem o mapeamento."""
    filiais = listar_mapeamentos("filial")
    resultados = [executar_coleta_filial(int(m["id_i9logic"])) for m in filiais]
    return {"ok": True, "filiais_processadas": len(resultados), "resultados": resultados}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v`
Expected: PASS (todos os testes do arquivo).

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/i9logic.py hermes_agents/tests/test_i9logic.py
git commit -m "feat: job de coleta i9Logic - pareia fisico/contabil por produto e grava snapshot por filial"
```

---

### Task 7: Seed inicial — novo motivo de entrada + aplicação no Athena

**Files:**
- Modify: `hermes_agents/core/estoque.py:19` (adicionar `"import_i9logic"` a `MOTIVOS_ENTRADA` e mapeamento em `_MAPA_MOVIMENTO_ENTRADA`)
- Modify: `hermes_agents/core/i9logic.py`
- Test: `hermes_agents/tests/test_i9logic.py`
- Test: `hermes_agents/tests/test_estoque.py` (se existir; verificar antes — se o arquivo de teste de `core/estoque.py` tiver alguma lista fixa de `MOTIVOS_ENTRADA` esperada, ela precisa incluir o novo motivo)

**Interfaces:**
- Consumes: `core.estoque.entrada(sku, loja, quantidade, motivo, usuario_id, usuario_nome)` (já existente, ver `hermes_agents/core/estoque.py:102`).
- Produces: `core.i9logic.seed_inicial(sku_athena: str, loja_athena: str, usuario_id: int = None, usuario_nome: str = "") -> dict`. Usada pela Task 8 (rota `/seed`).

- [ ] **Step 1: Verificar se há teste existente que lista `MOTIVOS_ENTRADA` explicitamente**

Run: `grep -rn "MOTIVOS_ENTRADA" hermes_agents/tests/`

Se algum teste fizer uma asserção de igualdade contra a lista inteira (ex: `self.assertEqual(estoque.MOTIVOS_ENTRADA, [...])`), anote o arquivo/linha — o Step 3 vai precisar atualizar essa asserção junto (adicionar `"import_i9logic"` na lista esperada). Se nenhum teste existente fizer isso (mais provável — normalmente só se testa `motivo in MOTIVOS_ENTRADA` ou o comportamento de fallback pra `"outro"`), siga direto pro Step 2.

- [ ] **Step 2: Escrever os testes que falham**

Adicionar ao final de `hermes_agents/tests/test_i9logic.py`:

```python
class TestSeedInicial(unittest.TestCase):
    def test_sem_snapshot_retorna_erro(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=AsyncMock(return_value=None))
            resultado = i9logic.seed_inicial("SKU-X", "Loja Y")
        self.assertIn("erro", resultado)

    def test_quantidade_zero_ou_negativa_nao_aplica_seed(self):
        async def _fetchrow(query, *args):
            return {"qtd_fisico": 0}
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.seed_inicial("SKU-X", "Loja Y")
        self.assertIn("erro", resultado)

    def test_seed_chama_entrada_com_motivo_import_i9logic(self):
        async def _fetchrow(query, *args):
            return {"qtd_fisico": 165}
        with patch("core.i9logic.get_db") as mock_get_db, \
             patch("core.estoque.entrada", return_value={"ok": True}) as mock_entrada:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.seed_inicial("SKU-X", "Loja Y", usuario_id=1, usuario_nome="Ana")
        mock_entrada.assert_called_once_with(
            "SKU-X", "Loja Y", 165.0, motivo="import_i9logic", usuario_id=1, usuario_nome="Ana")
        self.assertTrue(resultado["ok"])
```

E, em `hermes_agents/tests/test_estoque.py` (se existir — usar `find hermes_agents/tests -iname "test_estoque*"` pra confirmar o nome exato do arquivo), adicionar (ajustando a classe/import conforme o padrão já usado nesse arquivo):

```python
def test_import_i9logic_esta_em_motivos_entrada(self):
    from core.estoque import MOTIVOS_ENTRADA, _MAPA_MOVIMENTO_ENTRADA
    self.assertIn("import_i9logic", MOTIVOS_ENTRADA)
    self.assertIn("import_i9logic", _MAPA_MOVIMENTO_ENTRADA)
```

- [ ] **Step 3: Rodar e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v -k TestSeedInicial`
Expected: FAIL — `AttributeError: module 'core.i9logic' has no attribute 'seed_inicial'`.

- [ ] **Step 4: Adicionar o motivo novo em `core/estoque.py`**

Em `hermes_agents/core/estoque.py`, localizar (por volta da linha 19):

```python
MOTIVOS_ENTRADA = ["compra_fornecedor", "devolucao_cliente", "producao_interna", "ajuste_inventario", "outro"]
```

Trocar por:

```python
MOTIVOS_ENTRADA = ["compra_fornecedor", "devolucao_cliente", "producao_interna", "ajuste_inventario", "import_i9logic", "outro"]
```

E, no dicionário `_MAPA_MOVIMENTO_ENTRADA` (por volta da linha 31-37):

```python
_MAPA_MOVIMENTO_ENTRADA = {
    "compra_fornecedor": "compra",
    "devolucao_cliente": "devolucao",
    "producao_interna": "recebimento",
    "ajuste_inventario": "ajuste",
    "outro": "ajuste",
}
```

Adicionar a linha `"import_i9logic": "recebimento",` (reaproveita o `tipo_movimento` `"recebimento"` que já existe em `TIPOS_MOVIMENTO`, `core/estoque_saldos.py:25-28` — semanticamente é recebimento de estoque vindo de fora, mesma categoria de `producao_interna`):

```python
_MAPA_MOVIMENTO_ENTRADA = {
    "compra_fornecedor": "compra",
    "devolucao_cliente": "devolucao",
    "producao_interna": "recebimento",
    "ajuste_inventario": "ajuste",
    "import_i9logic": "recebimento",
    "outro": "ajuste",
}
```

- [ ] **Step 5: Implementar `seed_inicial`**

Em `hermes_agents/core/i9logic.py`, depois da seção do job de coleta (depois de `executar_coleta_todas_filiais`), adicionar:

```python
# ── Seed inicial ──

def seed_inicial(sku_athena: str, loja_athena: str, usuario_id: int = None, usuario_nome: str = "") -> dict:
    """Usa o fisico mais recente coletado como entrada UNICA no Athena — so' faz
    sentido na primeira migracao do sku/loja pra Athena (spec: 'modo 1'). O
    contabil nao participa do seed, fica so' no snapshot como referencia."""
    from core.estoque import entrada
    async def _go():
        db = await get_db()
        return await db.fetchrow("""
            SELECT qtd_fisico FROM i9logic_estoque_snapshot
            WHERE sku_athena=$1 AND loja_athena=$2 ORDER BY data_coleta DESC LIMIT 1
        """, sku_athena, loja_athena)
    try:
        ultimo = run_async(_go())
    except Exception as e:
        return {"erro": str(e)}
    if not ultimo:
        return {"erro": "sem snapshot para este sku/loja"}
    qtd = float(ultimo["qtd_fisico"] or 0)
    if qtd <= 0:
        return {"erro": "quantidade fisica coletada e' zero ou negativa, seed nao aplicado"}
    return entrada(sku_athena, loja_athena, qtd, motivo="import_i9logic",
                    usuario_id=usuario_id, usuario_nome=usuario_nome)
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v`
Expected: PASS (todos os testes do arquivo).

Run: `python -m pytest hermes_agents/tests/test_estoque.py -v` (ou o nome real do arquivo encontrado no Step 1/2)
Expected: PASS (incluindo o teste novo de `MOTIVOS_ENTRADA`/`_MAPA_MOVIMENTO_ENTRADA`, e nenhuma regressão nos testes já existentes desse arquivo).

- [ ] **Step 7: Commit**

```bash
git add hermes_agents/core/estoque.py hermes_agents/core/i9logic.py hermes_agents/tests/test_i9logic.py hermes_agents/tests/test_estoque.py
git commit -m "feat: seed inicial i9Logic - novo motivo import_i9logic, aplica fisico coletado como entrada unica"
```

(Se `hermes_agents/tests/test_estoque.py` não existir com esse nome exato, ajuste o `git add`/nome do arquivo pro que o Step 1 encontrou — ou, se não existir NENHUM arquivo de teste pra `core/estoque.py`, pule a parte de adicionar teste lá e documente essa lacuna pré-existente no relatório da task, sem criar um arquivo de teste novo do zero pra um módulo que esta task não está implementando.)

---

### Task 8: Rotas HTTP — `/api/integrations/i9logic/*`

**Files:**
- Create: `hermes_agents/routes/i9logic.py`
- Modify: `hermes_agents/athena_bridge.py` (import + `app.register_blueprint(i9logic_bp)`, junto com os outros `register_blueprint` já existentes)
- Test: `hermes_agents/tests/test_i9logic.py`

**Interfaces:**
- Consumes: `criar_mapeamento`, `listar_mapeamentos`, `executar_matching_automatico` (Task 1/2), `executar_coleta_todas_filiais` (Task 6), `listar_itens_para_revisao`, `marcar_revisado`, `aplicar_ajuste_divergencia`, `comparar_com_athena` (Task 5), `seed_inicial` (Task 7). `core.rbac.requer_permissao`/`usuario_atual_da_request` (já existentes, ver `hermes_agents/routes/estoque.py:261-262` como referência do padrão de uso).

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `hermes_agents/tests/test_i9logic.py`:

```python
from flask import Flask
import core.rbac as rbac


def _app():
    from routes.i9logic import i9logic_bp
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(i9logic_bp)
    return app.test_client()


class TestRotasI9Logic(unittest.TestCase):
    def setUp(self):
        self.client = _app()

    def _headers_com_permissao(self, permissoes):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            token = rbac.gerar_token_sessao(11, "u@x.com", "Gerente")
            return {"Authorization": f"Bearer {token}"}

    def test_listar_depara_exige_estoque_ver(self):
        headers = self._headers_com_permissao([])
        with patch("routes.i9logic.requer_permissao", side_effect=lambda cod: (lambda f: f)), \
             patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.get("/api/integrations/i9logic/depara", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_listar_depara_com_permissao_libera(self):
        headers = self._headers_com_permissao(["estoque.ver"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.listar_mapeamentos", return_value=[{"id": 1}]) as mock_listar:
            r = self.client.get("/api/integrations/i9logic/depara", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["data"], [{"id": 1}])
        mock_listar.assert_called_once()

    def test_coletar_exige_estoque_editar(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.post("/api/integrations/i9logic/coletar", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_coletar_com_permissao_dispara_job(self):
        headers = self._headers_com_permissao(["estoque.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.executar_coleta_todas_filiais", return_value={"ok": True}) as mock_coleta:
            r = self.client.post("/api/integrations/i9logic/coletar", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_coleta.assert_called_once()

    def test_resolver_divergencia_exige_estoque_editar(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.post("/api/integrations/i9logic/divergencias/1/resolver", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_ajustar_divergencia_exige_estoque_editar(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.post("/api/integrations/i9logic/divergencias/1/ajustar", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_ajustar_divergencia_com_permissao_chama_aplicar_ajuste(self):
        headers = self._headers_com_permissao(["estoque.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.aplicar_ajuste_divergencia", return_value={"ok": True}) as mock_ajustar:
            r = self.client.post("/api/integrations/i9logic/divergencias/1/ajustar", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_ajustar.assert_called_once()
        self.assertEqual(mock_ajustar.call_args[0][0], 1)
```

Nota sobre o padrão de teste de permissão: veja `hermes_agents/tests/test_chat.py` (classe `TestChatRotasPermissao`) pro padrão exato já usado no projeto — se `core.rbac.requer_permissao` verificar permissão via alguma outra função interna (não `usuario_tem_permissao`), ajuste o nome do patch pra bater com a implementação real de `core/rbac.py` (rode `grep -n "def requer_permissao" -A 15 hermes_agents/core/rbac.py` primeiro pra confirmar).

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v -k TestRotasI9Logic`
Expected: FAIL — `ModuleNotFoundError: No module named 'routes.i9logic'`.

- [ ] **Step 3: Criar as rotas**

Criar `hermes_agents/routes/i9logic.py`:

```python
"""Rotas REST da Reconciliacao i9Logic — /api/integrations/i9logic/*"""
from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao, usuario_atual_da_request
from core.i9logic import (
    criar_mapeamento, listar_mapeamentos, executar_matching_automatico,
    executar_coleta_todas_filiais, listar_itens_para_revisao, marcar_revisado,
    aplicar_ajuste_divergencia, comparar_com_athena, seed_inicial,
)

i9logic_bp = Blueprint("i9logic", __name__, url_prefix="/api/integrations/i9logic")


@i9logic_bp.route("/depara", methods=["GET"])
def i9logic_listar_depara():
    @requer_permissao("estoque.ver")
    def _go():
        return jsonify({"data": listar_mapeamentos(request.args.get("tipo"))})
    return _go()


@i9logic_bp.route("/depara", methods=["POST"])
def i9logic_criar_depara():
    @requer_permissao("estoque.editar")
    def _go():
        dados = request.json or {}
        return jsonify(criar_mapeamento(
            dados.get("tipo", ""), dados.get("id_i9logic", ""), dados.get("codigo_athena", "")))
    return _go()


@i9logic_bp.route("/depara/matching", methods=["POST"])
def i9logic_matching_automatico():
    @requer_permissao("estoque.editar")
    def _go():
        dados = request.json or {}
        return jsonify(executar_matching_automatico(
            dados.get("tipo", ""), dados.get("pares", [])))
    return _go()


@i9logic_bp.route("/coletar", methods=["POST"])
def i9logic_coletar():
    @requer_permissao("estoque.editar")
    def _go():
        return jsonify(executar_coleta_todas_filiais())
    return _go()


@i9logic_bp.route("/divergencias", methods=["GET"])
def i9logic_listar_divergencias():
    @requer_permissao("estoque.ver")
    def _go():
        return jsonify({"data": listar_itens_para_revisao()})
    return _go()


@i9logic_bp.route("/divergencias/<int:snapshot_id>/resolver", methods=["POST"])
def i9logic_resolver_divergencia(snapshot_id):
    """Aceita a divergencia como conhecida — so' marca revisado, nunca ajusta saldo."""
    @requer_permissao("estoque.editar")
    def _go():
        return jsonify(marcar_revisado(snapshot_id))
    return _go()


@i9logic_bp.route("/divergencias/<int:snapshot_id>/ajustar", methods=["POST"])
def i9logic_ajustar_divergencia(snapshot_id):
    """Ajusta o saldo Athena pro fisico coletado, via ledger formal (Fase 1)."""
    @requer_permissao("estoque.editar")
    def _go():
        usuario = usuario_atual_da_request()
        return jsonify(aplicar_ajuste_divergencia(snapshot_id, usuario.get("user_id"), usuario.get("nome", "")))
    return _go()


@i9logic_bp.route("/comparar", methods=["GET"])
def i9logic_comparar():
    @requer_permissao("estoque.ver")
    def _go():
        return jsonify(comparar_com_athena(request.args.get("sku", ""), request.args.get("loja", "")))
    return _go()


@i9logic_bp.route("/seed", methods=["POST"])
def i9logic_seed():
    @requer_permissao("estoque.editar")
    def _go():
        dados = request.json or {}
        usuario = usuario_atual_da_request()
        return jsonify(seed_inicial(
            dados.get("sku", ""), dados.get("loja", ""),
            usuario.get("user_id"), usuario.get("nome", "")))
    return _go()
```

Em `hermes_agents/athena_bridge.py`, localizar o bloco de imports de blueprints e a sequência de `app.register_blueprint(...)` (por volta da linha 228-247 — procure por `from routes.estoque import estoque_bp` como referência de onde ficam os imports, e `app.register_blueprint(estoque_bp)` como referência de onde fica o registro). Adicionar:

```python
from routes.i9logic import i9logic_bp
```

junto aos outros imports de `routes.*_bp`, e:

```python
app.register_blueprint(i9logic_bp)
```

junto aos outros `app.register_blueprint(...)` já existentes.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v`
Expected: PASS (todos os testes do arquivo).

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/routes/i9logic.py hermes_agents/athena_bridge.py hermes_agents/tests/test_i9logic.py
git commit -m "feat: rotas REST da reconciliacao i9Logic (de-para, coletar, divergencias, comparar, seed)"
```

---

### Task 9: Verificação final

**Files:** nenhum (task de validação, sem código novo).

- [ ] **Step 1: Suíte completa do backend**

Run: `python -m pytest hermes_agents/tests/ -q`
Expected: todos os testes passam (nenhuma regressão nos módulos que não mudaram; `test_i9logic.py` inteiro incluído, mais o teste novo em `test_estoque.py` se esse arquivo existir).

- [ ] **Step 2: Revisão manual rápida do fluxo**

Conferir manualmente (leitura de código):
- `de_para_i9logic` e `i9logic_estoque_snapshot` são criadas por `_ensure_tables()` em `core/i9logic.py`, chamada no import do módulo (mesmo padrão de `core/chat.py`).
- Nenhum bucket novo foi criado em `TIPOS_SALDO` (`core/estoque_saldos.py`) — confirmar que o arquivo não foi tocado por este plano.
- `seed_inicial` só é chamável via rota `estoque.editar`, nunca automático — não há chamada a `seed_inicial`/`entrada`/`ajustar_absoluto` em nenhum outro lugar deste plano fora do fluxo manual da rota `/seed`.
- `executar_coleta_todas_filiais` (job pesado, minutos de duração) não está registrado em `core/scheduler.py` — confirmar com `grep -rn "i9logic" hermes_agents/core/scheduler.py` (deve vir vazio).

Se algum problema for encontrado nesta revisão, corrigir e commitar antes de considerar a task concluída. Se tudo estiver certo, não há commit novo nesta task.
