# Chat Interno — Fase 1 (Núcleo) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao time comunicação interna (DM, grupo, canal de departamento, threads) em tempo real, com os tickets de atendimento a cliente aparecendo no mesmo hub, sem migrar nenhum dado do módulo de atendimento já em produção.

**Architecture:** Novo blueprint Flask (`hermes_agents/routes/chat.py`) reaproveitando `get_db()`/`asyncpg`/`run_async()` do resto do projeto. Tempo real via `flask-sock` (WebSocket sobre WSGI puro, sem monkeypatch de eventlet/gevent — preserva o padrão `asyncio.run()` já usado em toda a base). Fan-out de eventos em registro de conexões em memória (processo Flask único, sem múltiplos workers). Tickets viram uma linha de `chat_conversas` (tipo `ticket`) apontando pro ticket original; a persistência de mensagem de ticket continua 100% em `atend_mensagens`/`atendimento.py` — o chat só lê de lá e propaga eventos no mesmo WebSocket.

**Tech Stack:** Flask (blueprint), asyncpg/Postgres, flask-sock (WebSocket), Next.js/React (frontend, export estático), TypeScript.

## Global Constraints

- Sem framework novo no backend além de `flask-sock` — reaproveitar `get_db()`/`run_async()`/`log()` de `hermes_agents/core/__init__.py`.
- Não usar `flask-socketio`/`eventlet`/`gevent` — quebraria o `asyncio.run()` já usado em `producao`, `bling_erp`, etc.
- Não migrar/alterar tabelas `atend_tickets`/`atend_mensagens` nem os endpoints `/api/atendimento/tickets/*` já existentes.
- Anexos salvos em volume local persistente do container (`hermes_agents/uploads/chat/`), limite de 25MB por arquivo.
- Canal de departamento: participação sempre derivada da permissão RBAC do módulo (`<departamento>.ver`), nunca lista manual.
- Editar/excluir mensagem: só o autor (moderação por terceiros fica pra Fase 2).
- Sem framework de teste novo no frontend — o projeto não tem jest/vitest configurado; validação do frontend é build (`npm run build`) + smoke test manual via dev server, igual ao resto do projeto.
- Todo texto de UI em português, consistente com o resto do app.

---

## Mapa de arquivos

**Backend (novo):**
- `hermes_agents/core/chat.py` — tabelas + toda lógica de conversas/mensagens/anexos/presença/canais/busca/ponte com ticket
- `hermes_agents/core/chat_ws.py` — registro de conexões WebSocket em memória + broadcast
- `hermes_agents/routes/chat.py` — blueprint REST `/api/chat/*`
- `hermes_agents/routes/chat_ws.py` — endpoint WebSocket `/ws/chat`
- `hermes_agents/tests/test_chat.py` — testes de permissão e isolamento de broadcast

**Backend (modificado):**
- `hermes_agents/core/atendimento.py` — hook em `criar_ticket`/`adicionar_mensagem` pra criar a conversa-ponte e disparar broadcast
- `hermes_agents/athena_bridge.py` — registra `chat_bp`, inicializa o WebSocket, `threaded=True`
- `hermes_agents/requirements.txt` — adiciona `flask-sock`

**Frontend (novo):**
- `web/src/lib/types/chat.ts` — tipos TS (`ConversaChat`, `MensagemChat`, `AnexoChat`)
- `web/src/lib/useChatSocket.ts` — hook de conexão WebSocket com reconexão
- `web/src/app/chat/page.tsx` — página principal (3 colunas)
- `web/src/app/chat/_components/ConversaSidebar.tsx`
- `web/src/app/chat/_components/MensagensPainel.tsx`
- `web/src/app/chat/_components/ThreadPainel.tsx`

**Frontend (modificado):**
- `web/src/lib/api.ts` — adiciona `api.chat.*`
- `web/src/app/layout.tsx:64` — item de nav "Chat" aponta pra `/chat`
- `web/src/app/atendimento/chat/page.tsx` — vira redirect pra `/chat`

---

### Task 1: Tabelas do chat + conversas (DM, grupo, participantes)

**Files:**
- Create: `hermes_agents/core/chat.py`
- Test: `hermes_agents/tests/test_chat.py` (arquivo criado aqui, ganha mais casos nas próximas tasks)

**Interfaces:**
- Produces: `criar_conversa_dm(user_id_a: int, user_id_b: int) -> dict`, `criar_conversa_grupo(nome: str, descricao: str, criado_por: int, participantes: list, departamento: str = None, loja_id: int = None) -> dict`, `adicionar_participante(conversa_id: int, user_id: int, papel: str = "membro") -> dict`, `remover_participante(conversa_id: int, user_id: int) -> dict`, `papel_do_usuario(conversa_id: int, user_id: int)`, `participantes_ids(conversa_id: int) -> list`, `usuario_e_participante(conversa_id: int, user_id: int) -> bool`

- [ ] **Step 1: Criar `hermes_agents/core/chat.py` com as tabelas e as funções de conversa**

