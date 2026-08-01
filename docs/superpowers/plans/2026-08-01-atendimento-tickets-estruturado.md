# Atendimento — Tickets Estruturado (Fase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar `/atendimento/tickets` de um scaffold CRUD genérico (sem edição, sem detalhe, sem filtros) numa tela estruturada com CRUD completo, tela de detalhe com thread de mensagens, atribuição de atendente, mudança de status, anexos, WebSocket ao vivo (corrigindo um bug real de double-broadcast) e um sino de notificação genérico.

**Architecture:** Backend Flask + `asyncpg` (padrão `get_db()`/`run_async()` já usado no projeto), sem framework novo. Frontend Next.js App Router reescrevendo a tela do zero no padrão maduro já usado em `/vendas` (`PageHeader`/`KpiCard`/`StatusBadge`/`DataTable`/`TabBar`/`Can`/`DateFilter`). WebSocket reaproveita a infraestrutura existente (`flask-sock`, endpoint único `/ws/chat`, hook `useChatSocket`).

**Tech Stack:** Python 3 / Flask / asyncpg / flask-sock (backend), Next.js 15 / React 19 / TypeScript / Tailwind (frontend), unittest + AsyncMock (testes backend), Playwright (testes e2e).

## Global Constraints

- Reaproveitar as 4 permissões RBAC já existentes do módulo (`atendimento.ver/criar/editar/excluir`) — não criar permissões novas.
- Endpoints de mensagem/anexo usam `atendimento.criar` (mesma permissão já usada pelo endpoint de mensagem existente — preserva acesso do papel "Vendedor"/"Operador Loja", que tem `atendimento.criar` mas não `atendimento.editar`). Endpoints de status/atribuição/edição de campos usam `atendimento.editar`.
- Todo SQL usa parâmetros posicionais (`$1`, `$2`...) via `asyncpg` — nunca concatenar valor de usuário direto na string SQL.
- Migração de schema via `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` / `try/except` para `RENAME COLUMN` — nunca `DROP` de dado existente.
- Frontend: rota dinâmica `[id]` segue o padrão de export estático já usado em `/lojas/[id]` e `/produtos/[sku]` — `generateStaticParams` com placeholder + `usePathname()` no client (nunca `useParams()`, que quebra em produção com `output: "export"`).
- Sem paginação server-side nova, sem ações em lote, sem categoria/checklist, sem pipeline automático de canal, sem vínculo CRM — fora de escopo desta fase (ver spec).

---

## Mapa de arquivos

**Backend — modificados:**
- `hermes_agents/core/atendimento.py` — migração de schema, `criar_ticket` (numero), `mudar_status_ticket`, `atribuir_ticket`, `listar_tickets_filtrado`, `listar_atendentes`, `adicionar_mensagem` (bug fix + anexo), `_serializar_mensagem_ticket`.
- `hermes_agents/routes/atendimento.py` — 6 rotas novas, 1 rota existente ajustada.
- `hermes_agents/routes/chat.py` — remove broadcast duplicado em `chat_enviar_mensagem`.
- `hermes_agents/athena_bridge.py` — registra `notificacoes_bp`.

**Backend — novos:**
- `hermes_agents/core/notificacoes.py`
- `hermes_agents/routes/notificacoes.py`
- `hermes_agents/tests/test_atendimento_tickets_endpoints.py`
- `hermes_agents/tests/test_atendimento_ws.py`
- `hermes_agents/tests/test_notificacoes.py`

**Frontend — modificados:**
- `web/src/lib/api.ts` — namespaces `atendimento` e `notificacoes`.
- `web/src/lib/useChatSocket.ts` — estende union type de evento.
- `web/src/app/atendimento/tickets/page.tsx` — reescrita completa.
- `web/src/app/layout.tsx` — integra `NotificationBell`.

**Frontend — novos:**
- `web/src/lib/types/atendimento.ts`
- `web/src/app/atendimento/tickets/[id]/page.tsx`
- `web/src/app/atendimento/tickets/[id]/client.tsx`
- `web/src/app/atendimento/tickets/[id]/_components/PainelControle.tsx`
- `web/src/app/atendimento/tickets/[id]/_components/ThreadMensagens.tsx`
- `web/src/app/_components/NotificationBell.tsx`
- `web/tests/e2e/tickets.spec.ts`

---

### Task 1: Migração de schema + número sequencial do ticket

**Files:**
- Modify: `hermes_agents/core/atendimento.py:6-59` (`_ensure_tables`), `:121-143` (`criar_ticket`)
- Test: `hermes_agents/tests/test_atendimento_sla.py` (estende arquivo existente)

**Interfaces:**
- Produces: `criar_ticket(cliente, assunto, canal, prioridade)` passa a gravar `numero` (formato `#0001`) no dict retornado.

- [ ] **Step 1: Escrever teste que falha**

Adicionar ao final de `hermes_agents/tests/test_atendimento_sla.py`, antes de `if __name__ == "__main__":`:

```python
class TestNumeroTicket(unittest.TestCase):
    @patch("core.atendimento.get_db", return_value=_fake_db)
    def test_criar_ticket_preenche_numero_sequencial(self, mock_db):
        _fake_db.fetchrow.return_value = {"tempo_resposta_min": 60, "tempo_resolucao_h": 2}
        _fake_db.fetchval.return_value = 7
        with patch.object(atend, "create") as mock_create:
            mock_create.return_value = {"id": 1, "numero": "#0007", "status": "aberto"}
            atend.criar_ticket("Cliente", "Assunto", canal="chat", prioridade="urgente")
        args = mock_create.call_args[0][1]
        self.assertEqual(args["numero"], "#0007")
```

- [ ] **Step 2: Rodar teste, confirmar falha**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_sla.py::TestNumeroTicket -v`
Expected: FAIL (`KeyError: 'numero'` ou `AssertionError`, pois `criar_ticket` ainda não passa `numero`)

- [ ] **Step 3: Implementar migração de schema**

Em `hermes_agents/core/atendimento.py`, dentro de `_ensure_tables()`, logo após o bloco que cria `atend_tickets` (depois da linha 17, antes do `CREATE TABLE IF NOT EXISTS atend_mensagens`):

```python
        await db.execute("CREATE SEQUENCE IF NOT EXISTS atend_tickets_numero_seq")
        try:
            await db.execute("ALTER TABLE atend_tickets RENAME COLUMN atendente TO atendente_nome_legado")
        except Exception:
            pass
        await db.execute("ALTER TABLE atend_tickets ADD COLUMN IF NOT EXISTS atendente_id INT REFERENCES rbac_usuarios(id)")
```

- [ ] **Step 4: Implementar número sequencial em `criar_ticket`**

Substituir a função inteira (linhas 121-143):

```python
def criar_ticket(cliente: str, assunto: str, canal="whatsapp", prioridade="normal") -> dict:
    """Cria ticket com SLA aplicado — vencimento e tempo de resposta da regra da prioridade."""
    from datetime import datetime, timedelta
    async def _go():
        db = await get_db()
        sla_row = await db.fetchrow("SELECT tempo_resposta_min, tempo_resolucao_h FROM atend_sla WHERE prioridade = $1 AND ativo = TRUE", prioridade)
        agora = datetime.now()
        sla_vencimento = agora + timedelta(minutes=sla_row["tempo_resposta_min"]) if sla_row else None
        tempo_resposta = sla_row["tempo_resposta_min"] if sla_row else None
        numero_seq = await db.fetchval("SELECT nextval('atend_tickets_numero_seq')")
        return {"sla_vencimento": sla_vencimento, "tempo_resposta_min": tempo_resposta, "numero_seq": numero_seq}
    try: sla_data = run_async(_go())
    except Exception as e: sla_data = {"sla_vencimento": None, "tempo_resposta_min": None, "numero_seq": None}

    numero = f"#{sla_data['numero_seq']:04d}" if sla_data.get("numero_seq") else None
    ticket = create("tickets", {
        "cliente": cliente, "assunto": assunto, "canal": canal,
        "prioridade": prioridade, "status": "aberto", "data_abertura": hoje(),
        "sla_vencimento": sla_data["sla_vencimento"],
        "tempo_resposta_min": sla_data["tempo_resposta_min"],
        "numero": numero,
    })
    if not ticket.get("error"):
        from core.chat import criar_conversa_ticket
        criar_conversa_ticket(ticket["id"])
    return ticket
```

- [ ] **Step 5: Rodar teste, confirmar sucesso**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_sla.py -v`
Expected: PASS (todos os testes do arquivo, incluindo os 2 pré-existentes)

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/atendimento.py hermes_agents/tests/test_atendimento_sla.py
git commit -m "feat: adiciona numero sequencial e coluna atendente_id em atend_tickets"
```

---

### Task 2: Listagem de tickets com filtros

**Files:**
- Modify: `hermes_agents/core/atendimento.py` (adiciona função nova, após `dashboard()`)
- Modify: `hermes_agents/routes/atendimento.py` (adiciona rota nova, antes da rota genérica `/<tabela>`)
- Test: Create `hermes_agents/tests/test_atendimento_tickets_endpoints.py`

**Interfaces:**
- Produces: `listar_tickets_filtrado(status=None, prioridade=None, canal=None, atendente_id=None, q=None, de=None, ate=None) -> list`
- Produces: rota `GET /api/atendimento/tickets?status=&prioridade=&canal=&atendente_id=&q=&de=&ate=`

- [ ] **Step 1: Escrever teste que falha**

Create `hermes_agents/tests/test_atendimento_tickets_endpoints.py`:

```python
"""Testes de integracao — endpoints novos de tickets (filtros, atendentes, anexo)."""
import sys, os, io, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

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
from routes.atendimento import atendimento_bp
import core.rbac as rbac

_TEST_TOKEN = "test-master-token-32-bytes-long!!"


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(atendimento_bp)
    return app.test_client()


