"""Store management CRUD — substitui lojas hardcoded do core/config."""
from core import get_db, run_async, log

AGENT = "Lojas"
_table_ok = False

def _ensure_table():
    global _table_ok
    if _table_ok: return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lojas (
                id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL,
                ativa BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        count = await db.fetchval("SELECT COUNT(*) FROM lojas")
        if count == 0:
            try:
                from bling_erp import listar_depositos, get_access_token
                token = get_access_token()
                if token:
                    pagina = 1
                    while True:
                        r = listar_depositos(pagina=pagina, limite=100)
                        dados = r.get("data", [])
                        if not dados or r.get("error"):
                            break
                        for dep in dados:
                            nome = dep.get("descricao", f"Deposito {dep.get('id')}")
                            ativa = dep.get("situacao", "A") == "A"
                            await db.execute(
                                "INSERT INTO lojas (nome, ativa, bling_id, bling_descricao) VALUES ($1, $2, $3, $4)",
                                nome, ativa, dep.get("id"), nome)
                        if len(dados) < 100:
                            break
                        pagina += 1
                else:
                    await db.execute("INSERT INTO lojas (nome) VALUES ($1)", "Loja Padrão")
            except Exception:
                await db.execute("INSERT INTO lojas (nome) VALUES ($1)", "Loja Padrão")
    try:
        run_async(_go())
        _table_ok = True
    except Exception as e:
        log(AGENT, f"Erro tabela lojas: {e}")

def listar() -> list:
    _ensure_table()
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT id, nome, ativa, created_at, bling_id FROM lojas ORDER BY id")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"Erro listar: {e}"); return []

def criar(nome: str):
    _ensure_table()
    async def _go():
        db = await get_db()
        row = await db.fetchrow("INSERT INTO lojas (nome) VALUES ($1) RETURNING id, nome, ativa", nome)
        return dict(row) if row else None
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"Erro criar: {e}"); return None

def atualizar(id_loja: int, nome: str, shopee_markup_pct: float = None, grupos_publicacao: str = None) -> bool:
    _ensure_table()
    async def _go():
        db = await get_db()
        r = await db.execute("UPDATE lojas SET nome = $1 WHERE id = $2", nome, id_loja)
        if shopee_markup_pct is not None:
            await db.execute("UPDATE lojas SET shopee_markup_pct = $1 WHERE id = $2", float(shopee_markup_pct), id_loja)
        if grupos_publicacao is not None:
            await db.execute("UPDATE lojas SET grupos_publicacao = $1 WHERE id = $2", grupos_publicacao.strip(), id_loja)
        return r != "UPDATE 0"
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"Erro atualizar: {e}"); return False

def deletar(id_loja: int) -> bool:
    _ensure_table()
    async def _go():
        db = await get_db()
        r = await db.execute("DELETE FROM lojas WHERE id = $1", id_loja)
        return r != "DELETE 0"
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"Erro deletar: {e}"); return False

# ── Sync Bling ──

def _ensure_bling_id():
    async def _go():
        db = await get_db()
        try:
            exists = await db.fetchval("SELECT column_name FROM information_schema.columns WHERE table_name='lojas' AND column_name='bling_id'")
            if not exists:
                await db.execute("ALTER TABLE lojas ADD COLUMN bling_id BIGINT")
                await db.execute("ALTER TABLE lojas ADD COLUMN bling_descricao VARCHAR(200)")
        except Exception as e: pass
    try: run_async(_go())
    except Exception as e: pass

_ensure_bling_id()

# ── Shopee: multiloja (cada loja Shopee tem seu proprio shop_id + tokens) ──

def _ensure_shopee_cols():
    async def _go():
        db = await get_db()
        try:
            await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS shopee_shop_id VARCHAR(50)")
            await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS shopee_shop_name VARCHAR(200)")
            await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS shopee_access_token TEXT")
            await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS shopee_refresh_token TEXT")
            await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS shopee_token_expira_em TIMESTAMP")
            await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS shopee_markup_pct NUMERIC(5,2) DEFAULT 100")
            await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS grupos_publicacao VARCHAR(300)")
            await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_lojas_shopee_shop_id ON lojas (shopee_shop_id) WHERE shopee_shop_id IS NOT NULL")
        except Exception as e:
            log(AGENT, f"Erro colunas shopee: {e}")
    try: run_async(_go())
    except Exception as e: pass

_ensure_shopee_cols()

def listar_lojas_shopee() -> list:
    """Lojas que ja tem uma conta Shopee vinculada (shop_id + tokens).
    tem_token indica se o access_token foi realmente salvo (confirmacao visual na tela)."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT id, nome, shopee_shop_id, shopee_shop_name, shopee_token_expira_em,
                   (shopee_access_token IS NOT NULL AND shopee_access_token != '') AS tem_token
            FROM lojas WHERE shopee_shop_id IS NOT NULL ORDER BY id
        """)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"Erro listar_lojas_shopee: {e}"); return []

