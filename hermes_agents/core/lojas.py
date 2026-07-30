"""Store management CRUD — substitui lojas hardcoded do core/config."""
import traceback
from core import get_db, run_async, log

AGENT = "Lojas"
_table_ok = False

# Cadastro empresarial da loja (identificacao/endereco/contatos) — ALTER TABLE
# defensivo, mesmo padrao ja usado pra "tipo"/"ativa". Cada tupla e' (coluna, DDL).
_CAMPOS_GERAIS_DDL = [
    ("status", "VARCHAR(20) DEFAULT 'ativa'"),
    ("nome_fantasia", "VARCHAR(150)"),
    ("razao_social", "VARCHAR(200)"),
    ("cnpj_cpf", "VARCHAR(18)"),
    ("inscricao_estadual", "VARCHAR(20)"),
    ("inscricao_municipal", "VARCHAR(20)"),
    ("cor_principal", "VARCHAR(7)"),
    ("cor_secundaria", "VARCHAR(7)"),
    ("cep", "VARCHAR(9)"),
    ("rua", "VARCHAR(200)"),
    ("numero", "VARCHAR(20)"),
    ("complemento", "VARCHAR(100)"),
    ("bairro", "VARCHAR(100)"),
    ("cidade", "VARCHAR(100)"),
    ("estado", "VARCHAR(2)"),
    ("pais", "VARCHAR(60) DEFAULT 'Brasil'"),
    ("latitude", "NUMERIC(10,7)"),
    ("longitude", "NUMERIC(10,7)"),
    ("telefone", "VARCHAR(20)"),
    ("whatsapp", "VARCHAR(20)"),
    ("email", "VARCHAR(150)"),
    ("site", "VARCHAR(200)"),
    ("instagram", "VARCHAR(100)"),
    ("facebook", "VARCHAR(100)"),
    ("tiktok", "VARCHAR(100)"),
    ("youtube", "VARCHAR(100)"),
]
STATUS_VALIDOS = ("ativa", "inativa", "em_implantacao", "bloqueada")
TIPOS_VALIDOS = ("fisica", "virtual", "hibrida", "marketplace")
CAMPOS_GERAIS = {nome for nome, _ in _CAMPOS_GERAIS_DDL}

def _log_erro(onde: str, e: Exception):
    """Log local (console) + persistido no banco (system_logs), visivel em
    /seguranca/logs sem precisar acessar o log do container no Coolify."""
    tb = traceback.format_exc()
    log(AGENT, f"Erro {onde}: {e}\n{tb}")
    try:
        from core.seguranca import syslog
        syslog("ERROR", "lojas", f"{onde}: {e}", stacktrace=tb)
    except Exception:
        pass

# Cache simples nome->id, usado pelo dual-write da Fase 3 (migracao aditiva
# de estoque_lojas/etc de loja-por-texto pra loja_id). Invalidado sempre que
# uma loja e' criada/renomeada — ver invalidar_cache_loja_id().
_cache_loja_id: dict = {}

def invalidar_cache_loja_id():
    _cache_loja_id.clear()

def resolver_loja_id(nome: str):
    """Resolve o nome de uma loja pro id real — usado pelos write-paths que
    hoje so' tem o nome em maos (core/estoque.py e afins), pra popular a
    nova coluna loja_id em paralelo a coluna loja (texto) ja existente."""
    if not nome:
        return None
    if nome in _cache_loja_id:
        return _cache_loja_id[nome]
    async def _go():
        db = await get_db()
        return await db.fetchval("SELECT id FROM lojas WHERE nome = $1", nome)
    try:
        loja_id = run_async(_go())
    except Exception as e:
        _log_erro("resolver_loja_id", e)
        return None
    _cache_loja_id[nome] = loja_id
    return loja_id