class TestListarTicketsFiltrado(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_listar_tickets_com_filtro_status(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.listar_tickets_filtrado", return_value=[{"id": 1, "status": "aberto"}]) as mock_list:
            r = self.client.get("/api/atendimento/tickets?status=aberto", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["data"], [{"id": 1, "status": "aberto"}])
        mock_list.assert_called_once_with(
            status="aberto", prioridade=None, canal=None, atendente_id=None, q=None, de=None, ate=None)

    def test_listar_tickets_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.atendimento.listar_tickets_filtrado") as mock_list:
            r = self.client.get("/api/atendimento/tickets", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_list.assert_not_called()

    def test_rota_tickets_nao_cai_no_handler_generico(self):
        """Regressao: /tickets (estatico) precisa vencer /<tabela> (dinamico)."""
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.listar_tickets_filtrado", return_value=[]) as mock_filtrado, \
             patch("core.atendimento.list") as mock_generico:
            self.client.get("/api/atendimento/tickets", headers=headers)
        mock_filtrado.assert_called_once()
        mock_generico.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar teste, confirmar falha**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_tickets_endpoints.py -v`
Expected: FAIL (`AttributeError: module 'core.atendimento' has no attribute 'listar_tickets_filtrado'`)

- [ ] **Step 3: Implementar `listar_tickets_filtrado`**

Em `hermes_agents/core/atendimento.py`, adicionar após a função `dashboard()`:

```python
def listar_tickets_filtrado(status=None, prioridade=None, canal=None, atendente_id=None, q=None, de=None, ate=None) -> list:
    where = []
    params = []
    def _add(cond, val):
        params.append(val)
        where.append(cond.format(n=len(params)))
    if status: _add("status = ${n}", status)
    if prioridade: _add("prioridade = ${n}", prioridade)
    if canal: _add("canal = ${n}", canal)
    if atendente_id: _add("atendente_id = ${n}", int(atendente_id))
    if q: _add("(cliente ILIKE ${n} OR assunto ILIKE ${n} OR numero ILIKE ${n})", f"%{q}%")
    if de: _add("data_abertura >= ${n}", de)
    if ate: _add("data_abertura <= ${n}", ate)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"SELECT * FROM atend_tickets {where_sql} ORDER BY id DESC LIMIT 200", *params)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"listar_tickets_filtrado: {e}"); return []
```

- [ ] **Step 4: Implementar rota**

Em `hermes_agents/routes/atendimento.py`, adicionar logo antes da rota genérica `@atendimento_bp.route("/<tabela>", methods=["GET"])` (linha 55):

```python
@atendimento_bp.route("/tickets", methods=["GET"])
def atend_listar_tickets():
    @requer_permissao("atendimento.ver")
    def _go():
        from core.atendimento import listar_tickets_filtrado
        return jsonify({"data": listar_tickets_filtrado(
            status=request.args.get("status") or None,
            prioridade=request.args.get("prioridade") or None,
            canal=request.args.get("canal") or None,
            atendente_id=request.args.get("atendente_id") or None,
            q=request.args.get("q") or None,
            de=request.args.get("de") or None,
            ate=request.args.get("ate") or None,
        )})
    return _go()


```

- [ ] **Step 5: Rodar teste, confirmar sucesso**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_tickets_endpoints.py -v`
Expected: PASS (3 testes)

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/atendimento.py hermes_agents/routes/atendimento.py hermes_agents/tests/test_atendimento_tickets_endpoints.py
git commit -m "feat: adiciona filtros a listagem de tickets (status/prioridade/canal/atendente/busca/periodo)"
```

---

### Task 3: Lista de atendentes (dropdown de atribuição)

**Files:**
- Modify: `hermes_agents/core/atendimento.py` (adiciona função)
- Modify: `hermes_agents/routes/atendimento.py` (adiciona rota)
- Modify: `hermes_agents/tests/test_atendimento_tickets_endpoints.py`

**Interfaces:**
- Produces: `listar_atendentes() -> list[{"id": int, "nome": str}]`
- Produces: rota `GET /api/atendimento/atendentes` (protegida por `atendimento.ver`, não `configuracoes.ver` — atendentes comuns precisam listar colegas para atribuição sem acesso a Configurações)

- [ ] **Step 1: Escrever teste que falha**

Adicionar a `hermes_agents/tests/test_atendimento_tickets_endpoints.py`, antes de `if __name__ == "__main__":`:

```python
class TestListarAtendentes(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_listar_atendentes_com_permissao_ver(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.listar_atendentes", return_value=[{"id": 5, "nome": "Joao"}]) as mock_list:
            r = self.client.get("/api/atendimento/atendentes", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["data"], [{"id": 5, "nome": "Joao"}])
        mock_list.assert_called_once()

    def test_listar_atendentes_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.atendimento.listar_atendentes") as mock_list:
            r = self.client.get("/api/atendimento/atendentes", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_list.assert_not_called()
```

- [ ] **Step 2: Rodar teste, confirmar falha**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_tickets_endpoints.py::TestListarAtendentes -v`
Expected: FAIL (`AttributeError: module 'core.atendimento' has no attribute 'listar_atendentes'`)

- [ ] **Step 3: Implementar `listar_atendentes`**

Em `hermes_agents/core/atendimento.py`, adicionar após `listar_tickets_filtrado`:

```python
def listar_atendentes() -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT id, nome FROM rbac_usuarios WHERE ativo = TRUE ORDER BY nome")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"listar_atendentes: {e}"); return []
```

- [ ] **Step 4: Implementar rota**

Em `hermes_agents/routes/atendimento.py`, adicionar logo após a rota `/tickets` (Task 2):

```python
@atendimento_bp.route("/atendentes", methods=["GET"])
def atend_listar_atendentes():
    @requer_permissao("atendimento.ver")
    def _go():
        from core.atendimento import listar_atendentes
        return jsonify({"data": listar_atendentes()})
    return _go()


```

- [ ] **Step 5: Rodar teste, confirmar sucesso**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_tickets_endpoints.py -v`
Expected: PASS (5 testes)

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/atendimento.py hermes_agents/routes/atendimento.py hermes_agents/tests/test_atendimento_tickets_endpoints.py
git commit -m "feat: adiciona endpoint de listagem de atendentes para dropdown de atribuicao"
```

---

### Task 4: Máquina de estado de status do ticket

**Files:**
- Modify: `hermes_agents/core/atendimento.py` (adiciona `TRANSICOES_STATUS`, `mudar_status_ticket`)
- Modify: `hermes_agents/routes/atendimento.py` (adiciona rota)
- Test: Create `hermes_agents/tests/test_atendimento_ws.py`

**Interfaces:**
- Consumes: `get("tickets", id)`, `update("tickets", id, dict)` (Task existentes em `core/atendimento.py`), `conversa_id_do_ticket(ticket_id)` (`core/chat.py:516`), `broadcast_para_participantes(conversa_id, evento)` (`core/chat_ws.py:33`)
- Produces: `mudar_status_ticket(ticket_id: int, novo_status: str) -> dict` — retorna `{"error": ...}` em transição inválida, senão o ticket atualizado.
- Produces: evento WS `{"evento": "ticket_status_alterado", "ticket_id": int, "status": str, "conversa_id": int}`
- Produces: rota `PUT /api/atendimento/tickets/<int:id>/status` `{status}` (permissão `atendimento.editar`)

- [ ] **Step 1: Escrever teste que falha**

Create `hermes_agents/tests/test_atendimento_ws.py`:

```python
"""Testes — eventos WebSocket de tickets: broadcast unico de mensagem
(regressao do bug de double-broadcast), mudanca de status, atribuicao."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m
patcher = patch("asyncpg.create_pool", side_effect=_mock_pool)
patcher.start()

import core.atendimento as atend


class TestMudarStatusTicket(unittest.TestCase):
    def test_transicao_valida_aberto_para_pendente_dispara_evento(self):
        with patch.object(atend, "get", return_value={"id": 1, "status": "aberto"}), \
             patch.object(atend, "update", return_value={"id": 1, "status": "pendente"}), \
             patch("core.chat.conversa_id_do_ticket", return_value=42), \
             patch("core.chat_ws.broadcast_para_participantes") as mock_broadcast:
            r = atend.mudar_status_ticket(1, "pendente")
        self.assertEqual(r["status"], "pendente")
        mock_broadcast.assert_called_once_with(42, {
            "evento": "ticket_status_alterado", "ticket_id": 1, "status": "pendente", "conversa_id": 42,
        })

    def test_transicao_invalida_fechado_para_pendente_rejeitada(self):
        with patch.object(atend, "get", return_value={"id": 1, "status": "fechado"}), \
             patch.object(atend, "update") as mock_update:
            r = atend.mudar_status_ticket(1, "pendente")
        self.assertIn("error", r)
        mock_update.assert_not_called()

    def test_reabrir_de_fechado_e_valido(self):
        with patch.object(atend, "get", return_value={"id": 1, "status": "fechado"}), \
             patch.object(atend, "update", return_value={"id": 1, "status": "aberto"}), \
             patch("core.chat.conversa_id_do_ticket", return_value=None):
            r = atend.mudar_status_ticket(1, "aberto")
        self.assertEqual(r["status"], "aberto")


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar teste, confirmar falha**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_ws.py -v`
Expected: FAIL (`AttributeError: module 'core.atendimento' has no attribute 'mudar_status_ticket'`)

- [ ] **Step 3: Implementar máquina de estado**

Em `hermes_agents/core/atendimento.py`, adicionar após `reabrir_ticket` (linha 173):

```python
TRANSICOES_STATUS = {
    "aberto": {"pendente", "fechado"},
    "pendente": {"aberto", "fechado"},
    "fechado": {"aberto"},
}

def mudar_status_ticket(ticket_id: int, novo_status: str) -> dict:
    ticket = get("tickets", ticket_id)
    if ticket.get("error"):
        return ticket
    atual = ticket.get("status", "aberto")
    if novo_status not in TRANSICOES_STATUS.get(atual, set()):
        return {"error": f"Transicao invalida: {atual} -> {novo_status}"}
    campos = {"status": novo_status}
    if novo_status == "fechado":
        campos["data_fechamento"] = hoje()
    elif atual == "fechado":
        campos["data_fechamento"] = None
    resultado = update("tickets", ticket_id, campos)
    if not resultado.get("error"):
        from core.chat import conversa_id_do_ticket
        from core.chat_ws import broadcast_para_participantes
        conversa_id = conversa_id_do_ticket(ticket_id)
        if conversa_id:
            broadcast_para_participantes(conversa_id, {
                "evento": "ticket_status_alterado", "ticket_id": ticket_id,
                "status": novo_status, "conversa_id": conversa_id,
            })
    return resultado
```

- [ ] **Step 4: Implementar rota**

Em `hermes_agents/routes/atendimento.py`, adicionar após a rota `/tickets/<int:id>/reabrir` (linha 52):

```python
@atendimento_bp.route("/tickets/<int:id>/status", methods=["PUT"])
def atend_mudar_status(id):
    data = request.json or {}

    @requer_permissao("atendimento.editar")
    def _go():
        from core.atendimento import mudar_status_ticket
        resultado = mudar_status_ticket(id, data.get("status", ""))
        return jsonify(resultado), (400 if resultado.get("error") else 200)
    return _go()


```

- [ ] **Step 5: Rodar teste, confirmar sucesso**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_ws.py -v`
Expected: PASS (3 testes)

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/atendimento.py hermes_agents/routes/atendimento.py hermes_agents/tests/test_atendimento_ws.py
git commit -m "feat: adiciona maquina de estado de status do ticket com evento WS dedicado"
```

---

### Task 5: Sino de notificação genérico (core + rotas)

**Files:**
- Create: `hermes_agents/core/notificacoes.py`
- Create: `hermes_agents/routes/notificacoes.py`
- Modify: `hermes_agents/athena_bridge.py:211,245` (import + registro do blueprint)
- Test: Create `hermes_agents/tests/test_notificacoes.py`

**Interfaces:**
- Produces: `criar_notificacao(usuario_id, tipo, titulo, mensagem, link=None) -> dict`
- Produces: `listar_notificacoes(usuario_id, limit=30) -> list` (não lidas primeiro)
- Produces: `marcar_lida(notificacao_id, usuario_id) -> dict`
- Produces: `marcar_todas_lidas(usuario_id) -> dict`
- Produces: rotas `GET /api/notificacoes`, `POST /api/notificacoes/<id>/lida`, `POST /api/notificacoes/marcar-todas-lidas`

- [ ] **Step 1: Escrever teste que falha**

Create `hermes_agents/tests/test_notificacoes.py`:

```python
"""Testes — core de notificacoes (sino generico)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m
patcher = patch("asyncpg.create_pool", side_effect=_mock_pool)
patcher.start()

import core.notificacoes as notif


class TestNotificacoesCore(unittest.TestCase):
    @patch("core.notificacoes.get_db")
    def test_criar_notificacao_grava_e_retorna_linha(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetchrow = AsyncMock(return_value={"id": 1, "usuario_id": 5, "tipo": "ticket_atribuido",
                                                     "titulo": "Ticket #0001", "mensagem": "", "link": "/x",
                                                     "lida": False, "created_at": "2026-08-01T10:00:00"})
        mock_get_db.return_value = fake_db
        r = notif.criar_notificacao(5, "ticket_atribuido", "Ticket #0001", "", "/x")
        self.assertEqual(r["usuario_id"], 5)
        self.assertFalse(r["lida"])

    @patch("core.notificacoes.get_db")
    def test_marcar_lida_idempotente(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetchrow = AsyncMock(return_value={"id": 1, "usuario_id": 5, "lida": True})
        mock_get_db.return_value = fake_db
        r1 = notif.marcar_lida(1, 5)
        r2 = notif.marcar_lida(1, 5)
        self.assertTrue(r1["lida"])
        self.assertTrue(r2["lida"])

    @patch("core.notificacoes.get_db")
    def test_marcar_lida_de_outro_usuario_nao_encontra(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetchrow = AsyncMock(return_value=None)
        mock_get_db.return_value = fake_db
        r = notif.marcar_lida(1, 999)
        self.assertIn("error", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar teste, confirmar falha**

Run: `cd hermes_agents && python -m pytest tests/test_notificacoes.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'core.notificacoes'`)

- [ ] **Step 3: Implementar `core/notificacoes.py`**

Create `hermes_agents/core/notificacoes.py`:

```python
"""Notificacoes Core — sino generico, disparado por outros modulos via criar_notificacao."""
from core import get_db, run_async, log

AGENT = "Notificacoes Core"


def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS notificacoes (
            id SERIAL PRIMARY KEY, usuario_id INT REFERENCES rbac_usuarios(id) NOT NULL,
            tipo VARCHAR(50) NOT NULL, titulo VARCHAR(150) NOT NULL, mensagem TEXT,
            link VARCHAR(300), lida BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW()
        )""")
    try: run_async(_go())
    except Exception as e: log(AGENT, f"Erro tabela notificacoes: {e}")

_ensure_tables()


def criar_notificacao(usuario_id: int, tipo: str, titulo: str, mensagem: str, link: str = None) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "INSERT INTO notificacoes (usuario_id, tipo, titulo, mensagem, link) VALUES ($1,$2,$3,$4,$5) RETURNING *",
            usuario_id, tipo, titulo, mensagem, link)
        return dict(row)
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def listar_notificacoes(usuario_id: int, limit: int = 30) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch(
            "SELECT * FROM notificacoes WHERE usuario_id=$1 ORDER BY lida ASC, created_at DESC LIMIT $2",
            usuario_id, limit)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"listar_notificacoes: {e}"); return []


def marcar_lida(notificacao_id: int, usuario_id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "UPDATE notificacoes SET lida=TRUE WHERE id=$1 AND usuario_id=$2 RETURNING *",
            notificacao_id, usuario_id)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def marcar_todas_lidas(usuario_id: int) -> dict:
    async def _go():
        db = await get_db()
        await db.execute("UPDATE notificacoes SET lida=TRUE WHERE usuario_id=$1 AND lida=FALSE", usuario_id)
        return {"success": True}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}
```

- [ ] **Step 4: Rodar teste, confirmar sucesso**

Run: `cd hermes_agents && python -m pytest tests/test_notificacoes.py -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Implementar rotas**

Create `hermes_agents/routes/notificacoes.py`:

```python
from flask import Blueprint, jsonify
from core.rbac import usuario_atual_da_request

notificacoes_bp = Blueprint("notificacoes", __name__, url_prefix="/api/notificacoes")


@notificacoes_bp.route("", methods=["GET"])
def notif_listar():
    usuario = usuario_atual_da_request()
    if not usuario.get("user_id"):
        return jsonify({"error": "Nao autenticado"}), 401
    from core.notificacoes import listar_notificacoes
    return jsonify({"data": listar_notificacoes(int(usuario["user_id"]))})


@notificacoes_bp.route("/<int:id>/lida", methods=["POST"])
def notif_marcar_lida(id):
    usuario = usuario_atual_da_request()
    if not usuario.get("user_id"):
        return jsonify({"error": "Nao autenticado"}), 401
    from core.notificacoes import marcar_lida
    return jsonify(marcar_lida(id, int(usuario["user_id"])))


@notificacoes_bp.route("/marcar-todas-lidas", methods=["POST"])
def notif_marcar_todas_lidas():
    usuario = usuario_atual_da_request()
    if not usuario.get("user_id"):
        return jsonify({"error": "Nao autenticado"}), 401
    from core.notificacoes import marcar_todas_lidas
    return jsonify(marcar_todas_lidas(int(usuario["user_id"])))
```

- [ ] **Step 6: Registrar blueprint**

Em `hermes_agents/athena_bridge.py`, adicionar import perto da linha 211 (junto dos outros `from routes...import ..._bp`):

```python
from routes.notificacoes import notificacoes_bp
```

E registrar perto da linha 245 (junto de `app.register_blueprint(atendimento_bp)`):

```python
app.register_blueprint(notificacoes_bp)
```

- [ ] **Step 7: Rodar toda a suíte de atendimento/notificações, confirmar nada quebrou**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_sla.py tests/test_atendimento_seguranca.py tests/test_atendimento_tickets_endpoints.py tests/test_atendimento_ws.py tests/test_notificacoes.py -v`
Expected: PASS (todos)

- [ ] **Step 8: Commit**

```bash
git add hermes_agents/core/notificacoes.py hermes_agents/routes/notificacoes.py hermes_agents/athena_bridge.py hermes_agents/tests/test_notificacoes.py
git commit -m "feat: adiciona sino de notificacao generico (core + rotas + registro do blueprint)"
```

---

### Task 6: Atribuição de atendente (dispara evento WS + notificação)

**Files:**
- Modify: `hermes_agents/core/atendimento.py` (adiciona `atribuir_ticket`)
- Modify: `hermes_agents/routes/atendimento.py` (adiciona rota)
- Modify: `hermes_agents/tests/test_atendimento_ws.py`

**Interfaces:**
- Consumes: `criar_notificacao` (Task 5), `enviar_para_usuario` (`core/chat_ws.py:22`), `broadcast_para_participantes` (`core/chat_ws.py:33`), `conversa_id_do_ticket` (`core/chat.py:516`)
- Produces: `atribuir_ticket(ticket_id: int, atendente_id: int) -> dict`
- Produces: evento WS `{"evento": "ticket_atendente_alterado", "ticket_id": int, "atendente_id": int, "atendente_nome": str, "conversa_id": int}`
- Produces: rota `PUT /api/atendimento/tickets/<int:id>/atribuir` `{atendente_id}` (permissão `atendimento.editar`)

- [ ] **Step 1: Escrever teste que falha**

Adicionar a `hermes_agents/tests/test_atendimento_ws.py`, antes de `if __name__ == "__main__":`:

```python
class TestAtribuirTicket(unittest.TestCase):
    @patch("core.atendimento.get_db")
    def test_atribui_dispara_evento_e_notificacao(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetchrow = AsyncMock(return_value={"id": 5, "nome": "Joao"})
        mock_get_db.return_value = fake_db
        with patch.object(atend, "update", return_value={"id": 1, "numero": "#0001", "assunto": "Duvida"}), \
             patch("core.chat.conversa_id_do_ticket", return_value=42), \
             patch("core.chat_ws.broadcast_para_participantes") as mock_broadcast, \
             patch("core.chat_ws.enviar_para_usuario") as mock_enviar, \
             patch("core.notificacoes.criar_notificacao", return_value={"id": 99, "usuario_id": 5}) as mock_notif:
            r = atend.atribuir_ticket(1, 5)
        self.assertEqual(r["id"], 1)
        mock_broadcast.assert_called_once_with(42, {
            "evento": "ticket_atendente_alterado", "ticket_id": 1,
            "atendente_id": 5, "atendente_nome": "Joao", "conversa_id": 42,
        })
        mock_notif.assert_called_once_with(
            5, "ticket_atribuido", "Ticket #0001 atribuido a voce", "Duvida", "/atendimento/tickets/1")
        mock_enviar.assert_called_once()

    @patch("core.atendimento.get_db")
    def test_atendente_inexistente_retorna_erro(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetchrow = AsyncMock(return_value=None)
        mock_get_db.return_value = fake_db
        with patch.object(atend, "update") as mock_update:
            r = atend.atribuir_ticket(1, 999)
        self.assertIn("error", r)
        mock_update.assert_not_called()
```

- [ ] **Step 2: Rodar teste, confirmar falha**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_ws.py::TestAtribuirTicket -v`
Expected: FAIL (`AttributeError: module 'core.atendimento' has no attribute 'atribuir_ticket'`)

- [ ] **Step 3: Implementar `atribuir_ticket`**

Em `hermes_agents/core/atendimento.py`, adicionar após `mudar_status_ticket`:

```python
def atribuir_ticket(ticket_id: int, atendente_id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT id, nome FROM rbac_usuarios WHERE id=$1 AND ativo=TRUE", atendente_id)
        return dict(row) if row else None
    try:
        atendente = run_async(_go())
    except Exception as e:
        return {"error": str(e)}
    if not atendente:
        return {"error": "Atendente nao encontrado ou inativo"}

    resultado = update("tickets", ticket_id, {"atendente_id": atendente_id})
    if resultado.get("error"):
        return resultado

    from core.chat import conversa_id_do_ticket
    from core.chat_ws import broadcast_para_participantes, enviar_para_usuario
    from core.notificacoes import criar_notificacao

    conversa_id = conversa_id_do_ticket(ticket_id)
    if conversa_id:
        broadcast_para_participantes(conversa_id, {
            "evento": "ticket_atendente_alterado", "ticket_id": ticket_id,
            "atendente_id": atendente_id, "atendente_nome": atendente["nome"], "conversa_id": conversa_id,
        })

    numero = resultado.get("numero") or f"#{ticket_id}"
    notificacao = criar_notificacao(
        atendente_id, "ticket_atribuido",
        f"Ticket {numero} atribuido a voce",
        resultado.get("assunto") or "",
        f"/atendimento/tickets/{ticket_id}",
    )
    if not notificacao.get("error"):
        payload = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in notificacao.items()}
        enviar_para_usuario(atendente_id, {"evento": "notificacao", **payload})
    return resultado
```

- [ ] **Step 4: Implementar rota**

Em `hermes_agents/routes/atendimento.py`, adicionar após a rota `/tickets/<int:id>/status` (Task 4):

```python
@atendimento_bp.route("/tickets/<int:id>/atribuir", methods=["PUT"])
def atend_atribuir(id):
    data = request.json or {}

    @requer_permissao("atendimento.editar")
    def _go():
        atendente_id = data.get("atendente_id")
        if not atendente_id:
            return jsonify({"error": "atendente_id obrigatorio"}), 400
        from core.atendimento import atribuir_ticket
        resultado = atribuir_ticket(id, int(atendente_id))
        return jsonify(resultado), (400 if resultado.get("error") else 200)
    return _go()


```

- [ ] **Step 5: Rodar teste, confirmar sucesso**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_ws.py -v`
Expected: PASS (5 testes)

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/atendimento.py hermes_agents/routes/atendimento.py hermes_agents/tests/test_atendimento_ws.py
git commit -m "feat: adiciona atribuicao de atendente com evento WS e notificacao"
```

---

### Task 7: Corrige bug de double-broadcast + endpoint REST de mensagens

**Files:**
- Modify: `hermes_agents/core/atendimento.py:145-167` (`adicionar_mensagem`, `listar_mensagens_ticket`)
- Modify: `hermes_agents/routes/atendimento.py:25-34` (rota de mensagem existente), adiciona rota nova
- Modify: `hermes_agents/routes/chat.py:97-108` (`chat_enviar_mensagem`) — remove broadcast duplicado
- Modify: `hermes_agents/tests/test_atendimento_ws.py`

**Interfaces:**
- Produces: `_serializar_mensagem_ticket(m: dict, conversa_id: int) -> dict` — shape `{id, conversa_id, thread_pai_id, remetente_id, remetente_nome, texto, anexo_id, anexo_url, created_at, editado_em, excluido_em}`, reaproveitado tanto no broadcast quanto no endpoint REST.
- Produces: rota `GET /api/atendimento/tickets/<int:id>/mensagens` (permissão `atendimento.ver`)

- [ ] **Step 1: Escrever teste que falha**

Adicionar a `hermes_agents/tests/test_atendimento_ws.py`, antes de `if __name__ == "__main__":`:

```python
class TestAdicionarMensagemBroadcastUnico(unittest.TestCase):
    """Regressao: antes deste fix, adicionar_mensagem (core/atendimento.py) e
    chat_enviar_mensagem (routes/chat.py) juntos disparavam 2 frames
    nova_mensagem com shapes diferentes para a mesma mensagem de ticket."""

    def test_adicionar_mensagem_emite_exatamente_um_broadcast_normalizado(self):
        with patch.object(atend, "create", return_value={
                "id": 10, "ticket_id": 1, "conteudo": "oi", "remetente": "Ana",
                "tipo": "texto", "anexo_url": None, "enviado_em": "2026-08-01T10:00:00"}), \
             patch("core.chat.conversa_id_do_ticket", return_value=42), \
             patch("core.chat_ws.broadcast_para_participantes") as mock_broadcast:
            atend.adicionar_mensagem(1, "Ana", "oi")
        mock_broadcast.assert_called_once()
        _, evento = mock_broadcast.call_args[0]
        self.assertEqual(evento["evento"], "nova_mensagem")
        self.assertEqual(evento["mensagem"]["conversa_id"], 42)
        self.assertEqual(evento["mensagem"]["texto"], "oi")
        self.assertEqual(evento["mensagem"]["remetente_nome"], "Ana")
        self.assertIsNone(evento["mensagem"]["remetente_id"])
```

- [ ] **Step 2: Rodar teste, confirmar falha**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_ws.py::TestAdicionarMensagemBroadcastUnico -v`
Expected: FAIL (`KeyError: 'remetente_nome'` — shape atual não tem esse campo)

- [ ] **Step 3: Implementar `_serializar_mensagem_ticket` e corrigir `adicionar_mensagem`**

Em `hermes_agents/core/atendimento.py`, substituir `adicionar_mensagem` e `listar_mensagens_ticket` (linhas 145-167) por:

```python
def _serializar_mensagem_ticket(m: dict, conversa_id: int) -> dict:
    enviado_em = m.get("enviado_em")
    return {
        "id": m["id"], "conversa_id": conversa_id, "thread_pai_id": None,
        "remetente_id": None, "remetente_nome": m.get("remetente"),
        "texto": m.get("conteudo"), "anexo_id": None, "anexo_url": m.get("anexo_url"),
        "created_at": enviado_em.isoformat() if hasattr(enviado_em, "isoformat") else enviado_em,
        "editado_em": None, "excluido_em": None,
    }

def adicionar_mensagem(ticket_id: int, remetente: str, conteudo: str, tipo="texto", anexo_url: str = None) -> dict:
    campos = {"ticket_id": ticket_id, "remetente": remetente, "conteudo": conteudo, "tipo": tipo, "enviado_em": hoje()}
    if anexo_url:
        campos["anexo_url"] = anexo_url
    mensagem = create("mensagens", campos)
    if not mensagem.get("error"):
        from core.chat import conversa_id_do_ticket
        from core.chat_ws import broadcast_para_participantes
        conversa_id = conversa_id_do_ticket(ticket_id)
        if conversa_id:
            broadcast_para_participantes(conversa_id, {
                "evento": "nova_mensagem",
                "mensagem": _serializar_mensagem_ticket(mensagem, conversa_id),
            })
    return mensagem

def listar_mensagens_ticket(ticket_id: int) -> list:
    """Mensagens de UM ticket, em ordem cronologica — usado pela ponte do chat
    interno (conversa tipo 'ticket' le/escreve em atend_mensagens, nao em
    chat_mensagens)."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM atend_mensagens WHERE ticket_id=$1 ORDER BY enviado_em ASC", ticket_id)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"listar_mensagens_ticket: {e}"); return []
```

- [ ] **Step 4: Remover broadcast duplicado em `routes/chat.py`**

Em `hermes_agents/routes/chat.py`, dentro de `chat_enviar_mensagem` (linhas 97-108), substituir:

```python
    if conversa and conversa.get("tipo") == "ticket":
        from core.atendimento import adicionar_mensagem
        texto_processado = processar_mencoes(conversa_id, data.get("texto", ""))
        criada = adicionar_mensagem(conversa["ticket_ref_id"],
                                    usuario.get("nome") or usuario.get("email"),
                                    texto_processado, "texto")
        if criada.get("error"):
            return jsonify(criada)
        mensagem = _adaptar_mensagem_ticket(criada, conversa_id)
        broadcast_para_participantes(conversa_id, {"evento": "nova_mensagem", "mensagem": _serializar(mensagem)})
        return jsonify(mensagem)
```

por:

```python
    if conversa and conversa.get("tipo") == "ticket":
        from core.atendimento import adicionar_mensagem
        texto_processado = processar_mencoes(conversa_id, data.get("texto", ""))
        criada = adicionar_mensagem(conversa["ticket_ref_id"],
                                    usuario.get("nome") or usuario.get("email"),
                                    texto_processado, "texto")
        if criada.get("error"):
            return jsonify(criada)
        # broadcast ja disparado dentro de adicionar_mensagem — nao duplicar aqui
        return jsonify(_adaptar_mensagem_ticket(criada, conversa_id))
```

- [ ] **Step 5: Ajustar rota de mensagem existente para usar remetente autenticado**

Em `hermes_agents/routes/atendimento.py`, substituir a rota `/tickets/<int:id>/mensagem` (linhas 25-34):

```python
@atendimento_bp.route("/tickets/<int:id>/mensagem", methods=["POST"])
def atend_mensagem(id):
    data = request.json or {}

    @requer_permissao("atendimento.criar")
    def _go():
        from core.atendimento import adicionar_mensagem
        from core.rbac import usuario_atual_da_request
        usuario = usuario_atual_da_request()
        remetente = usuario.get("nome") or usuario.get("email") or data.get("remetente", "")
        return jsonify(adicionar_mensagem(id, remetente, data.get("conteudo", ""), data.get("tipo", "texto")))
    return _go()
```

(Mantém `atendimento.criar` — mesma permissão de antes, evita regressão de acesso para papéis como "Vendedor" que têm `atendimento.criar` mas não `atendimento.editar`. Só troca a fonte do remetente: antes vinha do body, spoofável; agora vem do token autenticado.)

- [ ] **Step 6: Implementar rota REST de listagem de mensagens**

Em `hermes_agents/routes/atendimento.py`, adicionar após a rota `/tickets/<int:id>/atribuir` (Task 6):

```python
@atendimento_bp.route("/tickets/<int:id>/mensagens", methods=["GET"])
def atend_listar_mensagens(id):
    @requer_permissao("atendimento.ver")
    def _go():
        from core.atendimento import listar_mensagens_ticket, _serializar_mensagem_ticket
        from core.chat import conversa_id_do_ticket
        conversa_id = conversa_id_do_ticket(id)
        mensagens = listar_mensagens_ticket(id)
        return jsonify({"data": [_serializar_mensagem_ticket(m, conversa_id) for m in mensagens]})
    return _go()


```

- [ ] **Step 7: Rodar toda a suíte, confirmar sucesso**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_ws.py tests/test_atendimento_seguranca.py tests/test_chat.py -v`
Expected: PASS (todos — inclusive `test_chat.py`, que mocka `adicionar_mensagem` inteiro e não deve ser afetado pela mudança de shape interno)

- [ ] **Step 8: Commit**

```bash
git add hermes_agents/core/atendimento.py hermes_agents/routes/atendimento.py hermes_agents/routes/chat.py hermes_agents/tests/test_atendimento_ws.py
git commit -m "fix: elimina double-broadcast de mensagem de ticket e normaliza shape do evento WS"
```

---

### Task 8: Upload de anexo em mensagem de ticket

**Files:**
- Modify: `hermes_agents/routes/atendimento.py` (adiciona 2 rotas: upload + download)
- Modify: `hermes_agents/tests/test_atendimento_tickets_endpoints.py`

**Interfaces:**
- Consumes: `adicionar_mensagem(ticket_id, remetente, conteudo, tipo, anexo_url)` (Task 7, já aceita `anexo_url`)
- Produces: rota `POST /api/atendimento/tickets/<int:id>/anexo` (multipart, campo `arquivo`; permissão `atendimento.criar`, mesma da rota de mensagem)
- Produces: rota `GET /api/atendimento/tickets/<int:id>/anexo/<path:nome_arquivo>` (permissão `atendimento.ver`)

- [ ] **Step 1: Escrever teste que falha**

Adicionar a `hermes_agents/tests/test_atendimento_tickets_endpoints.py`, antes de `if __name__ == "__main__":`:

```python
class TestUploadAnexoTicket(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_upload_anexo_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]):
            r = self.client.post(
                "/api/atendimento/tickets/1/anexo", headers=headers,
                data={"arquivo": (io.BytesIO(b"conteudo"), "teste.pdf")},
                content_type="multipart/form-data")
        self.assertEqual(r.status_code, 403)

    def test_upload_anexo_com_permissao_grava_mensagem(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.adicionar_mensagem", return_value={"id": 9, "tipo": "anexo"}) as mock_add:
            r = self.client.post(
                "/api/atendimento/tickets/1/anexo", headers=headers,
                data={"arquivo": (io.BytesIO(b"conteudo"), "teste.pdf")},
                content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        mock_add.assert_called_once()
        self.assertEqual(mock_add.call_args[0][0], 1)  # ticket_id
        self.assertEqual(mock_add.call_args[0][3], "anexo")  # tipo

    def test_upload_sem_arquivo_retorna_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.post("/api/atendimento/tickets/1/anexo", headers=headers,
                             data={}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)
```

- [ ] **Step 2: Rodar teste, confirmar falha**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_tickets_endpoints.py::TestUploadAnexoTicket -v`
Expected: FAIL (404 — rota ainda não existe)

- [ ] **Step 3: Implementar rotas de upload/download**

Em `hermes_agents/routes/atendimento.py`, adicionar após a rota `/tickets/<int:id>/mensagens` (Task 7):

```python
@atendimento_bp.route("/tickets/<int:id>/anexo", methods=["POST"])
def atend_upload_anexo(id):
    @requer_permissao("atendimento.criar")
    def _go():
        import os, time
        from werkzeug.utils import secure_filename
        from core.rbac import usuario_atual_da_request
        from core.atendimento import adicionar_mensagem

        arquivo = request.files.get("arquivo")
        if not arquivo:
            return jsonify({"error": "arquivo obrigatorio"}), 400
        TAMANHO_MAXIMO_BYTES = 25 * 1024 * 1024
        conteudo = arquivo.read()
        if len(conteudo) > TAMANHO_MAXIMO_BYTES:
            return jsonify({"error": "Arquivo maior que 25MB"}), 413

        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "atendimento")
        os.makedirs(upload_dir, exist_ok=True)
        nome_base = secure_filename(arquivo.filename) or "upload.bin"
        nome_seguro = f"{id}_{int(time.time() * 1000)}_{nome_base}"
        caminho_completo = os.path.realpath(os.path.join(upload_dir, nome_seguro))
        if not caminho_completo.startswith(os.path.realpath(upload_dir) + os.sep):
            return jsonify({"error": "nome de arquivo invalido"}), 400
        with open(caminho_completo, "wb") as f:
            f.write(conteudo)

        usuario = usuario_atual_da_request()
        remetente = usuario.get("nome") or usuario.get("email") or ""
        mensagem = adicionar_mensagem(id, remetente, arquivo.filename, "anexo", anexo_url=nome_seguro)
        return jsonify(mensagem)
    return _go()


@atendimento_bp.route("/tickets/<int:id>/anexo/<path:nome_arquivo>", methods=["GET"])
def atend_download_anexo(id, nome_arquivo):
    @requer_permissao("atendimento.ver")
    def _go():
        import os
        from flask import send_file
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "atendimento")
        caminho_completo = os.path.realpath(os.path.join(upload_dir, nome_arquivo))
        if not caminho_completo.startswith(os.path.realpath(upload_dir) + os.sep) or not os.path.isfile(caminho_completo):
            return jsonify({"error": "anexo invalido"}), 404
        return send_file(caminho_completo, as_attachment=True)
    return _go()