```python
"""Chat Interno Core — Conversas (DM/Grupo/Canal/Ticket), Mensagens, Anexos, Presenca, Busca"""
from core import get_db, run_async, log, hoje
from datetime import datetime

AGENT = "Chat Core"

DEPARTAMENTOS_CANAL = [
    "dashboard", "cadastros", "produtos", "estoque", "compras", "vendas", "pdv",
    "financeiro", "fiscal", "crm", "atendimento", "producao", "rh", "bi",
    "documentos", "automacoes", "relatorios", "configuracoes",
]

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS chat_conversas (
            id SERIAL PRIMARY KEY,
            tipo VARCHAR(30) NOT NULL,
            nome VARCHAR(150),
            descricao TEXT,
            foto_url VARCHAR(300),
            departamento VARCHAR(50),
            loja_id INT REFERENCES lojas(id),
            ticket_ref_id INT,
            criado_por INT REFERENCES rbac_usuarios(id),
            created_at TIMESTAMP DEFAULT NOW(),
            arquivado_em TIMESTAMP
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS chat_participantes (
            conversa_id INT REFERENCES chat_conversas(id) ON DELETE CASCADE,
            user_id INT REFERENCES rbac_usuarios(id),
            papel VARCHAR(20) NOT NULL DEFAULT 'membro',
            entrou_em TIMESTAMP DEFAULT NOW(),
            saiu_em TIMESTAMP,
            PRIMARY KEY (conversa_id, user_id)
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS chat_anexos (
            id SERIAL PRIMARY KEY,
            nome_arquivo VARCHAR(255) NOT NULL,
            mime VARCHAR(100),
            tamanho_bytes INT,
            storage_path VARCHAR(500) NOT NULL,
            enviado_por INT REFERENCES rbac_usuarios(id),
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS chat_mensagens (
            id SERIAL PRIMARY KEY,
            conversa_id INT REFERENCES chat_conversas(id) ON DELETE CASCADE,
            thread_pai_id INT REFERENCES chat_mensagens(id),
            remetente_id INT REFERENCES rbac_usuarios(id),
            texto TEXT,
            anexo_id INT REFERENCES chat_anexos(id),
            created_at TIMESTAMP DEFAULT NOW(),
            editado_em TIMESTAMP,
            excluido_em TIMESTAMP
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS chat_leituras (
            conversa_id INT REFERENCES chat_conversas(id) ON DELETE CASCADE,
            user_id INT REFERENCES rbac_usuarios(id),
            ultima_mensagem_lida_id INT,
            lido_em TIMESTAMP,
            PRIMARY KEY (conversa_id, user_id)
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS chat_presenca (
            user_id INT PRIMARY KEY REFERENCES rbac_usuarios(id),
            status VARCHAR(20) DEFAULT 'offline',
            last_seen TIMESTAMP
        )""")
        for depto in DEPARTAMENTOS_CANAL:
            existente = await db.fetchrow(
                "SELECT id FROM chat_conversas WHERE tipo='canal_departamento' AND departamento=$1", depto)
            if not existente:
                await db.execute(
                    "INSERT INTO chat_conversas (tipo, nome, departamento) VALUES ('canal_departamento', $1, $2)",
                    f"#{depto}", depto)
    try:
        run_async(_go())
        log(AGENT, "Chat tables seeded")
    except Exception as e:
        log(AGENT, f"Erro tabelas chat: {e}")

_ensure_tables()

# ── Conversas ──

def criar_conversa_dm(user_id_a: int, user_id_b: int) -> dict:
    """Retorna a DM existente entre os dois usuarios, ou cria uma nova."""
    async def _go():
        db = await get_db()
        existente = await db.fetchrow("""
            SELECT c.* FROM chat_conversas c
            JOIN chat_participantes p1 ON p1.conversa_id = c.id AND p1.user_id = $1 AND p1.saiu_em IS NULL
            JOIN chat_participantes p2 ON p2.conversa_id = c.id AND p2.user_id = $2 AND p2.saiu_em IS NULL
            WHERE c.tipo = 'dm'
        """, user_id_a, user_id_b)
        if existente:
            return dict(existente)
        row = await db.fetchrow(
            "INSERT INTO chat_conversas (tipo, criado_por) VALUES ('dm', $1) RETURNING *", user_id_a)
        conversa_id = row["id"]
        await db.execute(
            "INSERT INTO chat_participantes (conversa_id, user_id, papel) VALUES ($1,$2,'membro'), ($1,$3,'membro')",
            conversa_id, user_id_a, user_id_b)
        return dict(row)
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def criar_conversa_grupo(nome: str, descricao: str, criado_por: int, participantes: list, departamento: str = None, loja_id: int = None) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "INSERT INTO chat_conversas (tipo, nome, descricao, departamento, loja_id, criado_por) "
            "VALUES ('grupo', $1, $2, $3, $4, $5) RETURNING *",
            nome, descricao, departamento, loja_id, criado_por)
        conversa_id = row["id"]
        await db.execute(
            "INSERT INTO chat_participantes (conversa_id, user_id, papel) VALUES ($1,$2,'owner')",
            conversa_id, criado_por)
        for uid in participantes:
            if uid == criado_por:
                continue
            await db.execute(
                "INSERT INTO chat_participantes (conversa_id, user_id, papel) VALUES ($1,$2,'membro') ON CONFLICT DO NOTHING",
                conversa_id, uid)
        return dict(row)
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def _ids_com_permissao(codigo: str) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT DISTINCT u.id FROM rbac_usuarios u
            JOIN rbac_roles r ON r.id = u.role_id
            JOIN rbac_role_permissoes rp ON rp.role_id = r.id
            JOIN rbac_permissoes p ON p.id = rp.permissao_id
            WHERE p.codigo = $1 AND u.ativo = TRUE
        """, codigo)
        return [r["id"] for r in rows]
    try: return run_async(_go())
    except Exception: return []


def _obter_conversa(conversa_id: int):
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM chat_conversas WHERE id=$1", conversa_id)
        return dict(row) if row else None
    try: return run_async(_go())
    except Exception: return None


def participantes_ids(conversa_id: int) -> list:
    """user_id que devem receber mensagens/eventos desta conversa. Para DM/grupo
    vem de chat_participantes; para canal e ticket, deriva da permissao RBAC do
    modulo (nao ha lista fixa de membros nesses dois tipos)."""
    conversa = _obter_conversa(conversa_id)
    if not conversa:
        return []
    if conversa["tipo"] in ("dm", "grupo"):
        async def _go():
            db = await get_db()
            rows = await db.fetch(
                "SELECT user_id FROM chat_participantes WHERE conversa_id=$1 AND saiu_em IS NULL", conversa_id)
            return [r["user_id"] for r in rows]
        try: return run_async(_go())
        except Exception: return []
    if conversa["tipo"] == "canal_departamento":
        return _ids_com_permissao(f"{conversa['departamento']}.ver")
    if conversa["tipo"] == "ticket":
        return _ids_com_permissao("atendimento.ver")
    return []


def usuario_e_participante(conversa_id: int, user_id: int) -> bool:
    return user_id in participantes_ids(conversa_id)


def papel_do_usuario(conversa_id: int, user_id: int):
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "SELECT papel FROM chat_participantes WHERE conversa_id=$1 AND user_id=$2 AND saiu_em IS NULL",
            conversa_id, user_id)
        return row["papel"] if row else None
    try: return run_async(_go())
    except Exception: return None


def adicionar_participante(conversa_id: int, user_id: int, papel: str = "membro") -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "INSERT INTO chat_participantes (conversa_id, user_id, papel) VALUES ($1,$2,$3) "
            "ON CONFLICT (conversa_id, user_id) DO UPDATE SET saiu_em=NULL, papel=$3 RETURNING *",
            conversa_id, user_id, papel)
        return dict(row)
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def remover_participante(conversa_id: int, user_id: int) -> dict:
    async def _go():
        db = await get_db()
        await db.execute(
            "UPDATE chat_participantes SET saiu_em=NOW() WHERE conversa_id=$1 AND user_id=$2",
            conversa_id, user_id)
        return {"success": True}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}
```

- [ ] **Step 2: Escrever `hermes_agents/tests/test_chat.py` com o setup padrão do projeto e o primeiro caso**

```python
"""Testes de integracao — permissao e isolamento do chat interno."""
import sys, os, unittest
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

import core.chat as chat


class TestChatConversas(unittest.TestCase):
    def test_participantes_ids_conversa_inexistente_retorna_vazio(self):
        with patch("core.chat._obter_conversa", return_value=None):
            self.assertEqual(chat.participantes_ids(999), [])

    def test_usuario_e_participante_false_quando_fora_da_lista(self):
        with patch("core.chat.participantes_ids", return_value=[1, 2, 3]):
            self.assertFalse(chat.usuario_e_participante(5, 42))

    def test_usuario_e_participante_true_quando_na_lista(self):
        with patch("core.chat.participantes_ids", return_value=[1, 2, 3]):
            self.assertTrue(chat.usuario_e_participante(5, 2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 3: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_chat.py -v`
Expected: 3 passed

- [ ] **Step 4: Commit**

```bash
git add hermes_agents/core/chat.py hermes_agents/tests/test_chat.py
git commit -m "feat: tabelas e CRUD de conversas do chat interno (DM/grupo/participantes)"
```

---

### Task 2: Mensagens (enviar, listar, editar, excluir, leitura, busca)

**Files:**
- Modify: `hermes_agents/core/chat.py`
- Modify: `hermes_agents/tests/test_chat.py`

**Interfaces:**
- Consumes: `_obter_conversa`, `participantes_ids` (Task 1)
- Produces: `enviar_mensagem(conversa_id: int, remetente_id: int, texto: str, anexo_id: int = None, thread_pai_id: int = None) -> dict`, `listar_mensagens(conversa_id: int, antes_de: str = None, limit: int = 50) -> list`, `editar_mensagem(mensagem_id: int, user_id: int, novo_texto: str) -> dict`, `excluir_mensagem(mensagem_id: int, user_id: int) -> dict`, `marcar_lido(conversa_id: int, user_id: int, ultima_mensagem_id: int) -> dict`, `buscar_mensagens(user_id: int, termo: str) -> list`, `listar_conversas_usuario(user_id: int) -> list`, `listar_canais_departamento(user_id: int) -> list`

- [ ] **Step 1: Adicionar as funções de mensagem e a listagem unificada de conversas ao final de `hermes_agents/core/chat.py`**

