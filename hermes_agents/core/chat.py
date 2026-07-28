"""Chat Interno Core — Conversas (DM/Grupo/Canal/Ticket), Mensagens, Anexos, Presenca, Busca"""
from core import get_db, run_async, log
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
