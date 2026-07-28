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
