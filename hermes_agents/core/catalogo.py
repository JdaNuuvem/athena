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

        # ── Campos completos da Bling (GET /produtos/{id}) ──
        # bling_tipo = tipo nativo do Bling (P/S/N); nao confundir com a coluna 'tipo' (classificacao de producao/BOM)
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS bling_tipo VARCHAR(1)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS formato VARCHAR(1)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS codigo_barras VARCHAR(50)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS gtin_embalagem VARCHAR(50)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS descricao_curta TEXT")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS descricao_complementar TEXT")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS peso_liquido DECIMAL(10,3)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS volumes INTEGER")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS itens_por_caixa INTEGER")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS tipo_producao VARCHAR(1)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS condicao SMALLINT")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS frete_gratis BOOLEAN")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS link_externo VARCHAR(500)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS observacoes TEXT")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS categoria_id BIGINT")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS estoque_minimo DECIMAL(12,3)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS estoque_maximo DECIMAL(12,3)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS estoque_crossdocking INTEGER")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS estoque_localizacao VARCHAR(100)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS controlar_estoque BOOLEAN")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS largura DECIMAL(10,3)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS altura DECIMAL(10,3)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS profundidade DECIMAL(10,3)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS unidade_medida_dimensao VARCHAR(10)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS origem_fiscal VARCHAR(2)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS nfci VARCHAR(50)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS codigo_lista_servicos VARCHAR(20)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS cnae VARCHAR(20)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS codigo_item_fiscal VARCHAR(20)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS percentual_tributos DECIMAL(10,4)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS valor_base_st_retencao DECIMAL(12,2)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS valor_st_retencao DECIMAL(12,2)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS valor_icms_st DECIMAL(12,2)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS fornecedor_id BIGINT")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS fornecedor_nome VARCHAR(200)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS fornecedor_codigo VARCHAR(50)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS preco_custo DECIMAL(12,2)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS imagens JSONB")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS campos_customizados JSONB")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS estrutura JSONB")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS variacoes_detalhe JSONB")
        # Payload bruto completo do Bling — garante 100% dos campos, inclusive os que a Bling adicionar no futuro
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS dados_brutos_bling JSONB")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS grupo VARCHAR(50)")
        # ── Full-text search indexes (pg_trgm for ILIKE with leading wildcard) ──
        try:
            await db.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_catalogo_sku_trgm ON catalogo_produtos USING gin (sku gin_trgm_ops)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_catalogo_desc_trgm ON catalogo_produtos USING gin (descricao gin_trgm_ops)")
        except Exception as e:
            log(AGENT, f"pg_trgm indisponivel (permissoes?): {e}")
        # ── shop_id: permite o mesmo SKU anunciado em varias lojas do mesmo marketplace
        # (ex: 2 contas Shopee). marketplaces de conta unica (bling) usam shop_id = '' ──
        await db.execute("ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS shop_id VARCHAR(50) NOT NULL DEFAULT ''")

        # ── Covering indexes for PDV subqueries ──
        try:
            # Remove duplicates before adding unique constraint
            await db.execute("""DELETE FROM anuncios a USING (
                SELECT sku, marketplace, shop_id, MIN(ctid) as keep_ctid FROM anuncios
                GROUP BY sku, marketplace, shop_id HAVING COUNT(*) > 1
            ) dup WHERE a.sku = dup.sku AND a.marketplace = dup.marketplace AND a.shop_id = dup.shop_id AND a.ctid <> dup.keep_ctid""")
            await db.execute("DROP INDEX IF EXISTS idx_anuncios_sku_mkt_unique")
            await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_anuncios_sku_mkt_shop_unique ON anuncios (sku, marketplace, shop_id)")
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
            except Exception as e: pass
            # Migrar de anuncios
            try:
                await db.execute("""INSERT INTO catalogo_produtos (sku, descricao)
                    SELECT DISTINCT sku, sku FROM anuncios
                    ON CONFLICT (sku) DO NOTHING""")
            except Exception as e: pass
            # Migrar de produtos
            try:
                await db.execute("""INSERT INTO catalogo_produtos (sku, descricao)
                    SELECT DISTINCT sku, COALESCE(descricao, sku) FROM produtos
                    ON CONFLICT (sku) DO NOTHING""")
            except Exception as e: pass
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
    except Exception as e: return []

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
    except Exception as e: return {}

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
    except Exception as e: return 0

# ── Vinculo com estoque ──

def estoque_por_produto(produto_id: int) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM estoque_lojas WHERE sku = (SELECT sku FROM catalogo_produtos WHERE id = $1)", produto_id)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

# ── Vinculo com fichas tecnicas (BOM) ──

def ficha_tecnica_por_sku(sku: str) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM fichas_tecnicas WHERE sku = $1", sku)
        return dict(row) if row else {}
    try: return run_async(_go())
    except Exception as e: return {}