```python
# ── Mensagens ──

def enviar_mensagem(conversa_id: int, remetente_id: int, texto: str, anexo_id: int = None, thread_pai_id: int = None) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "INSERT INTO chat_mensagens (conversa_id, remetente_id, texto, anexo_id, thread_pai_id) "
            "VALUES ($1,$2,$3,$4,$5) RETURNING *",
            conversa_id, remetente_id, texto, anexo_id, thread_pai_id)
        return dict(row)
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def listar_mensagens(conversa_id: int, antes_de: str = None, limit: int = 50) -> list:
    async def _go():
        db = await get_db()
        if antes_de:
            rows = await db.fetch(
                "SELECT * FROM chat_mensagens WHERE conversa_id=$1 AND created_at < $2 "
                "ORDER BY created_at DESC LIMIT $3",
                conversa_id, antes_de, limit)
        else:
            rows = await db.fetch(
                "SELECT * FROM chat_mensagens WHERE conversa_id=$1 ORDER BY created_at DESC LIMIT $2",
                conversa_id, limit)
        return [dict(r) for r in rows][::-1]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"listar_mensagens: {e}"); return []


def editar_mensagem(mensagem_id: int, user_id: int, novo_texto: str) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "UPDATE chat_mensagens SET texto=$1, editado_em=NOW() WHERE id=$2 AND remetente_id=$3 RETURNING *",
            novo_texto, mensagem_id, user_id)
        return dict(row) if row else {"error": "not found or not owner"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def excluir_mensagem(mensagem_id: int, user_id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "UPDATE chat_mensagens SET excluido_em=NOW() WHERE id=$1 AND remetente_id=$2 RETURNING *",
            mensagem_id, user_id)
        return dict(row) if row else {"error": "not found or not owner"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def marcar_lido(conversa_id: int, user_id: int, ultima_mensagem_id: int) -> dict:
    async def _go():
        db = await get_db()
        await db.execute(
            "INSERT INTO chat_leituras (conversa_id, user_id, ultima_mensagem_lida_id, lido_em) "
            "VALUES ($1,$2,$3,NOW()) ON CONFLICT (conversa_id, user_id) "
            "DO UPDATE SET ultima_mensagem_lida_id=$3, lido_em=NOW()",
            conversa_id, user_id, ultima_mensagem_id)
        return {"success": True}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def _canais_departamento_permitidos(user_id: int) -> list:
    from core.rbac import get_permissoes_por_usuario
    perms = set(get_permissoes_por_usuario(user_id))
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT c.*, (SELECT MAX(created_at) FROM chat_mensagens m WHERE m.conversa_id = c.id) as ultima_atividade
            FROM chat_conversas c WHERE c.tipo = 'canal_departamento'
        """)
        return [dict(r) for r in rows]
    try: canais = run_async(_go())
    except Exception: canais = []
    return [c for c in canais if f"{c['departamento']}.ver" in perms]


def listar_canais_departamento(user_id: int) -> list:
    return _canais_departamento_permitidos(user_id)


def _conversas_ticket_permitidas(user_id: int) -> list:
    from core.rbac import get_permissoes_por_usuario
    perms = set(get_permissoes_por_usuario(user_id))
    if "atendimento.ver" not in perms:
        return []
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT c.*, t.assunto, t.cliente, t.canal as canal_externo, t.status as ticket_status,
                   (SELECT MAX(enviado_em) FROM atend_mensagens m WHERE m.ticket_id = c.ticket_ref_id) as ultima_atividade
            FROM chat_conversas c
            JOIN atend_tickets t ON t.id = c.ticket_ref_id
            WHERE c.tipo = 'ticket'
        """)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception: return []


def listar_conversas_usuario(user_id: int) -> list:
    """Une DM/grupo (participante), canal de departamento (permissao) e ticket
    (permissao atendimento.ver), ordenado por atividade mais recente."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT c.*, (SELECT MAX(created_at) FROM chat_mensagens m WHERE m.conversa_id = c.id) as ultima_atividade
            FROM chat_conversas c
            JOIN chat_participantes p ON p.conversa_id = c.id AND p.user_id = $1 AND p.saiu_em IS NULL
            WHERE c.tipo IN ('dm', 'grupo')
        """, user_id)
        return [dict(r) for r in rows]
    try: internas = run_async(_go())
    except Exception: internas = []

    todas = internas + _canais_departamento_permitidos(user_id) + _conversas_ticket_permitidas(user_id)
    todas.sort(key=lambda c: c.get("ultima_atividade") or c.get("created_at") or datetime.min, reverse=True)
    return todas


def buscar_mensagens(user_id: int, termo: str) -> list:
    conversa_ids = [c["id"] for c in listar_conversas_usuario(user_id) if c["tipo"] in ("dm", "grupo", "canal_departamento")]
    if not conversa_ids:
        return []
    async def _go():
        db = await get_db()
        rows = await db.fetch(
            "SELECT * FROM chat_mensagens WHERE conversa_id = ANY($1::int[]) AND texto ILIKE $2 "
            "AND excluido_em IS NULL ORDER BY created_at DESC LIMIT 50",
            conversa_ids, f"%{termo}%")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"buscar_mensagens: {e}"); return []
```

- [ ] **Step 2: Adicionar os testes de mensagem em `hermes_agents/tests/test_chat.py`**

```python
class TestChatMensagens(unittest.TestCase):
    def test_listar_mensagens_erro_de_db_retorna_lista_vazia(self):
        with patch("core.chat.get_db", side_effect=RuntimeError("sem conexao")):
            self.assertEqual(chat.listar_mensagens(1), [])

    def test_editar_mensagem_sem_ser_autor_retorna_error(self):
        async def _fetchrow(*a, **kw): return None
        with patch("core.chat.get_db") as mock_get_db:
            mock_db = AsyncMock(fetchrow=_fetchrow)
            mock_get_db.return_value = mock_db
            resultado = chat.editar_mensagem(1, 999, "novo texto")
        self.assertIn("error", resultado)

    def test_listar_conversas_usuario_ordena_por_atividade_recente(self):
        with patch("core.chat.get_db") as mock_get_db, \
             patch("core.chat._canais_departamento_permitidos", return_value=[]), \
             patch("core.chat._conversas_ticket_permitidas", return_value=[]):
            async def _fetch(*a, **kw):
                return [
                    {"id": 1, "tipo": "dm", "created_at": "2026-01-01", "ultima_atividade": "2026-01-01"},
                    {"id": 2, "tipo": "grupo", "created_at": "2026-01-01", "ultima_atividade": "2026-06-01"},
                ]
            mock_db = AsyncMock(fetch=_fetch)
            mock_get_db.return_value = mock_db
            resultado = chat.listar_conversas_usuario(7)
        self.assertEqual(resultado[0]["id"], 2)
```

- [ ] **Step 3: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_chat.py -v`
Expected: 6 passed

- [ ] **Step 4: Commit**

```bash
git add hermes_agents/core/chat.py hermes_agents/tests/test_chat.py
git commit -m "feat: mensagens, leitura, busca e listagem unificada de conversas do chat"
```

---

### Task 3: Anexos e presença

**Files:**
- Modify: `hermes_agents/core/chat.py`

**Interfaces:**
- Produces: `salvar_anexo(nome_arquivo: str, mime: str, tamanho_bytes: int, storage_path: str, enviado_por: int) -> dict`, `obter_anexo(anexo_id: int) -> dict`, `conversa_do_anexo(anexo_id: int)`, `atualizar_presenca(user_id: int, status: str) -> dict`, `obter_presenca(user_id: int) -> dict`

- [ ] **Step 1: Adicionar anexos e presença ao final de `hermes_agents/core/chat.py`**

```python
# ── Anexos ──

def salvar_anexo(nome_arquivo: str, mime: str, tamanho_bytes: int, storage_path: str, enviado_por: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "INSERT INTO chat_anexos (nome_arquivo, mime, tamanho_bytes, storage_path, enviado_por) "
            "VALUES ($1,$2,$3,$4,$5) RETURNING *",
            nome_arquivo, mime, tamanho_bytes, storage_path, enviado_por)
        return dict(row)
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def obter_anexo(anexo_id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM chat_anexos WHERE id=$1", anexo_id)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def conversa_do_anexo(anexo_id: int):
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT conversa_id FROM chat_mensagens WHERE anexo_id=$1", anexo_id)
        return row["conversa_id"] if row else None
    try: return run_async(_go())
    except Exception: return None


# ── Presenca ──

def atualizar_presenca(user_id: int, status: str) -> dict:
    async def _go():
        db = await get_db()
        await db.execute(
            "INSERT INTO chat_presenca (user_id, status, last_seen) VALUES ($1,$2,NOW()) "
            "ON CONFLICT (user_id) DO UPDATE SET status=$2, last_seen=NOW()",
            user_id, status)
        return {"success": True}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def obter_presenca(user_id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM chat_presenca WHERE user_id=$1", user_id)
        return dict(row) if row else {"user_id": user_id, "status": "offline", "last_seen": None}
    try: return run_async(_go())
    except Exception: return {"user_id": user_id, "status": "offline", "last_seen": None}


def conversa_id_do_ticket(ticket_id: int):
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT id FROM chat_conversas WHERE tipo='ticket' AND ticket_ref_id=$1", ticket_id)
        return row["id"] if row else None
    try: return run_async(_go())
    except Exception: return None


def criar_conversa_ticket(ticket_id: int, criado_por: int = None) -> dict:
    """Cria (ou retorna) a conversa de chat vinculada a um ticket de atendimento —
    ponte sem migrar dado: a mensagem em si continua em atend_mensagens."""
    existente_id = conversa_id_do_ticket(ticket_id)
    if existente_id:
        return _obter_conversa(existente_id)
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "INSERT INTO chat_conversas (tipo, ticket_ref_id, criado_por) VALUES ('ticket', $1, $2) RETURNING *",
            ticket_id, criado_por)
        return dict(row)
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}
```

- [ ] **Step 2: Adicionar teste da ponte com ticket em `hermes_agents/tests/test_chat.py`**

```python
class TestChatPonteTicket(unittest.TestCase):
    def test_criar_conversa_ticket_reaproveita_existente(self):
        with patch("core.chat.conversa_id_do_ticket", return_value=42), \
             patch("core.chat._obter_conversa", return_value={"id": 42, "tipo": "ticket", "ticket_ref_id": 7}) as mock_obter:
            resultado = chat.criar_conversa_ticket(7)
        self.assertEqual(resultado["id"], 42)
        mock_obter.assert_called_once_with(42)
```

- [ ] **Step 3: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_chat.py -v`
Expected: 7 passed

