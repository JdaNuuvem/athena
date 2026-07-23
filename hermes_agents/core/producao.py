"""Producao Core — OP, BOM, Consumo, Maquinas, Apontamentos, Custos, Perdas, Rendimento"""
from core import get_db, run_async, log, hoje

AGENT = "Producao Core"

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS producao_ops (
            id SERIAL PRIMARY KEY, numero VARCHAR(30), produto_codigo VARCHAR(50),
            descricao VARCHAR(200), quantidade DECIMAL(12,3) DEFAULT 0,
            unidade VARCHAR(10) DEFAULT 'UN', status VARCHAR(30) DEFAULT 'planejada',
            data_inicio DATE, data_prevista DATE, data_fim DATE,
            maquina_id INT, operador VARCHAR(100), prioridade VARCHAR(20) DEFAULT 'normal',
            observacoes TEXT, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS producao_bom (
            id SERIAL PRIMARY KEY, op_id INT REFERENCES producao_ops(id),
            produto_codigo VARCHAR(50), componente_codigo VARCHAR(50),
            descricao VARCHAR(200), quantidade DECIMAL(12,4) DEFAULT 0,
            unidade VARCHAR(10) DEFAULT 'UN', tipo VARCHAR(30) DEFAULT 'materia_prima',
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS producao_maquinas (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL,
            tipo VARCHAR(50), capacidade_hora DECIMAL(10,2), status VARCHAR(30) DEFAULT 'disponivel',
            ultima_manutencao DATE, proxima_manutencao DATE,
            custo_hora DECIMAL(10,2) DEFAULT 0, observacoes TEXT, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS producao_apontamentos (
            id SERIAL PRIMARY KEY, op_id INT REFERENCES producao_ops(id),
            maquina_id INT REFERENCES producao_maquinas(id),
            operador VARCHAR(100), data DATE DEFAULT CURRENT_DATE,
            hora_inicio TIME, hora_fim TIME, horas_trabalhadas DECIMAL(6,2),
            quantidade_produzida DECIMAL(12,3) DEFAULT 0,
            quantidade_boa DECIMAL(12,3) DEFAULT 0, quantidade_refugo DECIMAL(12,3) DEFAULT 0,
            paradas TEXT, observacoes TEXT, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS producao_consumo (
            id SERIAL PRIMARY KEY, op_id INT REFERENCES producao_ops(id),
            componente_codigo VARCHAR(50), descricao VARCHAR(200),
            quantidade_prevista DECIMAL(12,4) DEFAULT 0, quantidade_real DECIMAL(12,4) DEFAULT 0,
            unidade VARCHAR(10) DEFAULT 'UN', custo_unitario DECIMAL(10,4) DEFAULT 0,
            data DATE DEFAULT CURRENT_DATE, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS producao_perdas (
            id SERIAL PRIMARY KEY, op_id INT REFERENCES producao_ops(id),
            maquina_id INT REFERENCES producao_maquinas(id),
            tipo VARCHAR(50), descricao TEXT, quantidade DECIMAL(12,3) DEFAULT 0,
            motivo VARCHAR(100), data DATE DEFAULT CURRENT_DATE, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS producao_custos (
            id SERIAL PRIMARY KEY, op_id INT REFERENCES producao_ops(id),
            tipo VARCHAR(50), descricao VARCHAR(200), valor DECIMAL(12,2) DEFAULT 0,
            data DATE DEFAULT CURRENT_DATE, created_at TIMESTAMP DEFAULT NOW()
        )""")
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro tabelas producao: {e}")

_ensure_tables()

# ── CRUD ──

def _list(t: str, cols="*", order="id DESC", limit=100) -> list:
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
    cols = ", ".join(keys)
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"INSERT INTO {t} ({cols}) VALUES ({ph}) RETURNING *", *vals)
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

def _delete(t: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        await db.execute(f"DELETE FROM {t} WHERE id=$1", id)
        return {"success":True}
    try: run_async(_go()); return {"success":True}
    except Exception as e: return {"error":str(e)}

TABLES = ["ops","bom","maquinas","apontamentos","consumo","perdas","custos"]
def list(t: str): return _list(f"producao_{t}")
def get(t: str, i: int): return _get(f"producao_{t}", i)
def create(t: str, d: dict): return _create(f"producao_{t}", d)
def update(t: str, i: int, d: dict): return _update(f"producao_{t}", i, d)
def delete(t: str, i: int): return _delete(f"producao_{t}", i)

# ── Operacoes ──

def dashboard() -> dict:
    async def _go():
        db = await get_db()
        ops_ativas = await db.fetchval("SELECT COUNT(*) FROM producao_ops WHERE status IN ('planejada','em_andamento')")
        ops_hoje = await db.fetchval("SELECT COUNT(*) FROM producao_ops WHERE data_inicio = CURRENT_DATE")
        maquinas_ativas = await db.fetchval("SELECT COUNT(*) FROM producao_maquinas WHERE status = 'disponivel'")
        maquinas_paradas = await db.fetchval("SELECT COUNT(*) FROM producao_maquinas WHERE status = 'parada'")
        total_perdas = await db.fetchval("SELECT COALESCE(SUM(quantidade),0) FROM producao_perdas")
        # Rendimento: bom / total
        bom = await db.fetchval("SELECT COALESCE(SUM(quantidade_boa),0) FROM producao_apontamentos")
        total = await db.fetchval("SELECT COALESCE(SUM(quantidade_produzida),0) FROM producao_apontamentos")
        rendimento = round((bom/(total or 1))*100, 1)
        return {
            "ops_ativas": ops_ativas or 0, "ops_hoje": ops_hoje or 0,
            "maquinas_ativas": maquinas_ativas or 0, "maquinas_paradas": maquinas_paradas or 0,
            "total_perdas": float(total_perdas or 0), "rendimento_pct": rendimento,
        }
    try: return run_async(_go())
    except Exception as e: return {"ops_ativas":0,"ops_hoje":0,"maquinas_ativas":0,"maquinas_paradas":0,"total_perdas":0,"rendimento_pct":0}

def iniciar_op(op_id: int) -> dict:
    return update("ops", op_id, {"status":"em_andamento","data_inicio":hoje()})

def finalizar_op(op_id: int) -> dict:
    r = update("ops", op_id, {"status":"finalizada","data_fim":hoje()})
    try:
        from core.entidades import ao_finalizar_producao
        ao_finalizar_producao(op_id)
    except Exception as e: pass
    return r

def parar_maquina(maquina_id: int, motivo: str) -> dict:
    return update("maquinas", maquina_id, {"status":"parada","observacoes":motivo})

def liberar_maquina(maquina_id: int) -> dict:
    return update("maquinas", maquina_id, {"status":"disponivel"})
