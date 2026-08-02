# Financeiro — Caixa, Cofre e Relatórios por Loja — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estender o fechamento de caixa do PDV com contagem de cédulas e conferência por maquineta, adicionar um módulo "Cofre" por loja no Financeiro (alimentado automaticamente por sangrias de caixa), e adicionar 2 relatórios read-only por loja/dia.

**Architecture:** PDV continua dono da verdade transacional (`pdv_caixas`). Financeiro ganha só a camada de categorização (Cofre) e relatório — mesmo papel que já tem com contas a pagar/receber e DRE. Nenhum dado de venda/caixa é duplicado; tudo é lido por referência (`caixa_id`, `loja_id`) ou agregado em query.

**Tech Stack:** Flask + asyncpg (`hermes_agents/`), Next.js/React/TypeScript (`web/`). Testes com `unittest` + mocks (`unittest.mock.patch`), sem banco real.

## Global Constraints

- Não duplicar o conceito de "caixa" — toda leitura de venda/pagamento do PDV é feita por query, nunca copiada pra tabela nova do Financeiro.
- `fin_cofre` é criado sob demanda (lazy) na primeira movimentação de uma loja — sem seed manual.
- Ajuste de cofre (`tipo=ajuste`) sempre exige `financeiro.aprovar` (ou PIN/crachá de gerente via `autorizar_com_permissao`), independente do valor — diferente do limite de R$5000 de pagamentos.
- Maquineta é texto livre (`VARCHAR(50)`, sem enum) — nunca hardcodar nomes de adquirente no schema ou no código.
- Não reabrir caixas fechados para creditar troco — o crédito no cofre fica só registrado, o próximo caixa reflete manualmente no `saldo_inicial`.
- Receita nos relatórios é só por forma de pagamento (PIX/Dinheiro/Cartão) — nunca por categoria de produto (fora de escopo, decisão consciente do spec).
- `valor_sistema` de conferência por maquineta é sempre recalculado no servidor a partir de `pdv_pagamentos` — nunca confiar no valor que o cliente manda.
- Fechamentos sem contagem/conferência (payload antigo, sem essas chaves) continuam funcionando exatamente como hoje — `diferenca` cai pro cálculo antigo (só dinheiro).
- Bugs mecânicos já mapeados do Financeiro existente (SQLi, RBAC ausente, status HTTP, schema drift `bling_id`/`origem`, botões sem `onClick`) são um trabalho separado, já concluído — não fazem parte deste plano.

---

## Fase 1 — PDV: fechamento de caixa mais rico

### Task 1: Schema — `pdv_caixa_contagem`, `pdv_caixa_conferencia`, `pdv_pagamentos.maquineta`

**Files:**
- Modify: `hermes_agents/core/pdv.py` (`_ensure_tables()`, dentro do bloco que hoje cria `pdv_pagamentos`/`pdv_sangrias`/`pdv_suprimentos`, linhas 271–286)
- Test: Create `hermes_agents/tests/test_pdv_caixa_fase1.py`

**Interfaces:**
- Produces: tabelas `pdv_caixa_contagem(id, caixa_id, denominacao, quantidade, subtotal)` e `pdv_caixa_conferencia(id, caixa_id, maquineta, forma_pagamento, valor_sistema, valor_conferido, diferenca)`; coluna `pdv_pagamentos.maquineta VARCHAR(50)` (nullable).

- [ ] **Step 1: Escrever o teste que falha**

```python
# hermes_agents/tests/test_pdv_caixa_fase1.py
"""Fase 1 — contagem de denominacao e conferencia por maquineta no fechamento de caixa."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch


class _SpyDB:
    def __init__(self):
        self.queries = []

    async def execute(self, query, *params):
        self.queries.append(" ".join(query.split()))
        return "OK"

    async def fetchval(self, query, *params):
        self.queries.append(" ".join(query.split()))
        return 0

    async def fetchrow(self, query, *params):
        self.queries.append(" ".join(query.split()))
        return None

    async def fetch(self, query, *params):
        self.queries.append(" ".join(query.split()))
        return []


async def _get_spy(db):
    return db


class TestSchemaFase1(unittest.TestCase):
    def test_ensure_tables_cria_contagem_conferencia_e_coluna_maquineta(self):
        import core.pdv as pdv
        spy = _SpyDB()
        with patch("core.pdv.get_db", side_effect=lambda: _get_spy(spy)):
            pdv._ensure_tables()
        joined = " ".join(spy.queries)
        self.assertIn("CREATE TABLE IF NOT EXISTS pdv_caixa_contagem", joined)
        self.assertIn("CREATE TABLE IF NOT EXISTS pdv_caixa_conferencia", joined)
        self.assertIn("ALTER TABLE pdv_pagamentos ADD COLUMN IF NOT EXISTS maquineta", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar teste, confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_pdv_caixa_fase1.py -v`
Expected: FAIL — `AssertionError` (as strings "pdv_caixa_contagem"/"pdv_caixa_conferencia"/coluna maquineta não aparecem em nenhuma query ainda).

- [ ] **Step 3: Adicionar as 2 tabelas novas e a coluna `maquineta`**

Em `hermes_agents/core/pdv.py`, dentro de `_ensure_tables()`, logo depois do bloco que cria `pdv_pagamentos` (linhas 271–276 no arquivo atual — o `CREATE TABLE IF NOT EXISTS pdv_pagamentos (...)`), adicionar a `ALTER TABLE`:

```python
        await db.execute("ALTER TABLE pdv_pagamentos ADD COLUMN IF NOT EXISTS maquineta VARCHAR(50)")
```

Depois do bloco que cria `pdv_sangrias`/`pdv_suprimentos` (linhas 277–286), adicionar as 2 tabelas novas:

```python
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_caixa_contagem (
            id SERIAL PRIMARY KEY,
            caixa_id INT NOT NULL REFERENCES pdv_caixas(id),
            denominacao VARCHAR(10) NOT NULL,
            quantidade INT NOT NULL DEFAULT 0,
            subtotal DECIMAL(10,2) GENERATED ALWAYS AS (quantidade * denominacao::numeric) STORED,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_caixa_conferencia (
            id SERIAL PRIMARY KEY,
            caixa_id INT NOT NULL REFERENCES pdv_caixas(id),
            maquineta VARCHAR(50) NOT NULL,
            forma_pagamento VARCHAR(30) NOT NULL,
            valor_sistema DECIMAL(12,2) NOT NULL DEFAULT 0,
            valor_conferido DECIMAL(12,2),
            diferenca DECIMAL(12,2) GENERATED ALWAYS AS (COALESCE(valor_conferido,0) - valor_sistema) STORED,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
```

- [ ] **Step 4: Rodar teste, confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_pdv_caixa_fase1.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/pdv.py hermes_agents/tests/test_pdv_caixa_fase1.py
git commit -m "feat: adiciona schema de contagem por denominacao e conferencia por maquineta no PDV"
```

---

### Task 2: `registrar_contagem_caixa` e `registrar_conferencia_caixa` (server-side, com `valor_sistema` recalculado)

**Files:**
- Modify: `hermes_agents/core/pdv.py` (adicionar funções novas antes de `resumo_fechamento`, linha ~574)
- Test: Modify `hermes_agents/tests/test_pdv_caixa_fase1.py`

**Interfaces:**
- Consumes: `get_db()`, `run_async()` (já importados no topo de `core/pdv.py`).
- Produces:
  - `valor_sistema_por_maquineta(caixa_id: int) -> list[{"maquineta": str, "forma_pagamento": str, "valor_sistema": float}]`
  - `registrar_contagem_caixa(caixa_id: int, linhas: list[{"denominacao": str, "quantidade": int}]) -> dict` — retorna `{"total_contado": float}` ou `{"error": str}`
  - `registrar_conferencia_caixa(caixa_id: int, linhas: list[{"maquineta": str, "forma_pagamento": str, "valor_conferido": float}]) -> dict` — retorna `{"total_diferenca_maquinetas": float}` ou `{"error": str}`

- [ ] **Step 1: Escrever os testes que falham**

Adicionar em `hermes_agents/tests/test_pdv_caixa_fase1.py`:

```python
class _CaixaDB:
    """Spy que simula pdv_pagamentos com 2 linhas nao-dinheiro (Stone/pix e
    Stone/cartao_credito) pra testar o agrupamento de valor_sistema."""
    def __init__(self):
        self.inserts_contagem = []
        self.inserts_conferencia = []

    async def execute(self, query, *params):
        return "OK"

    async def fetchval(self, query, *params):
        return 0

    async def fetch(self, query, *params):
        q = " ".join(query.split())
        if "GROUP BY maquineta" in q:
            return [
                {"maquineta": "Stone", "forma_pagamento": "pix", "valor_sistema": 100.0},
                {"maquineta": "Stone", "forma_pagamento": "cartao_credito", "valor_sistema": 250.0},
            ]
        return []

    async def fetchrow(self, query, *params):
        q = " ".join(query.split())
        if "INSERT INTO pdv_caixa_contagem" in q:
            caixa_id, denom, qtd = params
            subtotal = round(qtd * float(denom), 2)
            self.inserts_contagem.append((denom, qtd, subtotal))
            return {"subtotal": subtotal}
        if "INSERT INTO pdv_caixa_conferencia" in q:
            caixa_id, maquineta, forma, valor_sistema, valor_conferido = params
            diferenca = round(float(valor_conferido or 0) - float(valor_sistema), 2)
            self.inserts_conferencia.append((maquineta, forma, valor_sistema, valor_conferido, diferenca))
            return {"diferenca": diferenca}
        return None


async def _get_caixa_db(db):
    return db


class TestContagemEConferencia(unittest.TestCase):
    def test_registrar_contagem_soma_subtotais_e_ignora_quantidade_zero(self):
        import core.pdv as pdv
        db = _CaixaDB()
        with patch("core.pdv.get_db", side_effect=lambda: _get_caixa_db(db)):
            r = pdv.registrar_contagem_caixa(1, [
                {"denominacao": "50", "quantidade": 3},
                {"denominacao": "10", "quantidade": 0},
                {"denominacao": "2", "quantidade": 5},
            ])
        self.assertEqual(r["total_contado"], 160.0)
        self.assertEqual(len(db.inserts_contagem), 2)

    def test_registrar_conferencia_recalcula_valor_sistema_no_servidor(self):
        import core.pdv as pdv
        db = _CaixaDB()
        with patch("core.pdv.get_db", side_effect=lambda: _get_caixa_db(db)):
            r = pdv.registrar_conferencia_caixa(1, [
                {"maquineta": "Stone", "forma_pagamento": "pix", "valor_conferido": 90.0},
                {"maquineta": "Stone", "forma_pagamento": "cartao_credito", "valor_conferido": 260.0},
            ])
        # cliente nao manda valor_sistema — mesmo se mandasse, seria ignorado.
        self.assertEqual(db.inserts_conferencia[0][2], 100.0)  # valor_sistema veio do servidor
        self.assertEqual(r["total_diferenca_maquinetas"], -10.0 + 10.0)

    def test_conferencia_sem_maquineta_cai_em_nao_informado(self):
        import core.pdv as pdv
        db = _CaixaDB()
        with patch("core.pdv.get_db", side_effect=lambda: _get_caixa_db(db)):
            pdv.registrar_conferencia_caixa(1, [{"maquineta": "", "forma_pagamento": "pix", "valor_conferido": 5}])
        self.assertEqual(db.inserts_conferencia[0][0], "nao informado")
```

- [ ] **Step 2: Rodar teste, confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_pdv_caixa_fase1.py::TestContagemEConferencia -v`
Expected: FAIL — `AttributeError: module 'core.pdv' has no attribute 'registrar_contagem_caixa'`

- [ ] **Step 3: Implementar**

Em `hermes_agents/core/pdv.py`, adicionar antes de `def resumo_fechamento(caixa_id: int) -> dict:` (linha ~574):