# Cache simples chave->nome_efetivo (chave = nome OU id como string), usado
# pelo vinculo de estoque fisica x virtual (Fase Vinculo). Uma loja virtual
# com loja_vinculada_id ativo compartilha o saldo da fisica vinculada —
# qualquer operacao de estoque na virtual deve gravar/ler na fisica.
# Invalidado sempre que um vinculo e' criado/desfeito — ver invalidar_cache_loja_efetiva().
_cache_loja_efetiva: dict = {}

def invalidar_cache_loja_efetiva():
    _cache_loja_efetiva.clear()

def _sync_run(coro):
    """Helper de teste — roda uma coroutine isolada sem passar por run_async
    (que abriria um pool asyncpg de verdade). Producao usa loja_efetiva()."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

async def _loja_efetiva_async(loja) -> str:
    """Aceita nome OU id (string de digitos) de loja; devolve sempre o NOME
    efetivo — se for virtual com vinculo ativo, o nome da fisica vinculada;
    senao, o proprio nome (resolvendo id->nome primeiro, se for o caso)."""
    if not loja:
        return loja
    chave = str(loja)
    if chave in _cache_loja_efetiva:
        return _cache_loja_efetiva[chave]
    db = await get_db()
    if chave.isdigit():
        row = await db.fetchrow(
            "SELECT l1.nome, l2.nome AS nome_fisica FROM lojas l1 "
            "LEFT JOIN lojas l2 ON l2.id = l1.loja_vinculada_id "
            "WHERE l1.id = $1", int(chave))
        efetiva = (row["nome_fisica"] or row["nome"]) if row else loja
    else:
        row = await db.fetchrow(
            "SELECT l2.nome FROM lojas l1 JOIN lojas l2 ON l2.id = l1.loja_vinculada_id "
            "WHERE l1.nome = $1 AND l1.tipo = 'virtual' AND l1.loja_vinculada_id IS NOT NULL", chave)
        efetiva = row["nome"] if row else chave
    _cache_loja_efetiva[chave] = efetiva
    return efetiva

def loja_efetiva(loja: str) -> str:
    """Versao sincrona (wrapper sobre run_async) — use em qualquer caller
    que ja tenha so' o nome/id em maos fora de um `async def`."""
    if not loja:
        return loja
    try:
        return run_async(_loja_efetiva_async(loja))
    except Exception as e:
        _log_erro("loja_efetiva", e)
        return loja

def loja_efetiva_sync(cur, loja: str) -> str:
    """Para callers com conexao psycopg2 direta (routes/estoque.py,
    athena_bridge.py) — usa cursor sincrono, mesmo cache compartilhado."""
    if not loja:
        return loja
    chave = str(loja)
    if chave in _cache_loja_efetiva:
        return _cache_loja_efetiva[chave]
    if chave.isdigit():
        cur.execute(
            "SELECT l1.nome, l2.nome AS nome_fisica FROM lojas l1 "
            "LEFT JOIN lojas l2 ON l2.id = l1.loja_vinculada_id "
            "WHERE l1.id = %s", (int(chave),))
        row = cur.fetchone()
        efetiva = (row[1] or row[0]) if row else loja
    else:
        cur.execute(
            "SELECT l2.nome FROM lojas l1 JOIN lojas l2 ON l2.id = l1.loja_vinculada_id "
            "WHERE l1.nome = %s AND l1.tipo = 'virtual' AND l1.loja_vinculada_id IS NOT NULL", (chave,))
        row = cur.fetchone()
        efetiva = row[0] if row else chave
    _cache_loja_efetiva[chave] = efetiva
    return efetiva

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
        # CREATE TABLE IF NOT EXISTS nao altera tabela ja existente — em prod a
        # tabela "lojas" foi criada antes da coluna "ativa" existir na definicao
        # acima, entao ela precisa do mesmo ALTER defensivo que "tipo" ja tem.
        try: await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS ativa BOOLEAN DEFAULT TRUE")
        except Exception as e: _log_erro("ALTER lojas.ativa", e)
        # fisica (PDV/estoque/caixa fisico) ou virtual (marketplace/Shopee) —
        # usado pelo frontend para mostrar so' os utilitarios relevantes no
        # menu quando essa loja especifica esta selecionada.
        try: await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS tipo VARCHAR(10) DEFAULT 'fisica'")
        except Exception as e: _log_erro("ALTER lojas.tipo", e)
        # tipo agora tambem aceita "hibrida"/"marketplace" (11 chars) —
        # VARCHAR(10) original nao cabe. ALTER COLUMN TYPE so' alarga,
        # nunca trunca dado existente.
        try: await db.execute("ALTER TABLE lojas ALTER COLUMN tipo TYPE VARCHAR(20)")
        except Exception as e: _log_erro("ALTER lojas.tipo (widen)", e)
        # vinculo de estoque fisica x virtual — quando preenchido numa loja
        # "virtual", aponta pra loja "fisica" que efetivamente detem o saldo
        # compartilhado (ver _loja_efetiva_async/loja_efetiva/loja_efetiva_sync acima).
        try: await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS loja_vinculada_id INT REFERENCES lojas(id)")
        except Exception as e: _log_erro("ALTER lojas.loja_vinculada_id", e)
        for col, ddl in _CAMPOS_GERAIS_DDL:
            try: await db.execute(f"ALTER TABLE lojas ADD COLUMN IF NOT EXISTS {col} {ddl}")
            except Exception as e: _log_erro(f"ALTER lojas.{col}", e)
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
        _log_erro("_ensure_table", e)

