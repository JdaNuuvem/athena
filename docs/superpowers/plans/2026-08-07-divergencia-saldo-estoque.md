# Divergência de Saldo em Estoque (i9Logic + Shopee) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nova seção "Divergência de Saldo" em `/estoque/discrepancias` comparando o saldo do Athena contra o saldo real do sistema externo — i9Logic pra loja física, Shopee pra loja online.

**Architecture:** Backend ganha uma função nova por lado (`core.i9logic.listar_divergencias_athena` pro físico, módulo novo `shopee/divergencia.py` pro online), reaproveitando ao máximo peças já existentes (`snapshot_mais_recente`, `_disparar_coleta_se_necessario`, `classificar_divergencia` extraída pra módulo compartilhado, `ajustar_absoluto`, `sync_all_items`). Frontend detecta a fonte pelo tipo de loja selecionado no seletor global e usa o mesmo padrão de polling que `EstoqueFisicoI9Logic.tsx` já usa.

**Tech Stack:** Flask + asyncpg (backend), Next.js/React + TypeScript (frontend).

## Global Constraints

- Nenhuma tabela nova pro lado i9Logic — a comparação Athena×i9Logic é calculada em memória a partir do snapshot já existente, sem persistir nada novo.
- Nova tabela `shopee_estoque_snapshot` guarda só o saldo Shopee bruto — nunca `qtd_athena` congelada; a divergência é sempre calculada ao vivo na leitura.
- Ação de ajuste sempre na direção Athena←externo (nunca escreve de volta na Shopee/i9Logic).
- Coleta Shopee usa lazy-trigger-on-read (mesma constante `FRESCOR_MAXIMO_MINUTOS = 30`, mesmo padrão de lock/set/thread daemon do i9Logic) — nunca job cronado, nunca bloqueia a resposta da rota esperando a API da Shopee terminar.
- Rotas GET exigem `estoque.ver`; rotas POST (ajustar/resolver) exigem `estoque.editar` — mesmo par já usado nas rotas i9Logic existentes.
- Nenhuma rota/tabela/função i9Logic já existente é modificada (`/divergencias`, `/comparar`, `i9logic_estoque_snapshot`, `listar_itens_para_revisao`, `aplicar_ajuste_divergencia`) — tudo aditivo.

---

### Task 1: Backend — extrai `core/estoque_divergencia.py`

**Files:**
- Create: `hermes_agents/core/estoque_divergencia.py`
- Modify: `hermes_agents/core/i9logic.py:28-30,354-365`
- Test: `hermes_agents/tests/test_i9logic.py` (adicionar classe nova)

**Interfaces:**
- Produces: `estoque_divergencia.LIMIAR_ALERTA_ABSOLUTO = 5`, `estoque_divergencia.LIMIAR_ALERTA_PERCENTUAL = 0.10`, `estoque_divergencia.TOLERANCIA_ZERO = 0.5`, `estoque_divergencia.classificar_divergencia(qtd_referencia: float, qtd_comparacao: float) -> str` (retorna `"sem_acao" | "registrado" | "alerta"`).
- Consumes (Tasks 2, 4, 5): `from core.estoque_divergencia import classificar_divergencia, TOLERANCIA_ZERO`.

- [ ] **Step 1: Escrever o teste de regressão (falhando)**

Adicionar ao final de `hermes_agents/tests/test_i9logic.py`:

```python
class TestClassificarDivergenciaReexport(unittest.TestCase):
    """i9logic.classificar_divergencia agora e' um re-export de
    core.estoque_divergencia — este teste confirma que o comportamento nao
    mudou apos a extracao."""
    def test_dentro_da_tolerancia_zero_e_sem_acao(self):
        self.assertEqual(i9logic.classificar_divergencia(100, 100.3), "sem_acao")

    def test_acima_do_limiar_absoluto_e_alerta(self):
        self.assertEqual(i9logic.classificar_divergencia(100, 106), "alerta")

    def test_acima_do_limiar_percentual_e_alerta(self):
        self.assertEqual(i9logic.classificar_divergencia(10, 12), "alerta")

    def test_divergencia_pequena_mas_fora_da_tolerancia_e_registrado(self):
        self.assertEqual(i9logic.classificar_divergencia(100, 102), "registrado")

    def test_constantes_reexportadas(self):
        from core.estoque_divergencia import TOLERANCIA_ZERO, LIMIAR_ALERTA_ABSOLUTO, LIMIAR_ALERTA_PERCENTUAL
        self.assertEqual(i9logic.TOLERANCIA_ZERO, TOLERANCIA_ZERO)
        self.assertEqual(i9logic.LIMIAR_ALERTA_ABSOLUTO, LIMIAR_ALERTA_ABSOLUTO)
        self.assertEqual(i9logic.LIMIAR_ALERTA_PERCENTUAL, LIMIAR_ALERTA_PERCENTUAL)
```

- [ ] **Step 2: Rodar o teste e confirmar que passa mesmo sem a extração (baseline)**

Run: `cd hermes_agents && python -m pytest tests/test_i9logic.py::TestClassificarDivergenciaReexport -v`
Expected: PASS — o comportamento já existe hoje, este teste é a rede de segurança pra próxima etapa (extrair sem quebrar).

- [ ] **Step 3: Criar o módulo compartilhado**

Criar `hermes_agents/core/estoque_divergencia.py`:

```python
"""Classificacao de divergencia de saldo — compartilhada entre reconciliacao
i9Logic (fisico x contabil, e Athena x fisico) e Shopee (Athena x saldo do
marketplace). Extraida de core/i9logic.py: a regra sempre foi generica
(compara um "saldo de referencia" contra um "saldo de comparacao"), sem
nada especifico de i9Logic no corpo."""

LIMIAR_ALERTA_ABSOLUTO = 5
LIMIAR_ALERTA_PERCENTUAL = 0.10
TOLERANCIA_ZERO = 0.5


def classificar_divergencia(qtd_referencia: float, qtd_comparacao: float) -> str:
    """qtd_comparacao e' o contabil (i9Logic isolado, modo seed/auditoria),
    o disponivel do Athena (modo monitoramento continuo i9Logic ou Shopee) —
    a mesma regra de classificacao serve pros tres casos, so' muda o que se
    compara contra o fisico/referencia. Nunca ajusta nada sozinho, so'
    classifica pra fila de revisao."""
    divergencia = abs(float(qtd_comparacao) - float(qtd_referencia))
    if divergencia <= TOLERANCIA_ZERO:
        return "sem_acao"
    base = max(float(qtd_referencia), 1)
    if divergencia >= LIMIAR_ALERTA_ABSOLUTO or (divergencia / base) >= LIMIAR_ALERTA_PERCENTUAL:
        return "alerta"
    return "registrado"
```

- [ ] **Step 4: Substituir as constantes e a função em `core/i9logic.py` por um re-export**

Em `hermes_agents/core/i9logic.py`, substituir as linhas 28-30 (`LIMIAR_ALERTA_ABSOLUTO = 5` / `LIMIAR_ALERTA_PERCENTUAL = 0.10` / `TOLERANCIA_ZERO = 0.5`) por:

```python
from core.estoque_divergencia import (
    LIMIAR_ALERTA_ABSOLUTO, LIMIAR_ALERTA_PERCENTUAL, TOLERANCIA_ZERO,
    classificar_divergencia,
)
```

E remover por completo a função `classificar_divergencia` original (linhas 354-365 — o corpo de `def classificar_divergencia(qtd_fisico, qtd_comparacao): ...` até o `return "registrado"`), já que agora vem do import acima.

- [ ] **Step 5: Rodar o teste de regressão e confirmar que ainda passa**

Run: `cd hermes_agents && python -m pytest tests/test_i9logic.py -v`
Expected: PASS (todos, incluindo os 5 novos de `TestClassificarDivergenciaReexport` e todos os pré-existentes do arquivo)