```python
def valor_sistema_por_maquineta(caixa_id: int) -> list:
    """Agrupa pagamentos nao-dinheiro do caixa por (maquineta, forma) — usado
    pra pre-preencher a conferencia no fechamento e pra recalcular
    valor_sistema no servidor quando o operador confirma a conferencia
    (nunca confiar no valor que o cliente manda)."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT COALESCE(NULLIF(p.maquineta, ''), 'nao informado') AS maquineta,
                   p.forma AS forma_pagamento, COALESCE(SUM(p.valor),0) AS valor_sistema
            FROM pdv_pagamentos p
            JOIN pdv_vendas v ON v.id = p.venda_id
            WHERE v.caixa_id = $1 AND v.status = 'finalizada' AND p.forma != 'dinheiro'
            GROUP BY maquineta, p.forma
            ORDER BY maquineta, p.forma
        """, caixa_id)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []


def registrar_contagem_caixa(caixa_id: int, linhas: list) -> dict:
    """linhas: [{"denominacao": "50", "quantidade": 3}, ...] — grava so'
    linhas com quantidade > 0. subtotal e' coluna GENERATED, nao e' inserida."""
    async def _go():
        db = await get_db()
        total = 0.0
        for linha in linhas:
            qtd = int(linha.get("quantidade") or 0)
            if qtd <= 0:
                continue
            denom = str(linha["denominacao"])
            row = await db.fetchrow(
                "INSERT INTO pdv_caixa_contagem (caixa_id, denominacao, quantidade) VALUES ($1,$2,$3) RETURNING subtotal",
                caixa_id, denom, qtd,
            )
            total += float(row["subtotal"]) if row else 0.0
        return {"total_contado": round(total, 2)}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def registrar_conferencia_caixa(caixa_id: int, linhas: list) -> dict:
    """linhas: [{"maquineta":..., "forma_pagamento":..., "valor_conferido": 123.45}, ...]
    valor_sistema e' sempre recalculado aqui a partir de pdv_pagamentos —
    o valor_conferido e' o unico dado que vem do cliente."""
    sistema = {(r["maquineta"], r["forma_pagamento"]): r["valor_sistema"] for r in valor_sistema_por_maquineta(caixa_id)}
    async def _go():
        db = await get_db()
        total_diferenca = 0.0
        for linha in linhas:
            maquineta = str(linha.get("maquineta") or "").strip() or "nao informado"
            forma = str(linha.get("forma_pagamento") or "")
            valor_conferido = linha.get("valor_conferido")
            valor_sistema = float(sistema.get((maquineta, forma), 0))
            row = await db.fetchrow("""
                INSERT INTO pdv_caixa_conferencia (caixa_id, maquineta, forma_pagamento, valor_sistema, valor_conferido)
                VALUES ($1,$2,$3,$4,$5) RETURNING diferenca
            """, caixa_id, maquineta, forma, valor_sistema, valor_conferido)
            total_diferenca += float(row["diferenca"]) if row else 0.0
        return {"total_diferenca_maquinetas": round(total_diferenca, 2)}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}
```

- [ ] **Step 4: Rodar teste, confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_pdv_caixa_fase1.py -v`
Expected: PASS (todos os testes do arquivo)

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/pdv.py hermes_agents/tests/test_pdv_caixa_fase1.py
git commit -m "feat: registra contagem por denominacao e conferencia por maquineta no fechamento"
```

---

### Task 3: `fechar_caixa` combina dinheiro contado + diferenças de maquineta (com fallback pro cálculo antigo)

**Files:**
- Modify: `hermes_agents/core/pdv.py:489-537` (`fechar_caixa`)
- Modify: `hermes_agents/routes/pdv.py:66-71` (rota `POST /api/pdv/caixa/<id>/fechar`)
- Test: Modify `hermes_agents/tests/test_pdv_caixa_fase1.py`

**Interfaces:**
- Consumes: `registrar_contagem_caixa`, `registrar_conferencia_caixa` (Task 2).
- Produces: `fechar_caixa(caixa_id, saldo_final, operador_id=None, senha="", gerente_pin_id=None, pin="", codigo_barras="", contagem=None, conferencia=None) -> dict` — mesmo retorno de hoje mais `"total_contado"` e `"total_diferenca_maquinetas"` quando aplicável.

- [ ] **Step 1: Escrever o teste que falha**

Adicionar em `hermes_agents/tests/test_pdv_caixa_fase1.py` (reusa `FakeDB`/setup de `tests/test_pdv_seguranca.py` — importar de lá em vez de duplicar):

```python
from test_pdv_seguranca import FakeDB


class TestFecharCaixaComContagemEConferencia(unittest.TestCase):
    def setUp(self):
        self.fake = FakeDB()
        self._patches = []
        async def _get_db(_fake=self.fake):
            return _fake
        p = patch("core.pdv.get_db", side_effect=_get_db)
        p.start()
        self._patches.append(p)
        import core.pdv as m
        m._ensure_tables = lambda: None
        self.fake.operadores[1] = {"id": 1, "nome": "gerente1", "role": "gerente", "ativo": True, "senha": None}
        self.fake.caixas[1] = {"saldo_inicial": 100}

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_sem_contagem_nem_conferencia_usa_calculo_antigo(self):
        """Fechamentos sem essas chaves continuam funcionando como hoje —
        diferenca so' considera dinheiro (saldo_final informado direto)."""
        from core.pdv import fechar_caixa
        with patch("core.pdv.verificar_operador", return_value={"ok": True, "id": 1, "nome": "gerente1", "role": "gerente"}), \
             patch("core.entidades.ao_fechar_caixa_pdv", return_value=None, create=True):
            r = fechar_caixa(caixa_id=1, saldo_final=100, operador_id=1, senha="x")
        self.assertEqual(self.fake.caixas[1]["diferenca"], 0)

    def test_com_contagem_e_conferencia_soma_diferenca_dinheiro_mais_maquinetas(self):
        from core.pdv import fechar_caixa
        with patch("core.pdv.verificar_operador", return_value={"ok": True, "id": 1, "nome": "gerente1", "role": "gerente"}), \
             patch("core.entidades.ao_fechar_caixa_pdv", return_value=None, create=True), \
             patch("core.pdv.registrar_contagem_caixa", return_value={"total_contado": 105.0}), \
             patch("core.pdv.registrar_conferencia_caixa", return_value={"total_diferenca_maquinetas": -3.5}):
            r = fechar_caixa(caixa_id=1, saldo_final=999, operador_id=1, senha="x",
                              contagem=[{"denominacao": "50", "quantidade": 2}],
                              conferencia=[{"maquineta": "Stone", "forma_pagamento": "pix", "valor_conferido": 96.5}])
        # saldo_esperado_cash = 100 (inicial) + 0 (vendas_dinheiro) - 0 (sangrias) + 0 (suprimentos) = 100
        # diferenca_dinheiro = 105.0 - 100 = 5.0 ; total = 5.0 + (-3.5) = 1.5
        self.assertEqual(self.fake.caixas[1]["diferenca"], 1.5)
        self.assertEqual(self.fake.caixas[1]["saldo_final"], 105.0)  # grava o total contado, nao o saldo_final legado

    def test_erro_na_contagem_aborta_fechamento_sem_gravar(self):
        from core.pdv import fechar_caixa
        with patch("core.pdv.verificar_operador", return_value={"ok": True, "id": 1, "nome": "gerente1", "role": "gerente"}), \
             patch("core.pdv.registrar_contagem_caixa", return_value={"error": "denominacao invalida"}):
            r = fechar_caixa(caixa_id=1, saldo_final=100, operador_id=1, senha="x",
                              contagem=[{"denominacao": "xyz", "quantidade": 1}])
        self.assertIn("error", r)
        self.assertNotIn(1, self.fake.caixas.__class__() and {})  # no-op guard, ver assert abaixo
        self.assertIsNone(self.fake.caixas[1].get("status"))
```

- [ ] **Step 2: Rodar teste, confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_pdv_caixa_fase1.py::TestFecharCaixaComContagemEConferencia -v`
Expected: FAIL — `TypeError: fechar_caixa() got an unexpected keyword argument 'contagem'`

- [ ] **Step 3: Implementar**

Substituir `fechar_caixa` em `hermes_agents/core/pdv.py:489-537` por:

```python
def fechar_caixa(caixa_id: int, saldo_final: float, operador_id: int = None, senha: str = "",
                  gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "",
                  contagem: list = None, conferencia: list = None) -> dict:
    fechador = _autorizar_gerencial(operador_id, senha, gerente_pin_id, pin, codigo_barras, _ROLES_GERENCIAIS)
    if fechador.get("error"): return fechador
    nome_fechador = fechador.get("nome", "")

    total_contado = None
    if contagem:
        r_contagem = registrar_contagem_caixa(caixa_id, contagem)
        if r_contagem.get("error"): return r_contagem
        total_contado = r_contagem["total_contado"]

    total_diferenca_maquinetas = 0.0
    if conferencia:
        r_conferencia = registrar_conferencia_caixa(caixa_id, conferencia)
        if r_conferencia.get("error"): return r_conferencia
        total_diferenca_maquinetas = r_conferencia["total_diferenca_maquinetas"]

    async def _go():
        db = await get_db()
        total_vendas = await db.fetchval("SELECT COALESCE(SUM(total),0) FROM pdv_vendas WHERE caixa_id = $1 AND status = 'finalizada'", caixa_id)
        sangrias = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM pdv_sangrias WHERE caixa_id = $1", caixa_id)
        suprimentos = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM pdv_suprimentos WHERE caixa_id = $1", caixa_id)
        vendas_dinheiro = await db.fetchval("""
            SELECT COALESCE(SUM(p.valor),0) FROM pdv_pagamentos p
            JOIN pdv_vendas v ON v.id = p.venda_id
            WHERE v.caixa_id = $1 AND v.status = 'finalizada' AND p.forma = 'dinheiro'
        """, caixa_id)
        operadores_venda = await db.fetch(
            "SELECT DISTINCT operador FROM pdv_vendas WHERE caixa_id = $1 AND status = 'finalizada'", caixa_id)
        nomes_vendedores = {r["operador"] for r in operadores_venda if r["operador"]}
        aviso_segregacao = bool(nome_fechador) and nomes_vendedores == {nome_fechador}

        saldo_inicial_row = await db.fetchval("SELECT saldo_inicial FROM pdv_caixas WHERE id = $1", caixa_id)
        saldo_inicial = float(saldo_inicial_row or 0)
        saldo_esperado_cash = saldo_inicial + float(vendas_dinheiro or 0) - float(sangrias or 0) + float(suprimentos or 0)

        # Se veio contagem por denominacao, o saldo em dinheiro gravado e'
        # o total contado (fonte de verdade fisica); senao, cai no legado
        # (saldo_final informado direto pelo operador).
        saldo_final_dinheiro = total_contado if total_contado is not None else float(saldo_final)
        diferenca_dinheiro = round(saldo_final_dinheiro - saldo_esperado_cash, 2)
        diferenca = round(diferenca_dinheiro + total_diferenca_maquinetas, 2)

        row = await db.fetchrow("""UPDATE pdv_caixas SET status='fechado', saldo_final=$1, diferenca=$2,
            operador_fechamento=$3, data_fechamento=NOW() WHERE id=$4 RETURNING *""",
            saldo_final_dinheiro, diferenca, nome_fechador, caixa_id)
        return {
            "caixa": dict(row) if row else {},
            "total_vendas": float(total_vendas or 0),
            "vendas_dinheiro": float(vendas_dinheiro or 0),
            "sangrias": float(sangrias or 0),
            "suprimentos": float(suprimentos or 0),
            "saldo_esperado_cash": round(saldo_esperado_cash, 2),
            "diferenca": diferenca,
            "aviso_segregacao": aviso_segregacao,
            "total_contado": total_contado,
            "total_diferenca_maquinetas": total_diferenca_maquinetas,
        }
    try:
        result = run_async(_go())
        try:
            from core.entidades import ao_fechar_caixa_pdv
            ao_fechar_caixa_pdv(caixa_id)
        except Exception as e: pass
        return result
    except Exception as e: return {"error": str(e)}
```

Em `hermes_agents/routes/pdv.py:66-71`, atualizar a rota pra encaminhar `contagem`/`conferencia`:

```python
@pdv_bp.route('/caixa/<int:id>/fechar', methods=['POST'])
def pdv_fechar_caixa(id):
    data = request.json or {}
    from core.pdv import fechar_caixa
    return jsonify(fechar_caixa(id, float(data.get("saldo_final",0)), data.get("operador_id"), data.get("senha",""),
        data.get("gerente_pin_id"), data.get("pin",""), data.get("codigo_barras",""),
        data.get("contagem"), data.get("conferencia")))
