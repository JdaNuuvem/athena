"""Documentos Core — Upload, storage, CRUD de arquivos."""
import os as _os, uuid, shutil
from datetime import datetime
from core import get_db, run_async, log, hoje

AGENT = "Documentos Core"
STORAGE_DIR = _os.environ.get("DOCUMENTOS_STORAGE", _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "storage"))

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS documentos (
            id SERIAL PRIMARY KEY, nome_original VARCHAR(500) NOT NULL,
            nome_armazenado VARCHAR(100) NOT NULL, entidade_tipo VARCHAR(50),
            entidade_id INT, mime_type VARCHAR(100), tamanho_bytes BIGINT DEFAULT 0,
            criado_por VARCHAR(100), tags VARCHAR(300), created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_documentos_entidade ON documentos(entidade_tipo, entidade_id)")
    try:
        run_async(_go())
        _os.makedirs(STORAGE_DIR, exist_ok=True)
    except Exception as e:
        log(AGENT, f"Erro tabela documentos: {e}")

_ensure_tables()

def _list(cols="*", order="id DESC", limit=100, entidade_tipo="", entidade_id=None) -> list:
    async def _go():
        db = await get_db()
        where = []; params = []; p = 0
        if entidade_tipo:
            p += 1; where.append(f"entidade_tipo = ${p}"); params.append(entidade_tipo)
        if entidade_id is not None:
            p += 1; where.append(f"entidade_id = ${p}"); params.append(entidade_id)
        clause = " AND ".join(where) if where else "1=1"
        p += 1
        rows = await db.fetch(f"SELECT {cols} FROM documentos WHERE {clause} ORDER BY {order} LIMIT ${p}", *params, limit)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def listar(entidade_tipo="", entidade_id=None) -> list:
    return _list(entidade_tipo=entidade_tipo, entidade_id=entidade_id)

def upload(file_data: bytes, nome_original: str, entidade_tipo: str = "", entidade_id: int = None, criado_por: str = "", mime_type: str = "application/octet-stream") -> dict:
    """Salva arquivo no disco e registra no banco."""
    ext = _os.path.splitext(nome_original)[1] or ""
    nome_armazenado = f"{uuid.uuid4().hex}{ext}"
    filepath = _os.path.join(STORAGE_DIR, nome_armazenado)
    try:
        _os.makedirs(STORAGE_DIR, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(file_data)
        tamanho = len(file_data)
        async def _go():
            db = await get_db()
            row = await db.fetchrow("""INSERT INTO documentos (nome_original, nome_armazenado, entidade_tipo, entidade_id, mime_type, tamanho_bytes, criado_por)
                VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *""",
                nome_original, nome_armazenado, entidade_tipo, entidade_id, mime_type, tamanho, criado_por)
            return dict(row) if row else {"error": "insert failed"}
        result = run_async(_go())
        if result and "error" not in result:
            log(AGENT, f"Upload: {nome_original} ({tamanho} bytes) -> {nome_armazenado}")
        return result
    except Exception as e:
        log(AGENT, f"Erro upload: {e}")
        return {"error": str(e)}

def download(doc_id: int) -> tuple:
    """Retorna (filepath, nome_original, mime_type) ou (None,None,None).
    SOLID: retorna path, nao bytes — o Flask route faz streaming com send_file."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT nome_original, nome_armazenado, mime_type FROM documentos WHERE id = $1", doc_id)
        if not row:
            return None, None, None
        filepath = _os.path.join(STORAGE_DIR, row["nome_armazenado"])
        if not _os.path.exists(filepath):
            return None, None, None
        return filepath, row["nome_original"], row["mime_type"]
    try: return run_async(_go())
    except Exception as e: return None, None, None

def deletar(doc_id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT nome_armazenado FROM documentos WHERE id = $1", doc_id)
        if row:
            filepath = _os.path.join(STORAGE_DIR, row["nome_armazenado"])
            if _os.path.exists(filepath):
                _os.remove(filepath)
        await db.execute("DELETE FROM documentos WHERE id = $1", doc_id)
        return {"success": True}
    try: run_async(_go()); return {"success": True}
    except Exception as e: return {"error": str(e)}

def stats() -> dict:
    async def _go():
        db = await get_db()
        total = await db.fetchval("SELECT COUNT(*) FROM documentos")
        tamanho = await db.fetchval("SELECT COALESCE(SUM(tamanho_bytes),0) FROM documentos")
        return {"total": total or 0, "tamanho_total_bytes": int(tamanho or 0)}
    try: return run_async(_go())
    except Exception as e: return {"total": 0, "tamanho_total_bytes": 0}