def listar() -> list:
    _ensure_table()
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT id, nome, ativa, created_at, bling_id, tipo FROM lojas ORDER BY id")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: _log_erro("listar", e); return []

def criar(nome: str, tipo: str = "fisica"):
    _ensure_table()
    if tipo not in TIPOS_VALIDOS:
        tipo = "fisica"
    async def _go():
        db = await get_db()
        row = await db.fetchrow("INSERT INTO lojas (nome, tipo) VALUES ($1, $2) RETURNING id, nome, ativa, tipo", nome, tipo)
        return dict(row) if row else None
    try:
        return run_async(_go())
    except Exception as e:
        _log_erro("criar", e); return {"error": str(e)}
    finally:
        invalidar_cache_loja_id()

def atualizar(id_loja: int, nome: str, shopee_markup_pct: float = None, grupos_publicacao: str = None, tipo: str = None) -> bool:
    _ensure_table()
    async def _go():
        db = await get_db()
        r = await db.execute("UPDATE lojas SET nome = $1 WHERE id = $2", nome, id_loja)
        if shopee_markup_pct is not None:
            await db.execute("UPDATE lojas SET shopee_markup_pct = $1 WHERE id = $2", float(shopee_markup_pct), id_loja)
        if grupos_publicacao is not None:
            await db.execute("UPDATE lojas SET grupos_publicacao = $1 WHERE id = $2", grupos_publicacao.strip(), id_loja)
        if tipo in TIPOS_VALIDOS:
            await db.execute("UPDATE lojas SET tipo = $1 WHERE id = $2", tipo, id_loja)
        return r != "UPDATE 0"
    try:
        return run_async(_go())
    except Exception as e:
        _log_erro("atualizar", e); return False
    finally:
        invalidar_cache_loja_id()

def _update_campos(id_loja: int, campos: dict, whitelist: set) -> bool:
    """Helper generico p/ atualizar um subconjunto de colunas de "lojas" a
    partir de um dict ja filtrado pela camada de rota. Reaproveitado por
    core/lojas_operacional.py, lojas_fiscal_financeiro.py e lojas_virtual.py
    pra nao duplicar a construcao de UPDATE dinamico em cada arquivo.
    O whitelist restringe os NOMES de coluna aceitos antes de qualquer
    interpolacao — os VALORES sempre vao parametrizados ($n)."""
    _ensure_table()
    campos = {k: v for k, v in campos.items() if k in whitelist and v is not None}
    if not campos:
        return True
    async def _go():
        db = await get_db()
        colunas = list(campos.keys())
        sets = ", ".join(f"{col} = ${i + 1}" for i, col in enumerate(colunas))
        valores = [campos[c] for c in colunas] + [id_loja]
        r = await db.execute(f"UPDATE lojas SET {sets} WHERE id = ${len(colunas) + 1}", *valores)
        return r != "UPDATE 0"
    try: return run_async(_go())
    except Exception as e: _log_erro("_update_campos", e); return False

