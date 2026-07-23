"""Compras Core — Solicitacoes, Cotacoes, Pedidos, Recebimento, Fornecedores, Aprovacoes"""
from core import get_db, run_async, log, hoje

AGENT = "Compras Core"

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS compras_fornecedores (
            id SERIAL PRIMARY KEY, nome VARCHAR(200) NOT NULL, cnpj VARCHAR(20),
            telefone VARCHAR(30), email VARCHAR(100), contato VARCHAR(100),
            endereco TEXT, prazo_entrega_dias INT DEFAULT 7, condicoes_pgto VARCHAR(100),
            status VARCHAR(20) DEFAULT 'ativo', created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS compras_solicitacoes (
            id SERIAL PRIMARY KEY, numero VARCHAR(30), descricao TEXT NOT NULL,
            solicitante VARCHAR(100), departamento VARCHAR(100), urgencia VARCHAR(20) DEFAULT 'normal',
            status VARCHAR(30) DEFAULT 'pendente', aprovado_por VARCHAR(100), aprovado_em TIMESTAMP,
            observacoes TEXT, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS compras_cotacoes (
            id SERIAL PRIMARY KEY, solicitacao_id INT REFERENCES compras_solicitacoes(id),
            fornecedor_id INT REFERENCES compras_fornecedores(id),
            valor_unitario DECIMAL(12,2), valor_frete DECIMAL(12,2) DEFAULT 0,
            prazo_entrega INT, condicoes TEXT, status VARCHAR(20) DEFAULT 'enviada',
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS compras_pedidos (
            id SERIAL PRIMARY KEY, numero VARCHAR(30), solicitacao_id INT REFERENCES compras_solicitacoes(id),
            fornecedor_id INT REFERENCES compras_fornecedores(id), cotacao_id INT REFERENCES compras_cotacoes(id),
            valor_total DECIMAL(12,2) DEFAULT 0, status VARCHAR(30) DEFAULT 'emitido',
            data_emissao DATE, data_entrega_prevista DATE, aprovado_por VARCHAR(100),
            observacoes TEXT, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS compras_itens (
            id SERIAL PRIMARY KEY, pedido_id INT REFERENCES compras_pedidos(id),
            solicitacao_id INT REFERENCES compras_solicitacoes(id),
            produto_codigo VARCHAR(50), descricao VARCHAR(200), quantidade DECIMAL(12,3) DEFAULT 0,
            unidade VARCHAR(10) DEFAULT 'UN', valor_unitario DECIMAL(12,2) DEFAULT 0, valor_total DECIMAL(12,2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS compras_recebimentos (
            id SERIAL PRIMARY KEY, pedido_id INT REFERENCES compras_pedidos(id),
            numero VARCHAR(30), data_recebimento DATE DEFAULT CURRENT_DATE,
            conferido_por VARCHAR(100), status VARCHAR(30) DEFAULT 'pendente',
            divergencias TEXT, observacoes TEXT, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS compras_notas_entrada (
            id SERIAL PRIMARY KEY, pedido_id INT REFERENCES compras_pedidos(id),
            recebimento_id INT REFERENCES compras_recebimentos(id),
            numero_nf VARCHAR(50), chave_acesso VARCHAR(50), valor DECIMAL(12,2) DEFAULT 0,
            data_emissao DATE, data_recebimento DATE, arquivo_url VARCHAR(500),
            status VARCHAR(30) DEFAULT 'pendente', created_at TIMESTAMP DEFAULT NOW()
        )""")
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro tabelas compras: {e}")

_ensure_tables()

# ── CRUD generico ──

def _list(tabela: str, cols="*", order="id DESC", limit=100) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"SELECT {cols} FROM {tabela} ORDER BY {order} LIMIT {limit}")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"list {tabela}: {e}"); return []

def _get(tabela: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"SELECT * FROM {tabela} WHERE id = $1", id)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def _create(tabela: str, dados: dict) -> dict:
    keys = list(dados.keys()); vals = list(dados.values())
    ph = ", ".join(f"${i+1}" for i in range(len(keys)))
    cols = ", ".join(keys)
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"INSERT INTO {tabela} ({cols}) VALUES ({ph}) RETURNING *", *vals)
        return dict(row) if row else {"error": "insert failed"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def _update(tabela: str, id: int, dados: dict) -> dict:
    sets = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(dados.keys()))
    vals = list(dados.values()) + [id]
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"UPDATE {tabela} SET {sets} WHERE id = ${len(vals)} RETURNING *", *vals)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def _delete(tabela: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        await db.execute(f"DELETE FROM {tabela} WHERE id = $1", id)
        return {"success": True}
    try: run_async(_go()); return {"success": True}
    except Exception as e: return {"error": str(e)}

TABLES = ["fornecedores","solicitacoes","cotacoes","pedidos","itens","recebimentos","notas_entrada"]
def list(t: str): return _list(f"compras_{t}")
def get(t: str, i: int): return _get(f"compras_{t}", i)
def create(t: str, d: dict): return _create(f"compras_{t}", d)
def update(t: str, i: int, d: dict): return _update(f"compras_{t}", i, d)
def delete(t: str, i: int): return _delete(f"compras_{t}", i)

# ── Aprovacao ──

def aprovar_solicitacao(id: int, aprovador: str) -> dict:
    return update("solicitacoes", id, {"status": "aprovada", "aprovado_por": aprovador, "aprovado_em": hoje()})

def confirmar_recebimento(id: int) -> dict:
    r = update("recebimentos", id, {"status": "confirmado"})
    try:
        from core.entidades import ao_receber_compra
        ao_receber_compra(id)
    except Exception as e: pass
    return r

def dashboard() -> dict:
    async def _go():
        db = await get_db()
        pendentes = await db.fetchval("SELECT COUNT(*) FROM compras_solicitacoes WHERE status = 'pendente'")
        pedidos_abertos = await db.fetchval("SELECT COUNT(*) FROM compras_pedidos WHERE status IN ('emitido','enviado')")
        total_recebido = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM compras_notas_entrada WHERE status = 'confirmada'")
        return {"pendentes": pendentes or 0, "pedidos_abertos": pedidos_abertos or 0, "total_recebido": float(total_recebido or 0)}
    try: return run_async(_go())
    except Exception as e: return {"pendentes":0,"pedidos_abertos":0,"total_recebido":0}
