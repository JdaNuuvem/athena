"""Catalogo SSOT — Fonte unica de verdade para Produtos. Todas as tabelas referenciam este catalogo."""
from core import get_db, run_async, log, hoje
from core.bling_logger import log_alteracao as bling_log_change

AGENT = "Catalogo SSOT"

def _ensure_tables():
    async def _go():
        db = await get_db()
        # ── Tabela central ──
        await db.execute("""CREATE TABLE IF NOT EXISTS catalogo_produtos (
            id SERIAL PRIMARY KEY, sku VARCHAR(50) UNIQUE NOT NULL, descricao VARCHAR(300),
            ncm VARCHAR(10), cest VARCHAR(10), cfop_padrao VARCHAR(5),
            unidade_padrao VARCHAR(10) DEFAULT 'UN', tipo VARCHAR(30) DEFAULT 'acabado',
            categoria VARCHAR(100), marca VARCHAR(100), peso_bruto DECIMAL(10,3),
            created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        # ── Estoque por loja ──
        await db.execute("""CREATE TABLE IF NOT EXISTS estoque_lojas (
            id SERIAL PRIMARY KEY, sku VARCHAR(50) NOT NULL, loja VARCHAR(50) NOT NULL,
            quantidade DECIMAL(12,3) DEFAULT 0, data_atualizacao TIMESTAMP DEFAULT NOW(),
            UNIQUE (sku, loja)
        )""")
        
        # ── Colunas de hierarquia pai/filho ──
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS id_bling BIGINT")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS sku_pai VARCHAR(50)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS atributo VARCHAR(200)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_catalogo_produtos_sku_pai ON catalogo_produtos (sku_pai)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS imagem_url VARCHAR(500)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS situacao VARCHAR(1) DEFAULT 'A'")
        # ── Full-text search indexes (pg_trgm for ILIKE with leading wildcard) ──
        try:
            await db.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_catalogo_sku_trgm ON catalogo_produtos USING gin (sku gin_trgm_ops)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_catalogo_desc_trgm ON catalogo_produtos USING gin (descricao gin_trgm_ops)")
        except Exception as e:
            log(AGENT, f"pg_trgm indisponivel (permissoes?): {e}")
        # ── Covering indexes for PDV subqueries ──
        try:
            # Remove duplicates before adding unique constraint
            await db.execute("""DELETE FROM anuncios a USING (
                SELECT sku, marketplace, MIN(ctid) as keep_ctid FROM anuncios
                GROUP BY sku, marketplace HAVING COUNT(*) > 1
            ) dup WHERE a.sku = dup.sku AND a.marketplace = dup.marketplace AND a.ctid <> dup.keep_ctid""")
            await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_anuncios_sku_mkt_unique ON anuncios (sku, marketplace)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_anuncios_sku_preco ON anuncios (sku, marketplace, preco)")
        except Exception as e:
            log(AGENT, f"idx_anuncios skip: {e}")
        # ── Migracao: popular a partir de tabelas existentes ──
        count = await db.fetchval("SELECT COUNT(*) FROM catalogo_produtos")
        if count == 0:
            # Migrar de fichas_tecnicas
            try:
                await db.execute("""INSERT INTO catalogo_produtos (sku, descricao)
                    SELECT sku, COALESCE(descricao, sku) FROM fichas_tecnicas
                    ON CONFLICT (sku) DO NOTHING""")
            except: pass
            # Migrar de anuncios
            try:
                await db.execute("""INSERT INTO catalogo_produtos (sku, descricao)
                    SELECT DISTINCT sku, sku FROM anuncios
                    ON CONFLICT (sku) DO NOTHING""")
            except: pass
            # Migrar de produtos
            try:
                await db.execute("""INSERT INTO catalogo_produtos (sku, descricao)
                    SELECT DISTINCT sku, COALESCE(descricao, sku) FROM produtos
                    ON CONFLICT (sku) DO NOTHING""")
            except: pass
            log(AGENT, f"Migrados {await db.fetchval('SELECT COUNT(*) FROM catalogo_produtos')} produtos para catalogo")
    try: run_async(_go())
    except Exception as e: log(AGENT, f"Erro catalogo: {e}")

_ensure_tables()

# ── CRUD ──

def _list(t: str, cols="*", order="id DESC", limit=500) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"SELECT {cols} FROM {t} ORDER BY {order} LIMIT {limit}")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except: return []

def _get(t: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"SELECT * FROM {t} WHERE id = $1", id)
        return dict(row) if row else {"error":"not found"}
    try: return run_async(_go())
    except Exception as e: return {"error":str(e)}

def _create(t: str, d: dict) -> dict:
    keys = list(d.keys()); vals = list(d.values())
    ph = ", ".join(f"${i+1}" for i in range(len(keys)))
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"INSERT INTO {t} ({', '.join(keys)}) VALUES ({ph}) RETURNING *", *vals)
        return dict(row) if row else {"error":"insert failed"}
    try: return run_async(_go())
    except Exception as e: return {"error":str(e)}

def _update(t: str, id: int, d: dict) -> dict:
    sets = ", ".join(f"{k}=${i+1}" for i,k in enumerate(d.keys()))
    vals = list(d.values())+[id]
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"UPDATE {t} SET {sets} WHERE id=${len(vals)} RETURNING *", *vals)
        return dict(row) if row else {"error":"not found"}
    try: return run_async(_go())
    except Exception as e: return {"error":str(e)}

def listar(): return _list("catalogo_produtos")
def obter(id: int): return _get("catalogo_produtos", id)
def criar(d: dict): return _create("catalogo_produtos", d)
def atualizar(id: int, d: dict): return _update("catalogo_produtos", id, d)

def buscar_por_sku(sku: str) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM catalogo_produtos WHERE sku = $1", sku)
        return dict(row) if row else {}
    try: return run_async(_go())
    except: return {}

def buscar_por_sku_ou_criar(sku: str, descricao: str = "") -> int:
    """Retorna o ID do produto, criando se nao existir."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT id FROM catalogo_produtos WHERE sku = $1", sku)
        if row: return row["id"]
        row = await db.fetchrow(
            "INSERT INTO catalogo_produtos (sku, descricao) VALUES ($1, $2) ON CONFLICT (sku) DO UPDATE SET descricao = COALESCE(NULLIF($2,''), catalogo_produtos.descricao) RETURNING id",
            sku, descricao or sku)
        return row["id"] if row else 0
    try: return run_async(_go())
    except: return 0

# ── Vinculo com estoque ──

def estoque_por_produto(produto_id: int) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM estoque_lojas WHERE sku = (SELECT sku FROM catalogo_produtos WHERE id = $1)", produto_id)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except: return []

# ── Vinculo com fichas tecnicas (BOM) ──

def ficha_tecnica_por_sku(sku: str) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM fichas_tecnicas WHERE sku = $1", sku)
        return dict(row) if row else {}
    try: return run_async(_go())
    except: return {}