```

- [ ] **Step 4: Rodar teste, confirmar sucesso**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_tickets_endpoints.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Rodar toda a suíte de atendimento uma última vez**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_sla.py tests/test_atendimento_seguranca.py tests/test_atendimento_tickets_endpoints.py tests/test_atendimento_ws.py tests/test_notificacoes.py tests/test_chat.py -v`
Expected: PASS (todos)

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/atendimento.py hermes_agents/tests/test_atendimento_tickets_endpoints.py
git commit -m "feat: adiciona upload e download de anexo em mensagem de ticket"
```

---

### Task 9: Tipos TS e namespace `api.atendimento` / `api.notificacoes`

**Files:**
- Create: `web/src/lib/types/atendimento.ts`
- Modify: `web/src/lib/api.ts` (adiciona 2 namespaces)

**Interfaces:**
- Produces: `Ticket`, `MensagemTicket`, `Atendente`, `Notificacao` (tipos TS)
- Produces: `api.atendimento.{listar, criar, obter, atualizar, mudarStatus, atribuir, listarMensagens, enviarMensagem, listarAtendentes, uploadAnexo}`
- Produces: `api.notificacoes.{listar, marcarLida, marcarTodasLidas}`

- [ ] **Step 1: Criar tipos**

Create `web/src/lib/types/atendimento.ts`:

```typescript
export interface Ticket {
  id: number;
  numero: string | null;
  cliente: string;
  email?: string;
  telefone?: string;
  assunto: string;
  canal: string;
  prioridade: "baixa" | "normal" | "alta" | "urgente";
  status: "aberto" | "pendente" | "fechado";
  atendente_id: number | null;
  sla_vencimento: string | null;
  data_abertura: string;
  data_fechamento: string | null;
  tempo_resposta_min: number | null;
  observacoes?: string;
  error?: string;
}

