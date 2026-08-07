"""Atendimento Core — Tickets, Chat, Canais, SLA, Base Conhecimento"""
import builtins
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

def _list(t: str, cols="*", order="id DESC", limit=500) -> list:
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

# ponytail: whitelist de colunas por tabela — _create/_update concatenam as
# CHAVES do dict recebido direto na string SQL (so' os valores sao
# parametrizados com $1, $2...). Sem essa whitelist, um cliente com permissao
# atendimento.criar/atendimento.editar poderia injetar SQL arbitrario via
# nome de campo no JSON (mesma classe de bug ja corrigida em core/crm.py).
ATEND_COLUNAS = {
    "tickets": {"cliente", "email", "telefone", "assunto", "canal", "prioridade",
                "status", "atendente_id", "sla_vencimento", "data_abertura",
                "data_fechamento", "tempo_resposta_min", "numero", "observacoes"},
    "mensagens": {"ticket_id", "remetente", "conteudo", "tipo", "anexo_url", "enviado_em"},
    "chat_sessoes": {"cliente", "atendente", "status", "data_inicio", "data_fim", "canal"},
    "canais": {"nome", "token", "url_webhook", "ativo", "config"},
    "sla": {"prioridade", "tempo_resposta_min", "tempo_resolucao_h", "ativo"},
    "kb_artigos": {"titulo", "categoria", "conteudo", "tags", "publicado"},
}

PRIORIDADES_SLA = ["baixa", "normal", "alta", "urgente"]

def _validar_campos(tabela: str, dados: dict, criando: bool) -> str | None:
    """Validacao de formato no boundary, antes de tocar o banco. Sem isso,
    um campo obrigatorio vazio ou invalido so' falhava (feio) na constraint
    do Postgres, sem mensagem util pro frontend."""
    if tabela == "sla":
        if criando and not str(dados.get("prioridade", "")).strip():
            return "Prioridade e obrigatoria"
        if dados.get("prioridade") and dados["prioridade"] not in PRIORIDADES_SLA:
            return f"Prioridade invalida — use uma de: {', '.join(PRIORIDADES_SLA)}"
        for campo, rotulo in (("tempo_resposta_min", "Tempo de resposta"), ("tempo_resolucao_h", "Tempo de resolucao")):
            if campo in dados and dados[campo] not in (None, ""):
                try:
                    if int(dados[campo]) <= 0:
                        return f"{rotulo} deve ser maior que zero"
                except (TypeError, ValueError):
                    return f"{rotulo} invalido"
        return None
    if tabela == "canais":
        from core.validadores import validar_url
        if criando and not str(dados.get("nome", "")).strip():
            return "Nome e obrigatorio"
        if "nome" in dados and not str(dados.get("nome", "")).strip():
            return "Nome nao pode ser vazio"
        if dados.get("url_webhook") and not validar_url(dados["url_webhook"]):
            return "URL do webhook invalida — use http:// ou https://"
        return None
    return None

# campos que nunca devem sair pela API generica, mesmo para quem tem
# permissao atendimento.ver — token de canal e' credencial de integracao
# externa (ex.: API key do WhatsApp/Evolution), nao ha motivo legitimo pro
# frontend le-lo de volta so' pra listar/editar o canal.
_CAMPOS_SENSIVEIS = {"canais": {"token"}}

def _sem_campos_sensiveis(tabela: str, registro):
    # ponytail: isinstance(x, list) quebra aqui — "list" nesse modulo e' a
    # funcao publica de CRUD (list(t), linha abaixo), nao o builtin. Precisa
    # do builtins.list explicito.
    campos = _CAMPOS_SENSIVEIS.get(tabela)
    if not campos:
        return registro
    if isinstance(registro, builtins.list):
        return [{k: v for k, v in r.items() if k not in campos} if isinstance(r, dict) else r for r in registro]
    if isinstance(registro, dict):
        return {k: v for k, v in registro.items() if k not in campos}
    return registro

def list(t: str): return _sem_campos_sensiveis(t, _list(f"atend_{t}"))
def get(t: str, i: int): return _sem_campos_sensiveis(t, _get(f"atend_{t}", i))

def create(t: str, d: dict) -> dict:
    colunas_validas = ATEND_COLUNAS.get(t)
    if colunas_validas is None:
        return {"error": "Tabela invalida"}
    filtrado = {k: v for k, v in d.items() if k in colunas_validas}
    if not filtrado:
        return {"error": "Nenhum campo valido informado"}
    erro = _validar_campos(t, filtrado, criando=True)
    if erro:
        return {"error": erro}
    return _sem_campos_sensiveis(t, _create(f"atend_{t}", filtrado))