def obter_credenciais_shopee(loja_id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""SELECT shopee_shop_id, shopee_access_token, shopee_refresh_token
                                   FROM lojas WHERE id = $1""", loja_id)
        return dict(row) if row else {}
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"Erro obter_credenciais_shopee: {e}"); return {}

def vincular_shopee(loja_id: int, shop_id: str, access_token: str, refresh_token: str = "",
                     shop_name: str = "", expira_em=None) -> dict:
    """Salva as credenciais de uma conta Shopee numa loja existente."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            UPDATE lojas SET shopee_shop_id = $1, shopee_shop_name = COALESCE(NULLIF($2,''), shopee_shop_name),
                shopee_access_token = $3, shopee_refresh_token = $4, shopee_token_expira_em = $5
            WHERE id = $6 RETURNING id, nome, shopee_shop_id
        """, shop_id, shop_name, access_token, refresh_token, expira_em, loja_id)
        return dict(row) if row else {"error": "loja nao encontrada"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def criar_loja_shopee(shop_id: str, access_token: str, refresh_token: str = "", shop_name: str = "", expira_em=None) -> dict:
    """Cria uma nova loja ja vinculada a uma conta Shopee (usado quando nenhuma loja_id foi indicada no auth)."""
    async def _go():
        db = await get_db()
        nome = shop_name or f"Shopee {shop_id}"
        row = await db.fetchrow("""
            INSERT INTO lojas (nome, shopee_shop_id, shopee_shop_name, shopee_access_token, shopee_refresh_token, shopee_token_expira_em)
            VALUES ($1, $2, $3, $4, $5, $6) RETURNING id, nome, shopee_shop_id
        """, nome, shop_id, shop_name, access_token, refresh_token, expira_em)
        return dict(row) if row else {"error": "falha ao criar loja"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def desconectar_shopee(loja_id: int) -> dict:
    """Remove a vinculacao de uma conta Shopee de uma loja (limpa shop_id e tokens).
    A loja em si nao e' apagada, apenas fica disponivel para conectar outra conta Shopee."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            UPDATE lojas SET shopee_shop_id = NULL, shopee_shop_name = NULL,
                shopee_access_token = NULL, shopee_refresh_token = NULL, shopee_token_expira_em = NULL
            WHERE id = $1 RETURNING id, nome
        """, loja_id)
        return dict(row) if row else {"error": "loja nao encontrada"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def sincronizar_bling() -> dict:
    """Puxa depositos/lojas do Bling e cria cada um como loja no Athena."""
    from bling_erp import listar_depositos, get_access_token, get_auth_url
    token = get_access_token()
    if not token:
        return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}
    _ensure_table()
    async def _go():
        db = await get_db()
        resultados = []
        pagina = 1
        while True:
            r = listar_depositos(pagina=pagina, limite=100)
            dados = r.get("data", [])
            if not dados or r.get("error"):
                break
            for dep in dados:
                bling_id = dep.get("id")
                nome = dep.get("descricao", f"Deposito {bling_id}")
                situacao = dep.get("situacao", "A")
                ativa = situacao == "A"
                existing = await db.fetchrow("SELECT id FROM lojas WHERE bling_id = $1", bling_id)
                if existing:
                    await db.execute("UPDATE lojas SET nome = $1, ativa = $2, bling_descricao = $3 WHERE bling_id = $4",
                        nome, ativa, nome, bling_id)
                    resultados.append({"acao": "atualizado", "id": existing["id"], "nome": nome})
                else:
                    row = await db.fetchrow(
                        "INSERT INTO lojas (nome, ativa, bling_id, bling_descricao) VALUES ($1, $2, $3, $4) RETURNING id",
                        nome, ativa, bling_id, nome)
                    resultados.append({"acao": "criado", "id": row["id"] if row else 0, "nome": nome})
            if len(dados) < 100:
                break
            pagina += 1
        return {"sync": len(resultados), "lojas": resultados}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

# ── Helpers para entidades ──

def _primeira_loja() -> str:
    """Nome da primeira loja ativa — usado como loja padrao em operacoes internas."""
    _ensure_table()
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT nome FROM lojas WHERE ativa = TRUE ORDER BY id LIMIT 1")
        return row["nome"] if row else "Loja Centro"
    try: return run_async(_go())
    except Exception as e: return "Loja Centro"

LOJA_PRINCIPAL: str = ""
LOJA_PRODUCAO: str = ""

def _init_loja_names():
    global LOJA_PRINCIPAL, LOJA_PRODUCAO
    if LOJA_PRINCIPAL:
        return
    LOJA_PRINCIPAL = _primeira_loja()
    LOJA_PRODUCAO = "Produção"

_init_loja_names()