export interface MensagemTicket {
  id: number;
  conversa_id: number;
  thread_pai_id: number | null;
  remetente_id: number | null;
  remetente_nome?: string;
  texto: string;
  anexo_id: number | null;
  anexo_url: string | null;
  created_at: string;
  editado_em: string | null;
  excluido_em: string | null;
  error?: string;
}

export interface Atendente {
  id: number;
  nome: string;
}

export interface Notificacao {
  id: number;
  usuario_id: number;
  tipo: string;
  titulo: string;
  mensagem: string;
  link: string | null;
  lida: boolean;
  created_at: string;
}
```

- [ ] **Step 2: Adicionar namespaces em `api.ts`**

Em `web/src/lib/api.ts`, adicionar o import no topo (junto dos outros tipos importados perto da linha 54):

```typescript
import type { Ticket, MensagemTicket, Atendente, Notificacao } from "@/lib/types/atendimento";
```

E adicionar os namespaces logo antes do fechamento do objeto `api` (após o bloco `chat: {...}`, antes de `// Hermes Chat (legado)` na linha 632):

```typescript
  // Atendimento — Tickets
  atendimento: {
    listar: (filtros: Record<string, string>) => {
      const qs = new URLSearchParams(filtros).toString();
      return request<{ data: Ticket[] }>(`/api/atendimento/tickets${qs ? `?${qs}` : ""}`);
    },
    criar: (dados: { cliente: string; email?: string; telefone?: string; assunto: string; canal: string; prioridade: string }) =>
      request<Ticket>("/api/atendimento/tickets/criar", { method: "POST", body: JSON.stringify(dados) }),
    obter: (id: number) => request<Ticket>(`/api/atendimento/tickets/${id}`),
    atualizar: (id: number, dados: Record<string, unknown>) =>
      request<{ success?: boolean; error?: string }>(`/api/atendimento/tickets/${id}`, { method: "PUT", body: JSON.stringify(dados) }),
    mudarStatus: (id: number, status: string) =>
      request<Ticket>(`/api/atendimento/tickets/${id}/status`, { method: "PUT", body: JSON.stringify({ status }) }),
    atribuir: (id: number, atendenteId: number) =>
      request<Ticket>(`/api/atendimento/tickets/${id}/atribuir`, { method: "PUT", body: JSON.stringify({ atendente_id: atendenteId }) }),
    listarMensagens: (id: number) => request<{ data: MensagemTicket[] }>(`/api/atendimento/tickets/${id}/mensagens`),
    enviarMensagem: (id: number, conteudo: string) =>
      request<MensagemTicket>(`/api/atendimento/tickets/${id}/mensagem`, { method: "POST", body: JSON.stringify({ conteudo, tipo: "texto" }) }),
    listarAtendentes: () => request<{ data: Atendente[] }>("/api/atendimento/atendentes"),
    uploadAnexo: async (ticketId: number, arquivo: File): Promise<MensagemTicket> => {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const formData = new FormData();
      formData.append("arquivo", arquivo);
      const res = await fetch(`/api/atendimento/tickets/${ticketId}/anexo`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      return res.json();
    },
  },

  // Notificacoes
  notificacoes: {
    listar: () => request<{ data: Notificacao[] }>("/api/notificacoes"),
    marcarLida: (id: number) => request<Notificacao>(`/api/notificacoes/${id}/lida`, { method: "POST" }),
    marcarTodasLidas: () => request<{ success: boolean }>("/api/notificacoes/marcar-todas-lidas", { method: "POST" }),
  },

```

