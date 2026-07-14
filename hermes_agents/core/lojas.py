"""Store management CRUD — substitui lojas hardcoded do core/config."""
from core import get_db, run_async, log

AGENT = "Lojas"

def _ensure_table():
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lojas (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                ativa BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Seed defaults se tabela vazia
        count = await db.fetchval("SELECT COUNT(*) FROM lojas")
        if count == 0:
            for nome in ["Loja Centro", "Loja Shopping", "Loja Norte", "Loja Sul"]:
                await db.execute("INSERT INTO lojas (nome) VALUES ($1)", nome)
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao criar tabela lojas: {e}")

_ensure_table()

def listar() -> list[dict]:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT id, nome, ativa, created_at FROM lojas ORDER BY id")
        return [dict(r) for r in rows]
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao listar lojas: {e}")
        return []

def criar(nome: str) -> dict | None:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("INSERT INTO lojas (nome) VALUES ($1) RETURNING id, nome, ativa", nome)
        return dict(row) if row else None
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao criar loja: {e}")
        return None

def atualizar(id_loja: int, nome: str) -> bool:
    async def _go():
        db = await get_db()
        r = await db.execute("UPDATE lojas SET nome = $1 WHERE id = $2", nome, id_loja)
        return r != "UPDATE 0"
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao atualizar loja: {e}")
        return False

def deletar(id_loja: int) -> bool:
    async def _go():
        db = await get_db()
        r = await db.execute("DELETE FROM lojas WHERE id = $1", id_loja)
        return r != "DELETE 0"
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao deletar loja: {e}")
        return False