def obter(id_loja: int) -> dict:
    """Retorna a loja completa (todas as colunas) — usado nas telas de
    detalhe/edicao, ao contrario de listar() que traz so' o resumo."""
    _ensure_table()
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM lojas WHERE id = $1", id_loja)
        return dict(row) if row else None
    try: return run_async(_go())
    except Exception as e: _log_erro("obter", e); return None

def atualizar_geral(id_loja: int, campos: dict) -> bool:
    """Atualiza identificacao/endereco/contatos da loja. 'status' sincroniza
    a coluna legada 'ativa' (usada em dezenas de "WHERE ativa = TRUE" em
    estoque/pdv/vendas/relatorios) sem exigir migrar essas queries agora."""
    campos = dict(campos)
    if "status" in campos:
        if campos["status"] not in STATUS_VALIDOS:
            campos["status"] = "ativa"
        campos["ativa"] = campos["status"] == "ativa"
    return _update_campos(id_loja, campos, CAMPOS_GERAIS | {"ativa"})

def deletar(id_loja: int) -> bool:
    _ensure_table()
    async def _go():
        db = await get_db()
        r = await db.execute("DELETE FROM lojas WHERE id = $1", id_loja)
        return r != "DELETE 0"
    try: return run_async(_go())
    except Exception as e: _log_erro("deletar", e); return False

# ── Sync Bling ──

def _ensure_bling_id():
    async def _go():
        db = await get_db()
        try:
            exists = await db.fetchval("SELECT column_name FROM information_schema.columns WHERE table_name='lojas' AND column_name='bling_id'")
            if not exists:
                await db.execute("ALTER TABLE lojas ADD COLUMN bling_id BIGINT")
                await db.execute("ALTER TABLE lojas ADD COLUMN bling_descricao VARCHAR(200)")
        except Exception as e: _log_erro("_ensure_bling_id", e)
    try: run_async(_go())
    except Exception as e: _log_erro("_ensure_bling_id (run_async)", e)

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
            _log_erro("_ensure_shopee_cols", e)
    try: run_async(_go())
    except Exception as e: _log_erro("_ensure_shopee_cols (run_async)", e)

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
    except Exception as e: _log_erro("listar_lojas_shopee", e); return []

def obter_credenciais_shopee(loja_id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""SELECT shopee_shop_id, shopee_access_token, shopee_refresh_token
                                   FROM lojas WHERE id = $1""", loja_id)
        return dict(row) if row else {}
    try: return run_async(_go())
    except Exception as e: _log_erro("obter_credenciais_shopee", e); return {}

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
    except Exception as e: _log_erro("vincular_shopee", e); return {"error": str(e)}

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
    except Exception as e: _log_erro("criar_loja_shopee", e); return {"error": str(e)}

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
    except Exception as e: _log_erro("sincronizar_bling", e); return {"error": str(e)}

# ── Helpers para entidades ──

def _primeira_loja() -> str:
    """Nome da primeira loja ativa — usado como loja padrao em operacoes internas."""
    _ensure_table()
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT nome FROM lojas WHERE ativa = TRUE ORDER BY id LIMIT 1")
        return row["nome"] if row else "Loja Centro"
    try: return run_async(_go())
    except Exception as e: _log_erro("_primeira_loja", e); return "Loja Centro"

LOJA_PRINCIPAL: str = ""
LOJA_PRODUCAO: str = ""

def _init_loja_names():
    global LOJA_PRINCIPAL, LOJA_PRODUCAO
    if LOJA_PRINCIPAL:
        return
    LOJA_PRINCIPAL = _primeira_loja()
    LOJA_PRODUCAO = "Produção"

_init_loja_names()