def update(t: str, i: int, d: dict) -> dict:
    colunas_validas = ATEND_COLUNAS.get(t)
    if colunas_validas is None:
        return {"error": "Tabela invalida"}
    filtrado = {k: v for k, v in d.items() if k in colunas_validas}
    if not filtrado:
        return {"error": "Nenhum campo valido informado"}
    erro = _validar_campos(t, filtrado, criando=False)
    if erro:
        return {"error": erro}
    return _sem_campos_sensiveis(t, _update(f"atend_{t}", i, filtrado))

def delete(t: str, i: int): return _delete(f"atend_{t}", i)

# ── Operacoes especificas ──

def visualizar_artigo_kb(id: int) -> dict:
    """Incrementa o contador de visualizacoes de um artigo da KB — chamado
    quando o atendente abre o artigo completo (nao a cada listagem)."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "UPDATE atend_kb_artigos SET visualizacoes = visualizacoes + 1 WHERE id = $1 RETURNING *", id)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def votar_artigo_kb(id: int, util: bool) -> dict:
    """Registra um voto de utilidade (util_sim/util_nao) num artigo da KB.
    coluna e' escolhida entre 2 literais fixos (nunca vem direto do cliente),
    entao nao ha risco de injecao ao interpolar na query."""
    coluna = "util_sim" if util else "util_nao"
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            f"UPDATE atend_kb_artigos SET {coluna} = {coluna} + 1 WHERE id = $1 RETURNING *", id)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def criar_ticket(cliente: str, assunto: str, canal="whatsapp", prioridade="normal", email: str = "", telefone: str = "") -> dict:
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
        "cliente": cliente, "assunto": assunto, "canal": canal, "email": email, "telefone": telefone,
        # ponytail: data_abertura e' TIMESTAMP — asyncpg exige datetime.datetime
        # nativo pro bind, nao aceita string (hoje() retorna str). Mesmo
        # precedente ja documentado em core/fiscal.py._data,
        # core/i9logic_vendas.py._gravar_pedido e core/pdv.py.
        "prioridade": prioridade, "status": "aberto", "data_abertura": datetime.now(),
        "sla_vencimento": sla_data["sla_vencimento"],
        "tempo_resposta_min": sla_data["tempo_resposta_min"],
        "numero": numero,
    })
    if not ticket.get("error"):
        from core.chat import criar_conversa_ticket
        criar_conversa_ticket(ticket["id"])
    return ticket

def _serializar_mensagem_ticket(m: dict, conversa_id: int) -> dict:
    """Shape normalizado de mensagem de ticket — usado tanto no broadcast WS
    quanto no endpoint REST de listagem, pra garantir que os dois nunca
    divirjam (era exatamente essa divergencia que causava o double-broadcast
    com payloads diferentes pra mesma mensagem)."""
    enviado_em = m.get("enviado_em")
    return {
        "id": m["id"], "conversa_id": conversa_id, "thread_pai_id": None,
        "remetente_id": None, "remetente_nome": m.get("remetente"),
        "texto": m.get("conteudo"), "anexo_id": None, "anexo_url": m.get("anexo_url"),
        "created_at": enviado_em.isoformat() if hasattr(enviado_em, "isoformat") else enviado_em,
        "editado_em": None, "excluido_em": None,
    }

def adicionar_mensagem(ticket_id: int, remetente: str, conteudo: str, tipo="texto", anexo_url: str = None) -> dict:
    # ponytail: enviado_em e' TIMESTAMP — asyncpg exige datetime.datetime
    # nativo pro bind, nao aceita string (hoje() retorna str). Mesmo
    # precedente ja documentado em core/fiscal.py._data e core/pdv.py.
    from datetime import datetime
    campos = {"ticket_id": ticket_id, "remetente": remetente, "conteudo": conteudo, "tipo": tipo, "enviado_em": datetime.now()}
    if anexo_url:
        campos["anexo_url"] = anexo_url
    mensagem = create("mensagens", campos)
    if not mensagem.get("error"):
        from core.chat import conversa_id_do_ticket
        from core.chat_ws import broadcast_para_participantes
        conversa_id = conversa_id_do_ticket(ticket_id)
        if conversa_id:
            broadcast_para_participantes(conversa_id, {
                "evento": "nova_mensagem",
                "mensagem": _serializar_mensagem_ticket(mensagem, conversa_id),
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

TRANSICOES_STATUS = {
    "aberto": {"pendente", "fechado"},
    "pendente": {"aberto", "fechado"},
    "fechado": {"aberto"},
}

def mudar_status_ticket(ticket_id: int, novo_status: str) -> dict:
    """Aplica a maquina de estado de status do ticket (aberto <-> pendente ->
    fechado, reabrir sempre volta para aberto) e avisa participantes via WS."""
    ticket = get("tickets", ticket_id)
    if ticket.get("error"):
        return ticket
    atual = ticket.get("status", "aberto")
    if novo_status not in TRANSICOES_STATUS.get(atual, set()):
        return {"error": f"Transicao invalida: {atual} -> {novo_status}"}
    campos = {"status": novo_status}
    if novo_status == "fechado":
        # ponytail: data_fechamento e' TIMESTAMP — asyncpg exige
        # datetime.datetime nativo pro bind, nao aceita string (hoje()
        # retorna str). Mesmo precedente ja documentado em
        # core/fiscal.py._data e core/pdv.py.
        from datetime import datetime
        campos["data_fechamento"] = datetime.now()
    elif atual == "fechado":
        campos["data_fechamento"] = None
    resultado = update("tickets", ticket_id, campos)
    if not resultado.get("error"):
        from core.chat import conversa_id_do_ticket
        from core.chat_ws import broadcast_para_participantes
        conversa_id = conversa_id_do_ticket(ticket_id)
        if conversa_id:
            broadcast_para_participantes(conversa_id, {
                "evento": "ticket_status_alterado", "ticket_id": ticket_id,
                "status": novo_status, "conversa_id": conversa_id,
            })
    return resultado

def atribuir_ticket(ticket_id: int, atendente_id: int) -> dict:
    """Atribui um atendente ao ticket: valida que o atendente existe e esta
    ativo, atualiza o ticket, avisa participantes da conversa via WS e manda
    notificacao + evento WS direto pro atendente designado."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT id, nome FROM rbac_usuarios WHERE id=$1 AND ativo=TRUE", atendente_id)
        return dict(row) if row else None
    try:
        atendente = run_async(_go())
    except Exception as e:
        return {"error": str(e)}
    if not atendente:
        return {"error": "Atendente nao encontrado ou inativo"}

    resultado = update("tickets", ticket_id, {"atendente_id": atendente_id})
    if resultado.get("error"):
        return resultado

    from core.chat import conversa_id_do_ticket
    from core.chat_ws import broadcast_para_participantes, enviar_para_usuario
    from core.notificacoes import criar_notificacao

    conversa_id = conversa_id_do_ticket(ticket_id)
    if conversa_id:
        broadcast_para_participantes(conversa_id, {
            "evento": "ticket_atendente_alterado", "ticket_id": ticket_id,
            "atendente_id": atendente_id, "atendente_nome": atendente["nome"], "conversa_id": conversa_id,
        })

    numero = resultado.get("numero") or f"#{ticket_id}"
    notificacao = criar_notificacao(
        atendente_id, "ticket_atribuido",
        f"Ticket {numero} atribuido a voce",
        resultado.get("assunto") or "",
        f"/atendimento/tickets/{ticket_id}",
    )
    if not notificacao.get("error"):
        payload = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in notificacao.items()}
        enviar_para_usuario(atendente_id, {"evento": "notificacao", **payload})
    return resultado

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

def _parse_data_filtro(s):
    """Converte string 'YYYY-MM-DD...' (query param de/ate) para date real —
    asyncpg exige um objeto date/datetime nos parametros ligados a coluna
    TIMESTAMP, nao aceita string mesmo com ::date (mesmo precedente ja
    documentado em core/fiscal.py._data e core/i9logic_vendas.py._gravar_pedido).
    Retorna None se vazio ou nao-parseavel — quem chama decide o que fazer."""
    if not s:
        return None
    from datetime import datetime
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

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
    if de:
        de_data = _parse_data_filtro(de)
        if de_data: _add("data_abertura >= ${n}", de_data)
        else: log(AGENT, f"listar_tickets_filtrado: filtro 'de' invalido ignorado ({de!r})")
    if ate:
        ate_data = _parse_data_filtro(ate)
        if ate_data: _add("data_abertura <= ${n}", ate_data)
        else: log(AGENT, f"listar_tickets_filtrado: filtro 'ate' invalido ignorado ({ate!r})")
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
