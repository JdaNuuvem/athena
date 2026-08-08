# Fiscal — Limpeza e Fundação Real (Fase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remover dado fabricado e andaime morto da área Fiscal, e transformar Tributos e Obrigações em dados reais e editáveis — fundação limpa antes das Fases 2 (Registro de Entrada) e 3 (Export pro contador).

**Architecture:** Backend Flask + asyncpg (`hermes_agents/`), frontend Next.js (`web/`). Segue a convenção já estabelecida no repo: nunca `DROP TABLE`/`DROP COLUMN` em produção — só parar de criar/usar/expor o que não serve mais (mesmo padrão já visto em `fiscal_contas_receber_bling`, que já ficou órfã sem nunca ter sido apagada). Tabelas/colunas removidas do código ficam fisicamente no banco, inertes, sem risco de perda de dado.

**Tech Stack:** Flask, asyncpg, Postgres, Next.js 15 App Router, React 19, Tailwind v4.

## Global Constraints

- `/fiscal/notas` e `/fiscal/apuracao` (frontend, backend, testes) não são tocados nesta fase — nem código, nem comportamento.
- Nunca `DROP TABLE`/`DROP COLUMN`/`ALTER TABLE ... DROP COLUMN` em nenhuma task — só remover a criação/uso em código Python/TS. Tabela ou coluna que já existir no banco fica lá, inerte.
- Toda tabela nova segue o padrão `CREATE TABLE IF NOT EXISTS` idempotente já usado em todo `_ensure_tables()`/`_ensure_cols()` do projeto.
- RBAC segue a convenção já estabelecida: `fiscal.ver`/`fiscal.criar`/`fiscal.editar`/`fiscal.excluir`.
- Sem emissão própria de NF-e/NFC-e nesta fase (nem física nem virtual).
- Sem cálculo automático de tributos (fica com o contador/i9Logic) — por isso `calcular_tributos_nota` sai, não fica "melhorado".

---

### Task 1: Backend — remove tabelas, colunas e rotas mortas

**Files:**
- Modify: `hermes_agents/core/fiscal.py:1-120` (remove criação de `fiscal_contas_receber_bling`/`fiscal_contas_pagar_bling`, remove do `TABLES`, remove `calcular_tributos_nota`)
- Modify: `hermes_agents/routes/fiscal.py:18-60` (remove rotas `/tabelas/cfop`, `/tabelas/ncm`, `/tabelas/cest`), `:142-149` (remove rota `/tributos/calcular/<id>`)
- Modify: `hermes_agents/core/pdv.py:350-357,425` (remove tabela `pdv_nfce`, remove `"nfce"` de `TABLES`)
- Modify: `hermes_agents/core/lojas_fiscal_financeiro.py` (remove `_FISCAL_DDL`, `CAMPOS_FISCAL`, `atualizar_fiscal`, tira campos fiscais de `CAMPOS_SENSIVEIS`)
- Modify: `hermes_agents/routes/lojas_config.py:36-45` (remove import e registro da seção "fiscal")
- Modify: `web/src/lib/api.ts:661-662` (remove `lojasFiscalAtualizar`), `:1745-1748` (remove `fiscalCalcularTributos`)
- Modify: `hermes_agents/tests/test_fiscal_apuracao_fechamento.py:254-281` (remove `TestCalcularTributosNotaDecimal`)
- Modify: `hermes_agents/tests/test_lojas_fiscal_financeiro.py` (remove `test_atualizar_fiscal`, restringe testes de máscara a `pix_chave`)
- Modify: `hermes_agents/tests/test_lojas_manage_seguranca.py:153-165` (restringe `test_obter_loja_esconde_campos_sensiveis` a `pix_chave`)
- Test: `hermes_agents/tests/test_fiscal_seguranca.py` (adiciona teste de regressão: rotas removidas retornam 404)

**Interfaces:**
- Produces: `core.fiscal.TABLES = ["tributos","obrigacoes","notas_fiscais","nfe_itens","impostos_nota"]` (sem `contas_receber_bling`/`contas_pagar_bling`)
- Produces: `core.lojas_fiscal_financeiro.CAMPOS_SENSIVEIS = {"pix_chave"}`

- [ ] **Step 1: Remover tabelas/rotas mortas em `core/fiscal.py`**

Em `hermes_agents/core/fiscal.py`, localizar (linha 7):
```python
TABLES = ["tributos","obrigacoes","notas_fiscais","nfe_itens","impostos_nota","contas_receber_bling","contas_pagar_bling"]
```
Substituir por:
```python
TABLES = ["tributos","obrigacoes","notas_fiscais","nfe_itens","impostos_nota"]
```

Localizar e remover por completo os blocos de criação (linhas 74-95):
```python
        await db.execute("""CREATE TABLE IF NOT EXISTS fiscal_contas_receber_bling (
            id SERIAL PRIMARY KEY, bling_id BIGINT,
            numero VARCHAR(50), descricao VARCHAR(200),
            contato_nome VARCHAR(200), contato_documento VARCHAR(20),
            valor DECIMAL(12,2) DEFAULT 0, valor_pago DECIMAL(12,2) DEFAULT 0,
            vencimento DATE, data_recebimento DATE, data_emissao DATE,
            situacao VARCHAR(30) DEFAULT 'pendente', forma_pagamento VARCHAR(50),
            portador VARCHAR(100), categoria VARCHAR(100),
            data_pagamento DATE, competencia VARCHAR(7),
            sincronizado_em TIMESTAMP DEFAULT NOW(), created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fiscal_contas_pagar_bling (
            id SERIAL PRIMARY KEY, bling_id BIGINT,
            numero VARCHAR(50), descricao VARCHAR(200),
            fornecedor_nome VARCHAR(200), fornecedor_documento VARCHAR(20),
            valor DECIMAL(12,2) DEFAULT 0, valor_pago DECIMAL(12,2) DEFAULT 0,
            vencimento DATE, data_pagamento DATE, data_emissao DATE,
            situacao VARCHAR(30) DEFAULT 'pendente', forma_pagamento VARCHAR(50),
            portador VARCHAR(100), categoria VARCHAR(100),
            competencia VARCHAR(7),
            sincronizado_em TIMESTAMP DEFAULT NOW(), created_at TIMESTAMP DEFAULT NOW()
        )""")
```
(o comentário e a criação de `fiscal_apuracao_fechada` logo depois continuam intactos, sem mudança).

Remover a função inteira `calcular_tributos_nota` (linhas 226-259, do `def calcular_tributos_nota` até o `except Exception as e: return {"error": str(e)}` que a fecha, imediatamente antes de `# ── Obrigacoes ──`).

- [ ] **Step 2: Remover rotas mortas em `routes/fiscal.py`**

Remover por completo (linhas 18-60):
```python
@fiscal_bp.route("/tabelas/cfop", methods=["GET"])
def fiscal_tabelas_cfop():
    @requer_permissao("fiscal.ver")
    def _go():
        async def _query():
            db = await get_db()
            rows = await db.fetch("SELECT DISTINCT cfop as codigo, natureza_operacao as descricao, tipo FROM fiscal_notas_fiscais WHERE cfop IS NOT NULL AND cfop != '' ORDER BY cfop LIMIT 50")
            return [dict(r) for r in (rows or [])]
        try:
            return jsonify(run_async(_query()))
        except Exception:
            return jsonify([])
    return _go()


@fiscal_bp.route("/tabelas/ncm", methods=["GET"])
def fiscal_tabelas_ncm():
    @requer_permissao("fiscal.ver")
    def _go():
        async def _query():
            db = await get_db()
            rows = await db.fetch("SELECT DISTINCT ncm as codigo, '' as descricao FROM fiscal_nfe_itens WHERE ncm IS NOT NULL AND ncm != '' ORDER BY ncm LIMIT 50")
            return [dict(r) for r in (rows or [])]
        try:
            return jsonify(run_async(_query()))
        except Exception:
            return jsonify([])
    return _go()


@fiscal_bp.route("/tabelas/cest", methods=["GET"])
def fiscal_tabelas_cest():
    @requer_permissao("fiscal.ver")
    def _go():
        async def _query():
            db = await get_db()
            rows = await db.fetch("SELECT DISTINCT cest as codigo, '' as descricao FROM fiscal_nfe_itens WHERE cest IS NOT NULL AND cest != '' ORDER BY cest LIMIT 50")
            return [dict(r) for r in (rows or [])]
        try:
            return jsonify(run_async(_query()))
        except Exception:
            return jsonify([])
    return _go()


```
(mantém a linha `@fiscal_bp.route("/<tabela>", methods=["GET"])` e tudo depois, intocado).

Remover por completo (linhas 142-150):
```python
@fiscal_bp.route("/tributos/calcular/<int:nota_id>", methods=["GET"])
def fiscal_calcular_tributos(nota_id):
    from core.fiscal import calcular_tributos_nota

    @requer_permissao("fiscal.ver")
    def _go():
        return jsonify(calcular_tributos_nota(nota_id))
    return _go()


```

- [ ] **Step 3: Remover `pdv_nfce`**

Em `hermes_agents/core/pdv.py`, remover o bloco (linhas 350-355):
```python
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_nfce (
            id SERIAL PRIMARY KEY, venda_id INT REFERENCES pdv_vendas(id),
            numero VARCHAR(20), chave_acesso VARCHAR(50), serie VARCHAR(10),
            status VARCHAR(30) DEFAULT 'emitida', xml_url VARCHAR(500),
            data_emissao TIMESTAMP DEFAULT NOW()
        )""")
```

Localizar (linha 425):
```python
TABLES = ["caixas","vendas","itens","pagamentos","sangrias","suprimentos","nfce","operadores","turnos","devolucoes"]
```
Substituir por:
```python
TABLES = ["caixas","vendas","itens","pagamentos","sangrias","suprimentos","operadores","turnos","devolucoes"]
```

Atualizar o docstring do módulo (linha 1), de:
```python
"""PDV Core — Vendas, Caixa, Pagamentos, Sangria, Suprimento, Fechamento, NFCe"""
```
para:
```python
"""PDV Core — Vendas, Caixa, Pagamentos, Sangria, Suprimento, Fechamento"""
```

- [ ] **Step 4: Remover config fiscal de loja em `core/lojas_fiscal_financeiro.py`**

Ler o arquivo completo antes de editar (`hermes_agents/core/lojas_fiscal_financeiro.py`, 70 linhas). Substituir o conteúdo inteiro por:

```python
"""Configuracoes financeiras e de estoque da loja — colunas
adicionais na tabela "lojas" ja criada por core/lojas.py."""
from core import get_db, run_async
from core.lojas import _log_erro, _update_campos

_FINANCEIRO_DDL = [
    ("conta_bancaria", "VARCHAR(100)"),
    ("conta_caixa_padrao", "VARCHAR(100)"),
    ("centro_financeiro", "VARCHAR(100)"),
    ("carteira_padrao", "VARCHAR(100)"),
    ("gateway_pagamento", "VARCHAR(50)"),
    ("pix_chave", "VARCHAR(150)"),
]
_ESTOQUE_CONFIG_DDL = [
    ("deposito_principal", "VARCHAR(100)"),
    ("permitir_estoque_negativo", "BOOLEAN DEFAULT FALSE"),
    ("estoque_minimo_padrao", "NUMERIC(10,2)"),
    ("estoque_reservado", "BOOLEAN DEFAULT FALSE"),
]
CAMPOS_FINANCEIRO = {nome for nome, _ in _FINANCEIRO_DDL}
CAMPOS_ESTOQUE_CONFIG = {nome for nome, _ in _ESTOQUE_CONFIG_DDL}

# Nunca deve voltar em texto puro em audit_log/system_logs.
CAMPOS_SENSIVEIS = {"pix_chave"}


def _ensure_cols():
    async def _go():
        db = await get_db()
        for col, ddl in _FINANCEIRO_DDL + _ESTOQUE_CONFIG_DDL:
            try: await db.execute(f"ALTER TABLE lojas ADD COLUMN IF NOT EXISTS {col} {ddl}")
            except Exception as e: _log_erro(f"ALTER lojas.{col} (financeiro/estoque)", e)
    try: run_async(_go())
    except Exception as e: _log_erro("lojas_fiscal_financeiro._ensure_cols (run_async)", e)


_ensure_cols()


def mascarar_para_auditoria(campos: dict) -> dict:
    """Substitui valor real dos campos sensiveis por um indicador booleano
    antes de gravar em audit_log — a auditoria registra QUE algo mudou, nunca
    o valor em si."""
    return {
        k: (f"configurado: {bool(v)}" if k in CAMPOS_SENSIVEIS else v)
        for k, v in campos.items()
    }


def atualizar_financeiro(id_loja: int, campos: dict) -> bool:
    return _update_campos(id_loja, campos, CAMPOS_FINANCEIRO)


def atualizar_estoque_config(id_loja: int, campos: dict) -> bool:
    return _update_campos(id_loja, campos, CAMPOS_ESTOQUE_CONFIG)
```

(Nota: o nome do arquivo/módulo `lojas_fiscal_financeiro.py` não muda nesta fase — renomear exigiria atualizar todos os imports em `routes/lojas_config.py`, `routes/lojas_manage.py` e os testes, fora do escopo de uma limpeza. Fica "fiscal" só no nome do arquivo, sem conteúdo fiscal dentro.)

- [ ] **Step 5: Remover registro da seção "fiscal" em `routes/lojas_config.py`**

Localizar (linhas 37-45):
```python
from core.lojas_fiscal_financeiro import (
    atualizar_fiscal, atualizar_financeiro, atualizar_estoque_config,
    CAMPOS_FISCAL, CAMPOS_FINANCEIRO, CAMPOS_ESTOQUE_CONFIG, mascarar_para_auditoria,
)
from core.lojas_virtual import atualizar_virtual, atualizar_delivery, CAMPOS_VIRTUAL, CAMPOS_DELIVERY

_registrar_secao("operacional", atualizar_operacional, CAMPOS_OPERACIONAL)
_registrar_secao("comercial", atualizar_comercial, CAMPOS_COMERCIAL)
_registrar_secao("fiscal", atualizar_fiscal, CAMPOS_FISCAL, mascarar=mascarar_para_auditoria)
_registrar_secao("financeiro", atualizar_financeiro, CAMPOS_FINANCEIRO, mascarar=mascarar_para_auditoria)
_registrar_secao("estoque-config", atualizar_estoque_config, CAMPOS_ESTOQUE_CONFIG)
```
Substituir por:
```python
from core.lojas_fiscal_financeiro import (
    atualizar_financeiro, atualizar_estoque_config,
    CAMPOS_FINANCEIRO, CAMPOS_ESTOQUE_CONFIG, mascarar_para_auditoria,
)
from core.lojas_virtual import atualizar_virtual, atualizar_delivery, CAMPOS_VIRTUAL, CAMPOS_DELIVERY

_registrar_secao("operacional", atualizar_operacional, CAMPOS_OPERACIONAL)
_registrar_secao("comercial", atualizar_comercial, CAMPOS_COMERCIAL)
_registrar_secao("financeiro", atualizar_financeiro, CAMPOS_FINANCEIRO, mascarar=mascarar_para_auditoria)
_registrar_secao("estoque-config", atualizar_estoque_config, CAMPOS_ESTOQUE_CONFIG)
```

- [ ] **Step 6: Remover funções mortas em `web/src/lib/api.ts`**

Localizar e remover (linhas 661-662):
```typescript
  lojasFiscalAtualizar: (id: number, campos: Record<string, unknown>) =>
    request<{ success?: boolean; error?: string }>(`/api/lojas/manage/${id}/fiscal`, { method: "PUT", body: JSON.stringify(campos) }),
```

Localizar e remover (linhas 1745-1748):
```typescript
export async function fiscalCalcularTributos(notaId: number): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/fiscal/tributos/calcular/${notaId}`);
  return res.json();
}

```

- [ ] **Step 7: Atualizar testes existentes que quebram com as remoções**

Em `hermes_agents/tests/test_fiscal_apuracao_fechamento.py`, remover a classe inteira (linhas 254-281):
```python
class TestCalcularTributosNotaDecimal(unittest.TestCase):
    def test_calcula_com_precisao_decimal(self):
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value={"id": 1, "valor_produtos": "100.10"})
        db.fetch = AsyncMock(return_value=[
            {"nome": "ICMS", "sigla": "ICMS", "aliquota": "18.0000"},
            {"nome": "PIS", "sigla": "PIS", "aliquota": "1.6500"},
        ])
        async def _fake_get_db(): return db
        with patch.object(fiscal, "get_db", _fake_get_db):
            r = fiscal.calcular_tributos_nota(1)
        self.assertNotIn("error", r)
        # 100.10 * 18% = 18.018 -> arredonda pra 18.02; 100.10 * 1.65% = 1.65165 -> 1.65
        icms = next(t for t in r["tributos"] if t["sigla"] == "ICMS")
        pis = next(t for t in r["tributos"] if t["sigla"] == "PIS")
        self.assertEqual(icms["valor"], 18.02)

    def test_nota_nao_encontrada(self):
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value=None)
        async def _fake_get_db(): return db
        with patch.object(fiscal, "get_db", _fake_get_db):
            r = fiscal.calcular_tributos_nota(999)
        self.assertEqual(r, {"error": "nota nao encontrada"})


```
(a linha em branco antes de `class TestSincronizarUmaNotaFiscal` some junto, sem deixar duas linhas em branco seguidas nem zero).

Em `hermes_agents/tests/test_lojas_fiscal_financeiro.py`, ler o arquivo completo (121 linhas) e substituir o conteúdo inteiro por:

```python
"""Testes de core/lojas_fiscal_financeiro.py — financeiro/estoque-config, e
a mascara de campos sensiveis antes de auditoria (chave PIX nunca em texto
puro em audit_log)."""
import sys, os, re, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


async def _mp(*a, **kw):
    return AsyncMock()


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.lojas as lojas
import core.lojas_fiscal_financeiro as ff


class FakeDB:
    def __init__(self):
        self.rows = {1: {"id": 1, "nome": "Loja Teste"}}

    async def execute(self, query, *params):
        q = " ".join(query.split())
        if "CREATE TABLE" in q or "ALTER TABLE" in q or "CREATE INDEX" in q:
            return "OK"
        m = re.match(r"UPDATE lojas SET (.+) WHERE id = \$(\d+)$", q)
        if m:
            id_loja = params[int(m.group(2)) - 1]
            if id_loja not in self.rows:
                return "UPDATE 0"
            for atrib in m.group(1).split(","):
                col, ph = [p.strip() for p in atrib.split("=")]
                self.rows[id_loja][col] = params[int(ph.lstrip("$")) - 1]
            return "UPDATE 1"
        return "OK"

    async def fetchval(self, query, *params):
        return 0

    async def fetchrow(self, query, *params):
        return None

    async def fetch(self, query, *params):
        return []