- [ ] **Step 3: Verificar tipos**

Run: `cd web && npx tsc --noEmit -p tsconfig.json`
Expected: sem erros novos relacionados a `atendimento.ts`/`api.ts` (erros pré-existentes no restante do projeto, se houver, não são desta tarefa)

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/types/atendimento.ts web/src/lib/api.ts
git commit -m "feat: adiciona tipos e namespace de API para tickets estruturados e notificacoes"
```

---

### Task 10: Estende `useChatSocket` com os novos tipos de evento

**Files:**
- Modify: `web/src/lib/useChatSocket.ts:5`

**Interfaces:**
- Produces: `EventoChatSocket["evento"]` inclui `"ticket_status_alterado" | "ticket_atendente_alterado" | "notificacao"`

- [ ] **Step 1: Editar union type**

Em `web/src/lib/useChatSocket.ts`, linha 5, substituir:

```typescript
  evento: "nova_mensagem" | "mensagem_editada" | "mensagem_excluida" | "usuario_digitando" | "presenca_atualizada" | "confirmacao_leitura";
```

por:

```typescript
  evento: "nova_mensagem" | "mensagem_editada" | "mensagem_excluida" | "usuario_digitando" | "presenca_atualizada" | "confirmacao_leitura" | "ticket_status_alterado" | "ticket_atendente_alterado" | "notificacao";
```

- [ ] **Step 2: Verificar tipos**

Run: `cd web && npx tsc --noEmit -p tsconfig.json`
Expected: sem erros novos

- [ ] **Step 3: Commit**

```bash
git add web/src/lib/useChatSocket.ts
git commit -m "feat: estende union type de eventos WS com status/atribuicao de ticket e notificacao"
```

---

### Task 11: Reescreve a listagem `/atendimento/tickets`

**Files:**
- Modify: `web/src/app/atendimento/tickets/page.tsx` (reescrita completa)

**Interfaces:**
- Consumes: `api.atendimento.{listar, criar, listarAtendentes}` (Task 9)
- Consumes: `PageHeader`, `KpiCard`, `StatusBadge`, `DataTable`, `TabBar`, `DateFilter`, `ErrorAlert`, `LoadingState`, `Icon`, `Can` (componentes existentes)

- [ ] **Step 1: Reescrever a página**

Replace `web/src/app/atendimento/tickets/page.tsx` inteiro por:

```tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Ticket, Atendente } from "@/lib/types/atendimento";
import PageHeader from "@/app/_components/PageHeader";
import StatusBadge from "@/app/_components/StatusBadge";
import DataTable from "@/app/_components/DataTable";
import TabBar from "@/app/_components/TabBar";
import DateFilter, { type DateFilterValue } from "@/app/_components/DateFilter";
import ErrorAlert from "@/app/_components/ErrorAlert";
import LoadingState from "@/app/_components/LoadingState";
import Icon from "@/app/_components/Icon";
import { Can } from "@/lib/auth";
import type { Column, StatusBadgeVariant } from "@/lib/types/ui";

const STATUS_VARIANT: Record<string, StatusBadgeVariant> = {
  aberto: "success", pendente: "warning", fechado: "neutral",
};
const PRIORIDADE_VARIANT: Record<string, StatusBadgeVariant> = {
  urgente: "danger", alta: "warning", normal: "neutral", baixa: "neutral",
};
const TABS = [
  { key: "", label: "Todos" },
  { key: "aberto", label: "Aberto" },
  { key: "pendente", label: "Pendente" },
  { key: "fechado", label: "Fechado" },
];

function slaVariant(t: Ticket): StatusBadgeVariant {
  if (t.status === "fechado" || !t.sla_vencimento) return "neutral";
  return new Date(t.sla_vencimento) < new Date() ? "danger" : "success";
}
function slaLabel(t: Ticket): string {
  if (t.status === "fechado" || !t.sla_vencimento) return "—";
  return new Date(t.sla_vencimento) < new Date() ? "Vencido" : "No prazo";
}

export default function TicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [atendentes, setAtendentes] = useState<Atendente[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [statusTab, setStatusTab] = useState("");
  const [prioridade, setPrioridade] = useState("");
  const [canal, setCanal] = useState("");
  const [atendenteId, setAtendenteId] = useState("");
  const [busca, setBusca] = useState("");
  const [dateFilter, setDateFilter] = useState<DateFilterValue>({});
  const [showModal, setShowModal] = useState(false);
  const [novo, setNovo] = useState({ cliente: "", email: "", telefone: "", assunto: "", canal: "whatsapp", prioridade: "normal" });

  const carregar = useCallback(() => {
    const filtros: Record<string, string> = {};
    if (statusTab) filtros.status = statusTab;
    if (prioridade) filtros.prioridade = prioridade;
    if (canal) filtros.canal = canal;
    if (atendenteId) filtros.atendente_id = atendenteId;
    if (busca) filtros.q = busca;
    if (dateFilter.data_inicio) filtros.de = dateFilter.data_inicio;
    if (dateFilter.data_fim) filtros.ate = dateFilter.data_fim;
    setLoading(true);
    api.atendimento.listar(filtros)
      .then(r => setTickets(r.data || []))
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar tickets"))
      .finally(() => setLoading(false));
  }, [statusTab, prioridade, canal, atendenteId, busca, dateFilter]);

  useEffect(() => { carregar(); }, [carregar]);
  useEffect(() => { api.atendimento.listarAtendentes().then(r => setAtendentes(r.data || [])).catch(() => {}); }, []);

  const criar = async () => {
    if (!novo.cliente.trim() || !novo.assunto.trim()) return;
    setErro("");
    try {
      const r = await api.atendimento.criar(novo);
      if (r.error) { setErro(r.error); return; }
      setShowModal(false);
      setNovo({ cliente: "", email: "", telefone: "", assunto: "", canal: "whatsapp", prioridade: "normal" });
      carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao criar ticket");
    }
  };

  const columns: Column<Ticket>[] = [
    { key: "numero", label: "Número", render: (v) => String(v ?? "—") },
    { key: "cliente", label: "Cliente" },
    { key: "assunto", label: "Assunto" },
    { key: "canal", label: "Canal", align: "center" },
    { key: "prioridade", label: "Prioridade", align: "center", render: (v) => <StatusBadge label={String(v)} variant={PRIORIDADE_VARIANT[String(v)] || "neutral"} /> },
    { key: "status", label: "Status", align: "center", render: (v) => <StatusBadge label={String(v)} variant={STATUS_VARIANT[String(v)] || "neutral"} /> },
    { key: "sla_vencimento", label: "SLA", align: "center", render: (_v, row) => <StatusBadge label={slaLabel(row)} variant={slaVariant(row)} /> },
    { key: "data_abertura", label: "Aberto em", align: "center", render: (v) => String(v ?? "—").slice(0, 10) },
  ];

  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between items-end flex-wrap gap-3">
        <PageHeader title="Tickets" subtitle="Atendimento ao cliente — chamados multicanal" />
        <div className="flex items-center gap-2 flex-wrap">
          <DateFilter value={dateFilter} onChange={setDateFilter} />
          <Can permission="atendimento.criar">
            <button onClick={() => setShowModal(true)} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg">
              + Novo Ticket
            </button>
          </Can>
        </div>
      </div>

      <ErrorAlert message={erro || null} />

      <TabBar tabs={TABS} active={statusTab} onChange={setStatusTab} />

      <div className="flex gap-2 flex-wrap">
        <select value={prioridade} onChange={e => setPrioridade(e.target.value)} className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200">
          <option value="">Toda prioridade</option>
          {["baixa", "normal", "alta", "urgente"].map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        <select value={canal} onChange={e => setCanal(e.target.value)} className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200">
          <option value="">Todo canal</option>
          {["whatsapp", "telegram", "instagram", "facebook", "chat", "email"].map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={atendenteId} onChange={e => setAtendenteId(e.target.value)} className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200">
          <option value="">Todo atendente</option>
          {atendentes.map(a => <option key={a.id} value={String(a.id)}>{a.nome}</option>)}
        </select>
        <input type="text" value={busca} onChange={e => setBusca(e.target.value)} placeholder="Buscar cliente, assunto, número..."
          className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 placeholder-neutral-500 w-56" />
      </div>

      {loading ? <LoadingState /> : (
        <DataTable
          columns={columns}
          data={tickets}
          keyExtractor={t => t.id}
          emptyMessage="Nenhum ticket encontrado"
        />
      )}

      {!loading && tickets.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {tickets.map(t => (
            <Link key={t.id} href={`/atendimento/tickets/${t.id}`} className="sr-only">{t.numero || t.id}</Link>
          ))}
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setShowModal(false)}>
          <div className="bg-neutral-900 border border-neutral-700 rounded-xl p-6 w-full max-w-md space-y-3" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-neutral-200">Novo Ticket</h3>
              <button onClick={() => setShowModal(false)} className="text-neutral-500 hover:text-neutral-300"><Icon name="close" size={16} /></button>
            </div>
            <input type="text" value={novo.cliente} onChange={e => setNovo(p => ({ ...p, cliente: e.target.value }))} placeholder="Nome do cliente"
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500" autoFocus />
            <input type="email" value={novo.email} onChange={e => setNovo(p => ({ ...p, email: e.target.value }))} placeholder="Email (opcional)"
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500" />
            <input type="text" value={novo.telefone} onChange={e => setNovo(p => ({ ...p, telefone: e.target.value }))} placeholder="Telefone (opcional)"
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500" />
            <input type="text" value={novo.assunto} onChange={e => setNovo(p => ({ ...p, assunto: e.target.value }))} placeholder="Assunto"
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500" />
            <div className="flex gap-2">
              <select value={novo.canal} onChange={e => setNovo(p => ({ ...p, canal: e.target.value }))} className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200">
                {["whatsapp", "telegram", "instagram", "facebook", "chat", "email"].map(c => <option key={c} value={c}>{c}</option>)}
              </select>
              <select value={novo.prioridade} onChange={e => setNovo(p => ({ ...p, prioridade: e.target.value }))} className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200">
                {["baixa", "normal", "alta", "urgente"].map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <button onClick={criar} className="w-full bg-emerald-600 hover:bg-emerald-500 text-white text-sm py-2 rounded-lg">Criar Ticket</button>
          </div>
        </div>
      )}
    </div>
  );
}
```

Nota: `DataTable` não suporta `onRowClick` nativamente (ver `web/src/app/_components/DataTable.tsx`) — o link de acesso ao detalhe é feito via a coluna `numero` renderizada como link, não por clique na linha inteira. Ajustar a coluna `numero`:

```tsx
    { key: "numero", label: "Número", render: (v, row) => <Link href={`/atendimento/tickets/${row.id}`} className="text-indigo-400 hover:text-indigo-300">{String(v ?? row.id)}</Link> },
