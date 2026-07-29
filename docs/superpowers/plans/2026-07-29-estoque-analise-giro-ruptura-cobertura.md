# Estoque Análise (Giro/Ruptura/Cobertura) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir os 3 indicadores 100% `Math.random()` da tela `/estoque/analise` (Giro, Ruptura, Cobertura) por cálculo real sobre `estoque_lojas`, `vendas_itens`/`vendas_pedidos` e `produtos_loja`/`catalogo_produtos`.

**Architecture:** Novo módulo `core/estoque_analise.py` com 3 funções sync (`giro`, `ruptura`, `cobertura`) no mesmo padrão de `core/estoque_contagem.py` — usam `run_async`/`get_db` internamente, retornam `list[dict]`, nunca lançam exceção pro chamador. 3 rotas finas em `routes/estoque.py`. Frontend troca 3 chamadas de mock por `fetch` real via `lib/api.ts`, adiciona seletor de loja opcional.

**Tech Stack:** Flask + asyncpg (Postgres) no backend, Next.js/TypeScript no frontend, pytest com `unittest.mock.AsyncMock` pros testes.

## Global Constraints

- Spec de referência: `docs/superpowers/specs/2026-07-29-estoque-analise-giro-ruptura-cobertura-design.md`.
- Nenhum tipo TypeScript novo — `IndicadorGiro`/`IndicadorRuptura`/`IndicadorCobertura` já existem em `web/src/lib/types/domain.ts:383-410` e os 3 backends devem retornar exatamente esses campos (mesmo nome, mesmo tipo).
- Nenhuma tabela nova no banco — só leitura de tabelas existentes (`estoque_lojas`, `catalogo_produtos`, `produtos_loja`, `vendas_itens`, `vendas_pedidos`, `estoque_movimentacoes`, `lojas`).
- Todo `WHERE` com filtro de loja usa parâmetro posicional (`$1`, `$2`...) — nunca concatena valor de usuário direto na string SQL (só `int(dias)`/`int(limite)` já validados como int são interpolados via f-string, seguindo o padrão já usado em `core/estoque_contagem.py:64` e `routes/estoque.py`).
- Toda função pública de `core/estoque_analise.py` captura exceção e retorna `[]` — nunca deixa um erro de SQL virar 500 HTML pro frontend (mesmo padrão de `core/estoque_contagem.py::sugestoes`).

---

### Task 1: `core/estoque_analise.py::giro()`

**Files:**
- Create: `hermes_agents/core/estoque_analise.py`
- Test: `hermes_agents/tests/test_estoque_analise.py`

**Interfaces:**
- Consumes: `core.get_db`, `core.run_async` (já existentes, mesmo padrão de `core/estoque_contagem.py`).
- Produces: `giro(loja: str = "", dias: int = 30) -> list[dict]`, cada dict com chaves `sku, produto, saidas_30d, estoque_medio, giro, tendencia` (`tendencia` é `"up"|"down"|"stable"`). Tasks 2 e 3 não dependem desta função, mas seguem o mesmo arquivo/helper `_filtro_loja`.

- [ ] **Step 1: Escrever o arquivo com o helper compartilhado e a função `giro`**

```python
"""Analise de estoque — giro, ruptura e cobertura calculados sobre dado
real (estoque_lojas, vendas_itens, produtos_loja/catalogo_produtos).
Substitui os indicadores que a tela `/estoque/analise` gerava com
Math.random() no cliente (ver spec 2026-07-29-estoque-analise-*)."""
from datetime import date
from core import get_db, run_async

AGENT = "Estoque Analise"

# Tipos de estoque_movimentacoes que representam reabastecimento sem
# ambiguidade de sinal. "ajuste" e "devolucao" sao usados tanto pra
# entrada quanto pra saida no ledger hoje (ver core/estoque.py
# _MAPA_MOVIMENTO_ENTRADA/_MAPA_MOVIMENTO_SAIDA) — contar um "ajuste"
# como abastecimento estaria errado metade das vezes, entao ficam de fora.
TIPOS_ABASTECIMENTO = ("compra", "recebimento")


def _filtro_loja(coluna: str, loja: str, where: list, params: list):
    if loja:
        params.append(loja)
        where.append(f"{coluna} = ${len(params)}")


def giro(loja: str = "", dias: int = 30) -> list:
    """Giro = saidas do periodo / saldo atual. "Estoque medio" e' aproximado
    pelo saldo atual — nao ha snapshot diario de estoque no banco pra
    calcular media de verdade (limitacao declarada na spec)."""
    async def _go():
        db = await get_db()
        where_saldo = ["1=1"]
        params_saldo = []
        _filtro_loja("e.loja", loja, where_saldo, params_saldo)
        saldos = await db.fetch(f"""
            SELECT e.sku, c.descricao AS produto, SUM(e.quantidade) AS saldo_atual
            FROM estoque_lojas e
            JOIN catalogo_produtos c ON c.sku = e.sku
            WHERE {" AND ".join(where_saldo)}
            GROUP BY e.sku, c.descricao
        """, *params_saldo)

        where_vendas = ["vp.status != 'cancelado'", f"vp.data >= CURRENT_DATE - {int(dias) * 2}"]
        params_vendas = []
        if loja:
            params_vendas.append(loja)
            where_vendas.append(f"vp.loja_id = (SELECT id FROM lojas WHERE nome = ${len(params_vendas)})")
        vendas = await db.fetch(f"""
            SELECT vi.sku,
                   SUM(CASE WHEN vp.data >= CURRENT_DATE - {int(dias)} THEN vi.quantidade ELSE 0 END) AS saidas_periodo,
                   SUM(CASE WHEN vp.data < CURRENT_DATE - {int(dias)} THEN vi.quantidade ELSE 0 END) AS saidas_periodo_anterior
            FROM vendas_itens vi
            JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE {" AND ".join(where_vendas)}
            GROUP BY vi.sku
        """, *params_vendas)
        vendas_por_sku = {v["sku"]: v for v in vendas}

        out = []
        for s in saldos:
            v = vendas_por_sku.get(s["sku"], {})
            saidas = float(v.get("saidas_periodo") or 0)
            saidas_ant = float(v.get("saidas_periodo_anterior") or 0)
            saldo_atual = float(s["saldo_atual"] or 0)
            divisor = saldo_atual if saldo_atual > 0 else 1
            giro_val = round(saidas / divisor, 1)
            tendencia = "up" if saidas > saidas_ant else "down" if saidas < saidas_ant else "stable"
            out.append({
                "sku": s["sku"], "produto": s["produto"],
                "saidas_30d": int(saidas), "estoque_medio": int(saldo_atual),
                "giro": giro_val, "tendencia": tendencia,
            })
        return out
    try:
        return run_async(_go())
    except Exception:
        return []
```