- [ ] **Step 6: Rodar a suíte de rotas i9Logic pra checar retrocompatibilidade**

Run: `cd hermes_agents && python -m pytest tests/test_i9logic.py tests/test_scheduler_i9logic.py -v`
Expected: PASS (todos)

- [ ] **Step 7: Commit**

```bash
git add hermes_agents/core/estoque_divergencia.py hermes_agents/core/i9logic.py hermes_agents/tests/test_i9logic.py
git commit -m "refactor: extrai classificar_divergencia para modulo compartilhado core.estoque_divergencia"
```

---

### Task 2: Backend — `core.i9logic.listar_divergencias_athena()`

**Files:**
- Modify: `hermes_agents/core/i9logic.py` (adicionar função nova, ao lado de `comparar_com_athena`)
- Test: `hermes_agents/tests/test_i9logic.py` (adicionar classe nova)

**Interfaces:**
- Consumes: `estoque_divergencia.classificar_divergencia` (Task 1), `core.i9logic.buscar_id_i9logic`, `core.i9logic.snapshot_mais_recente`, `core.i9logic._disparar_coleta_se_necessario` (todas já existentes, sem mudança), `core.estoque_saldos.saldo`.
- Produces: `listar_divergencias_athena(loja_athena: str) -> dict`. Sucesso: `{"ok": True, "status": "processando"|"pronto", "filial_i9logic": int, "data_coleta": str|None, "data": [{"sku": str, "descricao": str|None, "disponivel_athena": float, "qtd_fisico_i9logic": float, "divergencia": float, "classificacao": str}]}`. Erro (loja sem mapeamento): `{"erro": str}`.

- [ ] **Step 1: Escrever os testes (falhando)**

Adicionar ao final de `hermes_agents/tests/test_i9logic.py`:

```python
class TestListarDivergenciasAthena(unittest.TestCase):
    def test_loja_sem_mapeamento_retorna_erro(self):
        with patch("core.i9logic.buscar_id_i9logic", return_value=None):
            resultado = i9logic.listar_divergencias_athena("Loja Sem Mapeamento")
        self.assertIn("erro", resultado)
        self.assertIn("mapeamento de filial", resultado["erro"])

    def test_snapshot_vazio_retorna_lista_vazia_sem_quebrar(self):
        with patch("core.i9logic.buscar_id_i9logic", return_value="63"), \
             patch("core.i9logic.snapshot_mais_recente", return_value=(None, [])), \
             patch("core.i9logic._disparar_coleta_se_necessario", return_value=True):
            resultado = i9logic.listar_divergencias_athena("Loja Matriz")
        self.assertEqual(resultado["data"], [])
        self.assertEqual(resultado["status"], "processando")

    def test_item_sem_sku_athena_e_ignorado(self):
        itens = [{"idproduto": 1, "sku_athena": None, "qtd": 10, "descricao": "X"}]
        with patch("core.i9logic.buscar_id_i9logic", return_value="63"), \
             patch("core.i9logic.snapshot_mais_recente", return_value=(datetime.now(), itens)), \
             patch("core.i9logic._disparar_coleta_se_necessario", return_value=False):
            resultado = i9logic.listar_divergencias_athena("Loja Matriz")
        self.assertEqual(resultado["data"], [])

    def test_calcula_divergencia_e_classificacao_contra_saldo_athena(self):
        itens = [{"idproduto": 1, "sku_athena": "SKU-A", "qtd": 100, "descricao": "Produto A"}]
        with patch("core.i9logic.buscar_id_i9logic", return_value="63"), \
             patch("core.i9logic.snapshot_mais_recente", return_value=(datetime.now(), itens)), \
             patch("core.i9logic._disparar_coleta_se_necessario", return_value=False), \
             patch("core.estoque_saldos.saldo", return_value=106.0):
            resultado = i9logic.listar_divergencias_athena("Loja Matriz")
        self.assertEqual(len(resultado["data"]), 1)
        item = resultado["data"][0]
        self.assertEqual(item["sku"], "SKU-A")
        self.assertEqual(item["disponivel_athena"], 106.0)
        self.assertEqual(item["qtd_fisico_i9logic"], 100.0)
        self.assertEqual(item["divergencia"], 6.0)
        self.assertEqual(item["classificacao"], "alerta")
        self.assertEqual(resultado["status"], "pronto")
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_i9logic.py::TestListarDivergenciasAthena -v`
Expected: FAIL — `AttributeError: module 'core.i9logic' has no attribute 'listar_divergencias_athena'`

- [ ] **Step 3: Implementar a função**

Em `hermes_agents/core/i9logic.py`, adicionar logo após a função `comparar_com_athena` (procure o `return {...}` final dela, por volta da linha 484, e adicione depois, antes do comentário `# ── Job de coleta ──`):

```python
def listar_divergencias_athena(loja_athena: str) -> dict:
    """Modo monitoramento continuo EM LOTE — mesmo calculo de
    comparar_com_athena(), mas pra todos os skus de uma loja de uma vez,
    usando o snapshot fisico mais recente da filial em vez de uma query por
    sku. Dispara o mesmo lazy-trigger que a tela de Estoque Fisico usa —
    esta funcao nao tem coleta propria, so' consome o que a tela de Estoque
    Fisico ja mantem atualizado (mesma fonte de dado, outra visualizacao)."""
    from core.estoque_saldos import saldo
    id_i9logic = buscar_id_i9logic("filial", loja_athena)
    if id_i9logic is None:
        return {"erro": f"mapeamento de filial i9Logic nao encontrado para a loja '{loja_athena}' "
                         f"(cadastre em /api/integrations/i9logic/depara antes)"}
    filial_id = int(id_i9logic)
    data_coleta, itens = snapshot_mais_recente(filial_id)
    processando = _disparar_coleta_se_necessario(filial_id, data_coleta)
    divergencias = []
    for item in itens:
        sku = item.get("sku_athena")
        if not sku:
            continue
        qtd_fisico = float(item.get("qtd") or 0)
        disponivel_athena = saldo(sku, loja_athena, "disponivel")
        divergencias.append({
            "sku": sku,
            "descricao": item.get("descricao"),
            "disponivel_athena": disponivel_athena,
            "qtd_fisico_i9logic": qtd_fisico,
            "divergencia": round(disponivel_athena - qtd_fisico, 3),
            "classificacao": classificar_divergencia(qtd_fisico, disponivel_athena),
        })
    return {
        "ok": True,
        "status": "processando" if processando else "pronto",
        "filial_i9logic": filial_id,
        "data_coleta": data_coleta.isoformat() if data_coleta else None,
        "data": divergencias,
    }
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_i9logic.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/i9logic.py hermes_agents/tests/test_i9logic.py
git commit -m "feat: adiciona listar_divergencias_athena (comparacao Athena x i9Logic em lote)"
```

---

### Task 3: Backend — rotas i9Logic novas

**Files:**
- Modify: `hermes_agents/routes/i9logic.py` (adicionar 2 rotas, ao lado de `/comparar`)
- Test: `hermes_agents/tests/test_i9logic_rotas.py` (novo arquivo)

**Interfaces:**
- Consumes: `core.i9logic.listar_divergencias_athena(loja_athena)` (Task 2), `core.estoque.ajustar_absoluto(sku, loja, quantidade_absoluta, motivo, usuario_id, usuario_nome, ip, dispositivo)` (já existente).
- Produces: `GET /api/integrations/i9logic/divergencias-athena?loja=` → `jsonify(listar_divergencias_athena(loja))`. `POST /api/integrations/i9logic/divergencias-athena/ajustar` (corpo `{"sku": str, "loja": str}`) → aplica o ajuste, retorna o resultado de `ajustar_absoluto`.

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `hermes_agents/tests/test_i9logic_rotas.py`:

```python
"""Testes de rota — /api/integrations/i9logic/divergencias-athena (comparacao
Athena x i9Logic em lote, Task 2/3 da spec de Divergencia de Saldo)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"

async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"),
    )), __aexit__=AsyncMock(return_value=None))
    return m

patch("asyncpg.create_pool", side_effect=_mock_pool).start()

from flask import Flask
from routes.i9logic import i9logic_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(i9logic_bp)
    return app.test_client()


class TestDivergenciasAthenaRota(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def _headers(self):
        return {"Authorization": f"Bearer {_TEST_TOKEN}"}

    def test_listar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.i9logic.listar_divergencias_athena") as mock_fn:
            r = self.client.get("/api/integrations/i9logic/divergencias-athena?loja=Matriz", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_listar_com_permissao_libera(self):
        with patch("core.i9logic.listar_divergencias_athena", return_value={"ok": True, "data": []}) as mock_fn:
            r = self.client.get("/api/integrations/i9logic/divergencias-athena?loja=Matriz", headers=self._headers())
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once_with("Matriz")

    def test_ajustar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.estoque.ajustar_absoluto") as mock_fn:
            r = self.client.post("/api/integrations/i9logic/divergencias-athena/ajustar",
                                  json={"sku": "SKU-A", "loja": "Matriz"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_ajustar_com_permissao_libera_e_aplica(self):
        with patch("core.estoque.ajustar_absoluto", return_value={"ok": True}) as mock_fn:
            r = self.client.post("/api/integrations/i9logic/divergencias-athena/ajustar",
                                  json={"sku": "SKU-A", "loja": "Matriz", "quantidade": 100},
                                  headers=self._headers())
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once()
        self.assertEqual(mock_fn.call_args.args[0], "SKU-A")
        self.assertEqual(mock_fn.call_args.args[1], "Matriz")
        self.assertEqual(mock_fn.call_args.args[2], 100)

    def test_ajustar_sem_sku_retorna_400(self):
        r = self.client.post("/api/integrations/i9logic/divergencias-athena/ajustar",
                              json={"loja": "Matriz", "quantidade": 100}, headers=self._headers())
        self.assertEqual(r.status_code, 400)
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_i9logic_rotas.py -v`
Expected: FAIL — `404 NOT FOUND` (rotas não existem ainda)

- [ ] **Step 3: Implementar as rotas**

Em `hermes_agents/routes/i9logic.py`, adicionar logo após a rota `/comparar` (depois do bloco `i9logic_comparar`, antes de `/seed`):

```python
@i9logic_bp.route("/divergencias-athena", methods=["GET"])
def i9logic_divergencias_athena():
    """Comparacao Athena x i9Logic EM LOTE — diferente de /divergencias
    (fisico x contabil, interno ao i9Logic). Ver core.i9logic.listar_divergencias_athena."""
    @requer_permissao("estoque.ver")
    def _go():
        from core.i9logic import listar_divergencias_athena
        return jsonify(listar_divergencias_athena(request.args.get("loja", "")))
    return _go()


@i9logic_bp.route("/divergencias-athena/ajustar", methods=["POST"])
def i9logic_divergencias_athena_ajustar():
    """Ajusta o saldo Athena pro fisico i9Logic coletado — mesma direcao de
    aplicar_ajuste_divergencia, mas por (sku, loja) direto (esta comparacao
    nao tem snapshot_id proprio, e' calculada em memoria)."""
    @requer_permissao("estoque.editar")
    def _go():
        from core.estoque import ajustar_absoluto
        dados = request.get_json(silent=True) or {}
        sku = str(dados.get("sku", "")).strip()
        loja = str(dados.get("loja", "")).strip()
        quantidade = dados.get("quantidade")
        if not sku or not loja or quantidade is None:
            return jsonify({"erro": "sku, loja e quantidade sao obrigatorios"}), 400
        usuario = usuario_atual_da_request()
        resultado = ajustar_absoluto(
            sku, loja, float(quantidade), motivo="ajuste_inventario",
            usuario_id=usuario.get("user_id"), usuario_nome=usuario.get("nome", ""))
        if resultado.get("erro"):
            return jsonify(resultado), 400
        return jsonify(resultado)
    return _go()
```

Confirme que `usuario_atual_da_request` já está importado no topo do arquivo (procure o bloco `from core.i9logic import (...)` e imports de `core.rbac` — se `usuario_atual_da_request` não estiver lá, adicione `from core.rbac import usuario_atual_da_request` junto dos demais imports de rbac já presentes no arquivo).

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_i9logic_rotas.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Rodar a suíte completa de i9Logic pra checar retrocompatibilidade**

Run: `cd hermes_agents && python -m pytest tests/test_i9logic.py tests/test_i9logic_rotas.py tests/test_scheduler_i9logic.py -v`
Expected: PASS (todos)

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/i9logic.py hermes_agents/tests/test_i9logic_rotas.py
git commit -m "feat: rotas GET/ajustar de divergencias-athena (i9Logic)"
```

---

### Task 4: Backend — `shopee/divergencia.py`, parte 1 (coleta + snapshot + lazy-trigger)

**Files:**
- Create: `hermes_agents/shopee/divergencia.py`
- Test: `hermes_agents/tests/test_shopee_divergencia.py` (novo arquivo)

**Interfaces:**
- Consumes: `shopee.products.sync_all_items(loja_id) -> list[dict]` (já existente, cada item `{item_id, sku, name, status, stock, reserved, price}`), `core.lojas.obter(id_loja) -> dict` (já existente, tem `nome`), `core.get_db`, `core.run_async`, `core.log`.
- Produces: `executar_coleta_loja(loja_id: int) -> dict`, `snapshot_mais_recente(loja_id: int) -> tuple[datetime|None, list[dict]]`, `disparar_coleta_se_necessario(loja_id: int, data_coleta) -> bool`. Consumido por Task 5 (`listar_divergencias`) e Task 6 (rota).

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `hermes_agents/tests/test_shopee_divergencia.py`:

```python
"""Testes — shopee.divergencia (comparacao Athena x saldo Shopee, Task 4/5
da spec de Divergencia de Saldo)."""
import sys, os, unittest, threading
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"),
    )), __aexit__=AsyncMock(return_value=None))
    return m

patch("asyncpg.create_pool", side_effect=_mock_pool).start()

import shopee.divergencia as divergencia


