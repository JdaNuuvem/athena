"""Vendas Core — Pedidos, Itens, Pagamentos, Dashboard, Integracao Bling"""
import time
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
        try: await db.execute("ALTER TABLE vendas_pedidos ADD COLUMN IF NOT EXISTS transportadora_nome VARCHAR(200)")
        except: pass
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
    try:
        result = run_async(_go())
        if novo_status == "faturado":
            try:
                from core.entidades import ao_faturar_pedido
                ao_faturar_pedido(id)
            except: pass
        return result
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

MAPA_STATUS_BLING = {1:"pendente", 2:"aberto", 6:"concluido", 9:"cancelado", 12:"em_andamento", 15:"faturado", 18:"enviado", 21:"entregue", 24:"devolvido"}

def _mapear_pedido_detalhe(ped: dict) -> dict:
    """Mapeia o payload de detalhe do Bling (GET /pedidos/vendas/{id}) para vendas_pedidos.
    Traz frete, vendedor e transportadora que a listagem (GET /pedidos/vendas) nao inclui."""
    contato = ped.get("contato", {}) or {}
    situacao = ped.get("situacao", {}) or {}
    sit_id = situacao.get("id") if isinstance(situacao, dict) else situacao
    loja = ped.get("loja", {}) or {}
    vendedor = ped.get("vendedor", {}) or {}
    vendedor_contato = vendedor.get("contato", {}) if isinstance(vendedor, dict) else {}
    transporte = ped.get("transporte", {}) or {}
    transportadora = transporte.get("transportadora", {}) or transporte.get("contato", {}) or {}

    return {
        "cliente": contato.get("nome", ""),
        "cliente_documento": contato.get("numeroDocumento", ""),
        "total": float(ped.get("total", 0) or 0),
        "desconto": float(ped.get("desconto", 0) or transporte.get("desconto", 0) or 0),
        "acrescimo": float(ped.get("outrasDespesas", 0) or ped.get("acrescimo", 0) or 0),
        "frete": float(transporte.get("frete", 0) or ped.get("valorFrete", 0) or 0),
        "status": MAPA_STATUS_BLING.get(sit_id, "aberto"),
        "data": (ped.get("data") or ped.get("dataEmissao") or "")[:10] or None,
        "data_entrega": (ped.get("dataSaida") or ped.get("dataPrevistaEntrega") or "")[:10] or None,
        "vendedor": vendedor_contato.get("nome", "") or vendedor.get("nome", ""),
        "loja_id": loja.get("id"),
        "observacoes": ped.get("observacoes", "") or ped.get("observacoesInternas", ""),
        "transportadora_nome": transportadora.get("nome", ""),
    }