- [ ] **Step 2: Escrever o teste (RED) — saída zero não quebra e saldo zero não causa divisão por zero**

```python
"""Testes de core/estoque_analise.py — giro/ruptura/cobertura sobre dado
real (asyncpg mockado, sem banco de verdade)."""
import sys, os, unittest
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

import core.estoque_analise as analise


class TestGiro(unittest.TestCase):
    def test_sem_venda_no_periodo_giro_zero_sem_dividir_por_zero(self):
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                return [{"sku": "ABC-1", "produto": "Produto ABC", "saldo_atual": 0}]
            if "FROM vendas_itens" in q:
                return []
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.giro()
        self.assertEqual(resultado, [{
            "sku": "ABC-1", "produto": "Produto ABC",
            "saidas_30d": 0, "estoque_medio": 0, "giro": 0.0, "tendencia": "stable",
        }])
```

- [ ] **Step 3: Rodar o teste e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_analise.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.estoque_analise'` (o arquivo do Step 1 ainda não foi salvo em disco nesse ponto do ciclo TDD real; se já salvou junto, deve passar direto — nesse caso confirme rodando e siga pro Step 4).

- [ ] **Step 4: Confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_analise.py -v`
Expected: PASS

- [ ] **Step 5: Segundo teste — tendência compara período atual vs anterior**

Adicionar em `TestGiro`:

```python
    def test_tendencia_up_quando_periodo_atual_vende_mais(self):
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                return [{"sku": "ABC-1", "produto": "Produto ABC", "saldo_atual": 50}]
            if "FROM vendas_itens" in q:
                return [{"sku": "ABC-1", "saidas_periodo": 40, "saidas_periodo_anterior": 10}]
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.giro()
        self.assertEqual(resultado[0]["tendencia"], "up")
        self.assertEqual(resultado[0]["giro"], 0.8)
```

Run: `cd hermes_agents && python -m pytest tests/test_estoque_analise.py -v`
Expected: PASS (2 testes)

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/estoque_analise.py hermes_agents/tests/test_estoque_analise.py
git commit -m "feat: core/estoque_analise.giro() com dado real (substitui mock)"
```

---

### Task 2: `core/estoque_analise.py::ruptura()`

**Files:**
- Modify: `hermes_agents/core/estoque_analise.py`
- Test: `hermes_agents/tests/test_estoque_analise.py`

**Interfaces:**
- Consumes: `_filtro_loja` (Task 1), `TIPOS_ABASTECIMENTO` (Task 1).
- Produces: `ruptura(loja: str = "") -> list[dict]`, cada dict com `sku, produto, dias_ruptura, vendas_perdidas_estimadas, impacto_receita, ultimo_abastecimento` (`ultimo_abastecimento` é `str | None`, formato `YYYY-MM-DD`).

- [ ] **Step 1: Escrever o teste (RED) — SKU sem venda histórica não quebra, sem SKU em ruptura retorna lista vazia**

Adicionar em `hermes_agents/tests/test_estoque_analise.py`:

