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

def atualizar(id_loja: int, nome: str) -> bool:
    _ensure_table()
    async def _go():
        db = await get_db()
        r = await db.execute("UPDATE lojas SET nome = $1 WHERE id = $2", nome, id_loja)
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
        except: pass
    try: run_async(_go())
    except: pass

_ensure_bling_id()

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
    except: return "Loja Centro"

LOJA_PRINCIPAL: str = ""
LOJA_PRODUCAO: str = ""

def _init_loja_names():
    global LOJA_PRINCIPAL, LOJA_PRODUCAO
    if LOJA_PRINCIPAL:
        return
    LOJA_PRINCIPAL = _primeira_loja()
    LOJA_PRODUCAO = "Produção"

_init_loja_names()