class TestExecutarColetaLoja(unittest.TestCase):
    def test_grava_snapshot_por_item(self):
        itens_shopee = [
            {"item_id": 111, "sku": "SKU-A", "name": "Produto A", "status": "NORMAL", "stock": 50, "reserved": 0, "price": 10.0},
            {"item_id": 222, "sku": "SKU-B", "name": "Produto B", "status": "NORMAL", "stock": 30, "reserved": 2, "price": 20.0},
        ]
        gravados = []
        async def fake_fetchrow(query, *params):
            gravados.append(params)
            return {"id": len(gravados)}
        with patch("shopee.divergencia.sync_all_items", return_value=itens_shopee), \
             patch("shopee.divergencia.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetchrow = AsyncMock(side_effect=fake_fetchrow)
            mock_get_db.return_value = db
            resultado = divergencia.executar_coleta_loja(1)
        self.assertEqual(resultado["gravados"], 2)
        self.assertEqual(len(gravados), 2)

    def test_item_sem_sku_real_ainda_e_gravado(self):
        # sku == str(item_id) e' o fallback da propria Shopee quando nao ha' item_sku
        itens_shopee = [{"item_id": 999, "sku": "999", "name": "Sem SKU", "status": "NORMAL", "stock": 5, "reserved": 0, "price": 1.0}]
        async def fake_fetchrow(query, *params):
            return {"id": 1}
        with patch("shopee.divergencia.sync_all_items", return_value=itens_shopee), \
             patch("shopee.divergencia.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetchrow = AsyncMock(side_effect=fake_fetchrow)
            mock_get_db.return_value = db
            resultado = divergencia.executar_coleta_loja(1)
        self.assertEqual(resultado["gravados"], 1)

    def test_erro_de_api_shopee_nao_quebra_retorna_erro(self):
        with patch("shopee.divergencia.sync_all_items", side_effect=Exception("timeout Shopee")):
            resultado = divergencia.executar_coleta_loja(1)
        self.assertIn("erro", resultado)


class TestSnapshotMaisRecente(unittest.TestCase):
    def test_sem_coleta_retorna_none_e_lista_vazia(self):
        with patch("shopee.divergencia.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetchval = AsyncMock(return_value=None)
            mock_get_db.return_value = db
            data_coleta, itens = divergencia.snapshot_mais_recente(1)
        self.assertIsNone(data_coleta)
        self.assertEqual(itens, [])

    def test_com_coleta_retorna_itens_da_corrida_mais_recente(self):
        agora = datetime.now()
        async def fake_fetch(query, *params):
            return [{"sku": "SKU-A", "qtd_shopee": 50, "item_id_shopee": "111"}]
        with patch("shopee.divergencia.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetchval = AsyncMock(return_value=agora)
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            data_coleta, itens = divergencia.snapshot_mais_recente(1)
        self.assertEqual(data_coleta, agora)
        self.assertEqual(len(itens), 1)


class TestDispararColetaSeNecessario(unittest.TestCase):
    def setUp(self):
        divergencia._coleta_em_andamento.clear()

    def test_sem_snapshot_dispara_coleta(self):
        with patch("shopee.divergencia.threading.Thread") as mock_thread:
            resultado = divergencia.disparar_coleta_se_necessario(1, None)
        self.assertTrue(resultado)
        mock_thread.assert_called_once()

    def test_snapshot_fresco_nao_dispara(self):
        agora = datetime.now()
        with patch("shopee.divergencia.threading.Thread") as mock_thread:
            resultado = divergencia.disparar_coleta_se_necessario(1, agora)
        self.assertFalse(resultado)
        mock_thread.assert_not_called()

    def test_snapshot_velho_dispara_coleta(self):
        velho = datetime.now() - timedelta(minutes=divergencia.FRESCOR_MAXIMO_MINUTOS + 5)
        with patch("shopee.divergencia.threading.Thread") as mock_thread:
            resultado = divergencia.disparar_coleta_se_necessario(1, velho)
        self.assertTrue(resultado)
        mock_thread.assert_called_once()

    def test_coleta_ja_em_andamento_nao_dispara_segunda_thread(self):
        divergencia._coleta_em_andamento.add(1)
        try:
            with patch("shopee.divergencia.threading.Thread") as mock_thread:
                resultado = divergencia.disparar_coleta_se_necessario(1, None)
            self.assertTrue(resultado)
            mock_thread.assert_not_called()
        finally:
            divergencia._coleta_em_andamento.discard(1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_shopee_divergencia.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'shopee.divergencia'`

- [ ] **Step 3: Implementar o módulo**

Criar `hermes_agents/shopee/divergencia.py`:

```python
"""Divergencia de Saldo — Athena x Shopee. Mesmo principio do
core/i9logic.py: guarda so' o saldo externo bruto no snapshot (nunca o
saldo Athena, que muda a cada venda — comparacao e' sempre calculada ao
vivo na leitura, ver listar_divergencias em divergencia.py parte 2)."""
import sys, threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
from core import get_db, run_async, log
from core.lojas import obter as obter_loja
from .products import sync_all_items

AGENT = "Shopee Divergencia"

FRESCOR_MAXIMO_MINUTOS = 30  # mesmo valor do i9Logic — snapshot mais velho que isso dispara nova coleta

_coleta_em_andamento = set()  # loja_id -> coleta rodando agora, evita disparo duplicado
_coleta_erro_recente = {}  # loja_id -> mensagem de erro da ultima tentativa
_coleta_lock = threading.Lock()


def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS shopee_estoque_snapshot (
            id SERIAL PRIMARY KEY,
            sku VARCHAR(50) NOT NULL,
            loja_id INT NOT NULL REFERENCES lojas(id),
            item_id_shopee VARCHAR(100),
            qtd_shopee DECIMAL(12,3),
            data_coleta TIMESTAMP DEFAULT NOW(),
            revisado BOOLEAN DEFAULT FALSE,
            UNIQUE(sku, loja_id, data_coleta)
        )""")
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao criar tabela shopee_estoque_snapshot: {e}")

_ensure_tables()


def executar_coleta_loja(loja_id: int) -> dict:
    """Chama sync_all_items(loja_id) e grava um snapshot por sku com o
    saldo Shopee bruto. Item com sku == str(item_id) (fallback da propria
    Shopee quando nao ha' item_sku real) ainda e' gravado — o pareamento
    com o saldo Athena na leitura (listar_divergencias) e' quem trata a
    ausencia de produto correspondente, nao a coleta."""
    inicio_corrida = datetime.now()
    try:
        itens = sync_all_items(loja_id)
    except Exception as e:
        log(AGENT, f"Erro ao sincronizar itens da loja {loja_id}: {e}")
        return {"erro": str(e)}
    async def _go():
        db = await get_db()
        gravados, erros = 0, 0
        for item in itens:
            try:
                await db.fetchrow("""
                    INSERT INTO shopee_estoque_snapshot (sku, loja_id, item_id_shopee, qtd_shopee, data_coleta)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (sku, loja_id, data_coleta) DO UPDATE SET qtd_shopee = $4
                    RETURNING id
                """, item["sku"], loja_id, str(item["item_id"]), item.get("stock", 0), inicio_corrida)
                gravados += 1
            except Exception:
                erros += 1
        return gravados, erros
    try:
        gravados, erros = run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao gravar snapshot da loja {loja_id}: {e}")
        return {"erro": str(e)}
    return {"ok": True, "loja_id": loja_id, "itens": len(itens), "gravados": gravados, "erros": erros, "data_coleta": inicio_corrida}


def snapshot_mais_recente(loja_id: int):
    """(data_coleta, itens) da corrida mais recente da loja. (None, []) se
    essa loja nunca foi coletada. Identico em forma a
    core.i9logic.snapshot_mais_recente."""
    async def _go():
        db = await get_db()
        data_coleta = await db.fetchval(
            "SELECT MAX(data_coleta) FROM shopee_estoque_snapshot WHERE loja_id=$1", loja_id)
        if data_coleta is None:
            return None, []
        rows = await db.fetch(
            "SELECT id, sku, item_id_shopee, qtd_shopee FROM shopee_estoque_snapshot "
            "WHERE loja_id=$1 AND data_coleta=$2", loja_id, data_coleta)
        return data_coleta, [dict(r) for r in rows]
    try:
        return run_async(_go())
    except Exception:
        return None, []


def _coleta_em_background(loja_id: int):
    """Roda a coleta completa fora do request. Sempre libera o lock ao
    final, mesmo em erro — senao a loja fica presa em 'processando'."""
    try:
        executar_coleta_loja(loja_id)
        _coleta_erro_recente.pop(loja_id, None)
    except Exception as e:
        _coleta_erro_recente[loja_id] = str(e)
        log(AGENT, f"Erro na coleta em background da loja {loja_id}: {e}")
    finally:
        with _coleta_lock:
            _coleta_em_andamento.discard(loja_id)


def disparar_coleta_se_necessario(loja_id: int, data_coleta) -> bool:
    """Dispara coleta em background se nao houver uma rodando e o snapshot
    estiver ausente ou mais velho que FRESCOR_MAXIMO_MINUTOS. Retorna True
    se a loja ficou (ou ja estava) em processamento. Identico em forma a
    core.i9logic._disparar_coleta_se_necessario."""
    precisa_coletar = data_coleta is None or (
        (datetime.now() - data_coleta).total_seconds() / 60 > FRESCOR_MAXIMO_MINUTOS)
    with _coleta_lock:
        ja_rodando = loja_id in _coleta_em_andamento
        deve_iniciar = precisa_coletar and not ja_rodando
        if deve_iniciar:
            _coleta_em_andamento.add(loja_id)
    if deve_iniciar:
        threading.Thread(target=_coleta_em_background, args=(loja_id,), daemon=True).start()
    return ja_rodando or deve_iniciar
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_shopee_divergencia.py -v`
Expected: PASS (todos os 8 testes desta parte)

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/shopee/divergencia.py hermes_agents/tests/test_shopee_divergencia.py
git commit -m "feat: shopee.divergencia — coleta, snapshot e lazy-trigger de saldo Shopee"
```

---

### Task 5: Backend — `shopee/divergencia.py`, parte 2 (listagem + resolução)

**Files:**
- Modify: `hermes_agents/shopee/divergencia.py` (adicionar funções, ao final do arquivo)
- Test: `hermes_agents/tests/test_shopee_divergencia.py` (adicionar classes)

**Interfaces:**
- Consumes: `snapshot_mais_recente`, `disparar_coleta_se_necessario` (Task 4), `core.estoque_divergencia.classificar_divergencia` (Task 1), `core.estoque_saldos.saldo`, `core.estoque.ajustar_absoluto`, `core.lojas.obter`.
- Produces: `listar_divergencias(loja_id: int) -> dict` (mesmo formato de `core.i9logic.listar_divergencias_athena`: `{"ok", "status", "data_coleta", "data": [...]}`, cada item com `{"id": int, "sku": str, "qtd_shopee": float, "disponivel_athena": float, "divergencia": float, "classificacao": str, "revisado": bool}`), `marcar_revisado(snapshot_id: int) -> dict`, `aplicar_ajuste_divergencia(snapshot_id: int, usuario_id=None, usuario_nome="") -> dict`. Consumidos pela Task 6 (rotas).

- [ ] **Step 1: Escrever os testes (falhando)**

Adicionar ao final de `hermes_agents/tests/test_shopee_divergencia.py`, antes de `if __name__ == "__main__":`:

```python
class TestListarDivergencias(unittest.TestCase):
    def test_calcula_divergencia_contra_saldo_athena(self):
        itens = [{"id": 1, "sku": "SKU-A", "item_id_shopee": "111", "qtd_shopee": 50}]
        with patch("shopee.divergencia.snapshot_mais_recente", return_value=(datetime.now(), itens)), \
             patch("shopee.divergencia.disparar_coleta_se_necessario", return_value=False), \
             patch("shopee.divergencia.obter_loja", return_value={"id": 1, "nome": "Loja Online"}), \
             patch("core.estoque_saldos.saldo", return_value=44.0):
            resultado = divergencia.listar_divergencias(1)
        self.assertEqual(len(resultado["data"]), 1)
        item = resultado["data"][0]
        self.assertEqual(item["qtd_shopee"], 50.0)
        self.assertEqual(item["disponivel_athena"], 44.0)
        self.assertEqual(item["divergencia"], -6.0)
        self.assertEqual(item["classificacao"], "alerta")
        self.assertEqual(resultado["status"], "pronto")

    def test_snapshot_ausente_dispara_coleta_e_retorna_processando(self):
        with patch("shopee.divergencia.snapshot_mais_recente", return_value=(None, [])), \
             patch("shopee.divergencia.disparar_coleta_se_necessario", return_value=True), \
             patch("shopee.divergencia.obter_loja", return_value={"id": 1, "nome": "Loja Online"}):
            resultado = divergencia.listar_divergencias(1)
        self.assertEqual(resultado["data"], [])
        self.assertEqual(resultado["status"], "processando")


class TestMarcarRevisado(unittest.TestCase):
    def test_marca_revisado_true(self):
        async def fake_fetchrow(query, *params):
            return {"id": 1, "sku": "SKU-A", "revisado": True}
        with patch("shopee.divergencia.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetchrow = AsyncMock(side_effect=fake_fetchrow)
            mock_get_db.return_value = db
            resultado = divergencia.marcar_revisado(1)
        self.assertTrue(resultado["ok"])

    def test_snapshot_inexistente_retorna_erro(self):
        async def fake_fetchrow(query, *params):
            return None
        with patch("shopee.divergencia.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetchrow = AsyncMock(side_effect=fake_fetchrow)
            mock_get_db.return_value = db
            resultado = divergencia.marcar_revisado(999)
        self.assertIn("erro", resultado)


class TestAplicarAjusteDivergencia(unittest.TestCase):
    def test_aplica_ajuste_com_sucesso(self):
        async def fake_buscar():
            return {"sku": "SKU-A", "loja_id": 1, "qtd_shopee": 50}
        with patch("shopee.divergencia._buscar_snapshot", return_value={"sku": "SKU-A", "loja_id": 1, "qtd_shopee": 50}), \
             patch("shopee.divergencia._snapshot_mais_recente_id", return_value=1), \
             patch("shopee.divergencia.obter_loja", return_value={"id": 1, "nome": "Loja Online"}), \
             patch("shopee.divergencia.ajustar_absoluto", return_value={"ok": True}) as mock_ajustar, \
             patch("shopee.divergencia.marcar_revisado", return_value={"ok": True}):
            resultado = divergencia.aplicar_ajuste_divergencia(1, usuario_id=7, usuario_nome="Op")
        self.assertTrue(resultado["ok"])
        mock_ajustar.assert_called_once_with(
            "SKU-A", "Loja Online", 50, motivo="ajuste_inventario", usuario_id=7, usuario_nome="Op")

    def test_snapshot_desatualizado_recusa_ajuste(self):
        with patch("shopee.divergencia._buscar_snapshot", return_value={"sku": "SKU-A", "loja_id": 1, "qtd_shopee": 50}), \
             patch("shopee.divergencia._snapshot_mais_recente_id", return_value=2):
            resultado = divergencia.aplicar_ajuste_divergencia(1)
        self.assertIn("erro", resultado)
        self.assertIn("nao e' o mais recente", resultado["erro"])

    def test_snapshot_nao_encontrado_retorna_erro(self):
        with patch("shopee.divergencia._buscar_snapshot", return_value=None):
            resultado = divergencia.aplicar_ajuste_divergencia(999)
        self.assertIn("erro", resultado)
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_shopee_divergencia.py -v`
Expected: FAIL — `AttributeError: module 'shopee.divergencia' has no attribute 'listar_divergencias'` (e demais funções desta parte)

- [ ] **Step 3: Implementar as funções**

Em `hermes_agents/shopee/divergencia.py`, adicionar os imports que faltam no topo do arquivo (junto dos já existentes):

```python
from core.estoque_divergencia import classificar_divergencia
from core.estoque_saldos import saldo
from core.estoque import ajustar_absoluto
```

E adicionar ao final do arquivo:

```python
def listar_divergencias(loja_id: int) -> dict:
    """Le o snapshot mais recente da loja (disparando coleta se
    necessario), resolve o nome da loja, e pra cada sku compara qtd_shopee
    contra core.estoque_saldos.saldo() — mesmo formato de retorno de
    core.i9logic.listar_divergencias_athena, pra o frontend tratar os dois
    lados de forma simetrica."""
    loja = obter_loja(loja_id)
    nome_loja = loja["nome"] if loja else ""
    data_coleta, itens = snapshot_mais_recente(loja_id)
    processando = disparar_coleta_se_necessario(loja_id, data_coleta)
    divergencias = []
    for item in itens:
        qtd_shopee = float(item["qtd_shopee"] or 0)
        disponivel_athena = saldo(item["sku"], nome_loja, "disponivel")
        divergencias.append({
            "id": item["id"],
            "sku": item["sku"],
            "qtd_shopee": qtd_shopee,
            "disponivel_athena": disponivel_athena,
            "divergencia": round(disponivel_athena - qtd_shopee, 3),
            "classificacao": classificar_divergencia(qtd_shopee, disponivel_athena),
            "revisado": item.get("revisado", False),
        })
    return {
        "ok": True,
        "status": "processando" if processando else "pronto",
        "data_coleta": data_coleta.isoformat() if data_coleta else None,
        "data": divergencias,
    }


def marcar_revisado(snapshot_id: int) -> dict:
    """Aceita a divergencia como conhecida — so' marca revisado, nunca
    ajusta saldo. Identico em forma a core.i9logic.marcar_revisado."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "UPDATE shopee_estoque_snapshot SET revisado=TRUE WHERE id=$1 RETURNING *", snapshot_id)
        return dict(row) if row else None
    try:
        r = run_async(_go())
        return {"ok": True, "snapshot": r} if r else {"erro": "snapshot nao encontrado"}
    except Exception as e:
        return {"erro": str(e)}


def _buscar_snapshot(snapshot_id: int):
    async def _go():
        db = await get_db()
        return await db.fetchrow(
            "SELECT sku, loja_id, qtd_shopee FROM shopee_estoque_snapshot WHERE id=$1", snapshot_id)
    try:
        row = run_async(_go())
        return dict(row) if row else None
    except Exception:
        return None


def _snapshot_mais_recente_id(sku: str, loja_id: int):
    async def _go():
        db = await get_db()
        return await db.fetchval(
            "SELECT id FROM shopee_estoque_snapshot WHERE sku=$1 AND loja_id=$2 "
            "ORDER BY data_coleta DESC LIMIT 1", sku, loja_id)
    try:
        return run_async(_go())
    except Exception:
        return None


def aplicar_ajuste_divergencia(snapshot_id: int, usuario_id: int = None, usuario_nome: str = "") -> dict:
    """Le o snapshot (sku, qtd_shopee), resolve o nome da loja a partir de
    loja_id, chama core.estoque.ajustar_absoluto(sku, nome_loja, qtd_shopee,
    ...). Mesma guarda de frescor do i9Logic: so' aplica se for o snapshot
    mais recente pra aquele sku/loja."""
    snap = _buscar_snapshot(snapshot_id)
    if not snap:
        return {"erro": "snapshot nao encontrado"}
    id_mais_recente = _snapshot_mais_recente_id(snap["sku"], snap["loja_id"])
    if id_mais_recente is not None and id_mais_recente != snapshot_id:
        return {"erro": f"este snapshot (id={snapshot_id}) nao e' o mais recente pra este sku/loja "
                         f"(o mais recente e' id={id_mais_recente}) - ajuste a partir do mais recente"}
    loja = obter_loja(snap["loja_id"])
    nome_loja = loja["nome"] if loja else ""
    resultado = ajustar_absoluto(
        snap["sku"], nome_loja, float(snap["qtd_shopee"] or 0),
        motivo="ajuste_inventario", usuario_id=usuario_id, usuario_nome=usuario_nome)
    if resultado.get("erro"):
        return resultado
    marcado = marcar_revisado(snapshot_id)
    if marcado.get("erro"):
        return {"erro": f"ajuste aplicado mas falha ao marcar revisado: {marcado['erro']}", "ajuste": resultado}
    return {"ok": True, "ajuste": resultado, "snapshot": marcado.get("snapshot")}
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_shopee_divergencia.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/shopee/divergencia.py hermes_agents/tests/test_shopee_divergencia.py
git commit -m "feat: shopee.divergencia — listagem, marcar revisado e ajuste"
```

---

### Task 6: Backend — rotas Shopee novas

**Files:**
- Modify: `hermes_agents/routes/shopee.py` (adicionar 3 rotas, ao lado das rotas de `/estoque-rapido`)
- Test: `hermes_agents/tests/test_shopee_divergencia_rotas.py` (novo arquivo)

**Interfaces:**
- Consumes: `shopee.divergencia.listar_divergencias(loja_id)`, `shopee.divergencia.marcar_revisado(id)`, `shopee.divergencia.aplicar_ajuste_divergencia(id, usuario_id, usuario_nome)` (Task 5).
- Produces: `GET /api/shopee/divergencias?loja_id=`, `POST /api/shopee/divergencias/<id>/resolver`, `POST /api/shopee/divergencias/<id>/ajustar`.

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `hermes_agents/tests/test_shopee_divergencia_rotas.py`:

```python
"""Testes de rota — /api/shopee/divergencias (Task 6 da spec de Divergencia
de Saldo)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"

async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"),
    )), __aexit__=AsyncMock(return_value=None))
    return m

patch("asyncpg.create_pool", side_effect=_mock_pool).start()

from flask import Flask
from routes.shopee import shopee_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(shopee_bp)
    return app.test_client()


class TestDivergenciasShopeeRota(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def _headers(self):
        return {"Authorization": f"Bearer {_TEST_TOKEN}"}

    def test_listar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("shopee.divergencia.listar_divergencias") as mock_fn:
            r = self.client.get("/api/shopee/divergencias?loja_id=1", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_listar_com_permissao_libera(self):
        with patch("shopee.divergencia.listar_divergencias", return_value={"ok": True, "data": []}) as mock_fn:
            r = self.client.get("/api/shopee/divergencias?loja_id=1", headers=self._headers())
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once_with(1)

    def test_resolver_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("shopee.divergencia.marcar_revisado") as mock_fn:
            r = self.client.post("/api/shopee/divergencias/1/resolver", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_resolver_com_permissao_libera(self):
        with patch("shopee.divergencia.marcar_revisado", return_value={"ok": True}) as mock_fn:
            r = self.client.post("/api/shopee/divergencias/1/resolver", headers=self._headers())
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once_with(1)

    def test_ajustar_com_permissao_libera(self):
        with patch("shopee.divergencia.aplicar_ajuste_divergencia", return_value={"ok": True}) as mock_fn:
            r = self.client.post("/api/shopee/divergencias/1/ajustar", headers=self._headers())
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once()
        self.assertEqual(mock_fn.call_args.args[0], 1)

    def test_ajustar_com_erro_retorna_400(self):
        with patch("shopee.divergencia.aplicar_ajuste_divergencia", return_value={"erro": "snapshot nao encontrado"}):
            r = self.client.post("/api/shopee/divergencias/999/ajustar", headers=self._headers())
        self.assertEqual(r.status_code, 400)
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_shopee_divergencia_rotas.py -v`
Expected: FAIL — `404 NOT FOUND`

- [ ] **Step 3: Implementar as rotas**

Em `hermes_agents/routes/shopee.py`, adicionar logo após a rota `/estoque-rapido/celula` (procure o fim desse bloco, depois do `except Exception as e: return jsonify({"error": str(e)}), 500` da linha ~676):

```python
@shopee_bp.route('/divergencias', methods=['GET'])
def shopee_divergencias_listar():
    from core.rbac import requer_permissao
    @requer_permissao("estoque.ver")
    def _handler():
        from shopee.divergencia import listar_divergencias
        loja_id = request.args.get("loja_id", type=int)
        if not loja_id:
            return jsonify({"erro": "loja_id e' obrigatorio"}), 400
        return jsonify(listar_divergencias(loja_id))
    return _handler()


@shopee_bp.route('/divergencias/<int:snapshot_id>/resolver', methods=['POST'])
def shopee_divergencias_resolver(snapshot_id):
    from core.rbac import requer_permissao
    @requer_permissao("estoque.editar")
    def _handler():
        from shopee.divergencia import marcar_revisado
        return jsonify(marcar_revisado(snapshot_id))
    return _handler()


@shopee_bp.route('/divergencias/<int:snapshot_id>/ajustar', methods=['POST'])
def shopee_divergencias_ajustar(snapshot_id):
    from core.rbac import requer_permissao, usuario_atual_da_request
    @requer_permissao("estoque.editar")
    def _handler():
        from shopee.divergencia import aplicar_ajuste_divergencia
        usuario = usuario_atual_da_request()
        resultado = aplicar_ajuste_divergencia(
            snapshot_id, usuario_id=usuario.get("user_id"), usuario_nome=usuario.get("nome", ""))
        if resultado.get("erro"):
            return jsonify(resultado), 400
        return jsonify(resultado)
    return _handler()
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_shopee_divergencia_rotas.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Rodar toda a suíte de backend criada nesta feature**

Run: `cd hermes_agents && python -m pytest tests/test_i9logic.py tests/test_i9logic_rotas.py tests/test_shopee_divergencia.py tests/test_shopee_divergencia_rotas.py tests/test_scheduler_i9logic.py -v`
Expected: PASS (todos)

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/shopee.py hermes_agents/tests/test_shopee_divergencia_rotas.py
git commit -m "feat: rotas de divergencia de saldo Shopee (listar/resolver/ajustar)"
```

---

### Task 7: Frontend — `api.ts`

**Files:**
- Modify: `web/src/lib/api.ts` (adicionar tipos e funções, perto de `i9logicEstoquePorLoja`)

**Interfaces:**
- Produces: `export interface DivergenciaItem { sku: string; descricao?: string; disponivel_athena: number; qtd_fisico_i9logic?: number; qtd_shopee?: number; divergencia: number; classificacao: "sem_acao"|"registrado"|"alerta"; revisado?: boolean; id?: number }`, `export interface DivergenciaResponse { ok: boolean; status: "processando"|"pronto"; data_coleta: string|null; data: DivergenciaItem[]; erro?: string }`, `i9logicListarDivergenciasAthena(loja: string): Promise<DivergenciaResponse>`, `i9logicAjustarDivergenciaAthena(sku: string, loja: string, quantidade: number): Promise<{ok?: boolean; erro?: string}>`, `shopeeListarDivergencias(lojaId: number): Promise<DivergenciaResponse>`, `shopeeResolverDivergencia(id: number): Promise<{ok?: boolean; erro?: string}>`, `shopeeAjustarDivergencia(id: number): Promise<{ok?: boolean; erro?: string}>`.
- Consumes (Task 8): todas as 5 funções acima + os 2 tipos.

- [ ] **Step 1: Localizar o ponto de inserção**

Procure por `i9logicEstoquePorLoja` em `web/src/lib/api.ts` (já existe, usada por `EstoqueFisicoI9Logic.tsx`). Adicionar o código abaixo logo após essa função.

- [ ] **Step 2: Adicionar tipos e funções**

```typescript
export interface DivergenciaItem {
  id?: number;
  sku: string;
  descricao?: string;
  disponivel_athena: number;
  qtd_fisico_i9logic?: number;
  qtd_shopee?: number;
  divergencia: number;
  classificacao: "sem_acao" | "registrado" | "alerta";
  revisado?: boolean;
}

export interface DivergenciaResponse {
  ok?: boolean;
  status?: "processando" | "pronto";
  data_coleta?: string | null;
  data: DivergenciaItem[];
  erro?: string;
}

export async function i9logicListarDivergenciasAthena(loja: string): Promise<DivergenciaResponse> {
  const res = await fetch(`/api/integrations/i9logic/divergencias-athena?loja=${encodeURIComponent(loja)}`);
  if (!res.ok) return { data: [], erro: `HTTP ${res.status}` };
  return res.json().catch(() => ({ data: [], erro: "Resposta invalida" }));
}

export async function i9logicAjustarDivergenciaAthena(
  sku: string, loja: string, quantidade: number
): Promise<{ ok?: boolean; erro?: string }> {
  const res = await fetch("/api/integrations/i9logic/divergencias-athena/ajustar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sku, loja, quantidade }),
  });
  return res.json().catch(() => ({ erro: `HTTP ${res.status}` }));
}

export async function shopeeListarDivergencias(lojaId: number): Promise<DivergenciaResponse> {
  const res = await fetch(`/api/shopee/divergencias?loja_id=${lojaId}`);
  if (!res.ok) return { data: [], erro: `HTTP ${res.status}` };
  return res.json().catch(() => ({ data: [], erro: "Resposta invalida" }));
}

export async function shopeeResolverDivergencia(id: number): Promise<{ ok?: boolean; erro?: string }> {
  const res = await fetch(`/api/shopee/divergencias/${id}/resolver`, { method: "POST" });
  return res.json().catch(() => ({ erro: `HTTP ${res.status}` }));
}

export async function shopeeAjustarDivergencia(id: number): Promise<{ ok?: boolean; erro?: string }> {
  const res = await fetch(`/api/shopee/divergencias/${id}/ajustar`, { method: "POST" });
  return res.json().catch(() => ({ erro: `HTTP ${res.status}` }));
}
```

**ATENÇÃO:** `web/src/lib/api.ts` tem um único `export const api = {...}` no arquivo — as funções acima são exports SOLTOS (`export async function ...`), igual ao padrão de `i9logicEstoquePorLoja`/`listarBlingDepositos`, e ficam FORA desse objeto. Nunca insira `};` nem abra um segundo `export const api = {`. Depois de editar, confirme com `grep -c "export const api = {" web/src/lib/api.ts` que o resultado continua `1`.

- [ ] **Step 3: Type-check**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros novos (saída vazia)

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/api.ts
git commit -m "feat: adiciona funcoes de api para divergencia de saldo (i9Logic + Shopee)"
```

---

### Task 8: Frontend — seção "Divergência de Saldo" em `discrepancias/page.tsx`

**Files:**
- Create: `web/src/app/estoque/discrepancias/_components/DivergenciaSaldo.tsx`
- Modify: `web/src/app/estoque/discrepancias/page.tsx`

**Interfaces:**
- Consumes: `i9logicListarDivergenciasAthena`, `i9logicAjustarDivergenciaAthena`, `shopeeListarDivergencias`, `shopeeResolverDivergencia`, `shopeeAjustarDivergencia`, `type DivergenciaItem`, `type DivergenciaResponse` de `@/lib/api` (Task 7); `useStore` de `@/lib/store-context`.
- Produces: `export default function DivergenciaSaldo(): JSX.Element` — sem props, lê `useStore()` internamente.

- [ ] **Step 1: Criar o componente**

```tsx
"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useStore } from "@/lib/store-context";
import {
  i9logicListarDivergenciasAthena, i9logicAjustarDivergenciaAthena,
  shopeeListarDivergencias, shopeeResolverDivergencia, shopeeAjustarDivergencia,
  type DivergenciaItem, type DivergenciaResponse,
} from "@/lib/api";

const POLL_INTERVAL_MS = 5000;

const CLASSIFICACAO_LABEL: Record<string, string> = {
  sem_acao: "OK", registrado: "Registrado", alerta: "Alerta",
};
const CLASSIFICACAO_CLASSE: Record<string, string> = {
  sem_acao: "text-neutral-500", registrado: "text-amber-400", alerta: "text-red-400",
};

export default function DivergenciaSaldo() {
  const { lojaId, lojas, tipoLojaSelecionada } = useStore();
  const loja = lojas.find(l => String(l.id) === lojaId);
  const [itens, setItens] = useState<DivergenciaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [atualizando, setAtualizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [ajustando, setAjustando] = useState<string | number | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelarPoll = () => {
    if (pollRef.current) {
      clearTimeout(pollRef.current);
      pollRef.current = null;
    }
  };

  const carregar = useCallback(async (primeiraVez = false) => {
    cancelarPoll();
    if (!loja) return;
    if (primeiraVez) setLoading(true);
    setErro(null);
    try {
      let r: DivergenciaResponse;
      if (tipoLojaSelecionada === "fisica") {
        r = await i9logicListarDivergenciasAthena(loja.nome);
      } else {
        r = await shopeeListarDivergencias(loja.id);
      }
      if (r.erro) {
        setErro(r.erro);
        setAtualizando(false);
        return;
      }
      setItens(r.data || []);
      const processando = r.status === "processando";
      setAtualizando(processando);
      if (processando) {
        pollRef.current = setTimeout(() => carregar(false), POLL_INTERVAL_MS);
      }
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar divergencias");
      setAtualizando(false);
    } finally {
      if (primeiraVez) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loja?.id, loja?.nome, tipoLojaSelecionada]);

  useEffect(() => {
    carregar(true);
    return () => cancelarPoll();
  }, [carregar]);

  const ajustar = async (item: DivergenciaItem) => {
    if (!loja) return;
    const chave = tipoLojaSelecionada === "fisica" ? item.sku : (item.id as number);
    setAjustando(chave);
    try {
      const r = tipoLojaSelecionada === "fisica"
        ? await i9logicAjustarDivergenciaAthena(item.sku, loja.nome, item.qtd_fisico_i9logic || 0)
        : await shopeeAjustarDivergencia(item.id as number);
      if (r.erro) { setErro(r.erro); return; }
      await carregar(true);
    } finally {
      setAjustando(null);
    }
  };

  const resolver = async (item: DivergenciaItem) => {
    if (tipoLojaSelecionada !== "virtual" || item.id === undefined) return;
    setAjustando(item.id);
    try {
      const r = await shopeeResolverDivergencia(item.id);
      if (r.erro) { setErro(r.erro); return; }
      await carregar(true);
    } finally {
      setAjustando(null);
    }
  };

  const fonteLabel = tipoLojaSelecionada === "fisica" ? "i9Logic" : "Shopee";

  return (
    <section className="space-y-2">
      <div>
        <h2 className="text-sm font-medium text-neutral-400">Divergência de Saldo</h2>
        <p className="text-xs text-neutral-500 mt-0.5">
          Compara o saldo disponível no Athena contra o saldo real no {fonteLabel} — aponta onde o saldo local está desatualizado.
        </p>
      </div>

      {!loja ? (
        <div className="text-neutral-500 text-xs">Selecione uma loja no topo da página.</div>
      ) : erro ? (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>
      ) : loading ? (
        <div className="text-neutral-500 text-sm">Carregando...</div>
      ) : (
        <>
          {atualizando && (
            <div className="bg-indigo-900/20 border border-indigo-800/60 text-indigo-300 text-xs px-3 py-2 rounded-lg">
              Coletando saldo atualizado do {fonteLabel} em segundo plano — a lista atualiza sozinha quando terminar.
            </div>
          )}
          {itens.length === 0 ? (
            <div className="text-neutral-500 text-xs">Nenhuma divergência encontrada.</div>
          ) : (
            <div className="overflow-x-auto border border-neutral-800 rounded-lg">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-neutral-900 text-neutral-400 text-left">
                    <th className="px-3 py-2 font-medium">SKU</th>
                    <th className="px-3 py-2 font-medium text-right">Saldo Athena</th>
                    <th className="px-3 py-2 font-medium text-right">Saldo {fonteLabel}</th>
                    <th className="px-3 py-2 font-medium text-right">Divergência</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2 font-medium text-right">Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {itens.map(item => {
                    const chave = tipoLojaSelecionada === "fisica" ? item.sku : (item.id as number);
                    const saldoExterno = tipoLojaSelecionada === "fisica" ? item.qtd_fisico_i9logic : item.qtd_shopee;
                    return (
                      <tr key={chave} className="border-t border-neutral-800 text-neutral-300">
                        <td className="px-3 py-2 font-mono text-neutral-200">{item.sku}</td>
                        <td className="px-3 py-2 text-right numeric">{item.disponivel_athena}</td>
                        <td className="px-3 py-2 text-right numeric">{saldoExterno}</td>
                        <td className="px-3 py-2 text-right numeric font-medium">{item.divergencia > 0 ? `+${item.divergencia}` : item.divergencia}</td>
                        <td className={`px-3 py-2 font-medium ${CLASSIFICACAO_CLASSE[item.classificacao]}`}>
                          {CLASSIFICACAO_LABEL[item.classificacao]}
                        </td>
                        <td className="px-3 py-2 text-right">
                          <div className="flex justify-end gap-2">
                            <button onClick={() => ajustar(item)} disabled={ajustando === chave}
                              className="text-indigo-400 hover:text-indigo-300 disabled:opacity-50">
                              Ajustar
                            </button>
                            {tipoLojaSelecionada === "virtual" && (
                              <button onClick={() => resolver(item)} disabled={ajustando === chave}
                                className="text-neutral-500 hover:text-neutral-300 disabled:opacity-50">
                                Marcar revisado
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros

- [ ] **Step 3: Integrar na página de Discrepâncias**

Em `web/src/app/estoque/discrepancias/page.tsx`, adicionar o import no topo:

```tsx
import DivergenciaSaldo from "./_components/DivergenciaSaldo";
```

E adicionar `<DivergenciaSaldo />` como uma terceira `<section>` dentro do bloco `{loading ? (...) : (<>...</>)}`, logo após a seção "Por operador" (depois do `</section>` que fecha o bloco "Por operador", antes do `</>` de fechamento):

```tsx
          <section>
            <DivergenciaSaldo />
          </section>
```

- [ ] **Step 4: Type-check e build completo**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: build passa sem erros

- [ ] **Step 5: Commit**

```bash
git add web/src/app/estoque/discrepancias/_components/DivergenciaSaldo.tsx web/src/app/estoque/discrepancias/page.tsx
git commit -m "feat: secao Divergencia de Saldo em /estoque/discrepancias (i9Logic + Shopee)"
```

---

## Self-Review

**Spec coverage:** módulo compartilhado de classificação (Task 1), comparação Athena×i9Logic em lote reaproveitando peças existentes (Task 2), rotas i9Logic novas com RBAC (Task 3), coleta+snapshot+lazy-trigger Shopee (Task 4), listagem+resolução+ajuste Shopee (Task 5), rotas Shopee com RBAC (Task 6), API client (Task 7), seção de UI com detecção de fonte por tipo de loja e polling (Task 8) — todos os itens da spec cobertos. Assimetria "Marcar revisado" só existir no lado Shopee está refletida no componente (botão condicional a `tipoLojaSelecionada === "virtual"`).

**Placeholder scan:** nenhum "TBD"/"implementar depois" — todo código é completo e executável.

**Type consistency:** `DivergenciaResponse`/`DivergenciaItem` (Task 7, `api.ts`) têm os mesmos campos que `listar_divergencias_athena` (Task 2) e `listar_divergencias` (Task 5) retornam (`status`, `data_coleta`, `data` com `sku`/`disponivel_athena`/`divergencia`/`classificacao`, mais os campos específicos `qtd_fisico_i9logic` vs `qtd_shopee`/`id`/`revisado`). `DivergenciaSaldo.tsx` (Task 8) usa exatamente esses nomes de campo ao consumir as respostas. As funções de ajuste do backend (`ajustar_absoluto`, chamada tanto pela rota i9Logic da Task 3 quanto por `shopee.divergencia.aplicar_ajuste_divergencia` da Task 5) usam a mesma assinatura já existente em `core/estoque.py`, sem alteração.
