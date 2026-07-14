"""PDV Core — Vendas, Caixa, Pagamentos, Sangria, Suprimento, Fechamento, NFCe"""
from core import get_db, run_async, log, hoje

AGENT = "PDV Core"

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_caixas (
            id SERIAL PRIMARY KEY, numero VARCHAR(20), operador VARCHAR(100),
            saldo_inicial DECIMAL(12,2) DEFAULT 0, saldo_final DECIMAL(12,2) DEFAULT 0,
            status VARCHAR(20) DEFAULT 'aberto', data_abertura TIMESTAMP DEFAULT NOW(),
            data_fechamento TIMESTAMP, observacoes TEXT
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_vendas (
            id SERIAL PRIMARY KEY, caixa_id INT REFERENCES pdv_caixas(id),
            numero VARCHAR(30), cliente VARCHAR(100), total DECIMAL(12,2) DEFAULT 0,
            desconto DECIMAL(12,2) DEFAULT 0, status VARCHAR(20) DEFAULT 'finalizada',
            tipo VARCHAR(20) DEFAULT 'venda', data TIMESTAMP DEFAULT NOW(),
            operador VARCHAR(100), observacoes TEXT
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_itens (
            id SERIAL PRIMARY KEY, venda_id INT REFERENCES pdv_vendas(id),
            produto_codigo VARCHAR(50), descricao VARCHAR(200),
            quantidade DECIMAL(12,3) DEFAULT 1, unidade VARCHAR(10) DEFAULT 'UN',
            valor_unitario DECIMAL(12,2) DEFAULT 0, valor_total DECIMAL(12,2) DEFAULT 0
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_pagamentos (
            id SERIAL PRIMARY KEY, venda_id INT REFERENCES pdv_vendas(id),
            forma VARCHAR(30) NOT NULL, valor DECIMAL(12,2) DEFAULT 0,
            bandeira VARCHAR(30), parcelas INT DEFAULT 1,
            autorizacao VARCHAR(50), data TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_sangrias (
            id SERIAL PRIMARY KEY, caixa_id INT REFERENCES pdv_caixas(id),
            valor DECIMAL(12,2) DEFAULT 0, motivo TEXT, operador VARCHAR(100),
            data TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_suprimentos (
            id SERIAL PRIMARY KEY, caixa_id INT REFERENCES pdv_caixas(id),
            valor DECIMAL(12,2) DEFAULT 0, motivo TEXT, operador VARCHAR(100),
            data TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_nfce (
            id SERIAL PRIMARY KEY, venda_id INT REFERENCES pdv_vendas(id),
            numero VARCHAR(20), chave_acesso VARCHAR(50), serie VARCHAR(10),
            status VARCHAR(30) DEFAULT 'emitida', xml_url VARCHAR(500),
            data_emissao TIMESTAMP DEFAULT NOW()
        )""")
    try: run_async(_go())
    except Exception as e: log(AGENT, f"Erro tabelas PDV: {e}")

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
    keys = list(d.keys()); vals = list(d.values())
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
    vals = list(d.values()) + [id]
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

TABLES = ["caixas","vendas","itens","pagamentos","sangrias","suprimentos","nfce"]
def list(t: str): return _list(f"pdv_{t}")
def get(t: str, i: int): return _get(f"pdv_{t}", i)
def create(t: str, d: dict): return _create(f"pdv_{t}", d)
def update(t: str, i: int, d: dict): return _update(f"pdv_{t}", i, d)
def delete(t: str, i: int): return _delete(f"pdv_{t}", i)

# ── Operacoes ──

def abrir_caixa(operador: str, saldo_inicial: float = 0) -> dict:
    return create("caixas", {"operador": operador, "saldo_inicial": saldo_inicial, "status": "aberto", "data_abertura": hoje()})

def fechar_caixa(caixa_id: int, saldo_final: float) -> dict:
    async def _go():
        db = await get_db()
        total_vendas = await db.fetchval("SELECT COALESCE(SUM(total),0) FROM pdv_vendas WHERE caixa_id = $1 AND status = 'finalizada'", caixa_id)
        sangrias = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM pdv_sangrias WHERE caixa_id = $1", caixa_id)
        suprimentos = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM pdv_suprimentos WHERE caixa_id = $1", caixa_id)
        row = await db.fetchrow("""UPDATE pdv_caixas SET status='fechado', saldo_final=$1, data_fechamento=NOW()
            WHERE id=$2 RETURNING *""", saldo_final, caixa_id)
        return {
            "caixa": dict(row) if row else {},
            "total_vendas": float(total_vendas or 0),
            "sangrias": float(sangrias or 0),
            "suprimentos": float(suprimentos or 0),
            "saldo_esperado": float(saldo_final),
            "diferenca": float(saldo_final) - float((row["saldo_inicial"] if row else 0) + (total_vendas or 0) - (sangrias or 0) + (suprimentos or 0)),
        }
    try:
        result = run_async(_go())
        try:
            from core.entidades import ao_fechar_caixa_pdv
            ao_fechar_caixa_pdv(caixa_id)
        except: pass
        return result
    except Exception as e: return {"error": str(e)}

def sangria(caixa_id: int, valor: float, motivo: str, operador: str) -> dict:
    return create("sangrias", {"caixa_id": caixa_id, "valor": valor, "motivo": motivo, "operador": operador})

def suprimento(caixa_id: int, valor: float, motivo: str, operador: str) -> dict:
    return create("suprimentos", {"caixa_id": caixa_id, "valor": valor, "motivo": motivo, "operador": operador})

def realizar_venda(caixa_id: int, itens: list, pagamentos: list, cliente="", operador="", desconto=0.0) -> dict:
    total_itens = sum((i.get("quantidade",1) or 1) * (i.get("valor_unitario",0) or 0) for i in itens)
    total = round(total_itens - desconto, 2)
    venda = create("vendas", {"caixa_id": caixa_id, "cliente": cliente, "total": total,
        "desconto": desconto, "operador": operador, "data": hoje()})
    if venda.get("error"): return venda
    vid = venda["id"]
    for item in itens:
        create("itens", {"venda_id": vid, "produto_codigo": item.get("codigo",""),
            "descricao": item.get("descricao",""), "quantidade": item.get("quantidade",1),
            "valor_unitario": item.get("valor_unitario",0),
            "valor_total": (item.get("quantidade",1) or 1) * (item.get("valor_unitario",0) or 0)})
    for pg in pagamentos:
        create("pagamentos", {"venda_id": vid, "forma": pg.get("forma","dinheiro"),
            "valor": pg.get("valor",total), "parcelas": pg.get("parcelas",1)})
    return {"venda": venda, "total": total}

def dashboard() -> dict:
    async def _go():
        db = await get_db()
        caixa_aberto = await db.fetchrow("SELECT * FROM pdv_caixas WHERE status='aberto' ORDER BY id DESC LIMIT 1")
        hoje_vendas = await db.fetchval("SELECT COALESCE(SUM(total),0) FROM pdv_vendas WHERE DATE(data) = CURRENT_DATE")
        hoje_qtd = await db.fetchval("SELECT COUNT(*) FROM pdv_vendas WHERE DATE(data) = CURRENT_DATE")
        return {
            "caixa_aberto": dict(caixa_aberto) if caixa_aberto else None,
            "vendas_hoje": float(hoje_vendas or 0),
            "qtd_hoje": hoje_qtd or 0,
        }
    try: return run_async(_go())
    except: return {"caixa_aberto": None, "vendas_hoje": 0, "qtd_hoje": 0}
