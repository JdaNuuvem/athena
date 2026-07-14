"""Automacoes Core — Webhooks, Filas, Eventos, Agendamentos, Integracoes, Bots, IA"""
from core import get_db, run_async, log, hoje

AGENT = "Automacoes Core"

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS autom_webhooks (
            id SERIAL PRIMARY KEY, nome VARCHAR(100), url VARCHAR(500) NOT NULL,
            evento VARCHAR(100), headers JSONB DEFAULT '{}', body_template TEXT,
            ativo BOOLEAN DEFAULT TRUE, ultimo_status INT, ultimo_envio TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS autom_filas (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL, tipo VARCHAR(50) DEFAULT 'fifo',
            tamanho_max INT DEFAULT 1000, processados INT DEFAULT 0, falhas INT DEFAULT 0,
            ativo BOOLEAN DEFAULT TRUE, config JSONB DEFAULT '{}', created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS autom_eventos (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL, gatilho VARCHAR(100),
            origem VARCHAR(100), destino VARCHAR(100), regras JSONB DEFAULT '{}',
            ativo BOOLEAN DEFAULT TRUE, execucoes INT DEFAULT 0, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS autom_agendamentos (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL, cron_expressao VARCHAR(100),
            acao VARCHAR(100), parametros JSONB DEFAULT '{}', ultima_execucao TIMESTAMP,
            proxima_execucao TIMESTAMP, ativo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS autom_integracoes (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL, tipo VARCHAR(50),
            config JSONB DEFAULT '{}', status VARCHAR(30) DEFAULT 'conectado',
            ultima_sinc TIMESTAMP, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS autom_bots (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL, tipo VARCHAR(50),
            plataforma VARCHAR(50), token VARCHAR(500), config JSONB DEFAULT '{}',
            ativo BOOLEAN DEFAULT TRUE, mensagens_enviadas INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS autom_ia (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL, modelo VARCHAR(100),
            provider VARCHAR(50) DEFAULT 'openai', api_key VARCHAR(500),
            config JSONB DEFAULT '{}', ativo BOOLEAN DEFAULT TRUE,
            total_tokens INT DEFAULT 0, custo DECIMAL(10,4) DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
    try: run_async(_go())
    except Exception as e: log(AGENT, f"Erro tabelas automacoes: {e}")

_ensure_tables()

def _list(t, cols="*", order="id DESC", limit=100):
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"SELECT {cols} FROM {t} ORDER BY {order} LIMIT {limit}")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except: return []

def _get(t, id):
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"SELECT * FROM {t} WHERE id=$1", id)
        return dict(row) if row else {"error":"not found"}
    try: return run_async(_go())
    except Exception as e: return {"error":str(e)}

def _create(t, d):
    keys = list(d.keys()); vals = list(d.values())
    ph = ", ".join(f"${i+1}" for i in range(len(keys)))
    cols = ", ".join(keys)
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"INSERT INTO {t} ({cols}) VALUES ({ph}) RETURNING *", *vals)
        return dict(row) if row else {"error":"insert failed"}
    try: return run_async(_go())
    except Exception as e: return {"error":str(e)}

def _update(t, id, d):
    sets = ", ".join(f"{k}=${i+1}" for i,k in enumerate(d.keys()))
    vals = list(d.values())+[id]
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"UPDATE {t} SET {sets} WHERE id=${len(vals)} RETURNING *", *vals)
        return dict(row) if row else {"error":"not found"}
    try: return run_async(_go())
    except Exception as e: return {"error":str(e)}

def _delete(t, id):
    async def _go():
        db = await get_db()
        await db.execute(f"DELETE FROM {t} WHERE id=$1", id)
        return {"success":True}
    try: run_async(_go()); return {"success":True}
    except Exception as e: return {"error":str(e)}

TABLES = ["webhooks","filas","eventos","agendamentos","integracoes","bots","ia"]
def list(t): return _list(f"autom_{t}")
def get(t,i): return _get(f"autom_{t}",i)
def create(t,d): return _create(f"autom_{t}",d)
def update(t,i,d): return _update(f"autom_{t}",i,d)
def delete(t,i): return _delete(f"autom_{t}",i)

def dashboard():
    async def _go():
        db = await get_db()
        webhooks = await db.fetchval("SELECT COUNT(*) FROM autom_webhooks WHERE ativo=TRUE")
        filas = await db.fetchval("SELECT COUNT(*) FROM autom_filas WHERE ativo=TRUE")
        eventos = await db.fetchval("SELECT COUNT(*) FROM autom_eventos WHERE ativo=TRUE")
        agendamentos = await db.fetchval("SELECT COUNT(*) FROM autom_agendamentos WHERE ativo=TRUE")
        integracoes = await db.fetchval("SELECT COUNT(*) FROM autom_integracoes")
        bots = await db.fetchval("SELECT COUNT(*) FROM autom_bots WHERE ativo=TRUE")
        ia = await db.fetchval("SELECT COUNT(*) FROM autom_ia WHERE ativo=TRUE")
        total_exec = await db.fetchval("SELECT COALESCE(SUM(execucoes),0) FROM autom_eventos")
        return {"webhooks":webhooks or 0,"filas":filas or 0,"eventos":eventos or 0,"agendamentos":agendamentos or 0,"integracoes":integracoes or 0,"bots":bots or 0,"ia":ia or 0,"total_execucoes":total_exec or 0}
    try: return run_async(_go())
    except: return {"webhooks":0,"filas":0,"eventos":0,"agendamentos":0,"integracoes":0,"bots":0,"ia":0,"total_execucoes":0}