```

Também expor `valor_sistema_por_maquineta` na rota de resumo (`routes/pdv.py:114-117`), pro modal pré-popular a grade de conferência:

```python
@pdv_bp.route('/caixa/<int:id>/resumo', methods=['GET'])
def pdv_resumo_caixa(id):
    from core.pdv import resumo_fechamento, valor_sistema_por_maquineta
    resumo = resumo_fechamento(id)
    if not resumo.get("error"):
        resumo["maquinetas"] = valor_sistema_por_maquineta(id)
    return jsonify(resumo)
```

- [ ] **Step 4: Rodar testes, confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_pdv_caixa_fase1.py tests/test_pdv_seguranca.py -v`
Expected: PASS (todos, incluindo os testes pré-existentes de `fechar_caixa` que não usam `contagem`/`conferencia` — o fallback precisa não quebrar nenhum deles)

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/pdv.py hermes_agents/routes/pdv.py hermes_agents/tests/test_pdv_caixa_fase1.py
git commit -m "feat: diferenca de fechamento soma contagem de dinheiro + conferencia por maquineta"
```

---

### Task 4: `maquineta` na venda (`realizar_venda`) e campo no frontend `VendaTab.tsx`

**Files:**
- Modify: `hermes_agents/core/pdv.py:858-860` (`realizar_venda`, insert de `pdv_pagamentos`)
- Modify: `web/src/app/pdv/_components/VendaTab.tsx` (bloco "Pagamento", linhas 259–272)
- Test: Modify `hermes_agents/tests/test_pdv_caixa_fase1.py`

**Interfaces:**
- Produces: `pagamento` (estado do `VendaTab.tsx`) ganha `maquineta?: string` por linha; POST `/api/pdv/venda` aceita `pagamentos: [{forma, valor, maquineta}]`.

- [ ] **Step 1: Escrever o teste que falha (backend)**

Adicionar em `hermes_agents/tests/test_pdv_caixa_fase1.py`:

```python
class TestRealizarVendaGravaMaquineta(unittest.IsolatedAsyncioTestCase):
    async def test_pagamento_com_maquineta_e_gravado(self):
        import core.pdv as pdv
        capturado = {}

        class _ConnSpy:
            async def fetchrow(self, query, *params):
                if "INSERT INTO pdv_vendas" in query:
                    return {"id": 1}
                return None
            async def execute(self, query, *params):
                if "INSERT INTO pdv_pagamentos" in query:
                    capturado["query"] = " ".join(query.split())
                    capturado["params"] = params
                return "OK"
            async def transaction(self):
                class _T:
                    async def __aenter__(self_): return self_
                    async def __aexit__(self_, *a): return False
                return _T()

        class _DBSpy:
            def acquire(self):
                class _A:
                    async def __aenter__(self_): return _ConnSpy()
                    async def __aexit__(self_, *a): return False
                return _A()

        async def _get_db(): return _DBSpy()
        async def _ensure_saldos(): return None

        with patch("core.pdv.get_db", side_effect=_get_db), \
             patch("core.pdv._ensure_saldos_async", side_effect=_ensure_saldos), \
             patch("core.pdv._resolver_loja_da_venda", return_value=None):
            pdv.realizar_venda(1, [], [{"forma": "cartao_credito", "valor": 100, "maquineta": "Stone"}])
        self.assertIn("maquineta", capturado["query"])
        self.assertIn("Stone", capturado["params"])
```

- [ ] **Step 2: Rodar teste, confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_pdv_caixa_fase1.py::TestRealizarVendaGravaMaquineta -v`
Expected: FAIL — `AssertionError` (query não contém "maquineta" ainda)

- [ ] **Step 3: Implementar backend**

Em `hermes_agents/core/pdv.py:858-860`, trocar:

```python
                for pg in pagamentos:
                    await conn.execute("INSERT INTO pdv_pagamentos (venda_id, forma, valor, parcelas) VALUES ($1,$2,$3,$4)",
                        vid, pg.get("forma","dinheiro"), pg.get("valor",total), pg.get("parcelas",1))
```

por:

```python
                for pg in pagamentos:
                    await conn.execute("INSERT INTO pdv_pagamentos (venda_id, forma, valor, parcelas, maquineta) VALUES ($1,$2,$3,$4,$5)",
                        vid, pg.get("forma","dinheiro"), pg.get("valor",total), pg.get("parcelas",1), pg.get("maquineta") or None)
```

- [ ] **Step 4: Rodar teste, confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_pdv_caixa_fase1.py -v`
Expected: PASS

- [ ] **Step 5: Implementar frontend — campo maquineta em `VendaTab.tsx`**

Em `web/src/app/pdv/_components/VendaTab.tsx`, o estado `pagamento` (tipo `{ forma: string; valor: number }[]`) ganha `maquineta?: string`. No bloco "Pagamento" (linhas 259–272), trocar o `.map`:

```tsx
{pagamento.map((p, i) => (
  <div key={i} className="flex gap-1.5">
    <select value={p.forma} onChange={e => { const c = [...pagamento]; c[i] = { ...c[i], forma: e.target.value }; setPagamento(c); }}
      className="flex-1 bg-neutral-900 rounded px-2 py-1.5 text-xs text-neutral-200">{FORMAS.map(f => <option key={f} value={f}>{f.replace(/_/g, " ")}</option>)}</select>
    {p.forma !== "dinheiro" && (
      <input value={p.maquineta || ""} onChange={e => { const c = [...pagamento]; c[i] = { ...c[i], maquineta: e.target.value }; setPagamento(c); }}
        placeholder="Maquineta" className="w-24 bg-neutral-900 rounded px-2 py-1.5 text-xs text-neutral-200" />
    )}
    <input type="number" step="0.01" value={p.valor || totalComDesconto} onChange={e => { const c = [...pagamento]; c[i] = { ...c[i], valor: Number(e.target.value) }; setPagamento(c); }}
      className="w-28 bg-neutral-900 rounded px-2 py-1 text-right text-xs text-neutral-200" />
    {pagamento.length > 1 && <button onClick={() => setPagamento(pagamento.filter((_, j) => j !== i))} className="text-red-400 text-xs px-1">×</button>}
  </div>
))}
```

E no POST de finalização (linhas 142–146), `pgts` (o array derivado de `pagamento` enviado no body) já inclui `maquineta` automaticamente por ser um spread do objeto de estado — confirmar que a construção de `pgts` não filtra campos manualmente (se filtrar, incluir `maquineta` na lista de campos repassados).

- [ ] **Step 6: Rodar typecheck do frontend**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros novos em `VendaTab.tsx`

- [ ] **Step 7: Commit**

```bash
git add hermes_agents/core/pdv.py hermes_agents/tests/test_pdv_caixa_fase1.py web/src/app/pdv/_components/VendaTab.tsx
git commit -m "feat: campo maquineta na venda do PDV, gravado em pdv_pagamentos"
```

---

### Task 5: Frontend — `FechaModal.tsx` com grade de denominação e conferência por maquineta

**Files:**
- Modify: `web/src/app/pdv/_components/FechaModal.tsx` (94 linhas — substituir campo `fechaSaldo` por grade de denominação + tabela de conferência)

**Interfaces:**
- Consumes: `GET /api/pdv/caixa/<id>/resumo` (agora retorna `maquinetas: [{maquineta, forma_pagamento, valor_sistema}]`, Task 3); `POST /api/pdv/caixa/<id>/fechar` (agora aceita `contagem`, `conferencia`, Task 3).

- [ ] **Step 1: Implementar**

Em `web/src/app/pdv/_components/FechaModal.tsx`, trocar o estado `fechaSaldo: string` por:

```tsx
const DENOMINACOES = ["200", "100", "50", "20", "10", "5", "2", "1", "0.50", "0.25", "0.10", "0.05"];
const [contagem, setContagem] = useState<Record<string, string>>({});
const [conferencia, setConferencia] = useState<Record<string, string>>({}); // chave: `${maquineta}|${forma}`
```

No `useEffect` que busca o resumo (que hoje também reseta `fechaSaldo`), resetar `contagem`/`conferencia`:

```tsx
useEffect(() => {
  if (!open || !caixa) return;
  setContagem({}); setConferencia({}); setFechaSenha(""); setFechaResumo(null);
  fetch("/api/pdv/caixa/" + caixa.id + "/resumo")
    .then(r => r.json()).then(setFechaResumo).catch(() => {});
}, [open, caixa]);
```

Trocar o input de "saldo conferido" (linhas 71–78) pela grade de denominação + total calculado:

```tsx
const totalContado = DENOMINACOES.reduce((s, d) => s + (Number(contagem[d]) || 0) * Number(d), 0);

<div className="grid grid-cols-4 gap-1.5 mb-2">
  {DENOMINACOES.map(d => (
    <div key={d} className="flex items-center gap-1">
      <span className="text-[10px] text-neutral-500 w-10">R$ {d}</span>
      <input type="number" min="0" value={contagem[d] || ""} onChange={e => setContagem({ ...contagem, [d]: e.target.value })}
        className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200" />
    </div>
  ))}
</div>
<p className="text-xs text-neutral-400 mb-2">Total contado: <span className="text-neutral-200 font-semibold">R$ {totalContado.toFixed(2)}</span></p>
```

Abaixo, a tabela de conferência por maquineta (populada a partir de `fechaResumo.maquinetas`):

```tsx
{fechaResumo?.maquinetas?.length > 0 && (
  <div className="mb-3 space-y-1">
    <p className="text-xs text-neutral-400">Conferência por maquineta</p>
    {fechaResumo.maquinetas.map((m: { maquineta: string; forma_pagamento: string; valor_sistema: number }) => {
      const chave = `${m.maquineta}|${m.forma_pagamento}`;
      return (
        <div key={chave} className="flex items-center gap-2 text-xs">
          <span className="flex-1 text-neutral-400">{m.maquineta} · {m.forma_pagamento} (sistema: R$ {m.valor_sistema.toFixed(2)})</span>
          <input type="number" step="0.01" value={conferencia[chave] || ""} onChange={e => setConferencia({ ...conferencia, [chave]: e.target.value })}
            className="w-24 bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-neutral-200" />
        </div>
      );
    })}
  </div>
)}
```

E `fecharCaixa` (que hoje lê `fechaSaldo`) passa a montar `contagem`/`conferencia` no body:

```tsx
const fecharCaixa = async () => {
  if (totalContado <= 0 && !fechaResumo?.maquinetas?.length) { alert("Informe a contagem do caixa"); return; }
  try {
    const r = await fetch("/api/pdv/caixa/" + caixa.id + "/fechar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        saldo_final: totalContado,
        operador_id: operador.id, senha: fechaSenha,
        gerente_pin_id: autorizacao.gerente_pin_id, pin: autorizacao.pin, codigo_barras: autorizacao.codigo_barras,
        contagem: Object.entries(contagem).filter(([, v]) => Number(v) > 0).map(([denominacao, quantidade]) => ({ denominacao, quantidade: Number(quantidade) })),
        conferencia: Object.entries(conferencia).filter(([, v]) => v !== "").map(([chave, valor_conferido]) => {
          const [maquineta, forma_pagamento] = chave.split("|");
          return { maquineta, forma_pagamento, valor_conferido: Number(valor_conferido) };
        }),
      }),
    });
    ...
