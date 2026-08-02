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