def sincronizar_pedidos_bling(pagina: int = 1, limite: int = 100) -> dict:
    """Sync completo: lista todas as paginas de pedidos e busca o DETALHE de cada um
    (GET /pedidos/vendas/{id}) para importar frete, vendedor, transportadora e parcelas —
    dados que a listagem (GET /pedidos/vendas) nao traz."""
    from bling_erp import listar_pedidos as bling_pedidos, get_pedido_detalhe, get_access_token, get_auth_url
    token = get_access_token()
    if not token: return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}

    MAX_PAGINAS = 50  # limite de seguranca: evita loop/chamadas ilimitadas em contas com muitos pedidos
    pedidos_resumo = []
    erros = []
    pag = pagina
    mais_paginas = False
    for _ in range(MAX_PAGINAS):
        r = bling_pedidos(pag, limite)
        dados = r.get("data", [])
        if not dados or r.get("error"):
            if r.get("error"): erros.append(f"pag {pag}: {r['error']}")
            break
        pedidos_resumo.extend(dados)
        if len(dados) < limite:
            break
        pag += 1
    else:
        mais_paginas = True  # atingiu MAX_PAGINAS sem esgotar a listagem — rode de novo para continuar
    if not pedidos_resumo:
        return {"sync": 0, "message": "sem dados", "erros": erros}

    async def _go():
        db = await get_db()
        total = 0
        for ped_resumo in pedidos_resumo:
            bling_id = ped_resumo.get("id")
            if not bling_id:
                continue
            detalhe = None
            for attempt in range(3):
                r_detalhe = get_pedido_detalhe(bling_id)
                if not r_detalhe.get("error"):
                    detalhe = r_detalhe.get("data", {})
                    break
                if r_detalhe.get("status_code") == 429:
                    time.sleep(2 ** attempt)
                    continue
                erros.append(f"pedido {bling_id}: {r_detalhe['error']}")
                break
            if not detalhe:
                detalhe = ped_resumo  # fallback: usa ao menos o resumo da listagem

            try:
                existing = await db.fetchval("SELECT id FROM vendas_pedidos WHERE bling_id = $1", bling_id)
                campos = _mapear_pedido_detalhe(detalhe)
                if existing:
                    await db.execute("""UPDATE vendas_pedidos SET
                        cliente=$1, cliente_documento=$2, total=$3, desconto=$4, acrescimo=$5, frete=$6,
                        status=$7, data=$8::date, data_entrega=$9::date, vendedor=$10, transportadora_nome=$11,
                        marketplace='bling', loja_id=$12, observacoes=$13, updated_at=NOW()
                        WHERE bling_id=$14""",
                        campos["cliente"], campos["cliente_documento"], campos["total"], campos["desconto"],
                        campos["acrescimo"], campos["frete"], campos["status"], campos["data"], campos["data_entrega"],
                        campos["vendedor"], campos["transportadora_nome"], campos["loja_id"], campos["observacoes"], bling_id)
                    pid = existing
                    await db.execute("DELETE FROM vendas_itens WHERE pedido_id = $1", pid)
                    await db.execute("DELETE FROM vendas_pagamentos WHERE pedido_id = $1", pid)
                else:
                    pid = await db.fetchval("""INSERT INTO vendas_pedidos
                        (cliente, cliente_documento, total, desconto, acrescimo, frete, status, data, data_entrega,
                         vendedor, transportadora_nome, marketplace, origem, bling_id, bling_numero, loja_id, observacoes)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8::date,$9::date,$10,$11,'bling','bling',$12,$13,$14,$15)
                        RETURNING id""",
                        campos["cliente"], campos["cliente_documento"], campos["total"], campos["desconto"],
                        campos["acrescimo"], campos["frete"], campos["status"], campos["data"], campos["data_entrega"],
                        campos["vendedor"], campos["transportadora_nome"], bling_id, str(detalhe.get("numero", "")), campos["loja_id"], campos["observacoes"])

                itens = detalhe.get("itens", []) or []
                for idx, item in enumerate(itens, 1):
                    qtd = float(item.get("quantidade", 0) or 0)
                    vu = float(item.get("valorUnitario", 0) or 0)
                    vt = float(item.get("valor", 0) or 0) or (qtd * vu)
                    await db.execute("""INSERT INTO vendas_itens
                        (pedido_id, numero_item, sku, descricao, quantidade, valor_unitario, valor_total)
                        VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                        pid, idx, item.get("codigo",""), item.get("descricao",""), qtd, vu, vt)

                parcelas = detalhe.get("parcelas", []) or []
                for parcela in parcelas:
                    forma_pg = parcela.get("formaPagamento", {}) or {}
                    await db.execute("""INSERT INTO vendas_pagamentos
                        (pedido_id, forma, valor, parcelas, data)
                        VALUES ($1,$2,$3,$4,$5::date)""",
                        pid, forma_pg.get("descricao", "") or "nao_informado",
                        float(parcela.get("valor", 0) or 0), 1,
                        (parcela.get("data") or "")[:10] or None)
                total += 1
            except Exception as e:
                log(AGENT, f"Erro sync pedido {ped_resumo.get('numero')}: {e}")
        return {"sync": total, "erros": erros, "mais_paginas": mais_paginas}
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