- [ ] **Step 4: Commit**

```bash
git add hermes_agents/core/chat.py hermes_agents/tests/test_chat.py
git commit -m "feat: anexos, presenca e ponte de conversa com ticket de atendimento"
```

---

### Task 4: Ligar a ponte de ticket em `core/atendimento.py`

**Files:**
- Modify: `hermes_agents/core/atendimento.py:121-149`

**Interfaces:**
- Consumes: `core.chat.criar_conversa_ticket(ticket_id, criado_por=None)` (Task 3), `core.chat.conversa_id_do_ticket(ticket_id)` (Task 3), `core.chat_ws.broadcast_para_participantes(conversa_id, evento)` (Task 6 — este task só referencia a função; ela é implementada na Task 6, então rode este Task só depois da Task 6, ou deixe o import lazy dentro da função como abaixo, que já é seguro por ser resolvido em tempo de chamada, não de import do módulo)

- [ ] **Step 1: Editar `criar_ticket` para criar a conversa-ponte**

Em `hermes_agents/core/atendimento.py`, dentro de `criar_ticket` (linha ~134), trocar:

```python
    return create("tickets", {
        "cliente": cliente, "assunto": assunto, "canal": canal,
        "prioridade": prioridade, "status": "aberto", "data_abertura": hoje(),
        "sla_vencimento": sla_data["sla_vencimento"],
        "tempo_resposta_min": sla_data["tempo_resposta_min"],
    })
```

por:

```python
    ticket = create("tickets", {
        "cliente": cliente, "assunto": assunto, "canal": canal,
        "prioridade": prioridade, "status": "aberto", "data_abertura": hoje(),
        "sla_vencimento": sla_data["sla_vencimento"],
        "tempo_resposta_min": sla_data["tempo_resposta_min"],
    })
    if not ticket.get("error"):
        from core.chat import criar_conversa_ticket
        criar_conversa_ticket(ticket["id"])
    return ticket
```

- [ ] **Step 2: Editar `adicionar_mensagem` para propagar a mensagem no WebSocket do chat**

Trocar:

```python
def adicionar_mensagem(ticket_id: int, remetente: str, conteudo: str, tipo="texto") -> dict:
    return create("mensagens", {"ticket_id": ticket_id, "remetente": remetente,
        "conteudo": conteudo, "tipo": tipo, "enviado_em": hoje()})
```

por:

```python
def adicionar_mensagem(ticket_id: int, remetente: str, conteudo: str, tipo="texto") -> dict:
    mensagem = create("mensagens", {"ticket_id": ticket_id, "remetente": remetente,
        "conteudo": conteudo, "tipo": tipo, "enviado_em": hoje()})
    if not mensagem.get("error"):
        from core.chat import conversa_id_do_ticket
        from core.chat_ws import broadcast_para_participantes
        conversa_id = conversa_id_do_ticket(ticket_id)
        if conversa_id:
            broadcast_para_participantes(conversa_id, {
                "evento": "nova_mensagem", "ticket_id": ticket_id,
                "mensagem": {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in mensagem.items()},
            })
    return mensagem
```

- [ ] **Step 2b: Adicionar teste garantindo que `criar_ticket` chama a ponte**

Em `hermes_agents/tests/test_atendimento_seguranca.py`, adicionar:

```python
    def test_criar_ticket_cria_conversa_ponte_no_chat(self):
        with patch("core.atendimento.create", return_value={"id": 55}), \
             patch("core.chat.criar_conversa_ticket") as mock_ponte:
            from core.atendimento import criar_ticket
            criar_ticket("Cliente X", "Duvida sobre pedido")
        mock_ponte.assert_called_once_with(55)
```

