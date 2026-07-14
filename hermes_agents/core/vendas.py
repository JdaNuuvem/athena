"""Vendas Core — Pedidos, Itens, Pagamentos, Dashboard, Integracao Bling"""
from core import get_db, run_async, log, hoje

AGENT = "Vendas Core"

TABLES = ["pedidos", "itens", "pagamentos"]

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS vendas_pedidos (
            id SERIAL PRIMARY KEY, numero VARCHAR(30), cliente VARCHAR(200),
            cliente_documento VARCHAR(20), status VARCHAR(30) DEFAULT 'aberto',
            total DECIMAL(12,2) DEFAULT 0, desconto DECIMAL(12,2) DEFAULT 0,
            acrescimo DECIMAL(12,2) DEFAULT 0, frete DECIMAL(12,2) DEFAULT 0,
            data DATE DEFAULT CURRENT_DATE, data_entrega DATE, data_faturamento DATE,
            vendedor VARCHAR(100), marketplace VARCHAR(30), origem VARCHAR(30) DEFAULT 'manual',
            bling_id BIGINT, bling_numero VARCHAR(30), loja_id INT,
            observacoes TEXT, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS vendas_itens (
            id SERIAL PRIMARY KEY, pedido_id INT REFERENCES vendas_pedidos(id),
            numero_item INT DEFAULT 1, sku VARCHAR(50), descricao VARCHAR(200),
            quantidade DECIMAL(12,3) DEFAULT 0, unidade VARCHAR(10) DEFAULT 'UN',
            valor_unitario DECIMAL(12,4) DEFAULT 0, valor_total DECIMAL(12,2) DEFAULT 0,
            desconto DECIMAL(12,2) DEFAULT 0, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS vendas_pagamentos (
            id SERIAL PRIMARY KEY, pedido_id INT REFERENCES vendas_pedidos(id),
            forma VARCHAR(30) NOT NULL, valor DECIMAL(12,2) DEFAULT 0,
            parcelas INT DEFAULT 1, bandeira VARCHAR(30), autorizacao VARCHAR(50),
            data TIMESTAMP DEFAULT NOW(), created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS vendas_historico_status (
            id SERIAL PRIMARY KEY, pedido_id INT REFERENCES vendas_pedidos(id),
            status_anterior VARCHAR(30), status_novo VARCHAR(30) NOT NULL,
            usuario VARCHAR(100), motivo TEXT, data TIMESTAMP DEFAULT NOW()
        )""")
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro tabelas vendas: {e}")

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

def list(t: str): return _list(f"vendas_{t}")
def get(t: str, i: int): return _get(f"vendas_{t}", i)
def create(t: str, d: dict): return _create(f"vendas_{t}", d)
def update(t: str, i: int, d: dict): return _update(f"vendas_{t}", i, d)
def delete(t: str, i: int): return _delete(f"vendas_{t}", i)

# ── Listagem com filtro ──

DATE_FIELDS = {"pedidos": "data", "itens": "created_at", "pagamentos": "data"}

def _list_filtered(t: str, date_field: str, data_inicio: str = "", data_fim: str = "", dias: int = 0, status: str = "", order: str = "id DESC", limit: int = 500) -> list:
    async def _go():
        db = await get_db()
        where = []
        params = []
        p = 1
        if data_inicio:
            where.append(f"{date_field} >= ${p}::date"); params.append(data_inicio); p += 1
        if data_fim:
            where.append(f"{date_field} <= ${p}::date"); params.append(data_fim); p += 1
        if dias > 0 and not (data_inicio or data_fim):
            where.append(f"{date_field} >= CURRENT_DATE - ${p}"); params.append(dias); p += 1
        if status:
            where.append(f"status = ${p}"); params.append(status); p += 1
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        rows = await db.fetch(f"SELECT * FROM {t} {clause} ORDER BY {order} LIMIT {limit}", *params)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"list_filtered {t}: {e}"); return []

def listar_filtrado(tabela: str, data_inicio: str = "", data_fim: str = "", dias: int = 0, status: str = "") -> dict:
    t = f"vendas_{tabela}"
    field = DATE_FIELDS.get(tabela, "created_at")
    return {"data": _list_filtered(t, field, data_inicio, data_fim, dias, status)}

# ── Operacoes ──

def criar_pedido(cliente: str, itens: list, pagamentos: list, **kwargs) -> dict:
    total_itens = sum(float(i.get("valor_total", 0) or (i.get("quantidade", 1) or 1) * (i.get("valor_unitario", 0) or 0)) for i in itens)
    desconto = float(kwargs.get("desconto", 0))
    frete = float(kwargs.get("frete", 0))
    total = round(total_itens - desconto + frete, 2)
    pedido = create("pedidos", {
        "cliente": cliente, "total": total, "desconto": desconto, "frete": frete,
        "vendedor": kwargs.get("vendedor", ""), "marketplace": kwargs.get("marketplace", "manual"),
        "status": kwargs.get("status", "aberto"), "loja_id": kwargs.get("loja_id"),
        "observacoes": kwargs.get("observacoes", ""),
    })
    if pedido.get("error"): return pedido
    pid = pedido["id"]
    for item in itens:
        create("itens", {"pedido_id": pid, "sku": item.get("sku",""), "descricao": item.get("descricao",""),
            "quantidade": item.get("quantidade", 1), "valor_unitario": item.get("valor_unitario", 0),
            "valor_total": item.get("valor_total", (item.get("quantidade",1) or 1) * (item.get("valor_unitario",0) or 0))})
    for pg in pagamentos:
        create("pagamentos", {"pedido_id": pid, "forma": pg.get("forma","dinheiro"),
            "valor": pg.get("valor", total), "parcelas": pg.get("parcelas", 1)})
    return {"pedido": pedido, "total": total}

def detalhe_pedido(id: int) -> dict:
    pedido = get("pedidos", id)
    if pedido.get("error"): return pedido
    async def _go():
        db = await get_db()
        itens = await db.fetch("SELECT * FROM vendas_itens WHERE pedido_id = $1 ORDER BY numero_item", id)
        pagamentos = await db.fetch("SELECT * FROM vendas_pagamentos WHERE pedido_id = $1", id)
        historico = await db.fetch("SELECT * FROM vendas_historico_status WHERE pedido_id = $1 ORDER BY data DESC", id)
        return {"pedido": pedido, "itens": [dict(r) for r in itens], "pagamentos": [dict(r) for r in pagamentos], "historico": [dict(r) for r in historico]}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def atualizar_status(id: int, novo_status: str, usuario: str = "") -> dict:
    atual = get("pedidos", id)
    status_anterior = atual.get("status", "")
    async def _go():
        db = await get_db()
        await db.execute("INSERT INTO vendas_historico_status (pedido_id, status_anterior, status_novo, usuario) VALUES ($1,$2,$3,$4)",
            id, status_anterior, novo_status, usuario)
        row = await db.fetchrow("UPDATE vendas_pedidos SET status=$1, updated_at=NOW() WHERE id=$2 RETURNING *", novo_status, id)
        return dict(row) if row else {"error":"not found"}
    try: return run_async(_go())
    except Exception as e: return {"error":str(e)}

# ── Dashboard ──

def dashboard(dias: int = 30) -> dict:
    async def _go():
        db = await get_db()
        total = await db.fetchval("SELECT COALESCE(SUM(total),0) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1 AND status != 'cancelado'", dias)
        qtd = await db.fetchval("SELECT COUNT(*) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1", dias)
        abertos = await db.fetchval("SELECT COUNT(*) FROM vendas_pedidos WHERE status = 'aberto'")
        faturados = await db.fetchval("SELECT COUNT(*) FROM vendas_pedidos WHERE status IN ('faturado','concluido') AND data >= CURRENT_DATE - $1", dias)
        cancelados = await db.fetchval("SELECT COUNT(*) FROM vendas_pedidos WHERE status = 'cancelado' AND data >= CURRENT_DATE - $1", dias)
        ticket_medio = round(float(total or 0) / max(qtd or 1, 1), 2)
        # vendas diarias
        diarias = await db.fetch("SELECT DATE(data) as dia, COUNT(*) as qtd, COALESCE(SUM(total),0) as valor FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1 AND status != 'cancelado' GROUP BY DATE(data) ORDER BY dia", dias)
        # por marketplace
        por_canal = await db.fetch("SELECT COALESCE(marketplace,'manual') as canal, COUNT(*) as qtd, COALESCE(SUM(total),0) as valor FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1 AND status != 'cancelado' GROUP BY marketplace ORDER BY valor DESC", dias)
        # ultimos pedidos
        recentes = await db.fetch("SELECT id, numero, cliente, total, status, data, marketplace FROM vendas_pedidos ORDER BY id DESC LIMIT 5")
        return {
            "total_vendas": float(total or 0), "quantidade": qtd or 0,
            "ticket_medio": ticket_medio, "pedidos_abertos": abertos or 0,
            "faturados": faturados or 0, "cancelados": cancelados or 0,
            "periodo_dias": dias,
            "diarias": [dict(r) for r in (diarias or [])],
            "por_canal": [dict(r) for r in (por_canal or [])],
            "recentes": [dict(r) for r in (recentes or [])],
        }
    try: return run_async(_go())
    except: return {"total_vendas":0,"quantidade":0,"ticket_medio":0,"pedidos_abertos":0,"faturados":0,"cancelados":0,"periodo_dias":dias,"diarias":[],"por_canal":[],"recentes":[]}

# ── Bling Sync ──

def sincronizar_pedidos_bling(pagina: int = 1, limite: int = 100) -> dict:
    from bling_erp import listar_pedidos as bling_pedidos, get_access_token, get_auth_url
    token = get_access_token()
    if not token: return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}
    r = bling_pedidos(pagina, limite)
    if r.get("error"): return r
    dados = r.get("data", [])
    if not dados: return {"sync": 0, "message": "sem dados"}
    async def _go():
        db = await get_db()
        total = 0
        mapa_status = {1:"aberto", 6:"concluido", 9:"cancelado", 12:"em_andamento", 15:"faturado", 18:"devolvido"}
        for ped in dados:
            try:
                bling_id = ped.get("id")
                if not bling_id: continue
                existing = await db.fetchval("SELECT id FROM vendas_pedidos WHERE bling_id = $1", bling_id)
                contato = ped.get("contato", {}) or {}
                data_str = (ped.get("data") or ped.get("dataEmissao") or "")[:10] or None
                data_saida = (ped.get("dataSaida") or "")[:10] or None
                total_val = float(ped.get("total", 0) or 0)
                situacao = ped.get("situacao", {}) or {}
                sit_id = situacao.get("id") if isinstance(situacao, dict) else situacao
                status = mapa_status.get(sit_id, "aberto")
                loja = ped.get("loja", {}) or {}
                if existing:
                    await db.execute("""UPDATE vendas_pedidos SET
                        cliente=$1, total=$2, status=$3, data=$4::date, data_entrega=$5::date,
                        marketplace='bling', loja_id=$6, observacoes=$7, updated_at=NOW()
                        WHERE bling_id=$8""",
                        contato.get("nome",""), total_val, status, data_str, data_saida,
                        loja.get("id"), ped.get("observacoes",""), bling_id)
                else:
                    await db.execute("""INSERT INTO vendas_pedidos
                        (cliente, cliente_documento, total, status, data, data_entrega,
                         marketplace, origem, bling_id, bling_numero, loja_id, observacoes)
                        VALUES ($1,$2,$3,$4,$5::date,$6::date,'bling','bling',$7,$8,$9,$10)""",
                        contato.get("nome",""), contato.get("numeroDocumento",""),
                        total_val, status, data_str, data_saida,
                        bling_id, str(ped.get("numero","")), loja.get("id"),
                        ped.get("observacoes",""))
                # Sync itens
                pid = await db.fetchval("SELECT id FROM vendas_pedidos WHERE bling_id = $1", bling_id)
                if pid and not existing:
                    itens = ped.get("itens", []) or []
                    for idx, item in enumerate(itens, 1):
                        qtd = float(item.get("quantidade", 0) or 0)
                        vu = float(item.get("valorUnitario", 0) or 0)
                        vt = float(item.get("valor", 0) or 0) or (qtd * vu)
                        await db.execute("""INSERT INTO vendas_itens
                            (pedido_id, numero_item, sku, descricao, quantidade, valor_unitario, valor_total)
                            VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                            pid, idx, item.get("codigo",""), item.get("descricao",""), qtd, vu, vt)
                total += 1
            except Exception as e:
                log(AGENT, f"Erro sync pedido {ped.get('numero')}: {e}")
        return {"sync": total}
    return run_async(_go())

# ── Seed ──

def _seed():
    async def _go():
        db = await get_db()
        count = await db.fetchval("SELECT COUNT(*) FROM vendas_pedidos")
        if count == 0:
            from datetime import date, timedelta
            hoje = date.today()
            await db.execute("""INSERT INTO vendas_pedidos (cliente, total, status, data, marketplace, vendedor, observacoes) VALUES
                ('Carlos Alberto', 3500.00, 'aberto', $1, 'manual', 'Joao', 'Cliente recorrente'),
                ('Distribuidora ABC', 12800.50, 'faturado', $2, 'bling', 'Maria', ''),
                ('Marina Santos', 1800.00, 'concluido', $3, 'manual', 'Pedro', 'Entrega expressa'),
                ('Tech Solutions Ltda', 5400.00, 'em_andamento', $4, 'shopee', 'Ana', ''),
                ('Comercio Local ME', 2300.00, 'cancelado', $5, 'manual', 'Joao', 'Cliente desistiu')""",
                hoje, hoje - timedelta(days=2), hoje - timedelta(days=5),
                hoje - timedelta(days=1), hoje - timedelta(days=3))
            await db.execute("""INSERT INTO vendas_itens (pedido_id, sku, descricao, quantidade, valor_unitario, valor_total) VALUES
                (1,'PROD-001','Produto A',2,1000.00,2000.00),(1,'PROD-002','Produto B',1,1500.00,1500.00),
                (2,'PROD-003','Produto C',4,3200.00,12800.50),
                (3,'PROD-001','Produto A',1,1800.00,1800.00),
                (4,'PROD-004','Produto D',3,1800.00,5400.00),
                (5,'PROD-002','Produto B',1,2300.00,2300.00)""")
            await db.execute("""INSERT INTO vendas_pagamentos (pedido_id, forma, valor, parcelas) VALUES
                (1,'pix',2000.00,1),(1,'boleto',1500.00,1),
                (2,'boleto',12800.50,3),
                (3,'pix',1800.00,1),
                (4,'cartao',5400.00,6),
                (5,'dinheiro',2300.00,1)""")
    try: run_async(_go())
    except Exception as e: log(AGENT, f"Erro seed vendas: {e}")

_seed()