```python
class TestRuptura(unittest.TestCase):
    def test_nenhum_sku_abaixo_do_minimo_retorna_vazio(self):
        async def fake_fetch(query, *params):
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.ruptura()
        self.assertEqual(resultado, [])

    def test_sku_sem_abastecimento_registrado_nao_quebra_e_nao_inventa_numero(self):
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "estoque_movimentacoes" in q:
                return []  # nunca reabastecido
            return [{"sku": "XYZ-9", "produto": "Produto XYZ", "saldo_atual": 2, "estoque_minimo": 10}]
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.ruptura()
        self.assertEqual(resultado, [{
            "sku": "XYZ-9", "produto": "Produto XYZ",
            "dias_ruptura": 0, "vendas_perdidas_estimadas": 0,
            "impacto_receita": 0.0, "ultimo_abastecimento": None,
        }])
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_analise.py::TestRuptura -v`
Expected: FAIL — `AttributeError: module 'core.estoque_analise' has no attribute 'ruptura'`

- [ ] **Step 3: Implementar `ruptura()`**

Adicionar em `hermes_agents/core/estoque_analise.py`, depois de `giro`:

```python
def ruptura(loja: str = "") -> list:
    """SKU com saldo < minimo efetivo. Com loja filtrada, minimo efetivo e'
    o override de produtos_loja pra aquela loja (fallback catalogo mestre).
    Agregado (sem filtro), compara o total contra o minimo global do
    catalogo — somar minimos diferentes por loja nao teria um limiar unico
    que faca sentido."""
    async def _go():
        db = await get_db()
        where = ["1=1"]
        params = []
        if loja:
            params.append(loja)
            where.append(f"e.loja = ${len(params)}")
        if loja:
            rows = await db.fetch(f"""
                SELECT e.sku, c.descricao AS produto, SUM(e.quantidade) AS saldo_atual,
                       COALESCE(MAX(pl.estoque_minimo), MAX(c.estoque_minimo), 0) AS estoque_minimo
                FROM estoque_lojas e
                JOIN catalogo_produtos c ON c.sku = e.sku
                LEFT JOIN produtos_loja pl ON pl.sku = e.sku AND pl.loja = e.loja
                WHERE {" AND ".join(where)}
                GROUP BY e.sku, c.descricao
                HAVING SUM(e.quantidade) < COALESCE(MAX(pl.estoque_minimo), MAX(c.estoque_minimo), 0)
            """, *params)
        else:
            rows = await db.fetch(f"""
                SELECT e.sku, c.descricao AS produto, SUM(e.quantidade) AS saldo_atual,
                       COALESCE(c.estoque_minimo, 0) AS estoque_minimo
                FROM estoque_lojas e
                JOIN catalogo_produtos c ON c.sku = e.sku
                WHERE {" AND ".join(where)}
                GROUP BY e.sku, c.descricao, c.estoque_minimo
                HAVING SUM(e.quantidade) < COALESCE(c.estoque_minimo, 0)
            """, *params)
        if not rows:
            return []

        skus = [r["sku"] for r in rows]
        abastecimento = await db.fetch("""
            SELECT DISTINCT ON (sku) sku, data
            FROM estoque_movimentacoes
            WHERE sku = ANY($1) AND tipo = ANY($2)
            ORDER BY sku, data DESC
        """, skus, list(TIPOS_ABASTECIMENTO))
        abastecimento_por_sku = {a["sku"]: a["data"] for a in abastecimento}

        out = []
        for r in rows:
            ultimo = abastecimento_por_sku.get(r["sku"])
            if ultimo is None:
                out.append({
                    "sku": r["sku"], "produto": r["produto"],
                    "dias_ruptura": 0, "vendas_perdidas_estimadas": 0,
                    "impacto_receita": 0.0, "ultimo_abastecimento": None,
                })
                continue
            dias_ruptura = (date.today() - ultimo.date()).days
            # Velocidade media de venda do SKU nos 30d ANTES do ultimo
            # abastecimento (decisao da spec) — nao a media generica.
            vendas = await db.fetchrow("""
                SELECT COALESCE(SUM(vi.quantidade), 0) AS qtd, COALESCE(AVG(vi.valor_unitario), 0) AS preco_medio
                FROM vendas_itens vi
                JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
                WHERE vi.sku = $1 AND vp.status != 'cancelado'
                  AND vp.data >= $2::timestamp - INTERVAL '30 days' AND vp.data < $2
            """, r["sku"], ultimo)
            velocidade_diaria = float(vendas["qtd"] or 0) / 30
            vendas_perdidas = round(velocidade_diaria * dias_ruptura, 1)
            impacto = round(vendas_perdidas * float(vendas["preco_medio"] or 0), 2)
            out.append({
                "sku": r["sku"], "produto": r["produto"],
                "dias_ruptura": dias_ruptura,
                "vendas_perdidas_estimadas": vendas_perdidas,
                "impacto_receita": impacto,
                "ultimo_abastecimento": ultimo.date().isoformat(),
            })
        return out
    try:
        return run_async(_go())
    except Exception:
        return []
```

