"""Vinculo usuario <-> loja que CONTROLA ACESSO — diferente de
loja_responsaveis (que e' so' registro informativo de "quem responde pela
loja", sem gate de nada). Usuario sem nenhum vinculo aqui nao ve NENHUMA
loja (fail-closed), exceto quem tem a permissao "lojas.ver_todas" (Admin
recebe automaticamente, ver core/rbac.py) ou o token master."""
from core import get_db, run_async
from core.lojas import _log_erro

_table_ok = False


def _ensure_table():
    global _table_ok
    if _table_ok: return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS usuario_lojas (
                id SERIAL PRIMARY KEY,
                usuario_id INT NOT NULL REFERENCES rbac_usuarios(id) ON DELETE CASCADE,
                loja_id INT NOT NULL REFERENCES lojas(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (usuario_id, loja_id)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_usuario_lojas_usuario ON usuario_lojas (usuario_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_usuario_lojas_loja ON usuario_lojas (loja_id)")
        # ponytail: lojas_permitidas() e' fail-closed (sem vinculo = ve
        # nenhuma loja). Sem essa migracao, todo usuario ja cadastrado
        # perderia acesso a tudo no instante do deploy, ate' um admin sair
        # vinculando um por um. Roda so' 1x (tabela recem-criada e vazia):
        # da' a cada usuario ATIVO um vinculo com cada loja ATIVA, preservando
        # o "ve tudo" que ja era o comportamento de fato ate' aqui.
        total = await db.fetchval("SELECT COUNT(*) FROM usuario_lojas")
        if total == 0:
            await db.execute("""
                INSERT INTO usuario_lojas (usuario_id, loja_id)
                SELECT u.id, l.id FROM rbac_usuarios u CROSS JOIN lojas l
                WHERE u.ativo = TRUE AND l.ativa = TRUE
                ON CONFLICT DO NOTHING
            """)
    try:
        run_async(_go())
        _table_ok = True
    except Exception as e:
        _log_erro("usuario_lojas._ensure_table", e)


def listar_lojas_do_usuario(usuario_id: int) -> list:
    """Lojas vinculadas a este usuario (id + nome), para exibir na tela dele."""
    _ensure_table()
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT l.id, l.nome FROM usuario_lojas ul
            JOIN lojas l ON l.id = ul.loja_id
            WHERE ul.usuario_id = $1 ORDER BY l.nome
        """, usuario_id)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: _log_erro("usuario_lojas.listar_lojas_do_usuario", e); return []


def listar_ids_lojas_do_usuario(usuario_id: int) -> list:
    """So' os ids (mais rapido) — usado pelo enforcement de acesso."""
    _ensure_table()
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT loja_id FROM usuario_lojas WHERE usuario_id = $1", usuario_id)
        return [r["loja_id"] for r in rows]
    try: return run_async(_go())
    except Exception as e: _log_erro("usuario_lojas.listar_ids_lojas_do_usuario", e); return []


def substituir_vinculos(usuario_id: int, loja_ids: list) -> dict:
    """Define o conjunto COMPLETO de lojas do usuario (substitui o que
    existia) — mais conveniente pra uma UI de checkbox multi-select do que
    vincular/desvincular um por um."""
    _ensure_table()
    async def _go():
        db = await get_db()
        async with db.transaction():
            await db.execute("DELETE FROM usuario_lojas WHERE usuario_id = $1", usuario_id)
            for loja_id in loja_ids:
                await db.execute(
                    "INSERT INTO usuario_lojas (usuario_id, loja_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    usuario_id, loja_id)
        return {"usuario_id": usuario_id, "loja_ids": loja_ids}
    try: return run_async(_go())
    except Exception as e: _log_erro("usuario_lojas.substituir_vinculos", e); return {"error": str(e)}


def vincular(usuario_id: int, loja_id: int) -> dict:
    _ensure_table()
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            INSERT INTO usuario_lojas (usuario_id, loja_id) VALUES ($1, $2)
            ON CONFLICT (usuario_id, loja_id) DO NOTHING
            RETURNING id, usuario_id, loja_id
        """, usuario_id, loja_id)
        return dict(row) if row else {"usuario_id": usuario_id, "loja_id": loja_id, "ja_existia": True}
    try: return run_async(_go())
    except Exception as e: _log_erro("usuario_lojas.vincular", e); return {"error": str(e)}


def desvincular(usuario_id: int, loja_id: int) -> bool:
    _ensure_table()
    async def _go():
        db = await get_db()
        r = await db.execute("DELETE FROM usuario_lojas WHERE usuario_id = $1 AND loja_id = $2", usuario_id, loja_id)
        return r != "DELETE 0"
    try: return run_async(_go())
    except Exception as e: _log_erro("usuario_lojas.desvincular", e); return False