```

- [ ] **Step 2: Rodar typecheck do frontend**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros em `FechaModal.tsx`

- [ ] **Step 3: Testar manualmente no browser**

Rodar `npm run dev` em `web/`, abrir um caixa no PDV, fazer uma venda com forma não-dinheiro + maquineta preenchida, abrir o modal de fechamento e confirmar: grade de denominação soma corretamente, linha de conferência aparece pra maquineta usada na venda, fechamento não quebra.

- [ ] **Step 4: Commit**

```bash
git add web/src/app/pdv/_components/FechaModal.tsx
git commit -m "feat: fechamento de caixa usa grade de contagem por denominacao e conferencia por maquineta"
```

---

## Fase 2 — Financeiro: Cofre

### Task 6: Schema + CRUD server-side de `fin_cofre`/`fin_cofre_movimentos`

**Files:**
- Create: `hermes_agents/core/financeiro_cofre.py`
- Test: Create `hermes_agents/tests/test_financeiro_cofre.py`

**Interfaces:**
- Produces:
  - `obter_ou_criar_cofre(loja_id: int) -> dict` — retorna a linha de `fin_cofre` (cria se não existir)
  - `registrar_movimento_cofre(loja_id: int, tipo: str, valor: float, descricao: str = "", categoria: str = None, caixa_id: int = None, criado_por: str = "", criado_por_id: int = None) -> dict` — retorna `{"movimento": {...}, "saldo_atual": float}` ou `{"error": str}`
  - `listar_movimentos_cofre(loja_id: int, limit: int = 100) -> dict` — retorna `{"cofre": {...}, "movimentos": [...]}`
  - `TIPOS_MOVIMENTO_COFRE = {"entrada_sangria", "saida_troco", "saida_despesa", "ajuste"}`
  - `CATEGORIAS_DESPESA_COFRE = {"mat_limpeza", "padaria", "papelaria", "passagem", "outros"}`

- [ ] **Step 1: Escrever os testes que falham**

```python
# hermes_agents/tests/test_financeiro_cofre.py
"""Cofre por loja — saldo mantido incrementalmente, lazy-create, tipos/categorias validados."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch


class _CofreDB:
    def __init__(self, cofre_existente=None):
        self.cofre = cofre_existente
        self.movimentos = []
        self.saldo_atualizado = None

    async def fetchrow(self, query, *params):
        q = " ".join(query.split())
        if "SELECT * FROM fin_cofre WHERE loja_id" in q:
            return self.cofre
        if "INSERT INTO fin_cofre" in q:
            self.cofre = {"id": 1, "loja_id": params[0], "saldo_atual": 0.0}
            return self.cofre
        if "INSERT INTO fin_cofre_movimentos" in q:
            mov = {"id": len(self.movimentos) + 1}
            self.movimentos.append(params)
            return mov
        if "UPDATE fin_cofre SET saldo_atual" in q:
            self.saldo_atualizado = params[0]
            self.cofre["saldo_atual"] = params[0]
            return self.cofre
        return None

    async def fetch(self, query, *params):
        return []

    async def execute(self, query, *params):
        return "OK"

    async def fetchval(self, query, *params):
        return 0


async def _get_cofre_db(db):
    return db


class TestObterOuCriarCofre(unittest.TestCase):
    def test_cofre_inexistente_e_criado_com_saldo_zero(self):
        import core.financeiro_cofre as cofre
        db = _CofreDB(cofre_existente=None)
        with patch("core.financeiro_cofre.get_db", side_effect=lambda: _get_cofre_db(db)):
            r = cofre.obter_ou_criar_cofre(5)
        self.assertEqual(r["loja_id"], 5)
        self.assertEqual(r["saldo_atual"], 0.0)

    def test_cofre_existente_nao_e_recriado(self):
        import core.financeiro_cofre as cofre
        db = _CofreDB(cofre_existente={"id": 9, "loja_id": 5, "saldo_atual": 320.0})
        with patch("core.financeiro_cofre.get_db", side_effect=lambda: _get_cofre_db(db)):
            r = cofre.obter_ou_criar_cofre(5)
        self.assertEqual(r["id"], 9)
        self.assertEqual(r["saldo_atual"], 320.0)


class TestRegistrarMovimentoCofre(unittest.TestCase):
    def test_entrada_soma_ao_saldo(self):
        import core.financeiro_cofre as cofre
        db = _CofreDB(cofre_existente={"id": 1, "loja_id": 5, "saldo_atual": 100.0})
        with patch("core.financeiro_cofre.get_db", side_effect=lambda: _get_cofre_db(db)):
            r = cofre.registrar_movimento_cofre(5, "entrada_sangria", 50.0, caixa_id=7)
        self.assertEqual(r["saldo_atual"], 150.0)

    def test_saida_subtrai_do_saldo(self):
        import core.financeiro_cofre as cofre
        db = _CofreDB(cofre_existente={"id": 1, "loja_id": 5, "saldo_atual": 100.0})
        with patch("core.financeiro_cofre.get_db", side_effect=lambda: _get_cofre_db(db)):
            r = cofre.registrar_movimento_cofre(5, "saida_despesa", 30.0, categoria="padaria", descricao="Pães")
        self.assertEqual(r["saldo_atual"], 70.0)

    def test_ajuste_negativo_subtrai(self):
        import core.financeiro_cofre as cofre
        db = _CofreDB(cofre_existente={"id": 1, "loja_id": 5, "saldo_atual": 100.0})
        with patch("core.financeiro_cofre.get_db", side_effect=lambda: _get_cofre_db(db)):
            r = cofre.registrar_movimento_cofre(5, "ajuste", -15.0)
        self.assertEqual(r["saldo_atual"], 85.0)

    def test_tipo_invalido_e_rejeitado(self):
        import core.financeiro_cofre as cofre
        db = _CofreDB(cofre_existente={"id": 1, "loja_id": 5, "saldo_atual": 100.0})
        with patch("core.financeiro_cofre.get_db", side_effect=lambda: _get_cofre_db(db)):
            r = cofre.registrar_movimento_cofre(5, "tipo_inventado", 10.0)
        self.assertIn("error", r)

    def test_saida_despesa_sem_categoria_e_rejeitada(self):
        import core.financeiro_cofre as cofre
        db = _CofreDB(cofre_existente={"id": 1, "loja_id": 5, "saldo_atual": 100.0})
        with patch("core.financeiro_cofre.get_db", side_effect=lambda: _get_cofre_db(db)):
            r = cofre.registrar_movimento_cofre(5, "saida_despesa", 10.0)
        self.assertIn("error", r)

    def test_categoria_invalida_e_rejeitada(self):
        import core.financeiro_cofre as cofre
        db = _CofreDB(cofre_existente={"id": 1, "loja_id": 5, "saldo_atual": 100.0})
        with patch("core.financeiro_cofre.get_db", side_effect=lambda: _get_cofre_db(db)):
            r = cofre.registrar_movimento_cofre(5, "saida_despesa", 10.0, categoria="categoria_inventada")
        self.assertIn("error", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar teste, confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_financeiro_cofre.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.financeiro_cofre'`

- [ ] **Step 3: Implementar**

```python
# hermes_agents/core/financeiro_cofre.py
"""Cofre por loja — categorizacao de entradas/saidas fisicas de dinheiro
(sangria de caixa, troco, despesas pequenas, ajustes). Nao duplica o
conceito de caixa do PDV: so' referencia caixa_id quando aplicavel."""
from core import get_db, run_async, log

AGENT = "Financeiro Cofre"

TIPOS_MOVIMENTO_COFRE = {"entrada_sangria", "saida_troco", "saida_despesa", "ajuste"}
CATEGORIAS_DESPESA_COFRE = {"mat_limpeza", "padaria", "papelaria", "passagem", "outros"}


