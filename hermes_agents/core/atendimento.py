"""Atendimento Core — Tickets, Chat, Canais, SLA, Base Conhecimento"""
from core import get_db, run_async, log, hoje

AGENT = "Atendimento Core"

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS atend_tickets (
            id SERIAL PRIMARY KEY, numero VARCHAR(30), cliente VARCHAR(200),
            email VARCHAR(100), telefone VARCHAR(30), assunto VARCHAR(200),
            canal VARCHAR(30) DEFAULT 'whatsapp', prioridade VARCHAR(20) DEFAULT 'normal',
            status VARCHAR(30) DEFAULT 'aberto', atendente VARCHAR(100),
            sla_vencimento TIMESTAMP, data_abertura TIMESTAMP DEFAULT NOW(),
            data_fechamento TIMESTAMP, tempo_resposta_min INT,
            observacoes TEXT, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("CREATE SEQUENCE IF NOT EXISTS atend_tickets_numero_seq")
        try:
            await db.execute("ALTER TABLE atend_tickets RENAME COLUMN atendente TO atendente_nome_legado")
        except Exception:
            pass
        await db.execute("ALTER TABLE atend_tickets ADD COLUMN IF NOT EXISTS atendente_id INT REFERENCES rbac_usuarios(id)")
        await db.execute("""CREATE TABLE IF NOT EXISTS atend_mensagens (
            id SERIAL PRIMARY KEY, ticket_id INT REFERENCES atend_tickets(id),
            remetente VARCHAR(100), conteudo TEXT, tipo VARCHAR(20) DEFAULT 'texto',
            anexo_url VARCHAR(500), enviado_em TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS atend_chat_sessoes (
            id SERIAL PRIMARY KEY, cliente VARCHAR(200), atendente VARCHAR(100),
            status VARCHAR(20) DEFAULT 'ativa', data_inicio TIMESTAMP DEFAULT NOW(),
            data_fim TIMESTAMP, canal VARCHAR(30) DEFAULT 'chat'
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS atend_canais (
            id SERIAL PRIMARY KEY, nome VARCHAR(50) UNIQUE NOT NULL,
            token VARCHAR(500), url_webhook VARCHAR(300), ativo BOOLEAN DEFAULT TRUE,
            config JSONB DEFAULT '{}', created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS atend_sla (
            id SERIAL PRIMARY KEY, prioridade VARCHAR(20) UNIQUE NOT NULL,
            tempo_resposta_min INT DEFAULT 60, tempo_resolucao_h INT DEFAULT 24,
            ativo BOOLEAN DEFAULT TRUE
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS atend_kb_artigos (
            id SERIAL PRIMARY KEY, titulo VARCHAR(300) NOT NULL,
            categoria VARCHAR(100), conteudo TEXT, tags VARCHAR(300),
            visualizacoes INT DEFAULT 0, util_sim INT DEFAULT 0, util_nao INT DEFAULT 0,
            publicado BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        # Seed SLA defaults
        count = await db.fetchval("SELECT COUNT(*) FROM atend_sla")
        if count == 0:
            for p, t in [("baixa",48,72),("normal",24,48),("alta",4,8),("urgente",1,2)]:
                await db.execute("INSERT INTO atend_sla (prioridade,tempo_resposta_min,tempo_resolucao_h) VALUES ($1,$2,$3)", p, t[0], t[1])
        # Seed canais defaults
        count2 = await db.fetchval("SELECT COUNT(*) FROM atend_canais")
        if count2 == 0:
            for nome in ["whatsapp","telegram","instagram","facebook","chat","email"]:
                await db.execute("INSERT INTO atend_canais (nome,ativo) VALUES ($1,TRUE) ON CONFLICT DO NOTHING", nome)
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro tabelas atendimento: {e}")

_ensure_tables()

# ── CRUD ──

def _list(t: str, cols="*", order="id DESC", limit=100) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"SELECT {cols} FROM {t} ORDER BY {order} LIMIT {limit}")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"list {t}: {e}"); return []

def _get(t: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"SELECT * FROM {t} WHERE id = $1", id)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def _create(t: str, d: dict) -> dict:
    # ponytail: NAO usar list(...) — este modulo define list(t) no nivel de
    # modulo (funcao publica de CRUD), que sombreia o builtin para qualquer
    # funcao neste arquivo. list(d.keys()) chamaria list(t) com um dict_keys,
    # gerando um INSERT vazio (colunas/valores nulos) sem erro visivel.
    keys = [*d.keys()]; vals = [*d.values()]
    ph = ", ".join(f"${i+1}" for i in range(len(keys)))
    cols = ", ".join(keys)
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"INSERT INTO {t} ({cols}) VALUES ({ph}) RETURNING *", *vals)
        return dict(row) if row else {"error": "insert failed"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def _update(t: str, id: int, d: dict) -> dict:
    sets = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(d.keys()))
    vals = [*d.values(), id]
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"UPDATE {t} SET {sets} WHERE id = ${len(vals)} RETURNING *", *vals)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def _delete(t: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        await db.execute(f"DELETE FROM {t} WHERE id = $1", id)
        return {"success": True}
    try: run_async(_go()); return {"success": True}
    except Exception as e: return {"error": str(e)}

TABLES = ["tickets","mensagens","chat_sessoes","canais","sla","kb_artigos"]
def list(t: str): return _list(f"atend_{t}")
def get(t: str, i: int): return _get(f"atend_{t}", i)
def create(t: str, d: dict): return _create(f"atend_{t}", d)
def update(t: str, i: int, d: dict): return _update(f"atend_{t}", i, d)
def delete(t: str, i: int): return _delete(f"atend_{t}", i)

# ── Operacoes especificas ──

def criar_ticket(cliente: str, assunto: str, canal="whatsapp", prioridade="normal") -> dict:
    """Cria ticket com SLA aplicado — vencimento e tempo de resposta da regra da prioridade."""
    from datetime import datetime, timedelta
    async def _go():
        db = await get_db()
        sla_row = await db.fetchrow("SELECT tempo_resposta_min, tempo_resolucao_h FROM atend_sla WHERE prioridade = $1 AND ativo = TRUE", prioridade)
        agora = datetime.now()
        sla_vencimento = agora + timedelta(minutes=sla_row["tempo_resposta_min"]) if sla_row else None
        tempo_resposta = sla_row["tempo_resposta_min"] if sla_row else None
        numero_seq = await db.fetchval("SELECT nextval('atend_tickets_numero_seq')")
        return {"sla_vencimento": sla_vencimento, "tempo_resposta_min": tempo_resposta, "numero_seq": numero_seq}
    try: sla_data = run_async(_go())
    except Exception as e: sla_data = {"sla_vencimento": None, "tempo_resposta_min": None, "numero_seq": None}

    numero = f"#{sla_data['numero_seq']:04d}" if sla_data.get("numero_seq") else None
    ticket = create("tickets", {
        "cliente": cliente, "assunto": assunto, "canal": canal,
        "prioridade": prioridade, "status": "aberto", "data_abertura": hoje(),
        "sla_vencimento": sla_data["sla_vencimento"],
        "tempo_resposta_min": sla_data["tempo_resposta_min"],
        "numero": numero,
    })
    if not ticket.get("error"):
        from core.chat import criar_conversa_ticket
        criar_conversa_ticket(ticket["id"])
    return ticket

def adicionar_mensagem(ticket_id: int, remetente: str, conteudo: str, tipo="texto") -> dict:
    mensagem = create("mensagens", {"ticket_id": ticket_id, "remetente": remetente,
        "conteudo": conteudo, "tipo": tipo, "enviado_em": hoje()})
    if not mensagem.get("error"):
        from core.chat import conversa_id_do_ticket
        from core.chat_ws import broadcast_para_participantes
        conversa_id = conversa_id_do_ticket(ticket_id)
        if conversa_id:
            broadcast_para_participantes(conversa_id, {
                "evento": "nova_mensagem", "ticket_id": ticket_id,
                "mensagem": {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in mensagem.items()},
            })
    return mensagem
def listar_mensagens_ticket(ticket_id: int) -> list:
    """Mensagens de UM ticket, em ordem cronologica — usado pela ponte do chat
    interno (conversa tipo 'ticket' le/escreve em atend_mensagens, nao em
    chat_mensagens)."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM atend_mensagens WHERE ticket_id=$1 ORDER BY enviado_em ASC", ticket_id)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"listar_mensagens_ticket: {e}"); return []