- [ ] **Step 3: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_atendimento_seguranca.py -v`
Expected: todos passam, incluindo o novo caso

- [ ] **Step 4: Commit**

```bash
git add hermes_agents/core/atendimento.py hermes_agents/tests/test_atendimento_seguranca.py
git commit -m "feat: ticket de atendimento cria conversa-ponte e propaga mensagem no chat"
```

---

### Task 5: Blueprint REST `/api/chat/*`

**Files:**
- Create: `hermes_agents/routes/chat.py`
- Modify: `hermes_agents/tests/test_chat.py`

**Interfaces:**
- Consumes: todas as funções de `core/chat.py` (Tasks 1-3), `core.rbac.usuario_atual_da_request()`
- Produces: blueprint `chat_bp` com rotas `/api/chat/conversas`, `/api/chat/conversas/<id>/mensagens`, `/api/chat/mensagens/<id>`, `/api/chat/anexos`, `/api/chat/anexos/<id>`, `/api/chat/conversas/<id>/participantes[/<membro_id>]`, `/api/chat/conversas/<id>/lido`, `/api/chat/busca`, `/api/chat/canais-departamento`

- [ ] **Step 1: Criar `hermes_agents/routes/chat.py`**

```python
"""Rotas REST do Chat Interno — /api/chat/*"""
import os, time
from flask import Blueprint, request, jsonify, send_file
from core.rbac import usuario_atual_da_request
from core.chat import (
    criar_conversa_dm, criar_conversa_grupo, listar_conversas_usuario,
    listar_mensagens, enviar_mensagem, editar_mensagem, excluir_mensagem,
    marcar_lido, adicionar_participante, remover_participante, papel_do_usuario,
    usuario_e_participante, buscar_mensagens, listar_canais_departamento,
    salvar_anexo, obter_anexo, conversa_do_anexo,
)
from core.chat_ws import broadcast_para_participantes

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "chat")
TAMANHO_MAXIMO_BYTES = 25 * 1024 * 1024


def _serializar(mensagem: dict) -> dict:
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in mensagem.items()}


@chat_bp.route("/conversas", methods=["GET"])
def chat_listar_conversas():
    usuario = usuario_atual_da_request()
    if not usuario.get("user_id"):
        return jsonify({"error": "Nao autenticado"}), 401
    return jsonify({"data": listar_conversas_usuario(int(usuario["user_id"]))})


@chat_bp.route("/conversas", methods=["POST"])
def chat_criar_conversa():
    usuario = usuario_atual_da_request()
    if not usuario.get("user_id"):
        return jsonify({"error": "Nao autenticado"}), 401
    data = request.json or {}
    tipo = data.get("tipo")
    criado_por = int(usuario["user_id"])
    if tipo == "dm":
        outro_user_id = data.get("user_id")
        if not outro_user_id:
            return jsonify({"error": "user_id obrigatorio para DM"}), 400
        return jsonify(criar_conversa_dm(criado_por, int(outro_user_id)))
    if tipo == "grupo":
        return jsonify(criar_conversa_grupo(
            data.get("nome", ""), data.get("descricao", ""), criado_por,
            [int(u) for u in data.get("participantes", [])],
            data.get("departamento"), data.get("loja_id")))
    return jsonify({"error": "tipo invalido"}), 400


@chat_bp.route("/conversas/<int:conversa_id>/mensagens", methods=["GET"])
def chat_listar_mensagens(conversa_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id or not usuario_e_participante(conversa_id, int(user_id)):
        return jsonify({"error": "Permissao negada"}), 403
    antes_de = request.args.get("antes_de")
    return jsonify({"data": listar_mensagens(conversa_id, antes_de)})


@chat_bp.route("/conversas/<int:conversa_id>/mensagens", methods=["POST"])
def chat_enviar_mensagem(conversa_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id or not usuario_e_participante(conversa_id, int(user_id)):
        return jsonify({"error": "Permissao negada"}), 403
    data = request.json or {}
    mensagem = enviar_mensagem(conversa_id, int(user_id), data.get("texto", ""),
                                data.get("anexo_id"), data.get("thread_pai_id"))
    if not mensagem.get("error"):
        broadcast_para_participantes(conversa_id, {"evento": "nova_mensagem", "mensagem": _serializar(mensagem)})
    return jsonify(mensagem)


@chat_bp.route("/mensagens/<int:mensagem_id>", methods=["PUT"])
def chat_editar_mensagem(mensagem_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id:
        return jsonify({"error": "Nao autenticado"}), 401
    data = request.json or {}
    mensagem = editar_mensagem(mensagem_id, int(user_id), data.get("texto", ""))
    if not mensagem.get("error"):
        broadcast_para_participantes(mensagem["conversa_id"], {"evento": "mensagem_editada", "mensagem": _serializar(mensagem)})
    return jsonify(mensagem)


@chat_bp.route("/mensagens/<int:mensagem_id>", methods=["DELETE"])
def chat_excluir_mensagem(mensagem_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id:
        return jsonify({"error": "Nao autenticado"}), 401
    mensagem = excluir_mensagem(mensagem_id, int(user_id))
    if not mensagem.get("error"):
        broadcast_para_participantes(mensagem["conversa_id"], {"evento": "mensagem_excluida", "mensagem": _serializar(mensagem)})
    return jsonify(mensagem)


@chat_bp.route("/anexos", methods=["POST"])
def chat_upload_anexo():
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id:
        return jsonify({"error": "Nao autenticado"}), 401
    arquivo = request.files.get("arquivo")
    if not arquivo:
        return jsonify({"error": "arquivo obrigatorio"}), 400
    conteudo = arquivo.read()
    if len(conteudo) > TAMANHO_MAXIMO_BYTES:
        return jsonify({"error": "Arquivo maior que 25MB"}), 413
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    nome_seguro = f"{int(user_id)}_{int(time.time() * 1000)}_{arquivo.filename}"
    with open(os.path.join(UPLOAD_DIR, nome_seguro), "wb") as f:
        f.write(conteudo)
    return jsonify(salvar_anexo(arquivo.filename, arquivo.mimetype, len(conteudo), nome_seguro, int(user_id)))


@chat_bp.route("/anexos/<int:anexo_id>", methods=["GET"])
def chat_download_anexo(anexo_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id:
        return jsonify({"error": "Nao autenticado"}), 401
    conversa_id = conversa_do_anexo(anexo_id)
    if conversa_id is None or not usuario_e_participante(conversa_id, int(user_id)):
        return jsonify({"error": "Permissao negada"}), 403
    anexo = obter_anexo(anexo_id)
    if anexo.get("error"):
        return jsonify(anexo), 404
    return send_file(os.path.join(UPLOAD_DIR, anexo["storage_path"]), download_name=anexo["nome_arquivo"])


@chat_bp.route("/conversas/<int:conversa_id>/participantes", methods=["POST"])
def chat_adicionar_participante(conversa_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id:
        return jsonify({"error": "Nao autenticado"}), 401
    if papel_do_usuario(conversa_id, int(user_id)) not in ("owner", "admin", "moderador"):
        return jsonify({"error": "Permissao negada"}), 403
    data = request.json or {}
    novo_user_id = data.get("user_id")
    if not novo_user_id:
        return jsonify({"error": "user_id obrigatorio"}), 400
    return jsonify(adicionar_participante(conversa_id, int(novo_user_id)))


@chat_bp.route("/conversas/<int:conversa_id>/participantes/<int:membro_id>", methods=["DELETE"])
def chat_remover_participante(conversa_id, membro_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id:
        return jsonify({"error": "Nao autenticado"}), 401
    if papel_do_usuario(conversa_id, int(user_id)) not in ("owner", "admin", "moderador"):
        return jsonify({"error": "Permissao negada"}), 403
    return jsonify(remover_participante(conversa_id, membro_id))


@chat_bp.route("/conversas/<int:conversa_id>/lido", methods=["POST"])
def chat_marcar_lido(conversa_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id or not usuario_e_participante(conversa_id, int(user_id)):
        return jsonify({"error": "Permissao negada"}), 403
    data = request.json or {}
    return jsonify(marcar_lido(conversa_id, int(user_id), data.get("ultima_mensagem_id")))


@chat_bp.route("/busca", methods=["GET"])
def chat_busca():
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id:
        return jsonify({"error": "Nao autenticado"}), 401
    return jsonify({"data": buscar_mensagens(int(user_id), request.args.get("q", ""))})


@chat_bp.route("/canais-departamento", methods=["GET"])
def chat_canais_departamento():
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id:
        return jsonify({"error": "Nao autenticado"}), 401
    return jsonify({"data": listar_canais_departamento(int(user_id))})
```

- [ ] **Step 2: Criar `hermes_agents/core/chat_ws.py` com um stub de `broadcast_para_participantes` (implementação completa na Task 6) para o import acima não quebrar**

```python
"""Chat WebSocket — registro de conexoes em memoria (processo unico) e broadcast."""
import json, threading

_lock = threading.Lock()
_conexoes = {}  # user_id -> list[ws]


def registrar_conexao(user_id: int, ws) -> None:
    with _lock:
        _conexoes.setdefault(user_id, []).append(ws)


def remover_conexao(user_id: int, ws) -> None:
    with _lock:
        conexoes = _conexoes.get(user_id, [])
        if ws in conexoes:
            conexoes.remove(ws)
        if not conexoes and user_id in _conexoes:
            del _conexoes[user_id]


def enviar_para_usuario(user_id: int, evento: dict) -> None:
    with _lock:
        conexoes = list(_conexoes.get(user_id, []))
    payload = json.dumps(evento)
    for ws in conexoes:
        try:
            ws.send(payload)
        except Exception:
            remover_conexao(user_id, ws)


def broadcast_para_participantes(conversa_id: int, evento: dict) -> None:
    from core.chat import participantes_ids
    for user_id in participantes_ids(conversa_id):
        enviar_para_usuario(user_id, evento)
```

- [ ] **Step 3: Adicionar os testes de permissão em `hermes_agents/tests/test_chat.py`**

```python
from flask import Flask
from routes.chat import chat_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(chat_bp)
    return app.test_client()


class TestChatRotasPermissao(unittest.TestCase):
    def setUp(self):
        self.client = _app()

    def test_listar_mensagens_nao_participante_nega(self):
        token = rbac.gerar_token_sessao(11, "u@x.com", "Vendedor")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("routes.chat.usuario_e_participante", return_value=False):
            r = self.client.get("/api/chat/conversas/5/mensagens", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_listar_mensagens_participante_libera(self):
        token = rbac.gerar_token_sessao(11, "u@x.com", "Vendedor")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("routes.chat.usuario_e_participante", return_value=True), \
             patch("routes.chat.listar_mensagens", return_value=[{"id": 1, "texto": "oi"}]) as mock_listar:
            r = self.client.get("/api/chat/conversas/5/mensagens", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_listar.assert_called_once()

    def test_enviar_mensagem_nao_participante_nega(self):
        token = rbac.gerar_token_sessao(11, "u@x.com", "Vendedor")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("routes.chat.usuario_e_participante", return_value=False), \
             patch("routes.chat.enviar_mensagem") as mock_enviar:
            r = self.client.post("/api/chat/conversas/5/mensagens", json={"texto": "oi"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_enviar.assert_not_called()

    def test_adicionar_participante_exige_papel_admin(self):
        token = rbac.gerar_token_sessao(11, "u@x.com", "Vendedor")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("routes.chat.papel_do_usuario", return_value="membro"), \
             patch("routes.chat.adicionar_participante") as mock_add:
            r = self.client.post("/api/chat/conversas/5/participantes", json={"user_id": 9}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_add.assert_not_called()

    def test_adicionar_participante_owner_libera(self):
        token = rbac.gerar_token_sessao(11, "u@x.com", "Vendedor")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("routes.chat.papel_do_usuario", return_value="owner"), \
             patch("routes.chat.adicionar_participante", return_value={"conversa_id": 5, "user_id": 9}) as mock_add:
            r = self.client.post("/api/chat/conversas/5/participantes", json={"user_id": 9}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_add.assert_called_once()
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_chat.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/routes/chat.py hermes_agents/core/chat_ws.py hermes_agents/tests/test_chat.py
git commit -m "feat: blueprint REST /api/chat com checagem de participante/papel por rota"
```

---

### Task 6: WebSocket `/ws/chat` e registro no app

**Files:**
- Create: `hermes_agents/routes/chat_ws.py`
- Modify: `hermes_agents/athena_bridge.py`
- Modify: `hermes_agents/requirements.txt`
- Modify: `hermes_agents/tests/test_chat.py`

**Interfaces:**
- Consumes: `core.chat_ws.registrar_conexao/remover_conexao/broadcast_para_participantes/enviar_para_usuario` (Task 5), `core.chat.enviar_mensagem/participantes_ids/atualizar_presenca/marcar_lido` (Tasks 1-3), `core.rbac.verificar_token_sessao`
- Produces: `init_sock(app)` — chamado a partir de `athena_bridge.py`

- [ ] **Step 1: Adicionar `flask-sock` em `hermes_agents/requirements.txt`**

```
flask-sock>=0.7.0
```

- [ ] **Step 2: Criar `hermes_agents/routes/chat_ws.py`**

```python
"""WebSocket do chat interno — /ws/chat."""
import json
from flask import request
from flask_sock import Sock

from core.rbac import verificar_token_sessao
from core.chat import enviar_mensagem, participantes_ids, atualizar_presenca, marcar_lido
from core.chat_ws import registrar_conexao, remover_conexao, broadcast_para_participantes, enviar_para_usuario

sock = Sock()


def init_sock(app):
    sock.init_app(app)

    @sock.route("/ws/chat")
    def chat_socket(ws):
        token = request.args.get("token", "")
        payload = verificar_token_sessao(token)
        if not payload or not payload.get("user_id"):
            ws.close()
            return
        user_id = int(payload["user_id"])
        registrar_conexao(user_id, ws)
        atualizar_presenca(user_id, "online")
        try:
            while True:
                raw = ws.receive()
                if raw is None:
                    break
                try:
                    dados = json.loads(raw)
                except ValueError:
                    continue
                _processar_evento(user_id, dados)
        finally:
            remover_conexao(user_id, ws)
            atualizar_presenca(user_id, "offline")


def _processar_evento(user_id: int, dados: dict) -> None:
    tipo = dados.get("tipo")
    if tipo == "enviar_mensagem":
        conversa_id = dados.get("conversa_id")
        if user_id not in participantes_ids(conversa_id):
            return
        mensagem = enviar_mensagem(conversa_id, user_id, dados.get("texto", ""),
                                    dados.get("anexo_id"), dados.get("thread_pai_id"))
        if not mensagem.get("error"):
            broadcast_para_participantes(conversa_id, {
                "evento": "nova_mensagem",
                "mensagem": {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in mensagem.items()},
            })
    elif tipo == "digitando":
        conversa_id = dados.get("conversa_id")
        broadcast_para_participantes(conversa_id, {
            "evento": "usuario_digitando", "conversa_id": conversa_id, "user_id": user_id,
        })
    elif tipo == "presenca":
        status = dados.get("status", "online")
        atualizar_presenca(user_id, status)
        for outro_id in dados.get("notificar", []):
            enviar_para_usuario(outro_id, {"evento": "presenca_atualizada", "user_id": user_id, "status": status})
    elif tipo == "lido":
        conversa_id = dados.get("conversa_id")
        ultima_id = dados.get("ultima_mensagem_id")
        marcar_lido(conversa_id, user_id, ultima_id)
        broadcast_para_participantes(conversa_id, {
            "evento": "confirmacao_leitura", "conversa_id": conversa_id,
            "user_id": user_id, "ultima_mensagem_id": ultima_id,
        })
```

- [ ] **Step 3: Registrar o blueprint REST e o WebSocket em `hermes_agents/athena_bridge.py`**

Adicionar junto aos outros imports de rota (perto da linha 223, após `from routes.bi import bi_bp`):

```python
from routes.chat import chat_bp
from routes.chat_ws import init_sock
```

Adicionar junto aos outros `register_blueprint` (perto da linha 253, após `app.register_blueprint(bi_bp)`):

```python
app.register_blueprint(chat_bp)
init_sock(app)
```

Trocar a chamada final do servidor (linha 1935) de:

```python
    app.run(host="0.0.0.0", port=port, debug=debug)
```

por:

```python
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
```

`threaded=True` é necessário porque cada conexão WebSocket fica bloqueada em `ws.receive()` numa thread só sua — sem isso, uma segunda conexão trava esperando a primeira.

- [ ] **Step 4: Adicionar teste de isolamento de broadcast em `hermes_agents/tests/test_chat.py`**

```python
class TestChatWebsocketBroadcastIsolamento(unittest.TestCase):
    def test_broadcast_so_alcanca_participantes(self):
        from core.chat_ws import broadcast_para_participantes, registrar_conexao, remover_conexao

        enviados = []

        class FakeWs:
            def __init__(self, uid): self.uid = uid
            def send(self, payload): enviados.append((self.uid, payload))

        ws_membro = FakeWs(1)
        ws_estranho = FakeWs(2)
        registrar_conexao(1, ws_membro)
        registrar_conexao(2, ws_estranho)
        try:
            with patch("core.chat.participantes_ids", return_value=[1]):
                broadcast_para_participantes(99, {"evento": "nova_mensagem"})
        finally:
            remover_conexao(1, ws_membro)
            remover_conexao(2, ws_estranho)

        uids_notificados = [uid for uid, _ in enviados]
        self.assertIn(1, uids_notificados)
        self.assertNotIn(2, uids_notificados)
```

- [ ] **Step 5: Instalar a dependência nova e rodar os testes**

Run: `cd hermes_agents && pip install -r requirements.txt && python -m pytest tests/test_chat.py -v`
Expected: 13 passed

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/chat_ws.py hermes_agents/athena_bridge.py hermes_agents/requirements.txt hermes_agents/tests/test_chat.py
git commit -m "feat: websocket /ws/chat com flask-sock, registrado no app principal"
```

---

### Task 7: Tipos TypeScript e cliente de API do chat

**Files:**
- Create: `web/src/lib/types/chat.ts`
- Modify: `web/src/lib/api.ts`

**Interfaces:**
- Produces: tipos `TipoConversa`, `ConversaChat`, `MensagemChat`, `AnexoChat`; `api.chat.*` (listarConversas, criarConversaDm, criarConversaGrupo, listarMensagens, enviarMensagem, editarMensagem, excluirMensagem, marcarLido, buscar, canaisDepartamento, uploadAnexo, urlDownloadAnexo)

- [ ] **Step 1: Criar `web/src/lib/types/chat.ts`**

```typescript
export type TipoConversa = "dm" | "grupo" | "canal_departamento" | "ticket";

export interface ConversaChat {
  id: number;
  tipo: TipoConversa;
  nome: string | null;
  descricao: string | null;
  foto_url: string | null;
  departamento: string | null;
  loja_id: number | null;
  ticket_ref_id: number | null;
  criado_por: number | null;
  created_at: string;
  ultima_atividade: string | null;
  assunto?: string;
  cliente?: string;
  canal_externo?: string;
  ticket_status?: string;
}

export interface MensagemChat {
  id: number;
  conversa_id: number;
  thread_pai_id: number | null;
  remetente_id: number | null;
  texto: string | null;
  anexo_id: number | null;
  created_at: string;
  editado_em: string | null;
  excluido_em: string | null;
}

export interface AnexoChat {
  id: number;
  nome_arquivo: string;
  mime: string | null;
  tamanho_bytes: number | null;
  storage_path: string;
  enviado_por: number | null;
  created_at: string;
}
```

- [ ] **Step 2: Adicionar o import dos tipos e o objeto `chat` em `web/src/lib/api.ts`**

No topo do arquivo, junto aos outros imports de tipos (após o bloco `import type { ... } from "@/lib/types/domain";`):

```typescript
import type { ConversaChat, MensagemChat, AnexoChat } from "@/lib/types/chat";
```

Dentro do objeto `export const api = { ... }`, adicionar a propriedade `chat`:

```typescript
  chat: {
    listarConversas: () => request<{ data: ConversaChat[] }>("/api/chat/conversas"),
    criarConversaDm: (userId: number) =>
      request<ConversaChat>("/api/chat/conversas", {
        method: "POST", body: JSON.stringify({ tipo: "dm", user_id: userId }),
      }),
    criarConversaGrupo: (nome: string, descricao: string, participantes: number[], departamento?: string, lojaId?: number) =>
      request<ConversaChat>("/api/chat/conversas", {
        method: "POST",
        body: JSON.stringify({ tipo: "grupo", nome, descricao, participantes, departamento, loja_id: lojaId }),
      }),
    listarMensagens: (conversaId: number, antesDe?: string) =>
      request<{ data: MensagemChat[] }>(
        `/api/chat/conversas/${conversaId}/mensagens${antesDe ? `?antes_de=${encodeURIComponent(antesDe)}` : ""}`
      ),
    enviarMensagem: (conversaId: number, texto: string, anexoId?: number, threadPaiId?: number) =>
      request<MensagemChat>(`/api/chat/conversas/${conversaId}/mensagens`, {
        method: "POST", body: JSON.stringify({ texto, anexo_id: anexoId, thread_pai_id: threadPaiId }),
      }),
    editarMensagem: (mensagemId: number, texto: string) =>
      request<MensagemChat>(`/api/chat/mensagens/${mensagemId}`, {
        method: "PUT", body: JSON.stringify({ texto }),
      }),
    excluirMensagem: (mensagemId: number) =>
      request<MensagemChat>(`/api/chat/mensagens/${mensagemId}`, { method: "DELETE" }),
    marcarLido: (conversaId: number, ultimaMensagemId: number) =>
      request<{ success: boolean }>(`/api/chat/conversas/${conversaId}/lido`, {
        method: "POST", body: JSON.stringify({ ultima_mensagem_id: ultimaMensagemId }),
      }),
    buscar: (termo: string) => request<{ data: MensagemChat[] }>(`/api/chat/busca?q=${encodeURIComponent(termo)}`),
    canaisDepartamento: () => request<{ data: ConversaChat[] }>("/api/chat/canais-departamento"),
    uploadAnexo: async (arquivo: File): Promise<AnexoChat> => {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const formData = new FormData();
      formData.append("arquivo", arquivo);
      const res = await fetch("/api/chat/anexos", {
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
    urlDownloadAnexo: (anexoId: number) => `/api/chat/anexos/${anexoId}`,
  },
```

- [ ] **Step 3: Verificar que o projeto compila**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros novos relacionados a `chat.ts`/`api.ts`

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/types/chat.ts web/src/lib/api.ts
git commit -m "feat: tipos e cliente de API do chat interno no frontend"
```

---

### Task 8: Hook `useChatSocket`

**Files:**
- Create: `web/src/lib/useChatSocket.ts`

**Interfaces:**
- Consumes: nenhuma interface de outras tasks (só `localStorage`/`WebSocket` nativos do browser)
- Produces: `useChatSocket()` retornando `{ conectado: boolean, on: (fn) => () => void, enviarMensagem, marcarDigitando, marcarLido }`

- [ ] **Step 1: Criar `web/src/lib/useChatSocket.ts`**

```typescript
"use client";
import { useEffect, useRef, useState, useCallback } from "react";

export interface EventoChatSocket {
  evento: "nova_mensagem" | "mensagem_editada" | "mensagem_excluida" | "usuario_digitando" | "presenca_atualizada" | "confirmacao_leitura";
  [chave: string]: unknown;
}

type Listener = (evento: EventoChatSocket) => void;

export function useChatSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const listenersRef = useRef<Set<Listener>>(new Set());
  const tentativasRef = useRef(0);
  const [conectado, setConectado] = useState(false);

  const conectar = useCallback(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) return;
    const protocolo = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocolo}//${window.location.host}/ws/chat?token=${encodeURIComponent(token)}`);

    ws.onopen = () => { setConectado(true); tentativasRef.current = 0; };
    ws.onmessage = (ev) => {
      try {
        const dados = JSON.parse(ev.data) as EventoChatSocket;
        listenersRef.current.forEach((fn) => fn(dados));
      } catch {
        // ignora payload invalido
      }
    };
    ws.onclose = () => {
      setConectado(false);
      const espera = Math.min(30000, 1000 * 2 ** tentativasRef.current);
      tentativasRef.current += 1;
      setTimeout(conectar, espera);
    };
    ws.onerror = () => ws.close();
    wsRef.current = ws;
  }, []);

  useEffect(() => {
    conectar();
    return () => { wsRef.current?.close(); };
  }, [conectar]);

  const enviar = useCallback((dados: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(dados));
    }
  }, []);

  const on = useCallback((fn: Listener) => {
    listenersRef.current.add(fn);
    return () => { listenersRef.current.delete(fn); };
  }, []);

  const enviarMensagem = useCallback(
    (conversaId: number, texto: string, anexoId?: number, threadPaiId?: number) => {
      enviar({ tipo: "enviar_mensagem", conversa_id: conversaId, texto, anexo_id: anexoId, thread_pai_id: threadPaiId });
    },
    [enviar]
  );

  const marcarDigitando = useCallback(
    (conversaId: number) => enviar({ tipo: "digitando", conversa_id: conversaId }),
    [enviar]
  );

  const marcarLido = useCallback(
    (conversaId: number, ultimaMensagemId: number) =>
      enviar({ tipo: "lido", conversa_id: conversaId, ultima_mensagem_id: ultimaMensagemId }),
    [enviar]
  );

  return { conectado, on, enviarMensagem, marcarDigitando, marcarLido };
}
```

- [ ] **Step 2: Verificar que o projeto compila**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros novos relacionados a `useChatSocket.ts`

- [ ] **Step 3: Commit**

```bash
git add web/src/lib/useChatSocket.ts
git commit -m "feat: hook useChatSocket com reconexao automatica"
```

---

### Task 9: Componentes de UI do chat (sidebar, painel de mensagens, thread)

**Files:**
- Create: `web/src/app/chat/_components/ConversaSidebar.tsx`
- Create: `web/src/app/chat/_components/MensagensPainel.tsx`
- Create: `web/src/app/chat/_components/ThreadPainel.tsx`

**Interfaces:**
- Consumes: `ConversaChat`, `MensagemChat` (Task 7), `useChatSocket` (Task 8)
- Produces: componentes `ConversaSidebar`, `MensagensPainel`, `ThreadPainel` (usados na Task 10)

- [ ] **Step 1: Criar `web/src/app/chat/_components/ConversaSidebar.tsx`**

```typescript
"use client";
import type { ConversaChat } from "@/lib/types/chat";

const ICONE_TIPO: Record<string, string> = {
  dm: "💬", grupo: "👥", canal_departamento: "🏢", ticket: "🎫",
};

export default function ConversaSidebar({
  conversas, conversaSelecionadaId, onSelecionar,
}: {
  conversas: ConversaChat[];
  conversaSelecionadaId: number | null;
  onSelecionar: (conversa: ConversaChat) => void;
}) {
  return (
    <div className="w-72 shrink-0 border-r border-neutral-800 bg-neutral-900 overflow-y-auto">
      <div className="px-4 py-3 border-b border-neutral-800">
        <h1 className="text-sm font-bold text-neutral-200">Chat</h1>
      </div>
      {conversas.map((c) => {
        const titulo = c.tipo === "ticket" ? `${c.cliente || "Cliente"} — ${c.canal_externo || ""}` : (c.nome || "Conversa");
        return (
          <button
            key={`${c.tipo}-${c.id}`}
            onClick={() => onSelecionar(c)}
            className={`w-full text-left px-4 py-3 border-b border-neutral-800/50 hover:bg-neutral-800 ${
              conversaSelecionadaId === c.id ? "bg-neutral-800" : ""
            }`}
          >
            <div className="flex items-center gap-2">
              <span>{ICONE_TIPO[c.tipo]}</span>
              <span className="text-sm text-neutral-200 truncate">{titulo}</span>
            </div>
            {c.tipo === "ticket" && c.assunto && (
              <p className="text-[11px] text-neutral-500 mt-0.5 truncate">{c.assunto}</p>
            )}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Criar `web/src/app/chat/_components/MensagensPainel.tsx`**

```typescript
"use client";
import { useState, useEffect, useRef } from "react";
import type { ConversaChat, MensagemChat } from "@/lib/types/chat";
import { api } from "@/lib/api";

export default function MensagensPainel({
  conversa, mensagens, usuarioIdAtual, digitandoUserId, onEnviar, onAbrirThread, onUpload,
}: {
  conversa: ConversaChat;
  mensagens: MensagemChat[];
  usuarioIdAtual: number | null;
  digitandoUserId: number | null;
  onEnviar: (texto: string, anexoId?: number) => void;
  onAbrirThread: (mensagem: MensagemChat) => void;
  onUpload: (arquivo: File) => Promise<number>;
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
    try {
      const anexoId = await onUpload(arquivo);
      onEnviar(`📎 ${arquivo.name}`, anexoId);
    } catch {
      // falha de upload — usuario ve que a mensagem nao apareceu e tenta de novo
    } finally {
      setEnviandoArquivo(false);
      e.target.value = "";
    }
  };

  return (
    <div className="flex-1 flex flex-col">
      <div className="bg-neutral-900 border-b border-neutral-800 px-4 py-3 shrink-0">
        <h2 className="text-sm font-bold text-neutral-200">{conversa.nome || conversa.cliente || "Conversa"}</h2>
        {digitandoUserId && <p className="text-[11px] text-neutral-500">digitando...</p>}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {mensagens.map((m) => (
          <div
            key={m.id}
            className={`max-w-[70%] rounded-lg px-3 py-2 text-sm ${
              m.remetente_id === usuarioIdAtual ? "bg-indigo-700 text-white ml-auto" : "bg-neutral-700 text-neutral-200"
            }`}
          >
            <p>{m.excluido_em ? "[mensagem excluída]" : m.texto}</p>
            <div className="flex items-center gap-2 mt-1">
              <p className="text-[10px] opacity-60">{(m.created_at || "").slice(11, 16)}</p>
              {!m.excluido_em && (
                <button onClick={() => onAbrirThread(m)} className="text-[10px] underline opacity-70">
                  responder em thread
                </button>
              )}
            </div>
          </div>
        ))}
        <div ref={fimRef} />
      </div>

      <div className="p-3 border-t border-neutral-800 shrink-0 flex gap-2">
        <label className="cursor-pointer text-neutral-400 px-2 flex items-center">
          📎
          <input type="file" className="hidden" onChange={selecionarArquivo} disabled={enviandoArquivo} />
        </label>
        <input
          type="text" value={texto} onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && enviar()}
          placeholder="Digite sua mensagem..." autoFocus
          className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200"
        />
        <button onClick={enviar} className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm px-4 py-2 rounded-lg">
          Enviar
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Criar `web/src/app/chat/_components/ThreadPainel.tsx`**

```typescript
"use client";
import { useState, useEffect } from "react";
import type { MensagemChat } from "@/lib/types/chat";
import { api } from "@/lib/api";

export default function ThreadPainel({
  mensagemPai, onFechar, onEnviarResposta,
}: {
  mensagemPai: MensagemChat;
  onFechar: () => void;
  onEnviarResposta: (texto: string, threadPaiId: number) => void;
}) {
  const [respostas, setRespostas] = useState<MensagemChat[]>([]);
  const [texto, setTexto] = useState("");

  useEffect(() => {
    api.chat.listarMensagens(mensagemPai.conversa_id).then((r) => {
      setRespostas(r.data.filter((m) => m.thread_pai_id === mensagemPai.id));
    }).catch(() => {});
  }, [mensagemPai.id, mensagemPai.conversa_id]);

  const enviar = () => {
    if (!texto.trim()) return;
    onEnviarResposta(texto, mensagemPai.id);
    setTexto("");
  };

  return (
    <div className="w-80 shrink-0 border-l border-neutral-800 bg-neutral-900 flex flex-col">
      <div className="px-4 py-3 border-b border-neutral-800 flex items-center justify-between">
        <h3 className="text-sm font-bold text-neutral-200">Thread</h3>
        <button onClick={onFechar} className="text-neutral-500 text-xs">fechar</button>
      </div>
      <div className="p-3 border-b border-neutral-800 bg-neutral-800/50">
        <p className="text-sm text-neutral-300">{mensagemPai.texto}</p>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {respostas.map((r) => (
          <div key={r.id} className="bg-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200">
            {r.texto}
          </div>
        ))}
      </div>
      <div className="p-3 border-t border-neutral-800 flex gap-2">
        <input
          type="text" value={texto} onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && enviar()}
          placeholder="Responder na thread..."
          className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
        />
        <button onClick={enviar} className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-3 py-2 rounded-lg">
          Enviar
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verificar que o projeto compila**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros novos relacionados aos 3 componentes

- [ ] **Step 5: Commit**

```bash
git add "web/src/app/chat/_components"
git commit -m "feat: componentes de sidebar, painel de mensagens e thread do chat"
```

---

### Task 10: Página `/chat`, redirect da rota antiga e item de navegação

**Files:**
- Create: `web/src/app/chat/page.tsx`
- Modify: `web/src/app/atendimento/chat/page.tsx`
- Modify: `web/src/app/layout.tsx:64`

**Interfaces:**
- Consumes: `api.chat.*` (Task 7), `useChatSocket` (Task 8), `ConversaSidebar`/`MensagensPainel`/`ThreadPainel` (Task 9), `useAuth` de `web/src/lib/auth.tsx`

- [ ] **Step 1: Criar `web/src/app/chat/page.tsx`**

```typescript
"use client";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useChatSocket, type EventoChatSocket } from "@/lib/useChatSocket";
import type { ConversaChat, MensagemChat } from "@/lib/types/chat";
import ConversaSidebar from "./_components/ConversaSidebar";
import MensagensPainel from "./_components/MensagensPainel";
import ThreadPainel from "./_components/ThreadPainel";

export default function ChatPage() {
  const { user } = useAuth();
  const usuarioIdAtual = user ? parseInt(user.id, 10) : null;
  const { conectado, on, enviarMensagem, marcarDigitando, marcarLido } = useChatSocket();

  const [conversas, setConversas] = useState<ConversaChat[]>([]);
  const [conversaSelecionada, setConversaSelecionada] = useState<ConversaChat | null>(null);
  const [mensagens, setMensagens] = useState<MensagemChat[]>([]);
  const [threadAberta, setThreadAberta] = useState<MensagemChat | null>(null);
  const [digitandoUserId, setDigitandoUserId] = useState<number | null>(null);

  const carregarConversas = useCallback(() => {
    api.chat.listarConversas().then((r) => setConversas(r.data)).catch(() => {});
  }, []);

  useEffect(() => { carregarConversas(); }, [carregarConversas]);

  const selecionarConversa = useCallback((conversa: ConversaChat) => {
    setConversaSelecionada(conversa);
    setThreadAberta(null);
    api.chat.listarMensagens(conversa.id).then((r) => setMensagens(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    return on((evento: EventoChatSocket) => {
      if (evento.evento === "nova_mensagem") {
        const mensagem = evento.mensagem as MensagemChat;
        if (conversaSelecionada && mensagem.conversa_id === conversaSelecionada.id) {
          setMensagens((atual) => [...atual, mensagem]);
        }
        carregarConversas();
      }
      if (evento.evento === "usuario_digitando" && conversaSelecionada && evento.conversa_id === conversaSelecionada.id) {
        setDigitandoUserId(evento.user_id as number);
        setTimeout(() => setDigitandoUserId(null), 3000);
      }
    });
  }, [on, conversaSelecionada, carregarConversas]);

  const enviar = (texto: string, anexoId?: number) => {
    if (!conversaSelecionada) return;
    if (conversaSelecionada.tipo === "ticket") {
      api.chat.enviarMensagem(conversaSelecionada.id, texto, anexoId).catch(() => {});
      return;
    }
    enviarMensagem(conversaSelecionada.id, texto, anexoId);
  };

  const enviarRespostaThread = (texto: string, threadPaiId: number) => {
    if (!conversaSelecionada) return;
    enviarMensagem(conversaSelecionada.id, texto, undefined, threadPaiId);
  };

  const upload = async (arquivo: File) => {
    const anexo = await api.chat.uploadAnexo(arquivo);
    return anexo.id;
  };

  useEffect(() => {
    if (!conversaSelecionada) return;
    const ultima = mensagens[mensagens.length - 1];
    if (ultima) marcarLido(conversaSelecionada.id, ultima.id);
  }, [mensagens, conversaSelecionada, marcarLido]);

  return (
    <div className="h-screen flex">
      <ConversaSidebar
        conversas={conversas}
        conversaSelecionadaId={conversaSelecionada?.id ?? null}
        onSelecionar={selecionarConversa}
      />
      {conversaSelecionada ? (
        <MensagensPainel
          conversa={conversaSelecionada}
          mensagens={mensagens}
          usuarioIdAtual={usuarioIdAtual}
          digitandoUserId={digitandoUserId}
          onEnviar={enviar}
          onAbrirThread={setThreadAberta}
          onUpload={upload}
        />
      ) : (
        <div className="flex-1 flex items-center justify-center text-neutral-500 text-sm">
          Selecione uma conversa
        </div>
      )}
      {threadAberta && (
        <ThreadPainel
          mensagemPai={threadAberta}
          onFechar={() => setThreadAberta(null)}
          onEnviarResposta={enviarRespostaThread}
        />
      )}
      {!conectado && (
        <div className="fixed bottom-3 right-3 bg-amber-600 text-white text-xs px-3 py-1.5 rounded-lg">
          Reconectando...
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Trocar `web/src/app/atendimento/chat/page.tsx` por um redirect**

```typescript
"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AtendimentoChatRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/chat"); }, [router]);
  return null;
}
```

- [ ] **Step 3: Atualizar o item de navegação em `web/src/app/layout.tsx`**

Trocar a linha 64:

```typescript
  { href: "/atendimento/chat", label: "Chat", icon: "atendimento" },
```

por:

```typescript
  { href: "/chat", label: "Chat", icon: "atendimento" },
```

- [ ] **Step 4: Build do frontend e smoke test manual**

Run: `cd web && npm run build`
Expected: build conclui sem erro

Run manual (dev server): `cd web && npm run dev`, abrir `http://localhost:3000/chat` logado, confirmar que a sidebar carrega e que `/atendimento/chat` redireciona pra `/chat`.

- [ ] **Step 5: Commit**

```bash
git add web/src/app/chat/page.tsx web/src/app/atendimento/chat/page.tsx web/src/app/layout.tsx
git commit -m "feat: pagina /chat, redirect da rota antiga e item de navegacao"
```

---

## Ordem de execução

Tasks 1→6 são backend e dependem umas das outras em sequência (schema → mensagens → anexos/presença → ponte com ticket → REST → WebSocket). Tasks 7→10 são frontend e dependem das Tasks 5 e 6 estarem prontas (a API que elas chamam precisa existir). Não há tasks paralelizáveis de forma segura aqui, porque cada uma amplia o mesmo arquivo (`core/chat.py`) criado na Task 1 — rodar em paralelo geraria conflito de merge no mesmo arquivo.