def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_cofre (
            id SERIAL PRIMARY KEY, loja_id INT NOT NULL UNIQUE REFERENCES lojas(id),
            saldo_atual DECIMAL(12,2) NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_cofre_movimentos (
            id SERIAL PRIMARY KEY, cofre_id INT NOT NULL REFERENCES fin_cofre(id),
            tipo VARCHAR(20) NOT NULL, categoria VARCHAR(30), valor DECIMAL(12,2) NOT NULL,
            descricao VARCHAR(200), caixa_id INT REFERENCES pdv_caixas(id),
            data DATE NOT NULL DEFAULT CURRENT_DATE, criado_por VARCHAR(100), criado_por_id INT,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
    try: run_async(_go())
    except Exception as e: log(AGENT, f"Erro ao criar tabelas cofre: {e}")


_ensure_tables()


def obter_ou_criar_cofre(loja_id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM fin_cofre WHERE loja_id = $1", loja_id)
        if row:
            return dict(row)
        row = await db.fetchrow("INSERT INTO fin_cofre (loja_id, saldo_atual) VALUES ($1, 0) RETURNING *", loja_id)
        return dict(row)
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def registrar_movimento_cofre(loja_id: int, tipo: str, valor: float, descricao: str = "",
                               categoria: str = None, caixa_id: int = None,
                               criado_por: str = "", criado_por_id: int = None) -> dict:
    if tipo not in TIPOS_MOVIMENTO_COFRE:
        return {"error": "Tipo de movimento invalido"}
    if tipo == "saida_despesa":
        if not categoria:
            return {"error": "Categoria obrigatoria para saida de despesa"}
        if categoria not in CATEGORIAS_DESPESA_COFRE:
            return {"error": "Categoria de despesa invalida"}
    cofre = obter_ou_criar_cofre(loja_id)
    if cofre.get("error"):
        return cofre
    delta = float(valor) if tipo in ("entrada_sangria",) else -abs(float(valor))
    if tipo == "ajuste":
        delta = float(valor)  # ajuste pode ser positivo ou negativo, valor ja vem com sinal

    async def _go():
        db = await get_db()
        mov = await db.fetchrow("""
            INSERT INTO fin_cofre_movimentos (cofre_id, tipo, categoria, valor, descricao, caixa_id, criado_por, criado_por_id)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *
        """, cofre["id"], tipo, categoria, valor, descricao, caixa_id, criado_por, criado_por_id)
        atualizado = await db.fetchrow(
            "UPDATE fin_cofre SET saldo_atual = saldo_atual + $1 WHERE id = $2 RETURNING *",
            delta, cofre["id"])
        return {"movimento": dict(mov) if mov else {}, "saldo_atual": float(atualizado["saldo_atual"])}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def listar_movimentos_cofre(loja_id: int, limit: int = 100) -> dict:
    cofre = obter_ou_criar_cofre(loja_id)
    if cofre.get("error"):
        return cofre
    async def _go():
        db = await get_db()
        rows = await db.fetch(
            "SELECT * FROM fin_cofre_movimentos WHERE cofre_id = $1 ORDER BY id DESC LIMIT $2",
            cofre["id"], limit)
        return [dict(r) for r in rows]
    try:
        movimentos = run_async(_go())
    except Exception as e:
        movimentos = []
    return {"cofre": cofre, "movimentos": movimentos}
```

- [ ] **Step 4: Rodar teste, confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_financeiro_cofre.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/financeiro_cofre.py hermes_agents/tests/test_financeiro_cofre.py
git commit -m "feat: modulo Cofre por loja (schema + CRUD server-side)"
```

---

### Task 7: Hook automático — sangria de caixa gera `entrada_sangria` no cofre

**Files:**
- Modify: `hermes_agents/core/entidades.py` (`ao_fechar_caixa_pdv`, linhas 419–436)
- Test: Modify `hermes_agents/tests/test_financeiro_cofre.py`

**Interfaces:**
- Consumes: `core.financeiro_cofre.registrar_movimento_cofre` (Task 6).

- [ ] **Step 1: Escrever o teste que falha**

Adicionar em `hermes_agents/tests/test_financeiro_cofre.py`:

```python
class TestHookSangriaViraCofre(unittest.TestCase):
    def test_fechar_caixa_com_sangria_e_loja_gera_entrada_no_cofre(self):
        import core.entidades as ent

        class _DB:
            async def fetchrow(self, query, *params):
                if "SELECT * FROM pdv_caixas" in query:
                    return {"id": 7, "loja_id": 5}
                return None
            async def fetchval(self, query, *params):
                if "pdv_vendas" in query: return 500.0
                if "pdv_sangrias" in query: return 80.0
                if "pdv_suprimentos" in query: return 0.0
                return 0
            async def execute(self, query, *params):
                return "OK"

        async def _get_db(): return _DB()

        with patch("core.entidades.get_db", side_effect=_get_db), \
             patch("core.financeiro_cofre.registrar_movimento_cofre", return_value={"saldo_atual": 80.0}) as mock_reg:
            ent.ao_fechar_caixa_pdv(7)
        mock_reg.assert_called_once()
        args, kwargs = mock_reg.call_args
        self.assertEqual(args[0], 5)  # loja_id
        self.assertEqual(args[1], "entrada_sangria")
        self.assertEqual(args[2], 80.0)
        self.assertEqual(kwargs.get("caixa_id"), 7)

    def test_fechar_caixa_sem_loja_id_nao_gera_movimento_no_cofre(self):
        import core.entidades as ent

        class _DB:
            async def fetchrow(self, query, *params):
                if "SELECT * FROM pdv_caixas" in query:
                    return {"id": 8, "loja_id": None}
                return None
            async def fetchval(self, query, *params):
                if "pdv_sangrias" in query: return 50.0
                return 0
            async def execute(self, query, *params):
                return "OK"

        async def _get_db(): return _DB()

        with patch("core.entidades.get_db", side_effect=_get_db), \
             patch("core.financeiro_cofre.registrar_movimento_cofre") as mock_reg:
            ent.ao_fechar_caixa_pdv(8)
        mock_reg.assert_not_called()

    def test_falha_no_cofre_nao_quebra_o_fechamento(self):
        """Mesmo padrao de tolerancia a falha de ao_faturar_pedido: um erro
        no cofre nao pode impedir o fechamento do caixa (ja persistido antes
        deste hook rodar)."""
        import core.entidades as ent

        class _DB:
            async def fetchrow(self, query, *params):
                if "SELECT * FROM pdv_caixas" in query:
                    return {"id": 7, "loja_id": 5}
                return None
            async def fetchval(self, query, *params):
                if "pdv_sangrias" in query: return 80.0
                return 0
            async def execute(self, query, *params):
                return "OK"

        async def _get_db(): return _DB()

        with patch("core.entidades.get_db", side_effect=_get_db), \
             patch("core.financeiro_cofre.registrar_movimento_cofre", side_effect=Exception("boom")):
            r = ent.ao_fechar_caixa_pdv(7)
        self.assertNotIn("error", r)  # fluxo de caixa (fin_fluxo_caixa) continua sendo reportado normalmente
```

- [ ] **Step 2: Rodar teste, confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_financeiro_cofre.py::TestHookSangriaViraCofre -v`
Expected: FAIL — `mock_reg.assert_called_once()` falha (nenhuma chamada acontece ainda)

- [ ] **Step 3: Implementar**

Em `hermes_agents/core/entidades.py`, dentro de `ao_fechar_caixa_pdv` (linhas 419–436), depois do bloco que já busca `caixa`/`total_vendas`/`sangrias`/`suprimentos` e antes do `return`, adicionar:

```python
        if float(sangrias or 0) > 0 and caixa.get("loja_id"):
            try:
                from core.financeiro_cofre import registrar_movimento_cofre
                registrar_movimento_cofre(
                    caixa["loja_id"], "entrada_sangria", float(sangrias or 0),
                    descricao=f"Sangria Caixa #{caixa_id}", caixa_id=caixa_id,
                )
            except Exception as e:
                log(AGENT, f"Erro ao lancar sangria no cofre (caixa {caixa_id}): {e}")
```

(usar o `log`/`AGENT` já importados/definidos no topo de `core/entidades.py` — se o módulo não expuser um `AGENT` de módulo, usar a mesma string usada nos demais `log(...)` desse arquivo.)

- [ ] **Step 4: Rodar teste, confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_financeiro_cofre.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/entidades.py hermes_agents/tests/test_financeiro_cofre.py
git commit -m "feat: fechar caixa com sangria lanca entrada automatica no cofre da loja"
```

---

### Task 8: Rotas do Cofre (`requer_acesso_loja` + RBAC + alçada de ajuste)

**Files:**
- Create: `hermes_agents/routes/financeiro_cofre.py`
- Modify: `hermes_agents/athena_bridge.py` (registrar blueprint)
- Test: Create `hermes_agents/tests/test_financeiro_cofre_rotas.py`

**Interfaces:**
- Consumes: `core.financeiro_cofre.{listar_movimentos_cofre, registrar_movimento_cofre}` (Task 6), `core.rbac.{requer_permissao, requer_acesso_loja, usuario_atual_da_request, usuario_tem_permissao, autorizar_com_permissao}`.
- Produces:
  - `GET /api/financeiro/cofre/<int:loja_id>` (financeiro.ver + requer_acesso_loja)
  - `POST /api/financeiro/cofre/<int:loja_id>/saida` (financeiro.criar + requer_acesso_loja) — body `{tipo: "saida_despesa"|"saida_troco", valor, descricao, categoria?, caixa_id?}`
  - `POST /api/financeiro/cofre/<int:loja_id>/ajuste` (requer_acesso_loja; exige financeiro.aprovar OU PIN/crachá válido, sempre) — body `{valor, descricao, usuario_pin_id?, pin?, codigo_barras?}`

- [ ] **Step 1: Escrever os testes que falham**

```python
# hermes_agents/tests/test_financeiro_cofre_rotas.py
"""Rotas do Cofre — RBAC por loja + alcada de ajuste sempre obrigatoria."""
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
from routes.financeiro_cofre import financeiro_cofre_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(financeiro_cofre_bp)
    return app.test_client()


class TestCofreRBACPorLoja(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_ver_extrato_de_loja_fora_da_lista_permitida_bloqueia(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.ver"]), \
             patch("core.rbac_lojas.lojas_permitidas", return_value=[1]):
            r = self.client.get("/api/financeiro/cofre/2", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_ver_extrato_sem_permissao_financeiro_ver_bloqueia(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.rbac_lojas.lojas_permitidas", return_value=[1]):
            r = self.client.get("/api/financeiro/cofre/1", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_ver_extrato_loja_permitida_e_com_permissao_passa(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.ver"]), \
             patch("core.rbac_lojas.lojas_permitidas", return_value=[1]), \
             patch("core.financeiro_cofre.listar_movimentos_cofre", return_value={"cofre": {}, "movimentos": []}):
            r = self.client.get("/api/financeiro/cofre/1", headers=headers)
        self.assertEqual(r.status_code, 200)

    def test_nova_saida_sem_permissao_criar_bloqueia(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.ver"]), \
             patch("core.rbac_lojas.lojas_permitidas", return_value=[1]):
            r = self.client.post("/api/financeiro/cofre/1/saida",
                                  json={"tipo": "saida_despesa", "valor": 20, "categoria": "padaria"}, headers=headers)
        self.assertEqual(r.status_code, 403)


class TestCofreAjusteSempreExigeAprovacao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_ajuste_de_valor_baixo_sem_aprovar_ainda_e_bloqueado(self):
        """Diferente do limite de R$5000 dos pagamentos — ajuste de cofre e'
        sempre sensivel, mesmo R$1."""
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.criar"]), \
             patch("core.rbac_lojas.lojas_permitidas", return_value=[1]), \
             patch("core.financeiro_cofre.registrar_movimento_cofre") as mock_reg:
            r = self.client.post("/api/financeiro/cofre/1/ajuste", json={"valor": 1.0, "descricao": "correcao"}, headers=headers)
        self.assertEqual(r.status_code, 400)
        mock_reg.assert_not_called()

    def test_ajuste_com_financeiro_aprovar_libera(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.criar", "financeiro.aprovar"]), \
             patch("core.rbac_lojas.lojas_permitidas", return_value=[1]), \
             patch("core.financeiro_cofre.registrar_movimento_cofre", return_value={"saldo_atual": 99.0}) as mock_reg:
            r = self.client.post("/api/financeiro/cofre/1/ajuste", json={"valor": -1.0, "descricao": "correcao"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_reg.assert_called_once()

    def test_ajuste_com_cracha_de_gerente_libera(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.criar"]), \
             patch("core.rbac_lojas.lojas_permitidas", return_value=[1]), \
             patch("core.rbac.verificar_codigo_barras_usuario", return_value={"ok": True, "id": 9, "nome": "Gerente X"}), \
             patch("core.financeiro_cofre.registrar_movimento_cofre", return_value={"saldo_atual": 99.0}) as mock_reg:
            r = self.client.post("/api/financeiro/cofre/1/ajuste",
                                  json={"valor": 5.0, "descricao": "correcao", "codigo_barras": "ABC"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        _, kwargs = mock_reg.call_args
        self.assertEqual(kwargs.get("criado_por"), "Gerente X")


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar teste, confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_financeiro_cofre_rotas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'routes.financeiro_cofre'`

- [ ] **Step 3: Implementar**

```python
# hermes_agents/routes/financeiro_cofre.py
from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao, requer_acesso_loja, usuario_atual_da_request, usuario_tem_permissao, autorizar_com_permissao
from core.api_utils import status_for_resultado as _status_for

financeiro_cofre_bp = Blueprint("financeiro_cofre", __name__, url_prefix="/api/financeiro/cofre")


@financeiro_cofre_bp.route("/<int:loja_id>", methods=["GET"])
def cofre_extrato(loja_id):
    @requer_acesso_loja
    @requer_permissao("financeiro.ver")
    def _go(loja_id):
        from core.financeiro_cofre import listar_movimentos_cofre
        resultado = listar_movimentos_cofre(loja_id)
        return jsonify(resultado), _status_for(resultado)
    return _go(loja_id=loja_id)


@financeiro_cofre_bp.route("/<int:loja_id>/saida", methods=["POST"])
def cofre_saida(loja_id):
    data = request.json or {}
    tipo = data.get("tipo")
    if tipo not in ("saida_despesa", "saida_troco"):
        return jsonify({"error": "Tipo invalido para saida (use saida_despesa ou saida_troco)"}), 400

    @requer_acesso_loja
    @requer_permissao("financeiro.criar")
    def _go(loja_id):
        from core.financeiro_cofre import registrar_movimento_cofre
        usuario = usuario_atual_da_request()
        resultado = registrar_movimento_cofre(
            loja_id, tipo, float(data.get("valor") or 0),
            descricao=data.get("descricao", ""), categoria=data.get("categoria"),
            caixa_id=data.get("caixa_id"), criado_por=usuario["nome"], criado_por_id=usuario["user_id"],
        )
        return jsonify(resultado), _status_for(resultado)
    return _go(loja_id=loja_id)


@financeiro_cofre_bp.route("/<int:loja_id>/ajuste", methods=["POST"])
def cofre_ajuste(loja_id):
    data = request.json or {}

    @requer_acesso_loja
    def _go(loja_id):
        usuario = usuario_atual_da_request()
        aprovador_id, aprovador_nome = usuario["user_id"], usuario["nome"]
        tem_aprovar = usuario_tem_permissao("financeiro.aprovar")
        if not tem_aprovar and (data.get("usuario_pin_id") or data.get("codigo_barras")):
            auth = autorizar_com_permissao(
                "financeiro.aprovar", data.get("usuario_pin_id"),
                str(data.get("pin", "")), str(data.get("codigo_barras", "")),
            )
            if not auth.get("error"):
                tem_aprovar = True
                aprovador_id, aprovador_nome = auth["id"], auth["nome"]
        if not tem_aprovar:
            return jsonify({"error": "Ajuste de cofre exige aprovacao (financeiro.aprovar, PIN ou cracha de gerente)"}), 400
        from core.financeiro_cofre import registrar_movimento_cofre
        resultado = registrar_movimento_cofre(
            loja_id, "ajuste", float(data.get("valor") or 0),
            descricao=data.get("descricao", ""), criado_por=aprovador_nome, criado_por_id=aprovador_id,
        )
        return jsonify(resultado), _status_for(resultado)
    return _go(loja_id=loja_id)
```

Nota: remover a expressão morta `-abs(float(data.get("valor") or 0)) if False else` deixada por engano na primeira escrita de `cofre_saida` — a linha final correta é:

```python
        resultado = registrar_movimento_cofre(
            loja_id, tipo, float(data.get("valor") or 0),
            descricao=data.get("descricao", ""), categoria=data.get("categoria"),
            caixa_id=data.get("caixa_id"), criado_por=usuario["nome"], criado_por_id=usuario["user_id"],
        )
```

(`registrar_movimento_cofre`, Task 6, já aplica o sinal negativo internamente pra `saida_*` — a rota só repassa o valor absoluto informado pelo usuário.)

Registrar o blueprint em `hermes_agents/athena_bridge.py`, junto dos demais imports/registros de `financeiro_bp` (linhas 220–285):

```python
from routes.financeiro_cofre import financeiro_cofre_bp
...
app.register_blueprint(financeiro_cofre_bp)
```

- [ ] **Step 4: Rodar teste, confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_financeiro_cofre_rotas.py -v`
Expected: PASS

- [ ] **Step 5: Rodar suite completa (checar nenhuma rota colidiu)**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: todos passam

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/financeiro_cofre.py hermes_agents/athena_bridge.py hermes_agents/tests/test_financeiro_cofre_rotas.py
git commit -m "feat: rotas do Cofre com RBAC por loja e alcada obrigatoria no ajuste"
```

---

### Task 9: Frontend — aba "Cofre" em Financeiro

**Files:**
- Create: `web/src/app/financeiro/_components/CofreTab.tsx`
- Modify: `web/src/app/financeiro/page.tsx` (adicionar tab)
- Modify: `web/src/lib/api.ts` (adicionar `finCofreExtrato`/`finCofreSaida`/`finCofreAjuste`)

**Interfaces:**
- Consumes: `GET /api/financeiro/cofre/<loja_id>`, `POST /api/financeiro/cofre/<loja_id>/saida`, `POST /api/financeiro/cofre/<loja_id>/ajuste` (Task 8); `api.lojasManage()` (`web/src/lib/api.ts:575`) pro seletor de loja; `AutorizacaoGerencial`/`AutorizacaoGerencialValue` de `web/src/app/_components/AutorizacaoGerencial.tsx` (mesmo padrão de `PagarTab.tsx`).

- [ ] **Step 1: Adicionar funções em `web/src/lib/api.ts`**

Logo abaixo do bloco `// Financeiro` existente (linhas 849–856), adicionar:

```typescript
finCofreExtrato: (lojaId: number) =>
  request<{ cofre: { id: number; loja_id: number; saldo_atual: number }; movimentos: Array<{ id: number; tipo: string; categoria: string | null; valor: number; descricao: string; data: string; criado_por: string }> }>(`/api/financeiro/cofre/${lojaId}`),
finCofreSaida: (lojaId: number, data: { tipo: string; valor: number; descricao: string; categoria?: string; caixa_id?: number }) =>
  request<Record<string, unknown>>(`/api/financeiro/cofre/${lojaId}/saida`, { method: "POST", body: JSON.stringify(data) }),
finCofreAjuste: (lojaId: number, data: { valor: number; descricao: string; usuario_pin_id?: number | null; pin?: string; codigo_barras?: string }) =>
  request<Record<string, unknown>>(`/api/financeiro/cofre/${lojaId}/ajuste`, { method: "POST", body: JSON.stringify(data) }),
```

- [ ] **Step 2: Implementar `CofreTab.tsx`**

```tsx
"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt } from "@/lib/format";
import { AutorizacaoGerencial, type AutorizacaoGerencialValue } from "../../_components/AutorizacaoGerencial";

interface Loja { id: number; nome: string; ativa: boolean; }
interface Movimento { id: number; tipo: string; categoria: string | null; valor: number; descricao: string; data: string; criado_por: string; }

const CATEGORIAS_DESPESA = ["mat_limpeza", "padaria", "papelaria", "passagem", "outros"];
const AUTORIZACAO_VAZIA: AutorizacaoGerencialValue = { usuario_pin_id: null, pin: "", codigo_barras: "" };

export default function CofreTab() {
  const [lojas, setLojas] = useState<Loja[]>([]);
  const [lojaId, setLojaId] = useState<number | null>(null);
  const [saldo, setSaldo] = useState(0);
  const [movimentos, setMovimentos] = useState<Movimento[]>([]);
  const [loading, setLoading] = useState(true);

  const [saindo, setSaindo] = useState<"saida_despesa" | "saida_troco" | null>(null);
  const [novaSaida, setNovaSaida] = useState({ valor: "", descricao: "", categoria: "mat_limpeza" });
  const [erroSaida, setErroSaida] = useState("");

  const [ajustando, setAjustando] = useState(false);
  const [novoAjuste, setNovoAjuste] = useState({ valor: "", descricao: "" });
  const [autorizacao, setAutorizacao] = useState<AutorizacaoGerencialValue>(AUTORIZACAO_VAZIA);
  const [erroAjuste, setErroAjuste] = useState("");

  useEffect(() => {
    api.lojasManage().then(r => {
      setLojas(r.lojas || []);
      if (r.lojas?.length) setLojaId(r.lojas[0].id);
    }).catch(() => {});
  }, []);

  const load = (id: number) => {
    setLoading(true);
    api.finCofreExtrato(id)
      .then(r => { setSaldo(r.cofre?.saldo_atual || 0); setMovimentos((r.movimentos || []) as Movimento[]); })
      .catch(() => {}).finally(() => setLoading(false));
  };
  useEffect(() => { if (lojaId) load(lojaId); }, [lojaId]);

  const abrirSaida = (tipo: "saida_despesa" | "saida_troco") => {
    setNovaSaida({ valor: "", descricao: "", categoria: "mat_limpeza" });
    setErroSaida("");
    setSaindo(tipo);
  };

  const confirmarSaida = async () => {
    if (!lojaId || !saindo || !novaSaida.valor) { setErroSaida("Informe o valor"); return; }
    try {
      const r = await api.finCofreSaida(lojaId, {
        tipo: saindo, valor: Number(novaSaida.valor), descricao: novaSaida.descricao.trim(),
        categoria: saindo === "saida_despesa" ? novaSaida.categoria : undefined,
      });
      if ((r as { error?: string }).error) { setErroSaida((r as { error?: string }).error || "Erro ao registrar"); return; }
      setSaindo(null);
      load(lojaId);
    } catch {
      setErroSaida("Erro ao registrar saída");
    }
  };

  const abrirAjuste = () => {
    setNovoAjuste({ valor: "", descricao: "" });
    setAutorizacao(AUTORIZACAO_VAZIA);
    setErroAjuste("");
    setAjustando(true);
  };

  const confirmarAjuste = async () => {
    if (!lojaId || !novoAjuste.valor) { setErroAjuste("Informe o valor"); return; }
    try {
      const r = await api.finCofreAjuste(lojaId, {
        valor: Number(novoAjuste.valor), descricao: novoAjuste.descricao.trim(),
        usuario_pin_id: autorizacao.usuario_pin_id, pin: autorizacao.pin, codigo_barras: autorizacao.codigo_barras,
      });
      if ((r as { error?: string }).error) { setErroAjuste((r as { error?: string }).error || "Erro ao ajustar"); return; }
      setAjustando(false);
      load(lojaId);
    } catch {
      setErroAjuste("Erro ao ajustar cofre");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <select value={lojaId ?? ""} onChange={e => setLojaId(Number(e.target.value))}
          className="bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200">
          {lojas.map(l => <option key={l.id} value={l.id}>{l.nome}</option>)}
        </select>
        <button onClick={() => abrirSaida("saida_despesa")} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Saída (despesa)</button>
        <button onClick={() => abrirSaida("saida_troco")} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Saída (troco)</button>
        <button onClick={abrirAjuste} className="bg-neutral-700 hover:bg-neutral-600 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">Ajuste</button>
      </div>

      <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3 w-fit">
        <p className="text-[10px] text-neutral-500">Saldo Atual</p>
        <p className="text-lg font-semibold mt-0.5 text-emerald-400">{fmt(saldo)}</p>
      </div>

      {loading ? <p className="text-xs text-neutral-500">Carregando...</p> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead><tr className="border-b border-neutral-700 text-neutral-400 text-left">
              <th className="px-4 py-2 font-medium">Data</th><th className="px-4 py-2 font-medium">Tipo</th>
              <th className="px-4 py-2 font-medium">Categoria</th><th className="px-4 py-2 font-medium">Descrição</th>
              <th className="px-4 py-2 font-medium">Valor</th><th className="px-4 py-2 font-medium">Por</th>
            </tr></thead>
            <tbody>{movimentos.map(m => (
              <tr key={m.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300">
                <td className="px-4 py-2.5">{m.data ? new Date(m.data + "T00:00:00").toLocaleDateString("pt-BR") : "—"}</td>
                <td className="px-4 py-2.5">{m.tipo}</td>
                <td className="px-4 py-2.5 text-neutral-400">{m.categoria || "—"}</td>
                <td className="px-4 py-2.5">{m.descricao}</td>
                <td className={`px-4 py-2.5 font-medium ${m.tipo === "entrada_sangria" || (m.tipo === "ajuste" && m.valor > 0) ? "text-emerald-400" : "text-red-400"}`}>{fmt(m.valor)}</td>
                <td className="px-4 py-2.5 text-neutral-400">{m.criado_por}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}

      {saindo && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setSaindo(null)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">{saindo === "saida_despesa" ? "Nova Saída (Despesa)" : "Nova Saída (Troco)"}</h3>
            {erroSaida && <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2 mb-3">{erroSaida}</div>}
            <div className="space-y-2">
              <input type="number" step="0.01" value={novaSaida.valor} onChange={e => setNovaSaida({ ...novaSaida, valor: e.target.value })}
                placeholder="Valor" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              {saindo === "saida_despesa" && (
                <select value={novaSaida.categoria} onChange={e => setNovaSaida({ ...novaSaida, categoria: e.target.value })}
                  className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200">
                  {CATEGORIAS_DESPESA.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              )}
              <input value={novaSaida.descricao} onChange={e => setNovaSaida({ ...novaSaida, descricao: e.target.value })}
                placeholder="Descrição" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={() => setSaindo(null)} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
              <button onClick={confirmarSaida} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg">Registrar</button>
            </div>
          </div>
        </div>
      )}

      {ajustando && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setAjustando(false)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Ajuste de Cofre</h3>
            {erroAjuste && <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2 mb-3">{erroAjuste}</div>}
            <div className="space-y-2 mb-3">
              <input type="number" step="0.01" value={novoAjuste.valor} onChange={e => setNovoAjuste({ ...novoAjuste, valor: e.target.value })}
                placeholder="Valor (negativo para subtrair)" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novoAjuste.descricao} onChange={e => setNovoAjuste({ ...novoAjuste, descricao: e.target.value })}
                placeholder="Motivo do ajuste" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
            </div>
            <AutorizacaoGerencial permissao="financeiro.aprovar" onChange={setAutorizacao} />
            <div className="flex gap-2 mt-4">
              <button onClick={() => setAjustando(false)} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
              <button onClick={confirmarAjuste} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg">Confirmar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Registrar a aba em `web/src/app/financeiro/page.tsx`**

```tsx
import CofreTab from "./_components/CofreTab";
...
const TABS = [
  { key: "fluxo_caixa", label: "Fluxo Caixa" },
  { key: "receber", label: "Receber" },
  { key: "pagar", label: "Pagar" },
  { key: "boletos", label: "Boletos" },
  { key: "pix", label: "PIX" },
  { key: "conciliacao", label: "Conciliação" },
  { key: "banco", label: "Banco" },
  { key: "cofre", label: "Cofre" },
  { key: "dre", label: "DRE" },
] as const;
...
{activeTab === "cofre" && <CofreTab />}
```

- [ ] **Step 4: Rodar typecheck**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros

- [ ] **Step 5: Testar manualmente no browser**

`npm run dev` em `web/`, abrir `/financeiro`, clicar na aba "Cofre", trocar de loja, registrar 1 saída e 1 ajuste (com PIN ou crachá de um usuário de teste com `financeiro.aprovar`), confirmar saldo atualiza e extrato lista os 2 movimentos.

- [ ] **Step 6: Commit**

```bash
git add web/src/app/financeiro/_components/CofreTab.tsx web/src/app/financeiro/page.tsx web/src/lib/api.ts
git commit -m "feat: aba Cofre no Financeiro com saida/ajuste e alcada de aprovacao"
```

---

## Fase 3 — Financeiro: Relatórios (somente leitura)

### Task 10: Backend — `vendas_por_loja` e `movimento_diario_por_loja`

**Files:**
- Create: `hermes_agents/core/financeiro_relatorios.py`
- Test: Create `hermes_agents/tests/test_financeiro_relatorios.py`

**Interfaces:**
- Produces:
  - `vendas_por_loja(de: str, ate: str, loja_ids: list = None) -> dict` — retorna `{"lojas": [{id,nome}], "dias": [{"data": "YYYY-MM-DD", "valores_por_loja": {loja_id: valor}, "total_dia": valor}], "totais_por_loja": {loja_id: valor}}`
  - `movimento_diario_por_loja(de: str, ate: str, loja_id: int) -> dict` — retorna `{"dias": [{"data":..., "receita_por_forma": {...}, "despesa_por_categoria": {...}, "total_liquido": valor}]}`

- [ ] **Step 1: Escrever os testes que falham**

```python
# hermes_agents/tests/test_financeiro_relatorios.py
"""Relatorios Financeiro (read-only) — vendas por loja/dia, movimento diario por loja."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch


class _RelatorioDB:
    def __init__(self, vendas_pdv=None, vendas_bling=None, pagamentos=None, despesas=None, lojas=None):
        self.vendas_pdv = vendas_pdv or []
        self.vendas_bling = vendas_bling or []
        self.pagamentos = pagamentos or []
        self.despesas = despesas or []
        self.lojas = lojas or []

    async def fetch(self, query, *params):
        q = " ".join(query.split())
        if "FROM lojas" in q:
            return self.lojas
        if "FROM pdv_vendas" in q and "GROUP BY" in q:
            return self.vendas_pdv
        if "FROM vendas_pedidos" in q and "GROUP BY" in q:
            return self.vendas_bling
        if "FROM pdv_pagamentos" in q:
            return self.pagamentos
        if "FROM fin_cofre_movimentos" in q:
            return self.despesas
        return []

    async def fetchval(self, query, *params):
        return 0

    async def fetchrow(self, query, *params):
        return None

    async def execute(self, query, *params):
        return "OK"


async def _get_relatorio_db(db):
    return db


class TestVendasPorLoja(unittest.TestCase):
    def test_agrega_pdv_e_bling_por_loja_e_dia(self):
        import core.financeiro_relatorios as rel
        db = _RelatorioDB(
            lojas=[{"id": 1, "nome": "Loja A"}, {"id": 2, "nome": "Loja B"}],
            vendas_pdv=[{"loja_id": 1, "dia": "2026-08-01", "total": 100.0}],
            vendas_bling=[{"loja_id": 2, "dia": "2026-08-01", "total": 50.0}],
        )
        with patch("core.financeiro_relatorios.get_db", side_effect=lambda: _get_relatorio_db(db)):
            r = rel.vendas_por_loja("2026-08-01", "2026-08-01")
        self.assertEqual(r["dias"][0]["valores_por_loja"][1], 100.0)
        self.assertEqual(r["dias"][0]["valores_por_loja"][2], 50.0)
        self.assertEqual(r["dias"][0]["total_dia"], 150.0)
        self.assertEqual(r["totais_por_loja"][1], 100.0)

    def test_filtra_por_loja_ids_quando_informado(self):
        """usuario com acesso restrito so' ve as lojas permitidas."""
        import core.financeiro_relatorios as rel
        db = _RelatorioDB(lojas=[{"id": 1, "nome": "Loja A"}, {"id": 2, "nome": "Loja B"}])
        with patch("core.financeiro_relatorios.get_db", side_effect=lambda: _get_relatorio_db(db)):
            r = rel.vendas_por_loja("2026-08-01", "2026-08-01", loja_ids=[1])
        self.assertEqual([l["id"] for l in r["lojas"]], [1])

    def test_periodo_de_um_dia_so_funciona_com_de_igual_ate(self):
        import core.financeiro_relatorios as rel
        db = _RelatorioDB(lojas=[{"id": 1, "nome": "Loja A"}])
        with patch("core.financeiro_relatorios.get_db", side_effect=lambda: _get_relatorio_db(db)):
            r = rel.vendas_por_loja("2026-08-01", "2026-08-01")
        self.assertEqual(len(r["dias"]), 1)
        self.assertEqual(r["dias"][0]["data"], "2026-08-01")


class TestMovimentoDiarioPorLoja(unittest.TestCase):
    def test_receita_por_forma_menos_despesa_por_categoria(self):
        import core.financeiro_relatorios as rel
        db = _RelatorioDB(
            pagamentos=[{"dia": "2026-08-01", "forma": "pix", "total": 300.0}, {"dia": "2026-08-01", "forma": "dinheiro", "total": 100.0}],
            despesas=[{"dia": "2026-08-01", "categoria": "padaria", "total": 50.0}],
        )
        with patch("core.financeiro_relatorios.get_db", side_effect=lambda: _get_relatorio_db(db)):
            r = rel.movimento_diario_por_loja("2026-08-01", "2026-08-01", 1)
        dia = r["dias"][0]
        self.assertEqual(dia["receita_por_forma"]["pix"], 300.0)
        self.assertEqual(dia["despesa_por_categoria"]["padaria"], 50.0)
        self.assertEqual(dia["total_liquido"], 400.0 - 50.0)

    def test_loja_sem_cofre_ainda_despesa_zero_sem_erro(self):
        import core.financeiro_relatorios as rel
        db = _RelatorioDB(pagamentos=[{"dia": "2026-08-01", "forma": "pix", "total": 100.0}], despesas=[])
        with patch("core.financeiro_relatorios.get_db", side_effect=lambda: _get_relatorio_db(db)):
            r = rel.movimento_diario_por_loja("2026-08-01", "2026-08-01", 1)
        self.assertEqual(r["dias"][0]["despesa_por_categoria"], {})
        self.assertEqual(r["dias"][0]["total_liquido"], 100.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar teste, confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_financeiro_relatorios.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.financeiro_relatorios'`

- [ ] **Step 3: Implementar**

```python
# hermes_agents/core/financeiro_relatorios.py
"""Relatorios read-only do Financeiro por loja/dia — nao duplica dados,
so' agrega pdv_vendas/vendas_pedidos/pdv_pagamentos/fin_cofre_movimentos
ja existentes."""
from core import get_db, run_async

AGENT = "Financeiro Relatorios"


def vendas_por_loja(de: str, ate: str, loja_ids: list = None) -> dict:
    async def _go():
        db = await get_db()
        if loja_ids:
            placeholders = ",".join(str(int(i)) for i in loja_ids)
            filtro_lojas = f" AND id IN ({placeholders})"
        else:
            filtro_lojas = ""
        lojas = await db.fetch(f"SELECT id, nome FROM lojas WHERE ativa = true{filtro_lojas} ORDER BY nome")

        filtro_pdv = f" AND venda.caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id IN ({','.join(str(int(i)) for i in loja_ids)}))" if loja_ids else ""
        vendas_pdv = await db.fetch(f"""
            SELECT c.loja_id AS loja_id, DATE(venda.data) AS dia, COALESCE(SUM(venda.total),0) AS total
            FROM pdv_vendas venda JOIN pdv_caixas c ON c.id = venda.caixa_id
            WHERE venda.status = 'finalizada' AND DATE(venda.data) BETWEEN $1 AND $2 AND c.loja_id IS NOT NULL{filtro_pdv}
            GROUP BY c.loja_id, DATE(venda.data)
        """, de, ate)

        filtro_bling = f" AND loja_id IN ({','.join(str(int(i)) for i in loja_ids)})" if loja_ids else ""
        vendas_bling = await db.fetch(f"""
            SELECT loja_id, DATE(data) AS dia, COALESCE(SUM(total),0) AS total
            FROM vendas_pedidos
            WHERE status != 'cancelado' AND DATE(data) BETWEEN $1 AND $2 AND loja_id IS NOT NULL{filtro_bling}
            GROUP BY loja_id, DATE(data)
        """, de, ate)

        por_dia = {}
        totais_por_loja = {}
        for r in list(vendas_pdv) + list(vendas_bling):
            dia = str(r["dia"])
            loja_id = r["loja_id"]
            valor = float(r["total"] or 0)
            por_dia.setdefault(dia, {})
            por_dia[dia][loja_id] = por_dia[dia].get(loja_id, 0.0) + valor
            totais_por_loja[loja_id] = totais_por_loja.get(loja_id, 0.0) + valor

        dias_ordenados = sorted(por_dia.keys())
        dias = [{"data": d, "valores_por_loja": por_dia[d], "total_dia": round(sum(por_dia[d].values()), 2)} for d in dias_ordenados]
        return {
            "lojas": [dict(l) for l in lojas],
            "dias": dias,
            "totais_por_loja": {k: round(v, 2) for k, v in totais_por_loja.items()},
        }
    try: return run_async(_go())
    except Exception as e: return {"lojas": [], "dias": [], "totais_por_loja": {}, "error": str(e)}


def movimento_diario_por_loja(de: str, ate: str, loja_id: int) -> dict:
    async def _go():
        db = await get_db()
        pagamentos = await db.fetch("""
            SELECT DATE(v.data) AS dia, p.forma AS forma, COALESCE(SUM(p.valor),0) AS total
            FROM pdv_pagamentos p
            JOIN pdv_vendas v ON v.id = p.venda_id
            JOIN pdv_caixas c ON c.id = v.caixa_id
            WHERE v.status = 'finalizada' AND c.loja_id = $1 AND DATE(v.data) BETWEEN $2 AND $3
            GROUP BY DATE(v.data), p.forma
        """, loja_id, de, ate)
        despesas = await db.fetch("""
            SELECT m.data AS dia, m.categoria AS categoria, COALESCE(SUM(m.valor),0) AS total
            FROM fin_cofre_movimentos m
            JOIN fin_cofre cf ON cf.id = m.cofre_id
            WHERE cf.loja_id = $1 AND m.tipo = 'saida_despesa' AND m.data BETWEEN $2 AND $3
            GROUP BY m.data, m.categoria
        """, loja_id, de, ate)

        por_dia = {}
        for r in pagamentos:
            dia = str(r["dia"])
            por_dia.setdefault(dia, {"receita_por_forma": {}, "despesa_por_categoria": {}})
            por_dia[dia]["receita_por_forma"][r["forma"]] = por_dia[dia]["receita_por_forma"].get(r["forma"], 0.0) + float(r["total"] or 0)
        for r in despesas:
            dia = str(r["dia"])
            por_dia.setdefault(dia, {"receita_por_forma": {}, "despesa_por_categoria": {}})
            categoria = r["categoria"] or "outros"
            por_dia[dia]["despesa_por_categoria"][categoria] = por_dia[dia]["despesa_por_categoria"].get(categoria, 0.0) + float(r["total"] or 0)

        dias = []
        for dia in sorted(por_dia.keys()):
            receita_total = sum(por_dia[dia]["receita_por_forma"].values())
            despesa_total = sum(por_dia[dia]["despesa_por_categoria"].values())
            dias.append({
                "data": dia,
                "receita_por_forma": {k: round(v, 2) for k, v in por_dia[dia]["receita_por_forma"].items()},
                "despesa_por_categoria": {k: round(v, 2) for k, v in por_dia[dia]["despesa_por_categoria"].items()},
                "total_liquido": round(receita_total - despesa_total, 2),
            })
        return {"dias": dias}
    try: return run_async(_go())
    except Exception as e: return {"dias": [], "error": str(e)}
```

- [ ] **Step 4: Rodar teste, confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_financeiro_relatorios.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/financeiro_relatorios.py hermes_agents/tests/test_financeiro_relatorios.py
git commit -m "feat: relatorios Vendas por Loja e Movimento Diario por Loja (read-only)"
```

---

### Task 11: Rotas dos relatórios (RBAC + filtro por `lojas_permitidas`)

**Files:**
- Create: `hermes_agents/routes/financeiro_relatorios.py`
- Modify: `hermes_agents/athena_bridge.py` (registrar blueprint)
- Test: Create `hermes_agents/tests/test_financeiro_relatorios_rotas.py`

**Interfaces:**
- Consumes: `core.financeiro_relatorios.{vendas_por_loja, movimento_diario_por_loja}` (Task 10), `core.rbac_lojas.lojas_permitidas`, `core.rbac.{requer_permissao, requer_acesso_loja, usuario_atual_da_request}`.
- Produces:
  - `GET /api/financeiro/relatorios/vendas-por-loja?de=&ate=` (financeiro.ver)
  - `GET /api/financeiro/relatorios/movimento-diario?de=&ate=&loja_id=` (financeiro.ver + requer_acesso_loja)

- [ ] **Step 1: Escrever os testes que falham**

```python
# hermes_agents/tests/test_financeiro_relatorios_rotas.py
"""Rotas de relatorios Financeiro — RBAC financeiro.ver + filtro por lojas_permitidas."""
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
from routes.financeiro_relatorios import financeiro_relatorios_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(financeiro_relatorios_bp)
    return app.test_client()


class TestRelatoriosRBAC(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_vendas_por_loja_sem_permissao_bloqueia(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Vendedor")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]):
            r = self.client.get("/api/financeiro/relatorios/vendas-por-loja?de=2026-08-01&ate=2026-08-01", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_vendas_por_loja_com_permissao_filtra_por_lojas_permitidas(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.ver"]), \
             patch("core.rbac_lojas.lojas_permitidas", return_value=[1]), \
             patch("core.financeiro_relatorios.vendas_por_loja", return_value={"lojas": [], "dias": [], "totais_por_loja": {}}) as mock_rel:
            r = self.client.get("/api/financeiro/relatorios/vendas-por-loja?de=2026-08-01&ate=2026-08-01", headers=headers)
        self.assertEqual(r.status_code, 200)
        args, kwargs = mock_rel.call_args
        self.assertEqual(kwargs.get("loja_ids") or args[2], [1])

    def test_movimento_diario_loja_fora_da_lista_bloqueia(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.ver"]), \
             patch("core.rbac_lojas.lojas_permitidas", return_value=[1]):
            r = self.client.get("/api/financeiro/relatorios/movimento-diario?de=2026-08-01&ate=2026-08-01&loja_id=2", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_movimento_diario_loja_permitida_passa(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.ver"]), \
             patch("core.rbac_lojas.lojas_permitidas", return_value=[1]), \
             patch("core.financeiro_relatorios.movimento_diario_por_loja", return_value={"dias": []}):
            r = self.client.get("/api/financeiro/relatorios/movimento-diario?de=2026-08-01&ate=2026-08-01&loja_id=1", headers=headers)
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar teste, confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_financeiro_relatorios_rotas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'routes.financeiro_relatorios'`

- [ ] **Step 3: Implementar**

```python
# hermes_agents/routes/financeiro_relatorios.py
from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao, requer_acesso_loja, usuario_atual_da_request

financeiro_relatorios_bp = Blueprint("financeiro_relatorios", __name__, url_prefix="/api/financeiro/relatorios")


@financeiro_relatorios_bp.route("/vendas-por-loja", methods=["GET"])
def relatorio_vendas_por_loja():
    @requer_permissao("financeiro.ver")
    def _go():
        from core.financeiro_relatorios import vendas_por_loja
        from core.rbac_lojas import lojas_permitidas
        de = request.args.get("de")
        ate = request.args.get("ate")
        if not de or not ate:
            return jsonify({"error": "Parametros de e ate sao obrigatorios"}), 400
        permitidas = lojas_permitidas(usuario_atual_da_request().get("user_id"))
        return jsonify(vendas_por_loja(de, ate, loja_ids=permitidas))
    return _go()


@financeiro_relatorios_bp.route("/movimento-diario", methods=["GET"])
def relatorio_movimento_diario():
    loja_id = request.args.get("loja_id", type=int)

    @requer_acesso_loja
    @requer_permissao("financeiro.ver")
    def _go(loja_id):
        from core.financeiro_relatorios import movimento_diario_por_loja
        de = request.args.get("de")
        ate = request.args.get("ate")
        if not de or not ate or not loja_id:
            return jsonify({"error": "Parametros de, ate e loja_id sao obrigatorios"}), 400
        return jsonify(movimento_diario_por_loja(de, ate, loja_id))
    return _go(loja_id=loja_id)
```

Registrar em `hermes_agents/athena_bridge.py`, junto dos demais:

```python
from routes.financeiro_relatorios import financeiro_relatorios_bp
...
app.register_blueprint(financeiro_relatorios_bp)
```

- [ ] **Step 4: Rodar teste, confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_financeiro_relatorios_rotas.py -v`
Expected: PASS

- [ ] **Step 5: Rodar suite completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: todos passam

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/financeiro_relatorios.py hermes_agents/athena_bridge.py hermes_agents/tests/test_financeiro_relatorios_rotas.py
git commit -m "feat: rotas de relatorios Vendas por Loja e Movimento Diario, filtradas por lojas_permitidas"
```

---

### Task 12: Frontend — aba "Relatórios" em Financeiro

**Files:**
- Create: `web/src/app/financeiro/_components/RelatoriosTab.tsx`
- Modify: `web/src/app/financeiro/page.tsx` (adicionar tab)
- Modify: `web/src/lib/api.ts` (adicionar `finRelatorioVendasPorLoja`/`finRelatorioMovimentoDiario`)

**Interfaces:**
- Consumes: `GET /api/financeiro/relatorios/vendas-por-loja`, `GET /api/financeiro/relatorios/movimento-diario` (Task 11); `api.lojasManage()` pro seletor de loja do Movimento Diário.

- [ ] **Step 1: Adicionar funções em `web/src/lib/api.ts`**

```typescript
finRelatorioVendasPorLoja: (de: string, ate: string) =>
  request<{ lojas: Array<{ id: number; nome: string }>; dias: Array<{ data: string; valores_por_loja: Record<number, number>; total_dia: number }>; totais_por_loja: Record<number, number> }>(`/api/financeiro/relatorios/vendas-por-loja?de=${de}&ate=${ate}`),
finRelatorioMovimentoDiario: (de: string, ate: string, lojaId: number) =>
  request<{ dias: Array<{ data: string; receita_por_forma: Record<string, number>; despesa_por_categoria: Record<string, number>; total_liquido: number }> }>(`/api/financeiro/relatorios/movimento-diario?de=${de}&ate=${ate}&loja_id=${lojaId}`),
```

- [ ] **Step 2: Implementar `RelatoriosTab.tsx`**

```tsx
"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt } from "@/lib/format";

interface Loja { id: number; nome: string; ativa: boolean; }

function hojeISO() { return new Date().toISOString().slice(0, 10); }
function inicioMesISO() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`; }

export default function RelatoriosTab() {
  const [sub, setSub] = useState<"vendas" | "movimento">("vendas");
  const [de, setDe] = useState(inicioMesISO());
  const [ate, setAte] = useState(hojeISO());
  const [lojas, setLojas] = useState<Loja[]>([]);
  const [lojaId, setLojaId] = useState<number | null>(null);

  const [vendas, setVendas] = useState<{ lojas: { id: number; nome: string }[]; dias: { data: string; valores_por_loja: Record<number, number>; total_dia: number }[]; totais_por_loja: Record<number, number> } | null>(null);
  const [movimento, setMovimento] = useState<{ dias: { data: string; receita_por_forma: Record<string, number>; despesa_por_categoria: Record<string, number>; total_liquido: number }[] } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.lojasManage().then(r => { setLojas(r.lojas || []); if (r.lojas?.length) setLojaId(r.lojas[0].id); }).catch(() => {});
  }, []);

  const buscar = () => {
    setLoading(true);
    if (sub === "vendas") {
      api.finRelatorioVendasPorLoja(de, ate).then(setVendas).catch(() => {}).finally(() => setLoading(false));
    } else if (lojaId) {
      api.finRelatorioMovimentoDiario(de, ate, lojaId).then(setMovimento).catch(() => {}).finally(() => setLoading(false));
    }
  };
  useEffect(() => { buscar(); }, [sub, lojaId]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={() => setSub("vendas")} className={`px-3 py-1.5 text-xs rounded-md ${sub === "vendas" ? "bg-indigo-600 text-white" : "bg-neutral-800 text-neutral-400"}`}>Vendas por Loja</button>
        <button onClick={() => setSub("movimento")} className={`px-3 py-1.5 text-xs rounded-md ${sub === "movimento" ? "bg-indigo-600 text-white" : "bg-neutral-800 text-neutral-400"}`}>Movimento Diário</button>
        <input type="date" value={de} onChange={e => setDe(e.target.value)} className="bg-neutral-900 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200" />
        <span className="text-neutral-500 text-xs">até</span>
        <input type="date" value={ate} onChange={e => setAte(e.target.value)} className="bg-neutral-900 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200" />
        {sub === "movimento" && (
          <select value={lojaId ?? ""} onChange={e => setLojaId(Number(e.target.value))}
            className="bg-neutral-900 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200">
            {lojas.map(l => <option key={l.id} value={l.id}>{l.nome}</option>)}
          </select>
        )}
        <button onClick={buscar} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">Buscar</button>
      </div>

      {loading && <p className="text-xs text-neutral-500">Carregando...</p>}

      {!loading && sub === "vendas" && vendas && (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="border-b border-neutral-700 text-neutral-400 text-left">
              <th className="px-4 py-2 font-medium">Dia</th>
              {vendas.lojas.map(l => <th key={l.id} className="px-4 py-2 font-medium">{l.nome}</th>)}
              <th className="px-4 py-2 font-medium">Total</th>
            </tr></thead>
            <tbody>{vendas.dias.map(d => (
              <tr key={d.data} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300">
                <td className="px-4 py-2.5">{new Date(d.data + "T00:00:00").toLocaleDateString("pt-BR")}</td>
                {vendas.lojas.map(l => <td key={l.id} className="px-4 py-2.5">{fmt(d.valores_por_loja[l.id] || 0)}</td>)}
                <td className="px-4 py-2.5 font-medium text-emerald-400">{fmt(d.total_dia)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}

      {!loading && sub === "movimento" && movimento && (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="border-b border-neutral-700 text-neutral-400 text-left">
              <th className="px-4 py-2 font-medium">Dia</th><th className="px-4 py-2 font-medium">Receita (por forma)</th>
              <th className="px-4 py-2 font-medium">Despesa (por categoria)</th><th className="px-4 py-2 font-medium">Total Líquido</th>
            </tr></thead>
            <tbody>{movimento.dias.map(d => (
              <tr key={d.data} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300 align-top">
                <td className="px-4 py-2.5">{new Date(d.data + "T00:00:00").toLocaleDateString("pt-BR")}</td>
                <td className="px-4 py-2.5">{Object.entries(d.receita_por_forma).map(([f, v]) => <div key={f}>{f}: {fmt(v)}</div>)}</td>
                <td className="px-4 py-2.5">{Object.entries(d.despesa_por_categoria).map(([c, v]) => <div key={c}>{c}: {fmt(v)}</div>)}</td>
                <td className={`px-4 py-2.5 font-medium ${d.total_liquido >= 0 ? "text-emerald-400" : "text-red-400"}`}>{fmt(d.total_liquido)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Registrar a aba em `web/src/app/financeiro/page.tsx`**

```tsx
import RelatoriosTab from "./_components/RelatoriosTab";
...
  { key: "cofre", label: "Cofre" },
  { key: "relatorios", label: "Relatórios" },
  { key: "dre", label: "DRE" },
] as const;
...
{activeTab === "relatorios" && <RelatoriosTab />}
```

- [ ] **Step 4: Rodar typecheck**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros

- [ ] **Step 5: Testar manualmente no browser**

`npm run dev`, abrir `/financeiro` → aba "Relatórios", checar Vendas por Loja com período de 1 dia (`de == ate`) e período de um mês, e Movimento Diário trocando de loja.

- [ ] **Step 6: Commit**

```bash
git add web/src/app/financeiro/_components/RelatoriosTab.tsx web/src/app/financeiro/page.tsx web/src/lib/api.ts
git commit -m "feat: aba Relatorios no Financeiro (Vendas por Loja, Movimento Diario)"
```

---

## Verificação final

- [ ] Rodar suite Python completa 2x seguidas pra checar estabilidade: `cd hermes_agents && python -m pytest tests/ -q` (2x)
- [ ] Rodar typecheck completo do frontend: `cd web && npx tsc --noEmit`
- [ ] Testar manualmente o fluxo de ponta a ponta: abrir caixa PDV → vender com pagamento em maquineta → fechar caixa com contagem+conferência → conferir que a sangria (se houver) aparece no Cofre da loja → registrar uma saída de despesa e um ajuste no Cofre → conferir os 2 relatórios da aba Relatórios refletem os números.