def fechar_ticket(ticket_id: int) -> dict:
    return update("tickets", ticket_id, {"status": "fechado", "data_fechamento": hoje()})

def reabrir_ticket(ticket_id: int) -> dict:
    return update("tickets", ticket_id, {"status": "aberto", "data_fechamento": None})

def dashboard() -> dict:
    async def _go():
        db = await get_db()
        abertos = await db.fetchval("SELECT COUNT(*) FROM atend_tickets WHERE status = 'aberto'")
        pendentes = await db.fetchval("SELECT COUNT(*) FROM atend_tickets WHERE status IN ('aberto','pendente')")
        hoje_tickets = await db.fetchval("SELECT COUNT(*) FROM atend_tickets WHERE DATE(data_abertura) = CURRENT_DATE")
        tempo_medio = await db.fetchval("SELECT COALESCE(AVG(tempo_resposta_min),0) FROM atend_tickets WHERE tempo_resposta_min IS NOT NULL")
        canais = await db.fetch("SELECT canal, COUNT(*) as cnt FROM atend_tickets WHERE status='aberto' GROUP BY canal")
        slas = await db.fetch("SELECT * FROM atend_sla ORDER BY tempo_resposta_min")
        return {
            "tickets_abertos": abertos or 0, "tickets_pendentes": pendentes or 0,
            "hoje": hoje_tickets or 0, "tempo_medio_resposta": float(tempo_medio or 0),
            "canais": [dict(r) for r in (canais or [])],
            "slas": [dict(r) for r in (slas or [])],
        }
    try: return run_async(_go())
    except Exception as e: return {"tickets_abertos":0,"tickets_pendentes":0,"hoje":0,"tempo_medio_resposta":0,"canais":[],"slas":[]}

def listar_tickets_filtrado(status=None, prioridade=None, canal=None, atendente_id=None, q=None, de=None, ate=None) -> list:
    where = []
    params = []
    def _add(cond, val):
        params.append(val)
        where.append(cond.format(n=len(params)))
    if status: _add("status = ${n}", status)
    if prioridade: _add("prioridade = ${n}", prioridade)
    if canal: _add("canal = ${n}", canal)
    if atendente_id: _add("atendente_id = ${n}", int(atendente_id))
    if q: _add("(cliente ILIKE ${n} OR assunto ILIKE ${n} OR numero ILIKE ${n})", f"%{q}%")
    if de: _add("data_abertura >= ${n}", de)
    if ate: _add("data_abertura <= ${n}", ate)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"SELECT * FROM atend_tickets {where_sql} ORDER BY id DESC LIMIT 200", *params)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"listar_tickets_filtrado: {e}"); return []

def listar_atendentes() -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT id, nome FROM rbac_usuarios WHERE ativo = TRUE ORDER BY nome")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"listar_atendentes: {e}"); return []