class TestLojasFiscalFinanceiro(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        self._p = patch("core.lojas.get_db", side_effect=_get_db)
        self._p.start()
        lojas._table_ok = True

    def tearDown(self):
        self._p.stop()
        lojas._table_ok = False

    async def test_atualizar_financeiro(self):
        ok = ff.atualizar_financeiro(1, {
            "conta_bancaria": "Banco X ag 0001 cc 12345", "gateway_pagamento": "mercado_pago",
            "pix_chave": "loja1@charme.com",
        })
        self.assertTrue(ok)
        self.assertEqual(self.fake.rows[1]["gateway_pagamento"], "mercado_pago")

    async def test_atualizar_estoque_config(self):
        ok = ff.atualizar_estoque_config(1, {
            "deposito_principal": "CD Nilopolis", "permitir_estoque_negativo": False,
            "estoque_minimo_padrao": 10.0, "estoque_reservado": True,
        })
        self.assertTrue(ok)
        row = self.fake.rows[1]
        self.assertEqual(row["deposito_principal"], "CD Nilopolis")
        self.assertTrue(row["estoque_reservado"])

    async def test_atualizar_estoque_config_permitir_negativo_false_nao_e_ignorado(self):
        """False e' um valor valido (nao deve ser filtrado como 'ausente')."""
        ok = ff.atualizar_estoque_config(1, {"permitir_estoque_negativo": False})
        self.assertTrue(ok)
        self.assertIn("permitir_estoque_negativo", self.fake.rows[1])
        self.assertFalse(self.fake.rows[1]["permitir_estoque_negativo"])

    def test_mascarar_para_auditoria_esconde_campos_sensiveis(self):
        campos = {
            "gateway_pagamento": "mercado_pago",
            "pix_chave": "loja1@charme.com",
        }
        mascarado = ff.mascarar_para_auditoria(campos)
        self.assertEqual(mascarado["gateway_pagamento"], "mercado_pago")
        self.assertNotEqual(mascarado["pix_chave"], campos["pix_chave"])
        self.assertTrue(mascarado["pix_chave"].startswith("configurado:"))

    def test_mascarar_para_auditoria_campo_vazio_marca_configurado_false(self):
        mascarado = ff.mascarar_para_auditoria({"pix_chave": ""})
        self.assertEqual(mascarado["pix_chave"], "configurado: False")


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

Em `hermes_agents/tests/test_lojas_manage_seguranca.py`, localizar (linhas 153-165):
```python
    def test_obter_loja_esconde_campos_sensiveis(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        loja_com_segredos = {
            "id": 1, "nome": "Loja Charme", "token_fiscal": "segredo-super-secreto",
            "pix_chave": "chave@pix.com", "certificado_digital": "/certs/x.pfx", "csc_nfce": "abc123",
        }
        with patch("core.lojas.obter", return_value=loja_com_segredos):
            r = self.client.get("/api/lojas/manage/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        body = r.get_json()["loja"]
        for campo in ("token_fiscal", "pix_chave", "certificado_digital", "csc_nfce"):
            self.assertNotIn(campo, body)
        self.assertEqual(body["nome"], "Loja Charme")
```
Substituir por:
```python
    def test_obter_loja_esconde_campos_sensiveis(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        loja_com_segredos = {
            "id": 1, "nome": "Loja Charme", "pix_chave": "chave@pix.com",
        }
        with patch("core.lojas.obter", return_value=loja_com_segredos):
            r = self.client.get("/api/lojas/manage/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        body = r.get_json()["loja"]
        self.assertNotIn("pix_chave", body)
        self.assertEqual(body["nome"], "Loja Charme")
```

- [ ] **Step 8: Teste de regressão — rotas removidas não existem mais**

Adicionar ao final de `hermes_agents/tests/test_fiscal_seguranca.py` (ler o arquivo primeiro pra confirmar o padrão de `_app()`/token usado nele antes de escrever a classe — reaproveitar exatamente esse padrão):

```python
class TestRotasFiscalRemovidas(unittest.TestCase):
    """Fase 1 da limpeza do modulo Fiscal removeu tabelas/cfop|ncm|cest e
    tributos/calcular/<id> — confirma que nao respondem mais (404), nao
    algum outro erro que sugira que a rota ainda existe."""

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_tabelas_cfop_removida(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get("/api/fiscal/tabelas/cfop", headers=headers)
        self.assertEqual(r.status_code, 404)

    def test_tabelas_ncm_removida(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get("/api/fiscal/tabelas/ncm", headers=headers)
        self.assertEqual(r.status_code, 404)

    def test_tabelas_cest_removida(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get("/api/fiscal/tabelas/cest", headers=headers)
        self.assertEqual(r.status_code, 404)

    def test_tributos_calcular_removida(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get("/api/fiscal/tributos/calcular/1", headers=headers)
        self.assertEqual(r.status_code, 404)

    def test_contas_receber_bling_nao_e_mais_tabela_valida(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get("/api/fiscal/contas_receber_bling", headers=headers)
        self.assertEqual(r.status_code, 404)

    def test_contas_pagar_bling_nao_e_mais_tabela_valida(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get("/api/fiscal/contas_pagar_bling", headers=headers)
        self.assertEqual(r.status_code, 404)
```

(Nota: `_TEST_TOKEN`, `_app`, `os`, `patch` já devem estar importados/definidos no topo do arquivo, mesmo padrão das classes existentes — confirmar ao editar, não duplicar import.)

- [ ] **Step 9: Rodar suíte de testes fiscal + lojas e confirmar tudo verde**

Run: `cd hermes_agents && python -m pytest tests/test_fiscal.py tests/test_fiscal_seguranca.py tests/test_fiscal_apuracao_fechamento.py tests/test_lojas_fiscal_financeiro.py tests/test_lojas_manage_seguranca.py -v`
Expected: PASS (nenhuma falha, nenhum teste referenciando `calcular_tributos_nota`, `atualizar_fiscal`, `certificado_digital` etc.)

- [ ] **Step 10: Commit**

```bash
git add hermes_agents/core/fiscal.py hermes_agents/routes/fiscal.py hermes_agents/core/pdv.py hermes_agents/core/lojas_fiscal_financeiro.py hermes_agents/routes/lojas_config.py web/src/lib/api.ts hermes_agents/tests/test_fiscal_apuracao_fechamento.py hermes_agents/tests/test_fiscal_seguranca.py hermes_agents/tests/test_lojas_fiscal_financeiro.py hermes_agents/tests/test_lojas_manage_seguranca.py
git commit -m "fix: remove tabelas/rotas mortas do modulo Fiscal (contas_bling orfas, pdv_nfce, calculo de tributo inutilizavel, config fiscal de loja sem consumidor)"
```

---

### Task 2: Backend — Obrigações vira cadastro + ocorrência por competência

**Files:**
- Modify: `hermes_agents/core/fiscal.py` (schema: `dia_vencimento`/`ativo` em `fiscal_obrigacoes`, nova tabela `fiscal_obrigacoes_ocorrencias`, novas funções, novo seed)
- Modify: `hermes_agents/routes/fiscal.py` (rota nova `/obrigacoes/ocorrencias`, `/obrigacoes/<id>/baixar` passa a operar sobre ocorrência)
- Modify: `hermes_agents/core/entidades.py:560-569` (`gerar_alertas_obrigacoes` passa a consultar ocorrências)
- Test: `hermes_agents/tests/test_fiscal_obrigacoes_ocorrencias.py` (novo)

**Interfaces:**
- Consumes: nada de Task 1 diretamente (independente).
- Produces: `core.fiscal.garantir_ocorrencias_mes_atual() -> {"criadas": int}`, `core.fiscal.obrigacoes_ocorrencias_competencia(competencia: str = None) -> list[dict]` (cada item com `id, obrigacao_id, competencia, data_vencimento, status, data_entrega, responsavel, nome, sigla, orgao, periodicidade, regime, descricao`), `core.fiscal.baixar_ocorrencia(ocorrencia_id: int, responsavel: str = "") -> dict`. `obrigacoes_proximas`/`obrigacoes_atrasadas` mantêm assinatura, mudam de fonte (ocorrências, não mais `fiscal_obrigacoes.data_vencimento`).

- [ ] **Step 1: Escrever o teste (falha porque as funções ainda não existem)**

Criar `hermes_agents/tests/test_fiscal_obrigacoes_ocorrencias.py`:

```python
"""Fase 1 do redesenho Fiscal — Obrigacoes vira cadastro (fiscal_obrigacoes,
com dia_vencimento fixo + ativo) e ocorrencia por competencia
(fiscal_obrigacoes_ocorrencias, uma linha por mes, vencimento calculado de
verdade). Antes a "obrigacao" tinha uma unica data_vencimento congelada
desde o primeiro boot — nunca mais recalculada."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

patcher = patch("asyncpg.create_pool")
patcher.start()

import core.fiscal as fiscal


class _FakeDB:
    """Fake minimo o suficiente pra exercitar _garantir_ocorrencias sem
    depender de Postgres real — grava as ocorrencias inseridas num set em
    memoria e simula ON CONFLICT DO NOTHING checando esse set."""

    def __init__(self, obrigacoes_ativas, hoje):
        self._obrigacoes = obrigacoes_ativas
        self._hoje = hoje
        self.existentes = set()  # {(obrigacao_id, competencia)}
        self.inseridas = []

    async def fetchval(self, query, *params):
        if "CURRENT_DATE" in query:
            return self._hoje
        return 0

    async def fetch(self, query, *params):
        if "fiscal_obrigacoes WHERE ativo" in query:
            return self._obrigacoes
        return []

    async def execute(self, query, *params):
        if "INSERT INTO fiscal_obrigacoes_ocorrencias" in query:
            obrigacao_id, competencia, venc = params
            chave = (obrigacao_id, competencia)
            if chave in self.existentes:
                return "INSERT 0 0"
            self.existentes.add(chave)
            self.inseridas.append({"obrigacao_id": obrigacao_id, "competencia": competencia, "data_vencimento": venc})
            return "INSERT 0 1"
        return "OK"


class TestCalcularVencimento(unittest.TestCase):
    def test_dia_normal(self):
        import datetime
        self.assertEqual(fiscal._calcular_vencimento(2026, 8, 15), datetime.date(2026, 8, 15))

    def test_dia_alem_do_ultimo_dia_do_mes_e_ajustado(self):
        """Fevereiro nao tem dia 31 — clampa pro ultimo dia real do mes."""
        import datetime
        self.assertEqual(fiscal._calcular_vencimento(2026, 2, 31), datetime.date(2026, 2, 28))

    def test_ano_bissexto(self):
        import datetime
        self.assertEqual(fiscal._calcular_vencimento(2028, 2, 31), datetime.date(2028, 2, 29))


class TestGarantirOcorrencias(unittest.TestCase):
    def test_cria_ocorrencia_para_cada_obrigacao_ativa(self):
        import datetime
        db = _FakeDB(
            obrigacoes_ativas=[{"id": 1, "dia_vencimento": 15}, {"id": 2, "dia_vencimento": 10}],
            hoje=datetime.date(2026, 8, 8),
        )
        with patch.object(fiscal, "get_db", AsyncMock(return_value=db)):
            resultado = fiscal.garantir_ocorrencias_mes_atual()
        self.assertEqual(resultado["criadas"], 2)
        competencias = {i["competencia"] for i in db.inseridas}
        self.assertEqual(competencias, {"2026-08"})

    def test_idempotente_nao_duplica_na_segunda_chamada(self):
        import datetime
        db = _FakeDB(
            obrigacoes_ativas=[{"id": 1, "dia_vencimento": 15}],
            hoje=datetime.date(2026, 8, 8),
        )
        with patch.object(fiscal, "get_db", AsyncMock(return_value=db)):
            fiscal.garantir_ocorrencias_mes_atual()
            resultado2 = fiscal.garantir_ocorrencias_mes_atual()
        self.assertEqual(resultado2["criadas"], 0)
        self.assertEqual(len(db.inseridas), 1)

    def test_sem_dia_vencimento_usa_dia_1_como_fallback(self):
        import datetime
        db = _FakeDB(
            obrigacoes_ativas=[{"id": 1, "dia_vencimento": None}],
            hoje=datetime.date(2026, 8, 8),
        )
        with patch.object(fiscal, "get_db", AsyncMock(return_value=db)):
            fiscal.garantir_ocorrencias_mes_atual()
        self.assertEqual(db.inseridas[0]["data_vencimento"], datetime.date(2026, 8, 1))


class TestBaixarOcorrencia(unittest.TestCase):
    def test_marca_entregue_com_responsavel(self):
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value={"id": 5, "obrigacao_id": 1, "status": "entregue", "responsavel": "joao@x.com"})
        with patch.object(fiscal, "get_db", AsyncMock(return_value=db)):
            r = fiscal.baixar_ocorrencia(5, "joao@x.com")
        self.assertNotIn("error", r)
        self.assertEqual(r["status"], "entregue")
        db.fetchrow.assert_called_once()
        query = db.fetchrow.call_args.args[0]
        self.assertIn("UPDATE fiscal_obrigacoes_ocorrencias", query)
        self.assertIn("status='entregue'", query)

    def test_ocorrencia_inexistente(self):
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value=None)
        with patch.object(fiscal, "get_db", AsyncMock(return_value=db)):
            r = fiscal.baixar_ocorrencia(999)
        self.assertEqual(r, {"error": "ocorrencia nao encontrada"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_fiscal_obrigacoes_ocorrencias.py -v`
Expected: FAIL — `AttributeError: module 'core.fiscal' has no attribute '_calcular_vencimento'` (e equivalente pras demais).

- [ ] **Step 3: Adicionar colunas na tabela cadastro e criar a tabela de ocorrências**

Em `hermes_agents/core/fiscal.py`, localizar (linhas 20-28):
```python
        await db.execute("""CREATE TABLE IF NOT EXISTS fiscal_obrigacoes (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL, sigla VARCHAR(15),
            descricao TEXT, periodicidade VARCHAR(30) DEFAULT 'mensal',
            data_vencimento DATE, competencia VARCHAR(7),
            orgao VARCHAR(100), regime VARCHAR(30) DEFAULT 'normal',
            status VARCHAR(30) DEFAULT 'pendente', responsavel VARCHAR(100),
            multa_por_atraso DECIMAL(12,2) DEFAULT 0, observacoes TEXT,
            created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
```
Substituir por (mantém as colunas antigas intactas — `data_vencimento`/`competencia`/`status`/`responsavel` da linha do cadastro ficam vestigiais, nunca mais lidas/escritas por este módulo — e adiciona as duas novas):
```python
        await db.execute("""CREATE TABLE IF NOT EXISTS fiscal_obrigacoes (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL, sigla VARCHAR(15),
            descricao TEXT, periodicidade VARCHAR(30) DEFAULT 'mensal',
            data_vencimento DATE, competencia VARCHAR(7),
            orgao VARCHAR(100), regime VARCHAR(30) DEFAULT 'normal',
            status VARCHAR(30) DEFAULT 'pendente', responsavel VARCHAR(100),
            multa_por_atraso DECIMAL(12,2) DEFAULT 0, observacoes TEXT,
            created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        # ponytail: data_vencimento/competencia/status (colunas acima) eram
        # calculadas uma unica vez no primeiro boot (hoje() + N dias) e nunca
        # mais atualizadas — a tela mostrava vencimento congelado desde o
        # deploy, nao o mes corrente. Viram cadastro (dia_vencimento fixo +
        # ativo) + fiscal_obrigacoes_ocorrencias abaixo (uma linha real por
        # competencia, gerada sob demanda). Colunas antigas ficam no schema,
        # sem uso — nunca DROP em producao.
        await db.execute("ALTER TABLE fiscal_obrigacoes ADD COLUMN IF NOT EXISTS dia_vencimento INT")
        await db.execute("ALTER TABLE fiscal_obrigacoes ADD COLUMN IF NOT EXISTS ativo BOOLEAN DEFAULT true")
        await db.execute("""CREATE TABLE IF NOT EXISTS fiscal_obrigacoes_ocorrencias (
            id SERIAL PRIMARY KEY, obrigacao_id INT REFERENCES fiscal_obrigacoes(id),
            competencia VARCHAR(7) NOT NULL, data_vencimento DATE NOT NULL,
            status VARCHAR(30) DEFAULT 'pendente', data_entrega TIMESTAMP,
            responsavel VARCHAR(100), created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(obrigacao_id, competencia)
        )""")
```

- [ ] **Step 4: Reescrever o seed de obrigações com `dia_vencimento`**

Em `hermes_agents/core/fiscal.py`, dentro de `_seed()`, localizar (linhas 885-901):
```python
        count = await db.fetchval("SELECT COUNT(*) FROM fiscal_obrigacoes")
        if count == 0:
            hoje = __import__('datetime').date.today()
            await db.execute("""INSERT INTO fiscal_obrigacoes (nome, sigla, descricao, periodicidade, data_vencimento, orgao, regime, status) VALUES
                ('SPED Fiscal','SPED','Escrituracao Fiscal Digital','mensal',
                    $1::date + interval '15 days','SEFAZ','normal','pendente'),
                ('EFD-Contribuicoes','EFD','Escrituracao Fiscal Digital de PIS/COFINS','mensal',
                    $1::date + interval '10 days','Receita Federal','normal','pendente'),
                ('DCTF','DCTF','Declaracao de Debitos e Creditos Tributarios','mensal',
                    $1::date + interval '15 days','Receita Federal','normal','pendente'),
                ('DAS','DAS','Documento de Arrecadacao do Simples','mensal',
                    $1::date, 'Receita Federal','simples_nacional','pendente'),
                ('GIA','GIA','Guia de Informacao e Apuracao do ICMS','mensal',
                    $1::date + interval '14 days','SEFAZ','normal','pendente'),
                ('SINTEGRA','SINTEGRA','Sistema Integrado de Informacoes','mensal',
                    $1::date + interval '12 days','SEFAZ','normal','pendente')""",
                    hoje)
```
Substituir por:
```python
        count = await db.fetchval("SELECT COUNT(*) FROM fiscal_obrigacoes")
        if count == 0:
            # dia_vencimento e' ponto de partida editavel (tela de Obrigacoes
            # tem CRUD) — nao e' obrigacao de ajustar a data real de cada
            # empresa sem contador/i9Logic confirmando.
            await db.execute("""INSERT INTO fiscal_obrigacoes (nome, sigla, descricao, periodicidade, dia_vencimento, orgao, regime, ativo) VALUES
                ('SPED Fiscal','SPED','Escrituracao Fiscal Digital','mensal',15,'SEFAZ','normal',true),
                ('EFD-Contribuicoes','EFD','Escrituracao Fiscal Digital de PIS/COFINS','mensal',10,'Receita Federal','normal',true),
                ('DCTF','DCTF','Declaracao de Debitos e Creditos Tributarios','mensal',15,'Receita Federal','normal',true),
                ('DAS','DAS','Documento de Arrecadacao do Simples','mensal',20,'Receita Federal','simples_nacional',true),
                ('GIA','GIA','Guia de Informacao e Apuracao do ICMS','mensal',14,'SEFAZ','normal',true),
                ('SINTEGRA','SINTEGRA','Sistema Integrado de Informacoes','mensal',12,'SEFAZ','normal',true)""")
```

- [ ] **Step 5: Implementar `_calcular_vencimento`, `_garantir_ocorrencias`, `garantir_ocorrencias_mes_atual`, `obrigacoes_ocorrencias_competencia`, `baixar_ocorrencia`; reescrever `obrigacoes_proximas`/`obrigacoes_atrasadas`; remover `baixar_obrigacao`**

Em `hermes_agents/core/fiscal.py`, localizar a seção inteira `# ── Obrigacoes ──` (linhas 261-282, do comentário até o fim de `baixar_obrigacao`):
```python
# ── Obrigacoes ──

def obrigacoes_proximas(dias: int = 30) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT * FROM fiscal_obrigacoes WHERE data_vencimento BETWEEN CURRENT_DATE AND CURRENT_DATE + $1
            ORDER BY data_vencimento""", dias)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def obrigacoes_atrasadas() -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT * FROM fiscal_obrigacoes WHERE data_vencimento < CURRENT_DATE AND status = 'pendente'
            ORDER BY data_vencimento""")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def baixar_obrigacao(id: int) -> dict:
    return update("obrigacoes", id, {"status": "entregue"})
```
Substituir por:
```python
# ── Obrigacoes: cadastro + ocorrencia por competencia ──

def _calcular_vencimento(ano: int, mes: int, dia: int):
    """Data de vencimento real do mes (ano, mes) pro dia configurado no
    cadastro — clampa pro ultimo dia do mes quando o mes e' mais curto
    (ex.: dia 31 configurado, fevereiro so' tem 28/29)."""
    import calendar, datetime
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return datetime.date(ano, mes, min(dia or 1, ultimo_dia))

async def _garantir_ocorrencias(db) -> int:
    """Garante que a ocorrencia do mes corrente existe pra cada obrigacao
    ativa — idempotente (ON CONFLICT DO NOTHING). Retorna quantas foram
    criadas nesta chamada."""
    hoje_data = await db.fetchval("SELECT CURRENT_DATE")
    ano, mes = hoje_data.year, hoje_data.month
    competencia = f"{ano:04d}-{mes:02d}"
    obrigacoes = await db.fetch("SELECT id, dia_vencimento FROM fiscal_obrigacoes WHERE ativo = true")
    criadas = 0
    for o in obrigacoes:
        venc = _calcular_vencimento(ano, mes, o["dia_vencimento"])
        tag = await db.execute(
            """INSERT INTO fiscal_obrigacoes_ocorrencias (obrigacao_id, competencia, data_vencimento)
               VALUES ($1,$2,$3) ON CONFLICT (obrigacao_id, competencia) DO NOTHING""",
            o["id"], competencia, venc)
        if tag == "INSERT 0 1":
            criadas += 1
    return criadas

def garantir_ocorrencias_mes_atual() -> dict:
    async def _go():
        db = await get_db()
        criadas = await _garantir_ocorrencias(db)
        return {"criadas": criadas}
    try: return run_async(_go())
    except Exception as e:
        log(AGENT, f"garantir_ocorrencias_mes_atual: {e}")
        return {"criadas": 0, "erro": str(e)}

_OCORRENCIA_SELECT = """SELECT oc.id, oc.obrigacao_id, oc.competencia, oc.data_vencimento, oc.status,
           oc.data_entrega, oc.responsavel,
           ob.nome, ob.sigla, ob.orgao, ob.periodicidade, ob.regime, ob.descricao
    FROM fiscal_obrigacoes_ocorrencias oc
    JOIN fiscal_obrigacoes ob ON ob.id = oc.obrigacao_id"""

def obrigacoes_proximas(dias: int = 30) -> list:
    async def _go():
        db = await get_db()
        await _garantir_ocorrencias(db)
        rows = await db.fetch(
            f"{_OCORRENCIA_SELECT} WHERE oc.data_vencimento BETWEEN CURRENT_DATE AND CURRENT_DATE + $1 AND oc.status = 'pendente' ORDER BY oc.data_vencimento",
            dias)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"obrigacoes_proximas: {e}"); return []

def obrigacoes_atrasadas() -> list:
    async def _go():
        db = await get_db()
        await _garantir_ocorrencias(db)
        rows = await db.fetch(
            f"{_OCORRENCIA_SELECT} WHERE oc.data_vencimento < CURRENT_DATE AND oc.status = 'pendente' ORDER BY oc.data_vencimento")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"obrigacoes_atrasadas: {e}"); return []

def obrigacoes_ocorrencias_competencia(competencia: str = None) -> list:
    """Lista as ocorrencias de uma competencia (formato 'YYYY-MM'); sem
    argumento, usa o mes corrente e garante que as ocorrencias existam
    antes de listar."""
    async def _go():
        db = await get_db()
        comp = competencia
        if not comp:
            await _garantir_ocorrencias(db)
            hoje_data = await db.fetchval("SELECT CURRENT_DATE")
            comp = f"{hoje_data.year:04d}-{hoje_data.month:02d}"
        rows = await db.fetch(f"{_OCORRENCIA_SELECT} WHERE oc.competencia = $1 ORDER BY oc.data_vencimento", comp)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"obrigacoes_ocorrencias_competencia: {e}"); return []

def baixar_ocorrencia(ocorrencia_id: int, responsavel: str = "") -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "UPDATE fiscal_obrigacoes_ocorrencias SET status='entregue', data_entrega=NOW(), responsavel=$1 WHERE id=$2 RETURNING *",
            responsavel, ocorrencia_id)
        return dict(row) if row else {"error": "ocorrencia nao encontrada"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}
```

- [ ] **Step 6: Atualizar a rota de baixa e adicionar a rota de ocorrências**

Em `hermes_agents/routes/fiscal.py`, localizar (linhas 173-180):
```python
@fiscal_bp.route("/obrigacoes/<int:id>/baixar", methods=["POST"])
def fiscal_baixar_obrigacao(id):
    from core.fiscal import baixar_obrigacao

    @requer_permissao("fiscal.editar")
    def _go():
        return jsonify(baixar_obrigacao(id))
    return _go()
```
Substituir por (o `id` no path agora é o id da OCORRÊNCIA, não mais da obrigação — a URL não muda, só o que ela representa):
```python
@fiscal_bp.route("/obrigacoes/<int:id>/baixar", methods=["POST"])
def fiscal_baixar_obrigacao(id):
    from core.fiscal import baixar_ocorrencia
    from core.rbac import usuario_atual_da_request

    @requer_permissao("fiscal.editar")
    def _go():
        usuario = usuario_atual_da_request()
        responsavel = usuario.get("email") or usuario.get("nome") or ""
        return jsonify(baixar_ocorrencia(id, responsavel))
    return _go()


@fiscal_bp.route("/obrigacoes/ocorrencias", methods=["GET"])
def fiscal_obrigacoes_ocorrencias():
    from core.fiscal import obrigacoes_ocorrencias_competencia

    @requer_permissao("fiscal.ver")
    def _go():
        competencia = request.args.get("competencia", default=None, type=str)
        return jsonify({"data": obrigacoes_ocorrencias_competencia(competencia)})
    return _go()
```

- [ ] **Step 7: Atualizar `gerar_alertas_obrigacoes` em `core/entidades.py`**

Localizar (linhas 560-569):
```python
def gerar_alertas_obrigacoes() -> dict:
    """Gera alertas para obrigacoes vencendo hoje e atrasadas."""
    async def _go():
        db = await get_db()
        vencendo = await db.fetch("SELECT * FROM fiscal_obrigacoes WHERE data_vencimento = CURRENT_DATE AND status = 'pendente'")
        atrasadas = await db.fetch("SELECT * FROM fiscal_obrigacoes WHERE data_vencimento < CURRENT_DATE AND status = 'pendente'")
        return {"vencendo_hoje": len(vencendo), "atrasadas": len(atrasadas),
            "alertas": [dict(r) for r in (vencendo + atrasadas)]}
    try: return run_async(_go())
    except Exception as e: return {"vencendo_hoje": 0, "atrasadas": 0, "alertas": []}
```
Substituir por:
```python
def gerar_alertas_obrigacoes() -> dict:
    """Gera alertas para obrigacoes vencendo hoje e atrasadas.

    ponytail: consultava fiscal_obrigacoes.data_vencimento direto — coluna
    congelada desde o primeiro boot (Fase 1 do redesenho Fiscal moveu
    vencimento real pra fiscal_obrigacoes_ocorrencias, uma linha por
    competencia). Ver core/fiscal.py::obrigacoes_proximas/atrasadas, mesma
    fonte."""
    async def _go():
        db = await get_db()
        vencendo = await db.fetch("""SELECT oc.*, ob.nome, ob.sigla FROM fiscal_obrigacoes_ocorrencias oc
            JOIN fiscal_obrigacoes ob ON ob.id = oc.obrigacao_id
            WHERE oc.data_vencimento = CURRENT_DATE AND oc.status = 'pendente'""")
        atrasadas = await db.fetch("""SELECT oc.*, ob.nome, ob.sigla FROM fiscal_obrigacoes_ocorrencias oc
            JOIN fiscal_obrigacoes ob ON ob.id = oc.obrigacao_id
            WHERE oc.data_vencimento < CURRENT_DATE AND oc.status = 'pendente'""")
        return {"vencendo_hoje": len(vencendo), "atrasadas": len(atrasadas),
            "alertas": [dict(r) for r in (vencendo + atrasadas)]}
    try: return run_async(_go())
    except Exception as e: return {"vencendo_hoje": 0, "atrasadas": 0, "alertas": []}
```

- [ ] **Step 8: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_fiscal_obrigacoes_ocorrencias.py -v`
Expected: PASS (8 testes).

- [ ] **Step 9: Rodar a suíte completa de fiscal pra garantir que não quebrou nada**

Run: `cd hermes_agents && python -m pytest tests/test_fiscal.py tests/test_fiscal_seguranca.py tests/test_fiscal_apuracao_fechamento.py tests/test_fiscal_obrigacoes_ocorrencias.py -v`
Expected: PASS (todos).

- [ ] **Step 10: Commit**

```bash
git add hermes_agents/core/fiscal.py hermes_agents/routes/fiscal.py hermes_agents/core/entidades.py hermes_agents/tests/test_fiscal_obrigacoes_ocorrencias.py
git commit -m "feat: Obrigacoes fiscais vira cadastro + ocorrencia real por competencia"
```

---

### Task 3: Frontend — Tributos vira CRUD de verdade

**Files:**
- Modify: `web/src/app/fiscal/tributos/page.tsx` (adiciona criar/editar/excluir)
- Modify: `web/src/lib/api.ts:1717-1743` (`fiscalGet`/`fiscalCreate`/`fiscalUpdate`/`fiscalDelete` migram pra `request()`)
- Modify: `web/src/app/fiscal/types/index.ts:11-60` (remove as 6 interfaces mortas, mantém re-exports)
- Modify: `web/src/app/layout.tsx` (corrige `NAV_PERMS["/fiscal"]`)

**Interfaces:**
- Consumes: rotas genéricas já existentes `POST/PUT/DELETE /api/fiscal/tributos[/<id>]` (Task 1 não mexeu nelas).
- Produces: nenhuma interface nova consumida por outra task.

- [ ] **Step 1: Migrar `fiscalGet`/`fiscalCreate`/`fiscalUpdate`/`fiscalDelete` pra `request()`**

Em `web/src/lib/api.ts`, localizar (linhas 1717-1743):
```typescript
export async function fiscalGet(tabela: string, id: number): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/fiscal/${tabela}/${id}`);
  return res.json();
}

export async function fiscalCreate(tabela: string, data: Record<string, unknown>): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/fiscal/${tabela}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function fiscalUpdate(tabela: string, id: number, data: Record<string, unknown>): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/fiscal/${tabela}/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function fiscalDelete(tabela: string, id: number): Promise<{ success: boolean }> {
  const res = await fetch(`/api/fiscal/${tabela}/${id}`, { method: "DELETE" });
  return res.json();
}
```
Substituir por (mesma assinatura/retorno, agora com Bearer automático + `res.ok` checado — erro vira `throw`, não `{"error":...}` engolido silenciosamente):
```typescript
export async function fiscalGet(tabela: string, id: number): Promise<Record<string, unknown>> {
  return request(`/api/fiscal/${tabela}/${id}`);
}

export async function fiscalCreate(tabela: string, data: Record<string, unknown>): Promise<Record<string, unknown>> {
  return request(`/api/fiscal/${tabela}`, { method: "POST", body: JSON.stringify(data) });
}

export async function fiscalUpdate(tabela: string, id: number, data: Record<string, unknown>): Promise<Record<string, unknown>> {
  return request(`/api/fiscal/${tabela}/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function fiscalDelete(tabela: string, id: number): Promise<{ success: boolean }> {
  return request(`/api/fiscal/${tabela}/${id}`, { method: "DELETE" });
}
```

Como `request()` agora lança em erro (em vez de devolver `{"error": "..."}` silenciosamente), os chamadores de `fiscalCreate`/`fiscalUpdate`/`fiscalDelete` precisam de `try/catch` — a página de Tributos (Step 3 abaixo) já é escrita levando isso em conta.

- [ ] **Step 2: Remover interfaces mortas de `web/src/app/fiscal/types/index.ts`**

Ler o arquivo completo (`web/src/app/fiscal/types/index.ts`, 64 linhas). Localizar e remover (linhas 11-60, do comentário `// ── Tipos específicos do módulo Fiscal ──` até o fim de `IbptRecord`):
```typescript

// ── Tipos específicos do módulo Fiscal ──

export interface TributoRecord {
  id: number;
  tributo: string;
  apuracao: string;
  baseCalculo: number;
  aliquota: string;
  valor: number;
  vencimento: string;
  status: "pago" | "pendente";
}

export type ObrigacaoStatus = "entregue" | "pendente" | "andamento";

export interface Obrigacao {
  id: number;
  nome: string;
  descricao: string;
  ultimaEntrega: string;
  proximoVencimento: string;
  periodicidade: string;
  status: ObrigacaoStatus;
}

export interface CfopRecord {
  codigo: string;
  descricao: string;
  tipo: "Entrada" | "Saída";
}

export interface NcmRecord {
  codigo: string;
  descricao: string;
  aliquotaIPI: string;
  aliquotaNacional: string;
}

export interface CestRecord {
  codigo: string;
  descricao: string;
  ncm: string;
}

export interface IbptRecord {
  ncm: string;
  aliquotaFederal: string;
  aliquotaEstadual: string;
  aliquotaMunicipal: string;
}
```
O arquivo fica só com os re-exports (linhas 1-9) e a seção de Utilitários (linhas 62-64) — o comentário `ponytail` do topo (linhas 2-7) continua valendo, é sobre um tipo diferente já removido antes.

- [ ] **Step 3: Reescrever `web/src/app/fiscal/tributos/page.tsx` com CRUD**

Substituir o arquivo inteiro por:

```tsx
"use client";

import { useEffect, useState } from "react";
import { fiscalList, fiscalCreate, fiscalUpdate, fiscalDelete } from "@/lib/api";
import type { KpiMetric, Column } from "../types";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import DataTable from "@/app/_components/DataTable";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import { Can } from "@/lib/auth";
import Icon from "@/app/_components/Icon";

interface TributoRow {
  id: number;
  nome: string;
  sigla: string;
  aliquota: number;
  aliquota_interestadual: number;
  regime: string;
  tipo: string;
  incidencia: string;
  base_calculo: string;
  fato_gerador: string;
  contribuinte: string;
  observacoes: string;
  ativo: boolean;
}

const REGIMES = ["normal", "nao_cumulativo", "lucro_real", "simples_nacional", "monofasico"];
const TIPOS = ["federal", "estadual", "municipal"];

function extrairErro(res: unknown): string | null {
  if (res && typeof res === "object" && "error" in res && (res as { error?: unknown }).error) {
    return String((res as { error: unknown }).error);
  }
  return null;
}

export default function TributosPage() {
  const [tributos, setTributos] = useState<TributoRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [modal, setModal] = useState<{ open: boolean; mode: "create" | "edit"; row?: TributoRow }>({ open: false, mode: "create" });
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [excluirAlvo, setExcluirAlvo] = useState<TributoRow | null>(null);
  const [excluindo, setExcluindo] = useState(false);

  const carregar = () => {
    setLoading(true);
    fiscalList("tributos")
      .then(r => setTributos((r.data || []) as TributoRow[]))
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { carregar(); }, []);

  const abrirNovo = () => {
    setForm({ tipo: "federal", regime: "normal", ativo: "true" });
    setSaveError("");
    setModal({ open: true, mode: "create" });
  };

  const abrirEdicao = (row: TributoRow) => {
    setForm({
      nome: row.nome || "", sigla: row.sigla || "",
      aliquota: String(row.aliquota ?? ""), aliquota_interestadual: String(row.aliquota_interestadual ?? ""),
      regime: row.regime || "normal", tipo: row.tipo || "federal",
      incidencia: row.incidencia || "", base_calculo: row.base_calculo || "",
      fato_gerador: row.fato_gerador || "", contribuinte: row.contribuinte || "",
      observacoes: row.observacoes || "", ativo: row.ativo ? "true" : "false",
    });
    setSaveError("");
    setModal({ open: true, mode: "edit", row });
  };

  const fecharModal = () => { if (!saving) setModal({ open: false, mode: "create" }); };

  const salvar = async () => {
    if (!form.nome?.trim() || !form.sigla?.trim()) { setSaveError("Nome e sigla sao obrigatorios."); return; }
    setSaving(true); setSaveError("");
    const payload = {
      nome: form.nome.trim(), sigla: form.sigla.trim(),
      aliquota: Number(form.aliquota || 0), aliquota_interestadual: Number(form.aliquota_interestadual || 0),
      regime: form.regime || "normal", tipo: form.tipo || "federal",
      incidencia: form.incidencia?.trim() || "", base_calculo: form.base_calculo?.trim() || "",
      fato_gerador: form.fato_gerador?.trim() || "", contribuinte: form.contribuinte?.trim() || "",
      observacoes: form.observacoes?.trim() || "", ativo: form.ativo === "true",
    };
    try {
      const res = modal.mode === "create"
        ? await fiscalCreate("tributos", payload)
        : await fiscalUpdate("tributos", Number(modal.row?.id), payload);
      const erroResp = extrairErro(res);
      if (erroResp) { setSaveError(erroResp); return; }
      setModal({ open: false, mode: "create" });
      carregar();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Erro ao salvar");
    } finally { setSaving(false); }
  };

  const excluir = async () => {
    if (!excluirAlvo) return;
    setExcluindo(true);
    try {
      await fiscalDelete("tributos", excluirAlvo.id);
      setExcluirAlvo(null);
      carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao excluir");
    } finally { setExcluindo(false); }
  };

  const ativos = tributos.filter(t => t.ativo);
  const kpis: KpiMetric[] = [
    { label: "Tributos ativos", value: String(ativos.length), color: "text-blue-400" },
    { label: "Federais", value: String(ativos.filter(t => t.tipo === "federal").length), color: "text-amber-400" },
    { label: "Estaduais", value: String(ativos.filter(t => t.tipo === "estadual").length), color: "text-emerald-400" },
    { label: "Municipais", value: String(ativos.filter(t => t.tipo === "municipal").length), color: "text-purple-400" },
  ];

  const COLUMNS: Column<TributoRow>[] = [
    { key: "sigla", label: "Sigla" },
    { key: "nome", label: "Tributo" },
    { key: "tipo", label: "Esfera", render: (_, row) => <span className="capitalize">{row.tipo}</span> },
    { key: "aliquota", label: "Alíquota", align: "center", render: (_, row) => `${row.aliquota}%` },
    { key: "regime", label: "Regime", render: (_, row) => <span className="capitalize">{row.regime.replace(/_/g, " ")}</span> },
    { key: "incidencia", label: "Incidência", render: (_, row) => <span className="text-[10px] text-neutral-400 max-w-[200px] block truncate">{row.incidencia}</span> },
    { key: "ativo", label: "Ativo", align: "center", render: (_, row) => (
      <StatusBadge label={row.ativo ? "Ativo" : "Inativo"} variant={row.ativo ? "success" : "neutral"} />
    )},
    { key: "id", label: "Ações", align: "right", render: (_, row) => (
      <div className="flex justify-end gap-1">
        <Can permission="fiscal.editar">
          <button onClick={() => abrirEdicao(row)} title="Editar" className="rounded-md p-1.5 text-neutral-500 hover:bg-indigo-500/10 hover:text-indigo-400">
            <Icon name="pencil" size={13} />
          </button>
        </Can>
        <Can permission="fiscal.excluir">
          <button onClick={() => setExcluirAlvo(row)} title="Excluir" className="rounded-md p-1.5 text-neutral-500 hover:bg-red-500/10 hover:text-red-400">
            <Icon name="trash" size={13} />
          </button>
        </Can>
      </div>
    )},
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <PageHeader title="Tributos" subtitle="ICMS, IPI, PIS, COFINS, ISS, CSLL e IRPJ" />
        <Can permission="fiscal.criar">
          <button onClick={abrirNovo} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">+ Novo</button>
        </Can>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {kpis.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
      </div>

      <ErrorAlert message={erro} />
      {loading ? (
        <LoadingState />
      ) : (
        <DataTable<TributoRow>
          columns={COLUMNS}
          data={tributos}
          keyExtractor={item => item.id}
          emptyMessage="Nenhum tributo cadastrado"
          countLabel={`${tributos.length} tributos`}
        />
      )}

      {modal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={fecharModal}>
          <div className="w-full max-w-[520px] rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
              <h3 className="text-sm font-semibold text-neutral-100">{modal.mode === "create" ? "Novo tributo" : "Editar tributo"}</h3>
              <button onClick={fecharModal} className="rounded-md p-1 text-neutral-500 hover:bg-neutral-700 hover:text-neutral-300">
                <Icon name="close" size={15} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 px-5 py-4">
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Nome *</label>
                <input type="text" value={form.nome || ""} onChange={e => setForm({ ...form, nome: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Sigla *</label>
                <input type="text" value={form.sigla || ""} onChange={e => setForm({ ...form, sigla: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Alíquota (%)</label>
                <input type="number" step="0.0001" value={form.aliquota || ""} onChange={e => setForm({ ...form, aliquota: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Alíquota interestadual (%)</label>
                <input type="number" step="0.0001" value={form.aliquota_interestadual || ""} onChange={e => setForm({ ...form, aliquota_interestadual: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Esfera</label>
                <select value={form.tipo || "federal"} onChange={e => setForm({ ...form, tipo: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
                  {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Regime</label>
                <select value={form.regime || "normal"} onChange={e => setForm({ ...form, regime: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
                  {REGIMES.map(r => <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}
                </select>
              </div>
              <div className="col-span-2">
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Incidência</label>
                <input type="text" value={form.incidencia || ""} onChange={e => setForm({ ...form, incidencia: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div className="col-span-2">
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Base de cálculo</label>
                <input type="text" value={form.base_calculo || ""} onChange={e => setForm({ ...form, base_calculo: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div className="col-span-2">
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Observações</label>
                <textarea value={form.observacoes || ""} onChange={e => setForm({ ...form, observacoes: e.target.value })} rows={2}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" id="ativo" checked={form.ativo === "true"} onChange={e => setForm({ ...form, ativo: e.target.checked ? "true" : "false" })}
                  className="rounded border-neutral-600 bg-neutral-700 text-indigo-500 focus:ring-indigo-500/50" />
                <label htmlFor="ativo" className="text-[11px] font-medium text-neutral-400">Ativo</label>
              </div>
              {saveError && (
                <div className="col-span-2 text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2">{saveError}</div>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-neutral-700/70 px-5 py-4">
              <button onClick={fecharModal} disabled={saving} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200 disabled:opacity-50">Cancelar</button>
              <button onClick={salvar} disabled={saving} className="rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50">
                {saving ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {excluirAlvo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setExcluirAlvo(null)}>
          <div className="w-full max-w-[360px] rounded-xl border border-neutral-700 bg-neutral-800 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="mb-3 flex items-center gap-2 text-amber-400">
              <Icon name="alert" size={17} />
              <h3 className="text-sm font-semibold text-neutral-100">Excluir tributo</h3>
            </div>
            <p className="mb-4 text-xs text-neutral-400">
              &quot;{excluirAlvo.nome}&quot; será excluído. Essa ação não pode ser desfeita pela tela.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setExcluirAlvo(null)} disabled={excluindo} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200 disabled:opacity-50">Cancelar</button>
              <button onClick={excluir} disabled={excluindo} className="rounded-lg bg-red-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-red-500 disabled:opacity-50">
                {excluindo ? "Excluindo..." : "Excluir"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Corrigir `NAV_PERMS["/fiscal"]` em `web/src/app/layout.tsx`**

Localizar:
```typescript
  "/fiscal": "fiscal:view",
```
Substituir por:
```typescript
  "/fiscal": "fiscal.ver",
```

- [ ] **Step 5: Rodar `tsc` e confirmar limpo**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros (ignorar qualquer erro pré-existente de `.next/types/app/estoque/inventario` — cache stale de outra branch, não relacionado).

- [ ] **Step 6: Commit**

```bash
git add web/src/app/fiscal/tributos/page.tsx web/src/lib/api.ts web/src/app/fiscal/types/index.ts web/src/app/layout.tsx
git commit -m "feat: Tributos ganha CRUD de verdade (criar/editar/excluir)"
```

---

### Task 4: Frontend — remove `/fiscal/tabelas`, reescreve Obrigações, edita FiscalFinanceiroTab

**Files:**
- Delete: `web/src/app/fiscal/tabelas/page.tsx`
- Modify: `web/src/app/fiscal/page.tsx` (remove card "Tabelas Fiscais")
- Modify: `web/src/app/fiscal/obrigacoes/page.tsx` (reescrita completa: cadastro + ocorrências)
- Modify: `web/src/lib/api.ts` (novo `fiscalObrigacoesOcorrencias`, migra `fiscalObrigacoesProximas`/`fiscalObrigacoesAtrasadas`/`fiscalBaixarObrigacao` pra `request()`)
- Modify: `web/src/app/lojas/[id]/_components/FiscalFinanceiroTab.tsx` (remove seção Fiscal)
- Modify: `web/src/app/lojas/[id]/client.tsx` (tab "fiscal"→"financeiro", label "Fiscal & Financeiro"→"Financeiro")

**Interfaces:**
- Consumes: `GET /api/fiscal/obrigacoes/ocorrencias?competencia=`, `GET /api/fiscal/obrigacoes/proximas`, `GET /api/fiscal/obrigacoes/atrasadas`, `POST /api/fiscal/obrigacoes/<ocorrencia_id>/baixar`, CRUD genérico `/api/fiscal/obrigacoes[/<id>]` (Task 2). `atualizar_financeiro`/`atualizar_estoque_config` (Task 1, já existiam antes, intocados).

- [ ] **Step 1: Deletar `/fiscal/tabelas`**

```bash
git rm "web/src/app/fiscal/tabelas/page.tsx"
```

- [ ] **Step 2: Remover o card "Tabelas Fiscais" do hub**

Em `web/src/app/fiscal/page.tsx`, localizar:
```typescript
const SUBMENU: SubmenuItem[] = [
  { href: "/fiscal/notas", label: "Notas Fiscais", color: "bg-blue-600" },
  { href: "/fiscal/apuracao", label: "Apuração", color: "bg-red-600" },
  { href: "/fiscal/tributos", label: "Tributos", color: "bg-amber-600" },
  { href: "/fiscal/obrigacoes", label: "Obrigações", color: "bg-purple-600" },
  { href: "/fiscal/tabelas", label: "Tabelas Fiscais", color: "bg-emerald-600" },
];
```
Substituir por:
```typescript
const SUBMENU: SubmenuItem[] = [
  { href: "/fiscal/notas", label: "Notas Fiscais", color: "bg-blue-600" },
  { href: "/fiscal/apuracao", label: "Apuração", color: "bg-red-600" },
  { href: "/fiscal/tributos", label: "Tributos", color: "bg-amber-600" },
  { href: "/fiscal/obrigacoes", label: "Obrigações", color: "bg-purple-600" },
];
```

- [ ] **Step 3: Atualizar `web/src/lib/api.ts` — funções de Obrigações**

Localizar (linhas 1750-1758):
```typescript
export async function fiscalObrigacoesProximas(dias?: number): Promise<{ data: unknown[] }> {
  const res = await fetch(`/api/fiscal/obrigacoes/proximas${dias ? "?dias=" + dias : ""}`);
  return res.json();
}

export async function fiscalObrigacoesAtrasadas(): Promise<{ data: unknown[] }> {
  const res = await fetch("/api/fiscal/obrigacoes/atrasadas");
  return res.json();
}
```
Substituir por:
```typescript
export async function fiscalObrigacoesProximas(dias?: number): Promise<{ data: unknown[] }> {
  return request(`/api/fiscal/obrigacoes/proximas${dias ? "?dias=" + dias : ""}`);
}

export async function fiscalObrigacoesAtrasadas(): Promise<{ data: unknown[] }> {
  return request("/api/fiscal/obrigacoes/atrasadas");
}

export async function fiscalObrigacoesOcorrencias(competencia?: string): Promise<{ data: unknown[] }> {
  return request(`/api/fiscal/obrigacoes/ocorrencias${competencia ? "?competencia=" + competencia : ""}`);
}
```

Localizar (linhas 1792-1795):
```typescript
export async function fiscalBaixarObrigacao(id: number): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/fiscal/obrigacoes/${id}/baixar`, { method: "POST" });
  return res.json();
}
```
Substituir por:
```typescript
export async function fiscalBaixarObrigacao(id: number): Promise<Record<string, unknown>> {
  return request(`/api/fiscal/obrigacoes/${id}/baixar`, { method: "POST" });
}
```

- [ ] **Step 4: Reescrever `web/src/app/fiscal/obrigacoes/page.tsx`**

Substituir o arquivo inteiro por:

```tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import { fiscalObrigacoesOcorrencias, fiscalBaixarObrigacao, fiscalList, fiscalCreate, fiscalUpdate } from "@/lib/api";
import PageHeader from "@/app/_components/PageHeader";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import { Can } from "@/lib/auth";
import Icon from "@/app/_components/Icon";

interface OcorrenciaRow {
  id: number;
  obrigacao_id: number;
  competencia: string;
  data_vencimento: string;
  status: string;
  data_entrega: string | null;
  responsavel: string | null;
  nome: string;
  sigla: string;
  orgao: string;
  periodicidade: string;
  regime: string;
  descricao: string;
}

interface ObrigacaoCadastro {
  id: number;
  nome: string;
  sigla: string;
  descricao: string;
  periodicidade: string;
  dia_vencimento: number | null;
  orgao: string;
  regime: string;
  ativo: boolean;
}

function extrairErro(res: unknown): string | null {
  if (res && typeof res === "object" && "error" in res && (res as { error?: unknown }).error) {
    return String((res as { error: unknown }).error);
  }
  return null;
}

function fmtData(s: string | null) {
  if (!s) return "—";
  return s.slice(0, 10).split("-").reverse().join("/");
}

export default function ObrigacoesPage() {
  const [ocorrencias, setOcorrencias] = useState<OcorrenciaRow[]>([]);
  const [cadastro, setCadastro] = useState<ObrigacaoCadastro[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const [modal, setModal] = useState<{ open: boolean; mode: "create" | "edit"; row?: ObrigacaoCadastro }>({ open: false, mode: "create" });
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const carregar = useCallback(() => {
    setLoading(true);
    setErro(null);
    Promise.all([fiscalObrigacoesOcorrencias(), fiscalList("obrigacoes")])
      .then(([r1, r2]) => {
        setOcorrencias((r1.data || []) as OcorrenciaRow[]);
        setCadastro((r2.data || []) as ObrigacaoCadastro[]);
      })
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const baixar = async (id: number) => {
    await fiscalBaixarObrigacao(id);
    carregar();
  };

  const abrirNovo = () => {
    setForm({ periodicidade: "mensal", dia_vencimento: "1", ativo: "true" });
    setSaveError("");
    setModal({ open: true, mode: "create" });
  };

  const abrirEdicao = (o: ObrigacaoCadastro) => {
    setForm({
      nome: o.nome || "", sigla: o.sigla || "", descricao: o.descricao || "",
      periodicidade: o.periodicidade || "mensal", dia_vencimento: String(o.dia_vencimento ?? 1),
      orgao: o.orgao || "", regime: o.regime || "normal", ativo: o.ativo ? "true" : "false",
    });
    setSaveError("");
    setModal({ open: true, mode: "edit", row: o });
  };

  const fecharModal = () => { if (!saving) setModal({ open: false, mode: "create" }); };

  const salvar = async () => {
    if (!form.nome?.trim() || !form.sigla?.trim()) { setSaveError("Nome e sigla sao obrigatorios."); return; }
    const dia = Number(form.dia_vencimento || 1);
    if (dia < 1 || dia > 31) { setSaveError("Dia de vencimento precisa estar entre 1 e 31."); return; }
    setSaving(true); setSaveError("");
    const payload = {
      nome: form.nome.trim(), sigla: form.sigla.trim(), descricao: form.descricao?.trim() || "",
      periodicidade: form.periodicidade || "mensal", dia_vencimento: dia,
      orgao: form.orgao?.trim() || "", regime: form.regime?.trim() || "normal",
      ativo: form.ativo === "true",
    };
    try {
      const res = modal.mode === "create"
        ? await fiscalCreate("obrigacoes", payload)
        : await fiscalUpdate("obrigacoes", Number(modal.row?.id), payload);
      const erroResp = extrairErro(res);
      if (erroResp) { setSaveError(erroResp); return; }
      setModal({ open: false, mode: "create" });
      carregar();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Erro ao salvar");
    } finally { setSaving(false); }
  };

  const atrasadas = ocorrencias.filter(o => o.status === "pendente" && new Date(o.data_vencimento) < new Date(new Date().toDateString()));
  const pendentesNoPrazo = ocorrencias.filter(o => o.status === "pendente" && !atrasadas.includes(o));
  const entregues = ocorrencias.filter(o => o.status === "entregue");

  const renderOcorrencia = (o: OcorrenciaRow, atrasada: boolean) => (
    <div key={o.id} className={`bg-neutral-800 border rounded-lg p-4 space-y-3 ${atrasada ? "border-red-800/60" : "border-neutral-700"}`}>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-neutral-100">{o.nome}</h3>
        <StatusBadge
          label={o.status === "entregue" ? "Entregue" : atrasada ? "Atrasada" : "Pendente"}
          variant={o.status === "entregue" ? "success" : atrasada ? "danger" : "warning"}
        />
      </div>
      <p className="text-xs text-neutral-500">{o.descricao}</p>
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div>
          <p className="text-neutral-500">Vencimento</p>
          <p className={atrasada ? "text-red-400" : "text-neutral-300"}>{fmtData(o.data_vencimento)}</p>
        </div>
        <div>
          <p className="text-neutral-500">Competência</p>
          <p className="text-neutral-300">{o.competencia}</p>
        </div>
        <div>
          <p className="text-neutral-500">Órgão</p>
          <p className="text-neutral-300">{o.orgao}</p>
        </div>
        <div>
          <p className="text-neutral-500">Responsável</p>
          <p className="text-neutral-300">{o.responsavel || "—"}</p>
        </div>
      </div>
      {o.status === "pendente" && (
        <Can permission="fiscal.editar">
          <button
            onClick={() => baixar(o.id)}
            className="w-full mt-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs rounded"
          >
            Marcar como Entregue
          </button>
        </Can>
      )}
    </div>
  );

  return (
    <div className="p-6 space-y-8">
      <PageHeader title="Obrigações Acessórias" subtitle="SPED, EFD, DCTF, GIA, SINTEGRA e DAS" />

      <ErrorAlert message={erro} />
      {loading ? (
        <LoadingState />
      ) : (
        <>
          {atrasadas.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-red-400 mb-3">Atrasadas ({atrasadas.length})</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {atrasadas.map(o => renderOcorrencia(o, true))}
              </div>
            </div>
          )}

          <div>
            <h2 className="text-sm font-semibold text-neutral-300 mb-3">Pendentes este mês ({pendentesNoPrazo.length})</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {pendentesNoPrazo.length === 0 ? (
                <p className="text-xs text-neutral-500 col-span-3">Nenhuma obrigação pendente este mês.</p>
              ) : pendentesNoPrazo.map(o => renderOcorrencia(o, false))}
            </div>
          </div>

          {entregues.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-neutral-500 mb-3">Entregues este mês ({entregues.length})</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {entregues.map(o => renderOcorrencia(o, false))}
              </div>
            </div>
          )}

          <div className="border-t border-neutral-800 pt-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-neutral-300">Obrigações cadastradas ({cadastro.length})</h2>
              <Can permission="fiscal.criar">
                <button onClick={abrirNovo} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">+ Nova obrigação</button>
              </Can>
            </div>
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-neutral-700 text-neutral-400">
                    <th className="text-left p-3">Sigla</th>
                    <th className="text-left p-3">Nome</th>
                    <th className="text-left p-3">Periodicidade</th>
                    <th className="text-center p-3">Dia venc.</th>
                    <th className="text-left p-3">Órgão</th>
                    <th className="text-center p-3">Ativo</th>
                    <th className="text-right p-3">Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {cadastro.map(o => (
                    <tr key={o.id} className="border-b border-neutral-700/50">
                      <td className="p-3 text-neutral-300">{o.sigla}</td>
                      <td className="p-3 text-neutral-300">{o.nome}</td>
                      <td className="p-3 text-neutral-300 capitalize">{o.periodicidade}</td>
                      <td className="p-3 text-center text-neutral-300">{o.dia_vencimento ?? "—"}</td>
                      <td className="p-3 text-neutral-300">{o.orgao}</td>
                      <td className="p-3 text-center">
                        <StatusBadge label={o.ativo ? "Ativo" : "Inativo"} variant={o.ativo ? "success" : "neutral"} />
                      </td>
                      <td className="p-3">
                        <div className="flex justify-end gap-1">
                          <Can permission="fiscal.editar">
                            <button onClick={() => abrirEdicao(o)} title="Editar" className="rounded-md p-1.5 text-neutral-500 hover:bg-indigo-500/10 hover:text-indigo-400">
                              <Icon name="pencil" size={13} />
                            </button>
                          </Can>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {modal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={fecharModal}>
          <div className="w-full max-w-[480px] rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
              <h3 className="text-sm font-semibold text-neutral-100">{modal.mode === "create" ? "Nova obrigação" : "Editar obrigação"}</h3>
              <button onClick={fecharModal} className="rounded-md p-1 text-neutral-500 hover:bg-neutral-700 hover:text-neutral-300">
                <Icon name="close" size={15} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 px-5 py-4">
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Nome *</label>
                <input type="text" value={form.nome || ""} onChange={e => setForm({ ...form, nome: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Sigla *</label>
                <input type="text" value={form.sigla || ""} onChange={e => setForm({ ...form, sigla: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div className="col-span-2">
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Descrição</label>
                <input type="text" value={form.descricao || ""} onChange={e => setForm({ ...form, descricao: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Periodicidade</label>
                <select value={form.periodicidade || "mensal"} onChange={e => setForm({ ...form, periodicidade: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
                  <option value="mensal">Mensal</option>
                  <option value="anual">Anual</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Dia de vencimento *</label>
                <input type="number" min={1} max={31} value={form.dia_vencimento || "1"} onChange={e => setForm({ ...form, dia_vencimento: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Órgão</label>
                <input type="text" value={form.orgao || ""} onChange={e => setForm({ ...form, orgao: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div className="flex items-center gap-2 pt-5">
                <input type="checkbox" id="ativo" checked={form.ativo === "true"} onChange={e => setForm({ ...form, ativo: e.target.checked ? "true" : "false" })}
                  className="rounded border-neutral-600 bg-neutral-700 text-indigo-500 focus:ring-indigo-500/50" />
                <label htmlFor="ativo" className="text-[11px] font-medium text-neutral-400">Ativa (gera ocorrência mensal)</label>
              </div>
              {saveError && (
                <div className="col-span-2 text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2">{saveError}</div>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-neutral-700/70 px-5 py-4">
              <button onClick={fecharModal} disabled={saving} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200 disabled:opacity-50">Cancelar</button>
              <button onClick={salvar} disabled={saving} className="rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50">
                {saving ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Confirmar variante `"danger"` de `StatusBadge`**

Antes de seguir, ler `web/src/app/_components/StatusBadge.tsx` e confirmar que a prop `variant` aceita `"danger"` (usada acima pra "Atrasada"). Se a variante disponível pra vermelho tiver outro nome (ex.: `"error"`), ajustar a chamada em `obrigacoes/page.tsx` pra usar o nome real — não inventar variante nova no componente.

- [ ] **Step 6: Remover a seção Fiscal de `FiscalFinanceiroTab.tsx`**

Ler o arquivo completo (`web/src/app/lojas/[id]/_components/FiscalFinanceiroTab.tsx`, 106 linhas). Substituir o conteúdo inteiro por:

```tsx
"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Section, TextField, CheckboxField, strVal } from "./shared";

const CAMPOS_SENSIVEIS = new Set(["pix_chave"]);

const CAMPOS_FINANCEIRO = ["conta_bancaria", "conta_caixa_padrao", "centro_financeiro", "carteira_padrao", "gateway_pagamento", "pix_chave"];
const CAMPOS_ESTOQUE = ["deposito_principal", "permitir_estoque_negativo", "estoque_minimo_padrao", "estoque_reservado"];

// Campos sensiveis nunca voltam da API (GET /manage/<id> ja os filtra) — o
// form sempre parte vazio pra eles. So' entram no payload se o usuario
// digitar algo, pra nunca sobrescrever o valor real com string vazia.
function montarPayload(form: Record<string, string>, campos: string[], booleanos: string[] = [], numericos: string[] = []) {
  const payload: Record<string, unknown> = {};
  for (const c of campos) {
    const v = form[c];
    if (CAMPOS_SENSIVEIS.has(c) && !v) continue;
    if (numericos.includes(c) && !v) continue; // vazio = nao envia (coluna NUMERIC nao aceita string vazia)
    if (booleanos.includes(c)) payload[c] = v === "true";
    else if (numericos.includes(c)) payload[c] = Number(v);
    else payload[c] = v;
  }
  return payload;
}

export default function FiscalFinanceiroTab({ id, loja }: { id: number; loja: Record<string, unknown> | null }) {
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string>("");
  const [msg, setMsg] = useState<Record<string, string>>({});
  const [erro, setErro] = useState("");

  useEffect(() => {
    const todos = [...CAMPOS_FINANCEIRO, ...CAMPOS_ESTOQUE];
    const inicial: Record<string, string> = {};
    for (const c of todos) inicial[c] = strVal(loja, c);
    setForm(inicial);
  }, [loja]);

  const set = (campo: string) => (v: string) => setForm((p) => ({ ...p, [campo]: v }));

  const salvar = async (secao: "financeiro" | "estoque") => {
    setSaving(secao); setErro("");
    try {
      let r;
      if (secao === "financeiro") r = await api.lojasFinanceiroAtualizar(id, montarPayload(form, CAMPOS_FINANCEIRO));
      else r = await api.lojasEstoqueConfigAtualizar(id, montarPayload(form, CAMPOS_ESTOQUE, ["permitir_estoque_negativo", "estoque_reservado"], ["estoque_minimo_padrao"]));
      if (r.error) { setErro(r.error); return; }
      setMsg((p) => ({ ...p, [secao]: "Salvo!" }));
      setTimeout(() => setMsg((p) => ({ ...p, [secao]: "" })), 2500);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar");
    } finally {
      setSaving("");
    }
  };

  return (
    <div className="space-y-4">
      {erro && <p className="text-xs text-red-400">{erro}</p>}

      <Section title="Financeiro" onSave={() => salvar("financeiro")} saving={saving === "financeiro"} msg={msg.financeiro}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <TextField label="Conta bancária" value={form.conta_bancaria || ""} onChange={set("conta_bancaria")} />
          <TextField label="Conta caixa padrão" value={form.conta_caixa_padrao || ""} onChange={set("conta_caixa_padrao")} />
          <TextField label="Centro financeiro" value={form.centro_financeiro || ""} onChange={set("centro_financeiro")} />
          <TextField label="Carteira padrão" value={form.carteira_padrao || ""} onChange={set("carteira_padrao")} />
          <TextField label="Gateway de pagamento" value={form.gateway_pagamento || ""} onChange={set("gateway_pagamento")} />
          <TextField label="Chave PIX" value={form.pix_chave || ""} onChange={set("pix_chave")} type="password" placeholder="Deixe em branco pra manter a atual" />
        </div>
      </Section>

      <Section title="Configuração de estoque" onSave={() => salvar("estoque")} saving={saving === "estoque"} msg={msg.estoque}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <TextField label="Depósito principal" value={form.deposito_principal || ""} onChange={set("deposito_principal")} />
          <TextField label="Estoque mínimo padrão" value={form.estoque_minimo_padrao || ""} onChange={set("estoque_minimo_padrao")} type="number" />
        </div>
        <div className="flex gap-6">
          <CheckboxField label="Permitir estoque negativo" checked={form.permitir_estoque_negativo === "true"} onChange={(v) => set("permitir_estoque_negativo")(String(v))} />
          <CheckboxField label="Reservar estoque" checked={form.estoque_reservado === "true"} onChange={(v) => set("estoque_reservado")(String(v))} />
        </div>
      </Section>
    </div>
  );
}
```

(`SelectField` deixou de ser usado neste arquivo — removido do import. `atualizar_fiscal`/`api.lojasFiscalAtualizar` não são mais chamados.)

- [ ] **Step 7: Renomear a aba "fiscal" pra "financeiro" em `client.tsx`**

Em `web/src/app/lojas/[id]/client.tsx`, localizar (linha 19):
```typescript
  { id: "fiscal", label: "Fiscal & Financeiro" },
```
Substituir por:
```typescript
  { id: "financeiro", label: "Financeiro" },
```

Localizar (linha 85):
```tsx
      {tab === "fiscal" && <FiscalFinanceiroTab id={id} loja={loja} />}
```
Substituir por:
```tsx
      {tab === "financeiro" && <FiscalFinanceiroTab id={id} loja={loja} />}
```

(O nome do arquivo/componente `FiscalFinanceiroTab` não muda — só o `id`/label da aba visível ao usuário. Renomear o componente é cosmético e fora do escopo desta limpeza.)

- [ ] **Step 8: Rodar `tsc` e confirmar limpo**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros (mesma ressalva do cache stale de `estoque/inventario`, não relacionado).

- [ ] **Step 9: Smoke visual**

Rodar `npm run dev` em `web/`, navegar até `/fiscal`, `/fiscal/obrigacoes`, `/fiscal/tributos`, `/lojas/<id>` aba Financeiro, e confirmar:
- `/fiscal` não mostra mais card "Tabelas Fiscais".
- `/fiscal/tabelas` dá 404 (rota não existe mais).
- `/fiscal/obrigacoes` mostra seções Atrasadas/Pendentes/Entregues (podem estar vazias, tabela recém-migrada) + tabela de cadastro embaixo, com botão "+ Nova obrigação" funcionando (cria, some do form, aparece na tabela).
- `/fiscal/tributos` — criar um tributo novo, editar, excluir — tudo reflete na lista e nos KPIs.
- `/lojas/<id>`, aba agora chamada "Financeiro" (não mais "Fiscal & Financeiro"), sem nenhum campo de certificado digital/CSC/token fiscal/regime tributário/série NFe/NFCe — só Financeiro + Configuração de estoque.

- [ ] **Step 10: Commit**

```bash
git add web/src/app/fiscal/page.tsx web/src/app/fiscal/obrigacoes/page.tsx web/src/lib/api.ts "web/src/app/lojas/[id]/_components/FiscalFinanceiroTab.tsx" "web/src/app/lojas/[id]/client.tsx"
git rm "web/src/app/fiscal/tabelas/page.tsx"
git commit -m "feat: Obrigacoes mostra ocorrencia real por competencia; remove Tabelas Fiscais e config fiscal de loja da UI"
```

---

## Self-Review

**Cobertura do spec:** Remoção de `fiscal_contas_receber_bling`/`fiscal_contas_pagar_bling`/`pdv_nfce`/`calcular_tributos_nota`/config fiscal de loja/`/fiscal/tabelas` ✅ Task 1 + Task 4 Steps 1-2/6-7. Tributos editável de verdade ✅ Task 3. Obrigações cadastro+ocorrência ✅ Task 2 + Task 4 Step 4. Correção `NAV_PERMS` ✅ Task 3 Step 4. Tipos mortos ✅ Task 3 Step 2. Constraint "não tocar notas/apuração" ✅ nenhuma task toca esses arquivos. Constraint "nunca DROP" ✅ todas as remoções são de código (create/uso), nenhum `DROP TABLE`/`DROP COLUMN` em nenhuma task.

**Placeholders:** nenhum "TBD"/"implementar depois" — todo código é completo. Único ponto de verificação-antes-de-agir explícito é o Step 5 da Task 4 (nome real da variante "danger" do `StatusBadge`), que é uma checagem factual pontual, não um placeholder de lógica.

**Consistência de tipos:** `baixar_ocorrencia(ocorrencia_id, responsavel)` tem a mesma assinatura na definição (Task 2 Step 5), na rota (Task 2 Step 6) e no client `fiscalBaixarObrigacao` (Task 4 Step 3, mesmo path). `obrigacoes_ocorrencias_competencia` bate entre core (Task 2 Step 5), rota (Task 2 Step 6) e client `fiscalObrigacoesOcorrencias` (Task 4 Step 3). `ObrigacaoCadastro`/`OcorrenciaRow` (Task 4 Step 4) espelham exatamente as colunas que `fiscal_obrigacoes`/`_OCORRENCIA_SELECT` (Task 2) devolvem.

## Execution Handoff

Plano completo e salvo em `docs/superpowers/plans/2026-08-08-fiscal-limpeza-fase1.md`. Duas opções de execução:

1. **Subagent-Driven (recomendado)** — dispatch de subagente por task, review entre tasks, iteração rápida.
2. **Inline Execution** — executo as tasks nesta sessão com checkpoints de revisão.

Qual prefere?
