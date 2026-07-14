"""Seguranca Core — Auditoria, Logs, Historico de Alteracoes"""
from core import get_db, run_async, log, hoje
from datetime import datetime
import json

AGENT = "Seguranca Core"

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY, user_id INT, email VARCHAR(150),
            acao VARCHAR(50) NOT NULL, modulo VARCHAR(50), entidade VARCHAR(50),
            entidade_id INT, dados_antes JSONB, dados_depois JSONB,
            ip VARCHAR(50), user_agent TEXT, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE INDEX IF NOT EXISTS idx_audit_modulo ON audit_log(modulo)""")
        await db.execute("""CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(email)""")
        await db.execute("""CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS system_logs (
            id SERIAL PRIMARY KEY, level VARCHAR(10) NOT NULL DEFAULT 'INFO',
            modulo VARCHAR(50), mensagem TEXT, stacktrace TEXT,
            data JSONB, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE INDEX IF NOT EXISTS idx_syslog_level ON system_logs(level)""")
        await db.execute("""CREATE INDEX IF NOT EXISTS idx_syslog_modulo ON system_logs(modulo)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS change_history (
            id SERIAL PRIMARY KEY, entidade VARCHAR(50) NOT NULL,
            entidade_id INT NOT NULL, campo VARCHAR(100), valor_antes TEXT,
            valor_depois TEXT, user_id INT, email VARCHAR(150),
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE INDEX IF NOT EXISTS idx_ch_entidade ON change_history(entidade, entidade_id)""")
    try: run_async(_go())
    except Exception as e: log(AGENT, f"Erro tabelas seguranca: {e}")

_ensure_tables()

# ── Auditoria ──

def auditar(acao: str, modulo: str = "", entidade: str = "", entidade_id: int = None,
            dados_antes: dict = None, dados_depois: dict = None,
            user_id: int = None, email: str = "", ip: str = "", user_agent: str = "") -> int:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""INSERT INTO audit_log (user_id, email, acao, modulo, entidade, entidade_id,
            dados_antes, dados_depois, ip, user_agent) VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9,$10) RETURNING id""",
            user_id, email, acao, modulo, entidade, entidade_id,
            json.dumps(dados_antes or {}, ensure_ascii=False) if dados_antes else None,
            json.dumps(dados_depois or {}, ensure_ascii=False) if dados_depois else None,
            ip, user_agent)
        return row["id"] if row else None
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"Erro auditar: {e}"); return None

def listar_auditoria(modulo: str = "", email: str = "", entidade: str = "", limit: int = 100) -> list:
    async def _go():
        db = await get_db()
        where = []; params = []; p = 0
        if modulo:
            p += 1; where.append(f"modulo = ${p}"); params.append(modulo)
        if email:
            p += 1; where.append(f"email ILIKE ${p}"); params.append(f"%{email}%")
        if entidade:
            p += 1; where.append(f"entidade = ${p}"); params.append(entidade)
        clause = " AND ".join(where) if where else "1=1"
        p += 1
        rows = await db.fetch(f"SELECT * FROM audit_log WHERE {clause} ORDER BY created_at DESC LIMIT ${p}", *params, limit)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except: return []

# ── System Logs ──

def syslog(level: str, modulo: str, mensagem: str, stacktrace: str = "", data: dict = None):
    levels = ["DEBUG","INFO","WARN","ERROR","FATAL"]
    if level.upper() not in levels: level = "INFO"
    async def _go():
        db = await get_db()
        await db.execute("INSERT INTO system_logs (level, modulo, mensagem, stacktrace, data) VALUES ($1,$2,$3,$4,$5::jsonb)",
            level.upper(), modulo, mensagem, stacktrace, json.dumps(data or {}, ensure_ascii=False))
    try: run_async(_go())
    except Exception as e: log(AGENT, f"Erro syslog: {e}")

def listar_logs(level: str = "", modulo: str = "", limit: int = 100) -> list:
    async def _go():
        db = await get_db()
        where = []; params = []; p = 0
        if level:
            p += 1; where.append(f"level = ${p}"); params.append(level.upper())
        if modulo:
            p += 1; where.append(f"modulo = ${p}"); params.append(modulo)
        clause = " AND ".join(where) if where else "1=1"
        p += 1
        rows = await db.fetch(f"SELECT * FROM system_logs WHERE {clause} ORDER BY created_at DESC LIMIT ${p}", *params, limit)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except: return []

# ── Historico de Alteracoes ──

def registrar_alteracao(entidade: str, entidade_id: int, campo: str, valor_antes: str, valor_depois: str, user_id: int = None, email: str = ""):
    async def _go():
        db = await get_db()
        await db.execute("""INSERT INTO change_history (entidade, entidade_id, campo, valor_antes, valor_depois, user_id, email)
            VALUES ($1,$2,$3,$4,$5,$6,$7)""", entidade, entidade_id, campo, str(valor_antes)[:500], str(valor_depois)[:500], user_id, email)
    try: run_async(_go())
    except Exception as e: log(AGENT, f"Erro change_history: {e}")

def listar_historico(entidade: str, entidade_id: int) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM change_history WHERE entidade=$1 AND entidade_id=$2 ORDER BY created_at DESC LIMIT 100", entidade, entidade_id)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except: return []

def historico_resumo(entidade: str, limit: int = 50) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT entidade, entidade_id, COUNT(*) as alteracoes, MAX(created_at) as ultima
            FROM change_history WHERE entidade=$1 GROUP BY entidade, entidade_id ORDER BY ultima DESC LIMIT $2""", entidade, limit)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except: return []

# ── Auditoria de login ──

def auditar_login(email: str, sucesso: bool, ip: str = "", user_agent: str = ""):
    acao = "login_sucesso" if sucesso else "login_falha"
    syslog("INFO" if sucesso else "WARN", "auth", f"Login {'OK' if sucesso else 'FALHA'}: {email}", data={"email": email, "ip": ip})
    return auditar(acao, "auth", "login", email=email, ip=ip, user_agent=user_agent,
                   dados_depois={"email": email, "sucesso": sucesso})

if __name__ == "__main__":
    log(AGENT, "Auto-teste Seguranca")
    aid = auditar("teste", "seguranca", "test", dados_depois={"msg": "ok"})
    print(f"Audit ID: {aid}")
    syslog("INFO", "seguranca", "Teste de log")
    print(f"Audit logs: {len(listar_auditoria())}")
    print(f"Sys logs: {len(listar_logs())}")