```

E remover o bloco `sr-only` de links (era um placeholder inválido — substituído pelo link na própria coluna). Aplicar as duas correções antes de seguir.

- [ ] **Step 2: Rodar dev server e verificar visualmente**

Run: `cd web && npm run dev`
Navegar para `http://localhost:3000/atendimento/tickets`, confirmar: tabs, filtros, tabela com badges, modal de criação abrindo/fechando, link do número navegando para `/atendimento/tickets/<id>` (rota ainda não existe — 404 esperado até a Task 12).

- [ ] **Step 3: Verificar tipos**

Run: `cd web && npx tsc --noEmit -p tsconfig.json`
Expected: sem erros novos

- [ ] **Step 4: Commit**

```bash
git add web/src/app/atendimento/tickets/page.tsx
git commit -m "feat: reescreve listagem de tickets com filtros, tabs, badges e tabela padronizada"
```

---

### Task 12: Tela de detalhe do ticket — estrutura e painel de controle

**Files:**
- Create: `web/src/app/atendimento/tickets/[id]/page.tsx`
- Create: `web/src/app/atendimento/tickets/[id]/client.tsx`
- Create: `web/src/app/atendimento/tickets/[id]/_components/PainelControle.tsx`

**Interfaces:**
- Consumes: `api.atendimento.{obter, mudarStatus, atribuir, listarAtendentes}` (Task 9)
- Produces: `PainelControle` component — props `{ticket: Ticket, atendentes: Atendente[], onMudarStatus: (s: string) => void, onAtribuir: (id: number) => void}`

- [ ] **Step 1: Criar `page.tsx` (export estático)**

Create `web/src/app/atendimento/tickets/[id]/page.tsx`:

```tsx
import TicketDetalheClient from "./client";

// producao serve export estatico (output: 'export') — rotas dinamicas
// precisam de pelo menos um param conhecido em build-time. O id real e'
// lido em runtime no client (usePathname), mesmo padrao de /lojas/[id].
export async function generateStaticParams() {
  return [{ id: "placeholder" }];
}

export default function TicketDetalhePage() {
  return <TicketDetalheClient />;
}
```

- [ ] **Step 2: Criar `PainelControle.tsx`**

Create `web/src/app/atendimento/tickets/[id]/_components/PainelControle.tsx`:

```tsx
"use client";
import type { Ticket, Atendente } from "@/lib/types/atendimento";
import StatusBadge from "@/app/_components/StatusBadge";
import { Can } from "@/lib/auth";
import type { StatusBadgeVariant } from "@/lib/types/ui";

const PRIORIDADE_VARIANT: Record<string, StatusBadgeVariant> = {
  urgente: "danger", alta: "warning", normal: "neutral", baixa: "neutral",
};

const TRANSICOES: Record<string, { status: string; label: string }[]> = {
  aberto: [{ status: "pendente", label: "Marcar pendente" }, { status: "fechado", label: "Fechar" }],
  pendente: [{ status: "aberto", label: "Reabrir" }, { status: "fechado", label: "Fechar" }],
  fechado: [{ status: "aberto", label: "Reabrir" }],
};

export default function PainelControle({
  ticket, atendentes, onMudarStatus, onAtribuir,
}: {
  ticket: Ticket;
  atendentes: Atendente[];
  onMudarStatus: (status: string) => void;
  onAtribuir: (atendenteId: number) => void;
}) {
  const slaVencido = ticket.status !== "fechado" && !!ticket.sla_vencimento && new Date(ticket.sla_vencimento) < new Date();
  const atendenteAtual = atendentes.find(a => a.id === ticket.atendente_id);

  return (
    <div className="w-72 shrink-0 border-l border-neutral-800 p-4 space-y-4 overflow-y-auto">
      <div>
        <p className="text-[10px] uppercase text-neutral-500 mb-1">Status</p>
        <StatusBadge label={ticket.status} variant={ticket.status === "aberto" ? "success" : ticket.status === "pendente" ? "warning" : "neutral"} />
        <Can permission="atendimento.editar">
          <div className="flex flex-col gap-1.5 mt-2">
            {(TRANSICOES[ticket.status] || []).map(t => (
              <button key={t.status} onClick={() => onMudarStatus(t.status)}
                className="text-xs px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-left">
                {t.label}
              </button>
            ))}
          </div>
        </Can>
      </div>

      <div>
        <p className="text-[10px] uppercase text-neutral-500 mb-1">Prioridade</p>
        <StatusBadge label={ticket.prioridade} variant={PRIORIDADE_VARIANT[ticket.prioridade] || "neutral"} />
      </div>

      <div>
        <p className="text-[10px] uppercase text-neutral-500 mb-1">Atendente</p>
        <Can permission="atendimento.editar" fallback={<p className="text-xs text-neutral-300">{atendenteAtual?.nome || "Não atribuído"}</p>}>
          <select
            value={ticket.atendente_id ?? ""}
            onChange={e => e.target.value && onAtribuir(Number(e.target.value))}
            className="w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200"
          >
            <option value="">Não atribuído</option>
            {atendentes.map(a => <option key={a.id} value={a.id}>{a.nome}</option>)}
          </select>
        </Can>
      </div>

      <div>
        <p className="text-[10px] uppercase text-neutral-500 mb-1">SLA</p>
        <StatusBadge label={ticket.sla_vencimento ? (slaVencido ? "Vencido" : "No prazo") : "—"} variant={slaVencido ? "danger" : "success"} />
        {ticket.sla_vencimento && <p className="text-[10px] text-neutral-500 mt-1">{new Date(ticket.sla_vencimento).toLocaleString("pt-BR")}</p>}
      </div>

      <div className="space-y-1 pt-2 border-t border-neutral-800">
        <p className="text-[10px] uppercase text-neutral-500">Cliente</p>
        <p className="text-xs text-neutral-300">{ticket.cliente}</p>
        {ticket.email && <p className="text-xs text-neutral-500">{ticket.email}</p>}
        {ticket.telefone && <p className="text-xs text-neutral-500">{ticket.telefone}</p>}
        <p className="text-xs text-neutral-500">Canal: {ticket.canal}</p>
      </div>

      <div className="space-y-1 pt-2 border-t border-neutral-800 text-[10px] text-neutral-500">
        <p>Aberto em: {new Date(ticket.data_abertura).toLocaleString("pt-BR")}</p>
        {ticket.data_fechamento && <p>Fechado em: {new Date(ticket.data_fechamento).toLocaleString("pt-BR")}</p>}
        {ticket.tempo_resposta_min != null && <p>SLA resposta: {ticket.tempo_resposta_min} min</p>}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Criar `client.tsx` (esqueleto — thread de mensagens entra na Task 13)**

Create `web/src/app/atendimento/tickets/[id]/client.tsx`:

```tsx
"use client";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import type { Ticket, Atendente } from "@/lib/types/atendimento";
import Icon from "@/app/_components/Icon";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import PainelControle from "./_components/PainelControle";