Nota: lista de ruptura é, na prática, pequena (SKUs abaixo do mínimo) — o `fetchrow` por SKU dentro do loop é aceitável aqui; não vale a complexidade extra de um `LATERAL JOIN` pra um N pequeno.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_analise.py::TestRuptura -v`
Expected: PASS (2 testes)

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/estoque_analise.py hermes_agents/tests/test_estoque_analise.py
git commit -m "feat: core/estoque_analise.ruptura() com dado real (substitui mock)"
```

---

### Task 3: `core/estoque_analise.py::cobertura()`

**Files:**
- Modify: `hermes_agents/core/estoque_analise.py`
- Test: `hermes_agents/tests/test_estoque_analise.py`

**Interfaces:**
- Consumes: nenhuma das anteriores diretamente (função independente no mesmo arquivo).
- Produces: `cobertura(loja: str = "") -> list[dict]`, cada dict com `sku, produto, estoque_atual, demanda_diaria_media, cobertura_dias, estoque_minimo, estoque_maximo, status` (`status` é `"excesso"|"normal"|"baixo"|"critico"`).

- [ ] **Step 1: Escrever o teste (RED) — sem mínimo/máximo cai em "normal", demanda zero não crasha**

Adicionar em `hermes_agents/tests/test_estoque_analise.py`:

```python
class TestCobertura(unittest.TestCase):
    def test_sem_minimo_maximo_e_sem_demanda_cai_em_normal(self):
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                return [{"sku": "QQQ-1", "produto": "Produto QQQ", "estoque_atual": 50,
                          "estoque_minimo": 0, "estoque_maximo": 0}]
            if "FROM vendas_itens" in q:
                return []
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.cobertura()
        self.assertEqual(resultado, [{
            "sku": "QQQ-1", "produto": "Produto QQQ",
            "estoque_atual": 50, "demanda_diaria_media": 0.0, "cobertura_dias": 0,
            "estoque_minimo": 0, "estoque_maximo": 0, "status": "normal",
        }])

    def test_saldo_zero_e_critico(self):
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                return [{"sku": "RRR-1", "produto": "Produto RRR", "estoque_atual": 0,
                          "estoque_minimo": 10, "estoque_maximo": 100}]
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.cobertura()
        self.assertEqual(resultado[0]["status"], "critico")
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_analise.py::TestCobertura -v`
Expected: FAIL — `AttributeError: module 'core.estoque_analise' has no attribute 'cobertura'`

- [ ] **Step 3: Implementar `cobertura()`**

Adicionar em `hermes_agents/core/estoque_analise.py`, depois de `ruptura`:

```python
def cobertura(loja: str = "") -> list:
    """Cobertura = saldo atual / demanda diaria media (saidas 30d / 30).
    Sem demanda no periodo, cobertura fica None internamente ("sem venda
    recente", nao Infinity nem crash) e sai como 0 no payload."""
    async def _go():
        db = await get_db()
        where = ["1=1"]
        params = []
        if loja:
            params.append(loja)
            where.append(f"e.loja = ${len(params)}")
        if loja:
            saldos = await db.fetch(f"""
                SELECT e.sku, c.descricao AS produto, SUM(e.quantidade) AS estoque_atual,
                       COALESCE(MAX(pl.estoque_minimo), MAX(c.estoque_minimo), 0) AS estoque_minimo,
                       COALESCE(MAX(pl.estoque_maximo), MAX(c.estoque_maximo), 0) AS estoque_maximo
                FROM estoque_lojas e
                JOIN catalogo_produtos c ON c.sku = e.sku
                LEFT JOIN produtos_loja pl ON pl.sku = e.sku AND pl.loja = e.loja
                WHERE {" AND ".join(where)}
                GROUP BY e.sku, c.descricao
            """, *params)
        else:
            saldos = await db.fetch(f"""
                SELECT e.sku, c.descricao AS produto, SUM(e.quantidade) AS estoque_atual,
                       COALESCE(c.estoque_minimo, 0) AS estoque_minimo,
                       COALESCE(c.estoque_maximo, 0) AS estoque_maximo
                FROM estoque_lojas e
                JOIN catalogo_produtos c ON c.sku = e.sku
                WHERE {" AND ".join(where)}
                GROUP BY e.sku, c.descricao, c.estoque_minimo, c.estoque_maximo
            """, *params)

        where_v = ["vp.status != 'cancelado'", "vp.data >= CURRENT_DATE - 30"]
        params_v = []
        if loja:
            params_v.append(loja)
            where_v.append(f"vp.loja_id = (SELECT id FROM lojas WHERE nome = ${len(params_v)})")
        vendas = await db.fetch(f"""
            SELECT vi.sku, SUM(vi.quantidade) AS saidas_30d
            FROM vendas_itens vi
            JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE {" AND ".join(where_v)}
            GROUP BY vi.sku
        """, *params_v)
        vendas_por_sku = {v["sku"]: float(v["saidas_30d"] or 0) for v in vendas}

        out = []
        for s in saldos:
            estoque_atual = float(s["estoque_atual"] or 0)
            minimo = float(s["estoque_minimo"] or 0)
            maximo = float(s["estoque_maximo"] or 0)
            demanda_diaria = vendas_por_sku.get(s["sku"], 0.0) / 30
            cobertura_dias = round(estoque_atual / demanda_diaria) if demanda_diaria > 0 else None

            if estoque_atual <= 0:
                status = "critico"
            elif minimo > 0 and estoque_atual < minimo:
                status = "baixo"
            elif maximo > 0 and estoque_atual > maximo:
                status = "excesso"
            elif cobertura_dias is not None and cobertura_dias < 7:
                status = "baixo"
            else:
                status = "normal"

            out.append({
                "sku": s["sku"], "produto": s["produto"],
                "estoque_atual": int(estoque_atual),
                "demanda_diaria_media": round(demanda_diaria, 1),
                "cobertura_dias": cobertura_dias if cobertura_dias is not None else 0,
                "estoque_minimo": int(minimo), "estoque_maximo": int(maximo),
                "status": status,
            })
        return out
    try:
        return run_async(_go())
    except Exception:
        return []
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_analise.py -v`
Expected: PASS (6 testes no total do arquivo)

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/estoque_analise.py hermes_agents/tests/test_estoque_analise.py
git commit -m "feat: core/estoque_analise.cobertura() com dado real (substitui mock)"
```

---

### Task 4: Rotas Flask

**Files:**
- Modify: `hermes_agents/routes/estoque.py`

**Interfaces:**
- Consumes: `core.estoque_analise.giro/ruptura/cobertura` (Tasks 1-3).
- Produces: `GET /api/estoque/analise/giro?loja=&dias=30`, `GET /api/estoque/analise/ruptura?loja=`, `GET /api/estoque/analise/cobertura?loja=` — todas retornam `{"data": [...]}`.

- [ ] **Step 1: Adicionar as 3 rotas**

Em `hermes_agents/routes/estoque.py`, logo depois da rota `estoque_relatorio_discrepancias` (linha ~409):

```python
@estoque_bp.route('/analise/giro', methods=['GET'])
def estoque_analise_giro():
    from core.estoque_analise import giro
    loja = request.args.get("loja", "")
    dias = request.args.get("dias", 30, type=int)
    return jsonify({"data": giro(loja, dias)})