export default function TicketDetalheClient() {
  // ponytail: nao usa useParams() — export estatico pre-renderiza com
  // id="placeholder"; usePathname() sempre reflete a URL real do browser.
  // Mesmo padrao de /lojas/[id]/client.tsx.
  const pathname = usePathname();
  const id = Number(pathname?.split("/").filter(Boolean).pop() || 0);

  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [atendentes, setAtendentes] = useState<Atendente[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");

  const carregar = useCallback(() => {
    if (!id) { setLoading(false); return; }
    api.atendimento.obter(id)
      .then(t => setTicket(t))
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar ticket"))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { carregar(); }, [carregar]);
  useEffect(() => { api.atendimento.listarAtendentes().then(r => setAtendentes(r.data || [])).catch(() => {}); }, []);

  const mudarStatus = async (status: string) => {
    setErro("");
    try {
      const r = await api.atendimento.mudarStatus(id, status);
      if (r.error) { setErro(r.error); return; }
      carregar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao mudar status"); }
  };

  const atribuir = async (atendenteId: number) => {
    setErro("");
    try {
      const r = await api.atendimento.atribuir(id, atendenteId);
      if (r.error) { setErro(r.error); return; }
      carregar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao atribuir atendente"); }
  };

  if (loading) return <LoadingState />;
  if (!id) return <div className="p-6 text-red-400">Ticket inválido</div>;
  if (!ticket) return <div className="p-6 text-red-400">Ticket não encontrado</div>;

  return (
    <div className="h-screen flex flex-col">
      <div className="p-4 border-b border-neutral-800 shrink-0 space-y-1">
        <Link href="/atendimento/tickets" className="text-xs text-neutral-500 hover:text-neutral-300 inline-flex items-center gap-0.5">
          <Icon name="chevronLeft" size={12} /> Tickets
        </Link>
        <h1 className="text-sm font-bold text-neutral-100">{ticket.numero || `#${ticket.id}`} — {ticket.assunto}</h1>
        <ErrorAlert message={erro || null} />
      </div>
      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 flex items-center justify-center text-neutral-500 text-sm">
          Thread de mensagens — Task 13
        </div>
        <PainelControle ticket={ticket} atendentes={atendentes} onMudarStatus={mudarStatus} onAtribuir={atribuir} />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Rodar dev server e verificar visualmente**

Run: `cd web && npm run dev`
Navegar para `http://localhost:3000/atendimento/tickets/<id-de-um-ticket-existente>`, confirmar: header com número/assunto, painel de controle à direita com status/prioridade/atendente/SLA/cliente/metadados, botões de transição de status batendo na API.

- [ ] **Step 5: Verificar tipos**

Run: `cd web && npx tsc --noEmit -p tsconfig.json`
Expected: sem erros novos

- [ ] **Step 6: Commit**

```bash
git add web/src/app/atendimento/tickets/[id]/page.tsx web/src/app/atendimento/tickets/[id]/client.tsx web/src/app/atendimento/tickets/[id]/_components/PainelControle.tsx
git commit -m "feat: adiciona tela de detalhe do ticket com painel de controle (status/atendente/SLA)"
```

---

### Task 13: Thread de mensagens com WebSocket ao vivo

**Files:**
- Create: `web/src/app/atendimento/tickets/[id]/_components/ThreadMensagens.tsx`
- Modify: `web/src/app/atendimento/tickets/[id]/client.tsx`

**Interfaces:**
- Consumes: `api.atendimento.{listarMensagens, enviarMensagem, uploadAnexo, atualizar}` (Task 9), `useChatSocket` (Task 10)
- Produces: `ThreadMensagens` component — props `{ticket: Ticket, mensagens: MensagemTicket[], onEnviar: (texto: string) => void, onUpload: (arquivo: File) => Promise<void>}`
- Produces: `EditarTicketModal` component (inline em `client.tsx`) — reaproveita `api.atendimento.atualizar` (PUT genérico) para editar cliente/email/telefone/assunto/canal/prioridade

- [ ] **Step 1: Criar `ThreadMensagens.tsx`**

Create `web/src/app/atendimento/tickets/[id]/_components/ThreadMensagens.tsx`:

```tsx
"use client";
import { useEffect, useRef, useState } from "react";
import type { MensagemTicket } from "@/lib/types/atendimento";
import { Can } from "@/lib/auth";

export default function ThreadMensagens({
  mensagens, onEnviar, onUpload,
}: {
  mensagens: MensagemTicket[];
  onEnviar: (texto: string) => void;
  onUpload: (arquivo: File) => Promise<void>;
}) {
  const [texto, setTexto] = useState("");
  const [enviandoArquivo, setEnviandoArquivo] = useState(false);
  const fimRef = useRef<HTMLDivElement>(null);

  useEffect(() => { fimRef.current?.scrollIntoView({ behavior: "smooth" }); }, [mensagens]);

  const enviar = () => {
    if (!texto.trim()) return;
    onEnviar(texto);
    setTexto("");
  };

  const selecionarArquivo = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const arquivo = e.target.files?.[0];
    if (!arquivo) return;
    setEnviandoArquivo(true);
    try { await onUpload(arquivo); }
    finally { setEnviandoArquivo(false); e.target.value = ""; }
  };

  return (
    <div className="flex-1 flex flex-col min-w-0">
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {mensagens.length === 0 && <p className="text-xs text-neutral-500 text-center mt-8">Nenhuma mensagem ainda</p>}
        {mensagens.map(m => (
          <div key={m.id} className="max-w-[70%] rounded-lg px-3 py-2 text-sm bg-neutral-700 text-neutral-200">
            <p className="text-[10px] text-neutral-400 mb-0.5">{m.remetente_nome || "—"}</p>
            {m.anexo_url ? (
              <a href={`/api/atendimento/tickets/${m.conversa_id}/anexo/${m.anexo_url}`} target="_blank" rel="noreferrer" className="text-indigo-300 underline">
                📎 {m.texto}
              </a>
            ) : (
              <p>{m.texto}</p>
            )}
            <p className="text-[10px] opacity-60 mt-1">{(m.created_at || "").slice(11, 16)}</p>
          </div>
        ))}
        <div ref={fimRef} />
      </div>

      <Can permission="atendimento.criar">
        <div className="p-3 border-t border-neutral-800 shrink-0 flex gap-2">
          <label className="cursor-pointer text-neutral-400 px-2 flex items-center">
            <svg xmlns="http://www.w3.org/2000/svg" width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
              <path d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
            <input type="file" className="hidden" onChange={selecionarArquivo} disabled={enviandoArquivo} />
          </label>
          <input
            type="text" value={texto} onChange={e => setTexto(e.target.value)}
            onKeyDown={e => e.key === "Enter" && enviar()}
            placeholder="Digite sua mensagem..."
            className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200"
          />
          <button onClick={enviar} className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm px-4 py-2 rounded-lg">Enviar</button>
        </div>
      </Can>
    </div>
  );
}
```

- [ ] **Step 2: Integrar thread + WebSocket em `client.tsx`**

Em `web/src/app/atendimento/tickets/[id]/client.tsx`, substituir o conteúdo inteiro por:

```tsx
"use client";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import type { Ticket, Atendente, MensagemTicket } from "@/lib/types/atendimento";
import { useChatSocket, type EventoChatSocket } from "@/lib/useChatSocket";
import Icon from "@/app/_components/Icon";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import PainelControle from "./_components/PainelControle";
import ThreadMensagens from "./_components/ThreadMensagens";

export default function TicketDetalheClient() {
  // ponytail: nao usa useParams() — export estatico pre-renderiza com
  // id="placeholder"; usePathname() sempre reflete a URL real do browser.
  // Mesmo padrao de /lojas/[id]/client.tsx.
  const pathname = usePathname();
  const id = Number(pathname?.split("/").filter(Boolean).pop() || 0);
  const { conectado, on } = useChatSocket();

  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [atendentes, setAtendentes] = useState<Atendente[]>([]);
  const [mensagens, setMensagens] = useState<MensagemTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [showEditar, setShowEditar] = useState(false);

  const carregarTicket = useCallback(() => {
    if (!id) { setLoading(false); return; }
    api.atendimento.obter(id)
      .then(t => setTicket(t))
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar ticket"))
      .finally(() => setLoading(false));
  }, [id]);

  const carregarMensagens = useCallback(() => {
    if (!id) return;
    api.atendimento.listarMensagens(id).then(r => setMensagens(r.data || [])).catch(() => {});
  }, [id]);

  useEffect(() => { carregarTicket(); }, [carregarTicket]);
  useEffect(() => { carregarMensagens(); }, [carregarMensagens]);
  useEffect(() => { api.atendimento.listarAtendentes().then(r => setAtendentes(r.data || [])).catch(() => {}); }, []);

  useEffect(() => {
    return on((evento: EventoChatSocket) => {
      if (evento.evento === "nova_mensagem") {
        const m = evento.mensagem as MensagemTicket & { conversa_id: number };
        setMensagens(atual => (atual.some(x => x.id === m.id) ? atual : [...atual, m]));
      }
      if (evento.evento === "ticket_status_alterado" && evento.ticket_id === id) {
        setTicket(atual => atual ? { ...atual, status: evento.status as Ticket["status"] } : atual);
      }
      if (evento.evento === "ticket_atendente_alterado" && evento.ticket_id === id) {
        setTicket(atual => atual ? { ...atual, atendente_id: evento.atendente_id as number } : atual);
      }
    });
  }, [on, id]);

  const mudarStatus = async (status: string) => {
    setErro("");
    try {
      const r = await api.atendimento.mudarStatus(id, status);
      if (r.error) { setErro(r.error); return; }
      carregarTicket();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao mudar status"); }
  };

  const atribuir = async (atendenteId: number) => {
    setErro("");
    try {
      const r = await api.atendimento.atribuir(id, atendenteId);
      if (r.error) { setErro(r.error); return; }
      carregarTicket();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao atribuir atendente"); }
  };

  const enviarMensagem = async (texto: string) => {
    setErro("");
    try {
      const r = await api.atendimento.enviarMensagem(id, texto);
      if (r.error) setErro(r.error);
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao enviar mensagem"); }
  };

  const uploadAnexo = async (arquivo: File) => {
    setErro("");
    try {
      const r = await api.atendimento.uploadAnexo(id, arquivo);
      if (r.error) setErro(r.error);
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao enviar anexo"); }
  };

  const editar = async (campos: { cliente: string; email: string; telefone: string; assunto: string; canal: string; prioridade: string }) => {
    setErro("");
    try {
      const r = await api.atendimento.atualizar(id, campos);
      if (r.error) { setErro(r.error); return; }
      setShowEditar(false);
      carregarTicket();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao editar ticket"); }
  };

  if (loading) return <LoadingState />;
  if (!id) return <div className="p-6 text-red-400">Ticket inválido</div>;
  if (!ticket) return <div className="p-6 text-red-400">Ticket não encontrado</div>;

  return (
    <div className="h-screen flex flex-col">
      <div className="p-4 border-b border-neutral-800 shrink-0 space-y-1">
        <div className="flex items-start justify-between gap-3">
          <div>
            <Link href="/atendimento/tickets" className="text-xs text-neutral-500 hover:text-neutral-300 inline-flex items-center gap-0.5">
              <Icon name="chevronLeft" size={12} /> Tickets
            </Link>
            <h1 className="text-sm font-bold text-neutral-100">{ticket.numero || `#${ticket.id}`} — {ticket.assunto}</h1>
          </div>
          <Can permission="atendimento.editar">
            <button onClick={() => setShowEditar(true)} className="text-xs text-indigo-400 hover:text-indigo-300 shrink-0">Editar</button>
          </Can>
        </div>
        <ErrorAlert message={erro || null} />
      </div>
      <div className="flex-1 flex overflow-hidden">
        <ThreadMensagens mensagens={mensagens} onEnviar={enviarMensagem} onUpload={uploadAnexo} />
        <PainelControle ticket={ticket} atendentes={atendentes} onMudarStatus={mudarStatus} onAtribuir={atribuir} />
      </div>
      {!conectado && (
        <div className="fixed bottom-3 right-3 bg-amber-600 text-white text-xs px-3 py-1.5 rounded-lg">Reconectando...</div>
      )}
      {showEditar && (
        <EditarTicketModal ticket={ticket} onSalvar={editar} onFechar={() => setShowEditar(false)} />
      )}
    </div>
  );
}

function EditarTicketModal({
  ticket, onSalvar, onFechar,
}: {
  ticket: Ticket;
  onSalvar: (campos: { cliente: string; email: string; telefone: string; assunto: string; canal: string; prioridade: string }) => void;
  onFechar: () => void;
}) {
  const [form, setForm] = useState({
    cliente: ticket.cliente, email: ticket.email || "", telefone: ticket.telefone || "",
    assunto: ticket.assunto, canal: ticket.canal, prioridade: ticket.prioridade,
  });
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onFechar}>
      <div className="bg-neutral-900 border border-neutral-700 rounded-xl p-6 w-full max-w-md space-y-3" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-neutral-200">Editar Ticket</h3>
          <button onClick={onFechar} className="text-neutral-500 hover:text-neutral-300"><Icon name="close" size={16} /></button>
        </div>
        <input type="text" value={form.cliente} onChange={e => setForm(p => ({ ...p, cliente: e.target.value }))} placeholder="Nome do cliente"
          className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" autoFocus />
        <input type="email" value={form.email} onChange={e => setForm(p => ({ ...p, email: e.target.value }))} placeholder="Email"
          className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" />
        <input type="text" value={form.telefone} onChange={e => setForm(p => ({ ...p, telefone: e.target.value }))} placeholder="Telefone"
          className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" />
        <input type="text" value={form.assunto} onChange={e => setForm(p => ({ ...p, assunto: e.target.value }))} placeholder="Assunto"
          className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" />
        <div className="flex gap-2">
          <select value={form.canal} onChange={e => setForm(p => ({ ...p, canal: e.target.value }))} className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200">
            {["whatsapp", "telegram", "instagram", "facebook", "chat", "email"].map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <select value={form.prioridade} onChange={e => setForm(p => ({ ...p, prioridade: e.target.value }))} className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200">
            {["baixa", "normal", "alta", "urgente"].map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <button onClick={() => onSalvar(form)} className="w-full bg-indigo-600 hover:bg-indigo-500 text-white text-sm py-2 rounded-lg">Salvar</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Rodar dev server e verificar visualmente**

Run: `cd web && npm run dev`
Navegar para `/atendimento/tickets/<id>`, confirmar: thread de mensagens carregando, campo de envio funcionando, upload de anexo funcionando, botão "Editar" abrindo modal pré-preenchido e salvando, indicador "Reconectando..." aparecendo/sumindo conforme o WS conecta.

Teste manual de tempo real: abrir o mesmo ticket em duas abas, enviar mensagem/mudar status numa aba, confirmar que a outra atualiza sem F5.

- [ ] **Step 4: Verificar tipos**

Run: `cd web && npx tsc --noEmit -p tsconfig.json`
Expected: sem erros novos

- [ ] **Step 5: Commit**

```bash
git add web/src/app/atendimento/tickets/[id]/client.tsx web/src/app/atendimento/tickets/[id]/_components/ThreadMensagens.tsx
git commit -m "feat: adiciona thread de mensagens, edicao de ticket e atualizacao via WebSocket ao vivo"
```

---

### Task 14: Sino de notificação no layout principal

**Files:**
- Create: `web/src/app/_components/NotificationBell.tsx`
- Modify: `web/src/app/layout.tsx`

**Interfaces:**
- Consumes: `api.notificacoes.{listar, marcarLida, marcarTodasLidas}` (Task 9), `useChatSocket` (Task 10)
- Produces: `<NotificationBell />` — sem props, gerencia seu próprio estado

- [ ] **Step 1: Criar `NotificationBell.tsx`**

Create `web/src/app/_components/NotificationBell.tsx`:

```tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Notificacao } from "@/lib/types/atendimento";
import { useChatSocket, type EventoChatSocket } from "@/lib/useChatSocket";
import Icon from "./Icon";

export default function NotificationBell() {
  const router = useRouter();
  const { on } = useChatSocket();
  const [notificacoes, setNotificacoes] = useState<Notificacao[]>([]);
  const [aberto, setAberto] = useState(false);

  const carregar = () => { api.notificacoes.listar().then(r => setNotificacoes(r.data || [])).catch(() => {}); };

  useEffect(() => { carregar(); }, []);

  useEffect(() => {
    return on((evento: EventoChatSocket) => {
      if (evento.evento === "notificacao") carregar();
    });
  }, [on]);

  const naoLidas = notificacoes.filter(n => !n.lida).length;

  const abrir = async (n: Notificacao) => {
    if (!n.lida) await api.notificacoes.marcarLida(n.id);
    setAberto(false);
    carregar();
    if (n.link) router.push(n.link);
  };

  const marcarTodas = async () => {
    await api.notificacoes.marcarTodasLidas();
    carregar();
  };

  return (
    <div className="relative">
      <button
        onClick={() => setAberto(v => !v)}
        aria-label="Notificações"
        className="relative p-1.5 rounded shrink-0 transition-colors hover:bg-white/5"
        style={{ color: "var(--ink-700)" }}
      >
        <Icon name="bell" size={14} />
        {naoLidas > 0 && (
          <span className="absolute -top-0.5 -right-0.5 bg-red-600 text-white text-[9px] rounded-full min-w-[14px] h-[14px] flex items-center justify-center px-0.5">
            {naoLidas > 9 ? "9+" : naoLidas}
          </span>
        )}
      </button>
      {aberto && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setAberto(false)} />
          <div className="absolute bottom-full right-0 mb-2 w-72 max-h-96 overflow-y-auto bg-neutral-900 border border-neutral-700 rounded-lg shadow-xl z-50">
            <div className="flex items-center justify-between px-3 py-2 border-b border-neutral-800">
              <span className="text-xs font-semibold text-neutral-300">Notificações</span>
              {naoLidas > 0 && <button onClick={marcarTodas} className="text-[10px] text-indigo-400 hover:text-indigo-300">Marcar todas lidas</button>}
            </div>
            {notificacoes.length === 0 ? (
              <p className="text-xs text-neutral-500 text-center py-6">Nenhuma notificação</p>
            ) : (
              notificacoes.map(n => (
                <button key={n.id} onClick={() => abrir(n)}
                  className={`w-full text-left px-3 py-2 border-b border-neutral-800/50 hover:bg-neutral-800 ${!n.lida ? "bg-neutral-800/40" : ""}`}>
                  <p className="text-xs text-neutral-200">{n.titulo}</p>
                  {n.mensagem && <p className="text-[10px] text-neutral-500 mt-0.5">{n.mensagem}</p>}
                  <p className="text-[9px] text-neutral-600 mt-0.5">{new Date(n.created_at).toLocaleString("pt-BR")}</p>
                </button>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verificar se o ícone `bell` existe em `Icon.tsx`**

Run: `grep -n '"bell"' web/src/app/_components/Icon.tsx`

Se não existir, adicionar ao mapa de ícones de `web/src/app/_components/Icon.tsx` seguindo o padrão dos ícones vizinhos (SVG outline consistente com `power`/`chevronLeft` já usados no arquivo) — ler o arquivo antes de editar para replicar exatamente a estrutura do componente `Icon`.

- [ ] **Step 3: Integrar no layout**

Em `web/src/app/layout.tsx`, adicionar o import (perto da linha 8):

```typescript
import NotificationBell from "./_components/NotificationBell";
```

E no bloco do rodapé do `Sidebar` (linhas 311-339), adicionar o sino ao lado do botão de logout quando `sidebarOpen`:

```tsx
      {user && (
        <div className="px-3 py-2.5 shrink-0" style={{ borderTop: "1px solid var(--panel-border)" }}>
          {sidebarOpen ? (
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="text-xs font-medium truncate" style={{ color: "var(--ink-300)" }}>{user.name}</div>
                <div className="text-[9px] uppercase tracking-wide" style={{ color: "var(--ink-700)" }}>{user.role}</div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <NotificationBell />
                <button
                  onClick={logout}
                  aria-label="Sair"
                  className="p-1.5 rounded shrink-0 transition-colors hover:bg-white/5"
                  style={{ color: "var(--ink-700)" }}
                >
                  <Icon name="power" size={14} />
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={logout}
              aria-label="Sair"
              className="w-full flex justify-center p-1.5 rounded transition-colors hover:bg-white/5"
              style={{ color: "var(--ink-700)" }}
            >
              <Icon name="power" size={14} />
            </button>
          )}
        </div>
      )}
```

(Substitui apenas o bloco `sidebarOpen ? (...)` — o branch `else` de `sidebarOpen` colapsado permanece igual, sem o sino, para não lotar a barra estreita.)

- [ ] **Step 4: Rodar dev server e verificar visualmente**

Run: `cd web && npm run dev`
Confirmar: sino aparece no rodapé da sidebar (com sidebar aberta), badge de contador funciona, dropdown abre/fecha, clicar numa notificação marca como lida e navega pro link.

Teste manual do gatilho: atribuir um ticket a um usuário logado em outra aba/sessão, confirmar que o sino atualiza o contador sem F5.

- [ ] **Step 5: Verificar tipos**

Run: `cd web && npx tsc --noEmit -p tsconfig.json`
Expected: sem erros novos

- [ ] **Step 6: Commit**

```bash
git add web/src/app/_components/NotificationBell.tsx web/src/app/layout.tsx web/src/app/_components/Icon.tsx
git commit -m "feat: adiciona sino de notificacao generico na sidebar principal"
```

---

### Task 15: Teste e2e do fluxo completo de tickets

**Files:**
- Create: `web/tests/e2e/tickets.spec.ts`

**Interfaces:**
- Consumes: toda a stack construída nas Tasks 1-14

- [ ] **Step 1: Escrever o teste e2e**

Create `web/tests/e2e/tickets.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

// Golden path de tickets estruturados. Precisa de E2E_ADMIN_EMAIL/E2E_ADMIN_PW
// apontando pra um usuario admin real do ambiente local — mesmo padrao de
// web/tests/e2e/lojas.spec.ts, sem credencial hardcoded no teste.
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "";
const ADMIN_PW = process.env.E2E_ADMIN_PW || "";

test.beforeEach(async () => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PW, "E2E_ADMIN_EMAIL/E2E_ADMIN_PW nao configurados — pulei o teste E2E");
});

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.fill("#email", ADMIN_EMAIL);
  await page.fill("#password", ADMIN_PW);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.waitForURL(/\/dashboard/);
}

test("cria ticket, atribui, muda status, envia mensagem e fecha", async ({ page }) => {
  const cliente = `E2E Cliente ${Date.now()}`;

  await login(page);
  await page.goto("/atendimento/tickets");

  await page.getByRole("button", { name: "+ Novo Ticket" }).click();
  await page.getByPlaceholder("Nome do cliente").fill(cliente);
  await page.getByPlaceholder("Assunto").fill("Duvida sobre pedido E2E");
  await page.getByRole("button", { name: "Criar Ticket" }).click();
  await expect(page.getByText(cliente)).toBeVisible();

  await page.getByRole("link", { name: /#\d+/ }).last().click();
  await page.waitForURL(/\/atendimento\/tickets\/\d+/);

  await expect(page.getByText("Duvida sobre pedido E2E")).toBeVisible();

  // Atribui a si mesmo (primeiro atendente disponivel no select)
  const selectAtendente = page.locator("select").filter({ hasText: "Não atribuído" });
  await selectAtendente.selectOption({ index: 1 });

  // Muda status para pendente
  await page.getByRole("button", { name: "Marcar pendente" }).click();
  await expect(page.getByText("pendente")).toBeVisible();

  // Envia mensagem
  await page.getByPlaceholder("Digite sua mensagem...").fill("Mensagem de teste E2E");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText("Mensagem de teste E2E")).toBeVisible();

  // Fecha o ticket
  await page.getByRole("button", { name: "Fechar" }).click();
  await expect(page.getByText("fechado")).toBeVisible();

  // Volta pra listagem, confirma que aparece na tab Fechado
  await page.getByRole("link", { name: "Tickets" }).click();
  await page.getByRole("button", { name: "Fechado" }).click();
  await expect(page.getByText(cliente)).toBeVisible();
});

test("mudanca de status via WebSocket aparece em outra aba sem F5", async ({ browser }) => {
  const context = await browser.newContext();
  const pageA = await context.newPage();
  const pageB = await context.newPage();

  await login(pageA);
  await login(pageB);

  await pageA.goto("/atendimento/tickets");
  await pageA.getByRole("button", { name: "+ Novo Ticket" }).click();
  const cliente = `E2E WS ${Date.now()}`;
  await pageA.getByPlaceholder("Nome do cliente").fill(cliente);
  await pageA.getByPlaceholder("Assunto").fill("Teste WS");
  await pageA.getByRole("button", { name: "Criar Ticket" }).click();
  await pageA.getByRole("link", { name: /#\d+/ }).last().click();
  await pageA.waitForURL(/\/atendimento\/tickets\/(\d+)/);
  const url = pageA.url();

  await pageB.goto(url);
  await expect(pageB.getByText("aberto")).toBeVisible();

  await pageA.getByRole("button", { name: "Marcar pendente" }).click();
  await expect(pageB.getByText("pendente")).toBeVisible({ timeout: 10_000 });

  await context.close();
});
```

- [ ] **Step 2: Rodar o teste (requer ambiente local rodando com credenciais configuradas)**

Run: `cd web && E2E_ADMIN_EMAIL=<email> E2E_ADMIN_PW=<senha> npx playwright test tests/e2e/tickets.spec.ts`
Expected: PASS (2 testes), ou SKIP se as env vars não estiverem configuradas no ambiente atual — nesse caso, reportar ao usuário que o teste existe mas não pôde ser exercitado localmente, e que ele roda em qualquer ambiente com essas credenciais configuradas.

- [ ] **Step 3: Commit**

```bash
git add web/tests/e2e/tickets.spec.ts
git commit -m "test: adiciona e2e do fluxo completo de tickets (criar/atribuir/status/mensagem/WS)"
```

---

## Verificação final

Depois de todas as tasks:

- [ ] Rodar toda a suíte backend: `cd hermes_agents && python -m pytest tests/ -v`
- [ ] Rodar typecheck frontend: `cd web && npx tsc --noEmit -p tsconfig.json`
- [ ] Rodar build de produção: `cd web && npm run build`
- [ ] Testar manualmente no navegador (dev server): criar ticket → listar com filtros → abrir detalhe → atribuir → mudar status → enviar mensagem → anexar arquivo → confirmar sino de notificação → confirmar WS ao vivo em duas abas
- [ ] Confirmar que `/atendimento` (dashboard pai) e `/chat` (hub geral) continuam funcionando sem regressão (ambos dependem de `core/atendimento.py` e `core/chat.py`, tocados nas Tasks 1, 7)