@estoque_bp.route('/analise/ruptura', methods=['GET'])
def estoque_analise_ruptura():
    from core.estoque_analise import ruptura
    loja = request.args.get("loja", "")
    return jsonify({"data": ruptura(loja)})


@estoque_bp.route('/analise/cobertura', methods=['GET'])
def estoque_analise_cobertura():
    from core.estoque_analise import cobertura
    loja = request.args.get("loja", "")
    return jsonify({"data": cobertura(loja)})
```

- [ ] **Step 2: Smoke test das 3 rotas via Flask test client**

Criar `hermes_agents/tests/test_estoque_analise_rotas.py`:

```python
"""Smoke test das rotas /api/estoque/analise/* — confirma que o blueprint
esta registrado e devolve JSON valido (core ja e' testado em
test_estoque_analise.py; aqui so' testa o fio rota -> core -> jsonify)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch


class TestRotasAnalise(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        from routes.estoque import estoque_bp
        app = Flask(__name__)
        app.register_blueprint(estoque_bp)
        self.client = app.test_client()

    def test_giro_retorna_200_e_chave_data(self):
        with patch("core.estoque_analise.giro", return_value=[{"sku": "A"}]):
            r = self.client.get("/api/estoque/analise/giro")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"data": [{"sku": "A"}]})

    def test_ruptura_retorna_200_e_chave_data(self):
        with patch("core.estoque_analise.ruptura", return_value=[]):
            r = self.client.get("/api/estoque/analise/ruptura?loja=Principal")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"data": []})

    def test_cobertura_retorna_200_e_chave_data(self):
        with patch("core.estoque_analise.cobertura", return_value=[{"sku": "B"}]):
            r = self.client.get("/api/estoque/analise/cobertura")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"data": [{"sku": "B"}]})
```

- [ ] **Step 3: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_estoque_analise_rotas.py -v`
Expected: PASS (3 testes)

- [ ] **Step 4: Commit**

```bash
git add hermes_agents/routes/estoque.py hermes_agents/tests/test_estoque_analise_rotas.py
git commit -m "feat: rotas GET /api/estoque/analise/{giro,ruptura,cobertura}"
```

---

### Task 5: Cliente frontend (`lib/api.ts`)

**Files:**
- Modify: `web/src/lib/api.ts`

**Interfaces:**
- Consumes: rotas da Task 4.
- Produces: `api.estoqueAnaliseGiro(loja?, dias?)`, `api.estoqueAnaliseRuptura(loja?)`, `api.estoqueAnaliseCobertura(loja?)` — cada uma retorna `Promise<{ data: IndicadorGiro[] | IndicadorRuptura[] | IndicadorCobertura[] }>`. Task 6 depende exatamente desses 3 nomes.

- [ ] **Step 1: Adicionar os 3 tipos ao import existente de `@/lib/types/domain`**

Em `web/src/lib/api.ts:54-70`, no bloco `import type { ... } from "@/lib/types/domain";`, adicionar `IndicadorGiro, IndicadorRuptura, IndicadorCobertura` à lista (ordem alfabética não importa, seguir o padrão já existente de um por linha).

- [ ] **Step 2: Adicionar as 3 funções no objeto `api`**

Em `web/src/lib/api.ts`, logo depois do bloco `estoqueContagemHistorico` (linha ~393):

```typescript
  // Estoque — analise (giro/ruptura/cobertura)
  estoqueAnaliseGiro: (loja?: string, dias = 30) =>
    request<{ data: IndicadorGiro[] }>(`/api/estoque/analise/giro?dias=${dias}${loja ? `&loja=${encodeURIComponent(loja)}` : ""}`),
  estoqueAnaliseRuptura: (loja?: string) =>
    request<{ data: IndicadorRuptura[] }>(`/api/estoque/analise/ruptura${loja ? `?loja=${encodeURIComponent(loja)}` : ""}`),
  estoqueAnaliseCobertura: (loja?: string) =>
    request<{ data: IndicadorCobertura[] }>(`/api/estoque/analise/cobertura${loja ? `?loja=${encodeURIComponent(loja)}` : ""}`),
```

- [ ] **Step 3: Verificar tipos**

Run: `cd web && npx tsc --noEmit`
Expected: sem erro novo relacionado a `api.ts` (o arquivo é grande — confirme que nenhuma linha nova reportada é das que você acabou de adicionar).

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/api.ts
git commit -m "feat: cliente api.ts para /api/estoque/analise/*"
```

---

### Task 6: Frontend — `estoque/analise/page.tsx` com dado real

**Files:**
- Modify: `web/src/app/estoque/analise/page.tsx`

**Interfaces:**
- Consumes: `api.estoqueAnaliseGiro/Ruptura/Cobertura` (Task 5), `useStore` de `@/lib/store-context` (já existe, usado por `estoque/contagem/page.tsx`), `LoadingState`/`ErrorAlert` de `@/app/_components/` (já existem).
- Produces: nada consumido por outra task — é a última peça visível.

- [ ] **Step 1: Reescrever o arquivo**

Substituir todo o conteúdo de `web/src/app/estoque/analise/page.tsx`:

```tsx
"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import type { KpiMetric, Column } from "@/lib/types/ui";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import TabBar from "@/app/_components/TabBar";
import DataTable from "@/app/_components/DataTable";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import { api, type IndicadorGiro, type IndicadorRuptura, type IndicadorCobertura } from "@/lib/api";
import type { StatusBadgeVariant } from "@/lib/types/ui";
import { formatCurrency } from "../types";
import { useStore } from "@/lib/store-context";

const TABS = [
  { key: "giro", label: "Giro de Estoque" },
  { key: "ruptura", label: "Ruptura" },
  { key: "cobertura", label: "Cobertura" },
];

const GIRO_COLUMNS: Column<IndicadorGiro>[] = [
  { key: "sku", label: "SKU", render: (v) => <span className="font-mono text-neutral-300 text-[11px]">{v as string}</span> },
  { key: "produto", label: "Produto" },
  { key: "saidas_30d", label: "Saídas (30d)", align: "center", render: (v) => <span className="text-neutral-200">{v as number}</span> },
  { key: "estoque_medio", label: "Estoque Médio", align: "center" },
  {
    key: "giro", label: "Giro", align: "center",
    render: (v) => {
      const g = v as number;
      return <span className={`font-medium ${g >= 3 ? "text-emerald-400" : g >= 1 ? "text-amber-400" : "text-red-400"}`}>{g}x</span>;
    },
  },
  {
    key: "tendencia", label: "Tendência", align: "center",
    render: (v, row) => {
      const t = row.tendencia;
      return <span className={t === "up" ? "text-emerald-400" : t === "down" ? "text-red-400" : "text-neutral-400"}>
        {t === "up" ? "▲" : t === "down" ? "▼" : "—"}
      </span>;
    },
  },
];

const RUPTURA_COLUMNS: Column<IndicadorRuptura>[] = [
  { key: "sku", label: "SKU", render: (v) => <span className="font-mono text-neutral-300 text-[11px]">{v as string}</span> },
  { key: "produto", label: "Produto" },
  { key: "dias_ruptura", label: "Dias em Ruptura", align: "center", render: (v) => <span className="text-red-400 font-medium">{v as number}</span> },
  { key: "vendas_perdidas_estimadas", label: "Vendas Perdidas", align: "center" },
  { key: "impacto_receita", label: "Impacto Receita", align: "right", render: (v) => <span className="font-mono text-red-400">{formatCurrency(v as number)}</span> },
  { key: "ultimo_abastecimento", label: "Último Abastec.", render: (v) => v ? <span className="text-neutral-500">{(v as string)?.split("-").reverse().join("/")}</span> : <span className="text-neutral-600">—</span> },
];

const COBERTURA_COLUMNS: Column<IndicadorCobertura>[] = [
  { key: "sku", label: "SKU", render: (v) => <span className="font-mono text-neutral-300 text-[11px]">{v as string}</span> },
  { key: "produto", label: "Produto" },
  { key: "estoque_atual", label: "Estoque", align: "center" },
  { key: "demanda_diaria_media", label: "Demanda/dia", align: "center", render: (v) => <span className="text-neutral-300">{v as number}</span> },
  {
    key: "cobertura_dias", label: "Cobertura", align: "center",
    render: (v) => {
      const d = v as number;
      return <span className={`font-medium ${d > 30 ? "text-emerald-400" : d >= 7 ? "text-amber-400" : "text-red-400"}`}>{d} dias</span>;
    },
  },
  { key: "estoque_minimo", label: "Mínimo", align: "center" },
  { key: "estoque_maximo", label: "Máximo", align: "center" },
  {
    key: "status", label: "Status",
    render: (v, row) => {
      const s = row.status;
      const variant: StatusBadgeVariant = s === "excesso" ? "neutral" : s === "normal" ? "success" : s === "baixo" ? "warning" : "danger";
      const label = s === "excesso" ? "Excesso" : s === "normal" ? "Normal" : s === "baixo" ? "Baixo" : "Crítico";
      return <StatusBadge label={label} variant={variant} />;
    },
  },
];

export default function AnalisePage() {
  const { lojas } = useStore();
  const [loja, setLoja] = useState("");
  const [tab, setTab] = useState("giro");
  const [giro, setGiro] = useState<IndicadorGiro[]>([]);
  const [ruptura, setRuptura] = useState<IndicadorRuptura[]>([]);
  const [cobertura, setCobertura] = useState<IndicadorCobertura[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");

  const carregar = useCallback(async () => {
    setLoading(true);
    setErro("");
    try {
      const [g, r, c] = await Promise.all([
        api.estoqueAnaliseGiro(loja || undefined),
        api.estoqueAnaliseRuptura(loja || undefined),
        api.estoqueAnaliseCobertura(loja || undefined),
      ]);
      setGiro(g.data || []);
      setRuptura(r.data || []);
      setCobertura(c.data || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar indicadores de estoque");
    } finally {
      setLoading(false);
    }
  }, [loja]);

  useEffect(() => { carregar(); }, [carregar]);

  const giroMedio = giro.length ? Math.round(giro.reduce((s, g) => s + g.giro, 0) / giro.length * 10) / 10 : 0;
  const totalRuptura = ruptura.length;
  const impactoRuptura = ruptura.reduce((s, r) => s + r.impacto_receita, 0);
  const coberturaMedia = cobertura.length ? Math.round(cobertura.reduce((s, c) => s + c.cobertura_dias, 0) / cobertura.length) : 0;
  const criticos = cobertura.filter(c => c.status === "critico" || c.status === "baixo").length;

  const kpis: KpiMetric[] = [
    { label: "Giro Médio (30d)", value: `${giroMedio}x`, color: giroMedio >= 2 ? "text-emerald-400" : "text-amber-400" },
    { label: "SKUs em Ruptura", value: String(totalRuptura), color: totalRuptura > 0 ? "text-red-400" : "text-emerald-400" },
    { label: "Impacto Ruptura", value: formatCurrency(impactoRuptura), color: "text-red-400" },
    { label: "Cobertura Média", value: `${coberturaMedia} dias`, color: "text-blue-400" },
    { label: "SKUs Críticos/Baixos", value: String(criticos), color: criticos > 5 ? "text-red-400" : "text-amber-400" },
  ];

  return (
    <div className="p-6 space-y-4">
      <PageHeader title="Análise de Estoque" subtitle="Indicadores de giro, ruptura e cobertura para tomada de decisão" />

      <div className="flex items-center gap-2 max-w-xs">
        <label className="text-[10px] text-neutral-500 uppercase tracking-wider shrink-0">Loja</label>
        <select value={loja} onChange={e => setLoja(e.target.value)}
          className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500">
          <option value="">Todas as lojas</option>
          {lojas.map(l => <option key={l.id} value={l.nome}>{l.nome}</option>)}
        </select>
      </div>

      {erro && <ErrorAlert message={erro} />}

      {loading ? <LoadingState message="Calculando indicadores..." /> : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {kpis.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
          </div>

          <TabBar tabs={TABS} active={tab} onChange={setTab} />

          {tab === "giro" && (
            <div className="space-y-1">
              <p className="text-xs text-neutral-500">Giro = Saídas no período / Estoque médio (aproximado pelo saldo atual). Acima de 3x é saudável.</p>
              <DataTable columns={GIRO_COLUMNS} data={giro} keyExtractor={g => g.sku} countLabel={`${giro.length} SKUs`} />
            </div>
          )}

          {tab === "ruptura" && (
            <div className="space-y-1">
              {totalRuptura === 0 ? (
                <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center">
                  <p className="text-emerald-400 text-sm">✓ Nenhum SKU em ruptura no momento</p>
                </div>
              ) : (
                <>
                  <p className="text-xs text-neutral-500">SKUs com estoque abaixo do mínimo. Vendas perdidas estimadas pela velocidade de venda pré-ruptura.</p>
                  <DataTable columns={RUPTURA_COLUMNS} data={ruptura} keyExtractor={r => r.sku} countLabel={`${ruptura.length} SKUs em ruptura`} />
                </>
              )}
            </div>
          )}

          {tab === "cobertura" && (
            <div className="space-y-1">
              <p className="text-xs text-neutral-500">Cobertura = Estoque atual / Demanda diária média. Ideal: 7-30 dias.</p>
              <DataTable columns={COBERTURA_COLUMNS} data={cobertura} keyExtractor={c => c.sku} countLabel={`${cobertura.length} SKUs`} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verificar tipos**

Run: `cd web && npx tsc --noEmit`
Expected: sem erro em `estoque/analise/page.tsx`.

- [ ] **Step 3: Commit**

```bash
git add web/src/app/estoque/analise/page.tsx
git commit -m "feat: estoque/analise usa dado real (giro/ruptura/cobertura), seletor de loja"
```

---

### Task 7: Limpeza do mock morto + validação final

**Files:**
- Modify: `web/src/app/estoque/data/custos.ts`

**Interfaces:**
- Consumes: nada.
- Produces: nada (limpeza).

- [ ] **Step 1: Remover as 3 funções geradoras e os imports de tipo que ficaram sem uso**

Em `web/src/app/estoque/data/custos.ts`:
- Remover `gerarIndicadoresGiro`, `gerarIndicadoresRuptura`, `gerarIndicadoresCobertura` (linhas 50-92 do arquivo original).
- No import do topo (`import type { CurvaABCItem, IndicadorGiro, IndicadorRuptura, IndicadorCobertura } from "@/lib/types/domain";`), remover `IndicadorGiro, IndicadorRuptura, IndicadorCobertura`, mantendo só `CurvaABCItem` (ainda usado por `gerarCurvaABC`, que fica — é uma feature separada, fora do escopo desta spec).
- `SKUS`, `SkuInfo`, `gerarCurvaABC`, `ABC_COLORS` continuam intactos.

- [ ] **Step 2: Verificar que nada mais importa as 3 funções removidas**

Run: `cd web && grep -rn "gerarIndicadoresGiro\|gerarIndicadoresRuptura\|gerarIndicadoresCobertura" src/`
Expected: nenhum resultado.

- [ ] **Step 3: Rodar suite completa do backend**

Run: `cd hermes_agents && python -m pytest -q --ignore=test_fase2.py --ignore=test_fase3.py --ignore=test_fase_multiloja.py`
Expected: todos os testes existentes continuam passando, mais os novos desta feature (giro/ruptura/cobertura + rotas).

- [ ] **Step 4: Build do frontend**

Run: `cd web && npm run build`
Expected: build limpo, sem erro de tipo ou de import quebrado.

- [ ] **Step 5: Commit final**

```bash
git add web/src/app/estoque/data/custos.ts
git commit -m "chore: remove geradores mock de giro/ruptura/cobertura, ja substituidos por dado real"
```

---

## Self-Review

**Cobertura da spec:** escopo agregado+filtro de loja (Task 6), fórmula de giro com limitação declarada (Task 1 + nota na UI), fórmula de ruptura com velocidade pré-abastecimento (Task 2), fórmula de cobertura com status (Task 3), API (Task 4), frontend com loading/erro (Task 6), testes por caso de borda (Tasks 1-4), fora de escopo respeitado (nenhuma task toca `/sync/processar`, depósitos, custos ou inventário). Sem lacuna.

**Desvio da spec registrado aqui:** a spec descrevia "dias em ruptura" como "hoje − data da movimentação que derrubou o saldo abaixo do mínimo". Na implementação (Task 2) isso virou "hoje − data do último abastecimento claro (compra/recebimento)", porque `estoque_movimentacoes.tipo` usa `"ajuste"` e `"devolucao"` tanto pra entrada quanto pra saída (schema não guarda sinal) — reconstruir o cruzamento exato do mínimo exigiria assumir um sinal que o dado não garante. `ultimo_abastecimento` já era um campo da spec original; esta mudança só reaproveita o mesmo dado pra `dias_ruptura` em vez de inventar uma segunda fonte. Efeito observável pro usuário: nenhum — a UI mostra o número, não a definição interna.

**Consistência de tipos:** `giro`/`ruptura`/`cobertura` (core) → `{"data": [...]}` (rotas) → `api.estoqueAnalise*` (Task 5) → `IndicadorGiro/Ruptura/Cobertura` (Task 6) — mesmos nomes de campo em todas as camadas, conferido contra `web/src/lib/types/domain.ts:383-410`.
