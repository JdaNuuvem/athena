"""PDV Core — Vendas, Caixa, Pagamentos, Sangria, Suprimento, Fechamento, NFCe"""
from core import get_db, run_async, log, hoje
import hashlib, hmac, os as _os

AGENT = "PDV Core"

# ── Senha / Auth ──
# ponytail: hash usa scrypt (KDF lento, resistente a forca bruta) em vez de sha256 puro.
# Hashes legados (sha256:salt, gravados antes desta correcao) ainda sao aceitos na
# verificacao e migrados para scrypt automaticamente no proximo login bem-sucedido.

_SCRYPT_PARAMS = dict(n=2**14, r=8, p=1, dklen=32)

def _hash_senha(senha: str, salt: str = None) -> tuple:
    """Retorna (salt, hash) usando scrypt."""
    if salt is None:
        salt = _os.urandom(16).hex()
    pw_hash = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(salt), **_SCRYPT_PARAMS).hex()
    return salt, pw_hash

def _verificar_senha(senha: str, salt: str, hash_armazenado: str) -> tuple:
    """Verifica senha contra o hash armazenado. Retorna (valido, precisa_migrar_hash)."""
    salt_bytes = bytes.fromhex(salt)
    candidato = hashlib.scrypt(senha.encode(), salt=salt_bytes, **_SCRYPT_PARAMS).hex()
    if hmac.compare_digest(candidato, hash_armazenado):
        return True, False
    legado = hashlib.sha256(f"{senha}:{salt}".encode()).hexdigest()
    if hmac.compare_digest(legado, hash_armazenado):
        return True, True
    return False, False

def login_operador(nome: str, senha: str) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM pdv_operadores WHERE nome = $1 AND ativo = TRUE", nome)
        if not row:
            return {"error": "Operador nao encontrado ou inativo"}
        stored = row["senha"] or ""
        if not stored:
            return {"error": "Operador sem senha cadastrada — defina uma senha antes de logar"}
        if not senha:
            return {"error": "Senha obrigatoria"}
        parts = stored.split(":", 1)
        if len(parts) != 2:
            return {"error": "Senha invalida no cadastro"}
        salt, hash_stored = parts
        valido, precisa_migrar = _verificar_senha(senha, salt, hash_stored)
        if not valido:
            return {"error": "Senha incorreta"}
        if precisa_migrar:
            novo_salt, novo_hash = _hash_senha(senha)
            await db.execute("UPDATE pdv_operadores SET senha = $1 WHERE id = $2", f"{novo_salt}:{novo_hash}", row["id"])
        return {"id": row["id"], "nome": row["nome"], "role": row["role"],
                "desconto_maximo_percent": float(row.get("desconto_maximo_percent") or 0), "autenticado": True}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def verificar_operador(operador_id: int, senha: str = "") -> dict:
    """Valida operador ativo + senha (sempre obrigatoria — nenhum operador pode operar
    sem senha cadastrada, e uma senha vazia enviada pelo chamador nunca pula a checagem)."""
    if not operador_id:
        return {"error": "operador_id obrigatorio"}
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM pdv_operadores WHERE id = $1 AND ativo = TRUE", operador_id)
        if not row:
            return {"error": "Operador nao encontrado ou inativo"}
        stored = row["senha"] or ""
        if not stored:
            return {"error": "Operador sem senha cadastrada — defina uma senha antes de autorizar operacoes"}
        if not senha:
            return {"error": "Senha obrigatoria"}
        parts = stored.split(":", 1)
        if len(parts) != 2:
            return {"error": "Hash de senha invalido"}
        salt, hs = parts
        valido, precisa_migrar = _verificar_senha(senha, salt, hs)
        if not valido:
            return {"error": "Senha incorreta"}
        if precisa_migrar:
            novo_salt, novo_hash = _hash_senha(senha)
            await db.execute("UPDATE pdv_operadores SET senha = $1 WHERE id = $2", f"{novo_salt}:{novo_hash}", row["id"])
        return {"ok": True, "id": row["id"], "nome": row["nome"], "role": row["role"]}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

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
        
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_operadores (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL, senha VARCHAR(200),
            role VARCHAR(50) DEFAULT 'operador', ativo BOOLEAN DEFAULT TRUE,
            desconto_maximo_percent DECIMAL(5,2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        try: await db.execute("ALTER TABLE pdv_operadores ADD COLUMN IF NOT EXISTS desconto_maximo_percent DECIMAL(5,2) DEFAULT 0")
        except: pass
        try: await db.execute("ALTER TABLE pdv_operadores ALTER COLUMN senha TYPE VARCHAR(200)")
        except: pass
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_turnos (
            id SERIAL PRIMARY KEY, caixa_id INT REFERENCES pdv_caixas(id),
            operador_id INT REFERENCES pdv_operadores(id),
            aberto_em TIMESTAMP DEFAULT NOW(), fechado_em TIMESTAMP,
            saldo_abertura DECIMAL(12,2) DEFAULT 0, saldo_fechamento DECIMAL(12,2) DEFAULT 0,
            status VARCHAR(20) DEFAULT 'aberto', observacoes TEXT
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_devolucoes (
            id SERIAL PRIMARY KEY, venda_id INT REFERENCES pdv_vendas(id),
            motivo TEXT, valor DECIMAL(12,2) DEFAULT 0,
            operador VARCHAR(100), data TIMESTAMP DEFAULT NOW()
        )""")
        # Seed operador padrao SEM senha — nao ha default (fraco ou gerado) para logar
        # ou vazar. Como login_operador()/verificar_operador() exigem senha cadastrada,
        # este operador fica inerte ate alguem com sessao autenticada definir uma senha
        # via Cadastros > Operadores (PUT /api/pdv/operadores/<id>).
        op_count = await db.fetchval("SELECT COUNT(*) FROM pdv_operadores")
        if op_count == 0:
            await db.execute("INSERT INTO pdv_operadores (nome, senha, role, desconto_maximo_percent) VALUES ($1,$2,$3,$4)",
                "Admin", None, "admin", 100)
            log(AGENT, "Operador PDV padrao 'Admin' criado sem senha — defina uma senha em Cadastros > Operadores antes de usar o PDV")

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
        result = []
        for r in rows:
            d = dict(r)
            if d.get('preco'): d['preco'] = float(d['preco'])
            if d.get('estoque_atual'): d['estoque_atual'] = int(d['estoque_atual'])
            result.append(d)
        return result
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

TABLES = ["caixas","vendas","itens","pagamentos","sangrias","suprimentos","nfce","operadores","turnos","devolucoes"]
def list(t: str):
    extra = {"operadores":"pdv_operadores","turnos":"pdv_turnos","devolucoes":"pdv_devolucoes"}
    tbl = extra.get(t, f"pdv_{t}")
    return _list(tbl)
def get(t: str, i: int):
    extra = {"operadores":"pdv_operadores","turnos":"pdv_turnos","devolucoes":"pdv_devolucoes"}
    return _get(extra.get(t, f"pdv_{t}"), i)
def create(t: str, d: dict):
    extra = {"operadores":"pdv_operadores","turnos":"pdv_turnos","devolucoes":"pdv_devolucoes"}
    return _create(extra.get(t, f"pdv_{t}"), d)
def update(t: str, i: int, d: dict):
    extra = {"operadores":"pdv_operadores","turnos":"pdv_turnos","devolucoes":"pdv_devolucoes"}
    return _update(extra.get(t, f"pdv_{t}"), i, d)
def delete(t: str, i: int):
    extra = {"operadores":"pdv_operadores","turnos":"pdv_turnos","devolucoes":"pdv_devolucoes"}
    return _delete(extra.get(t, f"pdv_{t}"), i)

# ── Operacoes ──

_ROLES_GERENCIAIS = {"admin", "gerente"}

def _exigir_operador(operador_id, senha: str = "", roles_permitidas: set = None):
    """Exige identificacao de operador valida (operador_id sempre obrigatorio — nao pode
    ser omitido para pular a verificacao). Se roles_permitidas for informado, tambem exige
    que o operador tenha uma dessas roles. Retorna dict de erro, ou None se autorizado."""
    if not operador_id:
        return {"error": "operador_id obrigatorio"}
    v = verificar_operador(operador_id, senha)
    if v.get("error"):
        return v
    if roles_permitidas and v.get("role") not in roles_permitidas:
        return {"error": f"Operacao restrita a: {', '.join(sorted(roles_permitidas))}"}
    return None

def abrir_caixa(operador: str, saldo_inicial: float = 0, operador_id: int = None, senha: str = "") -> dict:
    erro = _exigir_operador(operador_id, senha)
    if erro: return erro
    return create("caixas", {"operador": operador, "saldo_inicial": saldo_inicial, "status": "aberto", "data_abertura": hoje()})

def fechar_caixa(caixa_id: int, saldo_final: float, operador_id: int = None, senha: str = "") -> dict:
    erro = _exigir_operador(operador_id, senha, _ROLES_GERENCIAIS)
    if erro: return erro
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



def abrir_turno(caixa_id: int, operador_id: int = None, operador_nome: str = "", saldo_abertura: float = 0) -> dict:
    return create("turnos", {"caixa_id": caixa_id, "operador_id": operador_id, "operador": operador_nome,
        "saldo_abertura": saldo_abertura, "status": "aberto", "aberto_em": hoje()})

def fechar_turno(turno_id: int, saldo_fechamento: float, observacoes: str = "") -> dict:
    return update("turnos", turno_id, {"status": "fechado", "saldo_fechamento": saldo_fechamento,
        "fechado_em": hoje(), "observacoes": observacoes})

def buscar_produtos(q: str, limit: int = 15) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT c.id, c.sku AS codigo, c.descricao AS nome,
                   COALESCE(
                       (SELECT a.preco FROM anuncios a WHERE a.sku = c.sku AND a.marketplace = 'bling' LIMIT 1),
                       (SELECT a.preco FROM anuncios a WHERE a.sku = c.sku ORDER BY a.preco ASC LIMIT 1),
                       0
                   ) AS preco,
                   COALESCE((SELECT SUM(e.quantidade) FROM estoque_lojas e WHERE e.sku = c.sku), 0) AS estoque_atual,
                   'A' AS situacao
            FROM catalogo_produtos c
            WHERE c.situacao = 'A' AND (
                c.sku ILIKE $1 OR c.descricao ILIKE $1 OR CAST(c.id AS TEXT) = $2 OR c.codigo_barras = $3
            )
            ORDER BY c.id DESC LIMIT $4
        """, f"%{q}%", q, q, limit)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except: return []

def cancelar_venda(venda_id: int, motivo: str = "", operador: str = "", operador_id: int = None, senha: str = "") -> dict:
    erro = _exigir_operador(operador_id, senha)
    if erro: return erro
    async def _go():
        db = await get_db()
        venda = await db.fetchrow("SELECT * FROM pdv_vendas WHERE id = $1", venda_id)
        if not venda: return {"error": "Venda nao encontrada"}
        if venda["status"] == "cancelada": return {"error": "Venda ja cancelada"}
        await db.execute("UPDATE pdv_vendas SET status = 'cancelada', observacoes = $2 WHERE id = $1", venda_id, f"Cancelada: {motivo}" if motivo else "Cancelada")
        # Registrar devolucao
        await db.execute("INSERT INTO pdv_devolucoes (venda_id, motivo, valor, operador) VALUES ($1,$2,$3,$4)",
            venda_id, motivo, float(venda["total"] or 0), operador)
        return {"success": True, "venda_id": venda_id}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def historico_vendas(caixa_id: int = None, data_inicio: str = None, data_fim: str = None, limit: int = 50) -> list:
    async def _go():
        db = await get_db()
        where = []; params = []; p = 0
        if caixa_id:
            p += 1; where.append(f"caixa_id = ${p}"); params.append(caixa_id)
        if data_inicio:
            p += 1; where.append(f"data::date >= ${p}::date"); params.append(data_inicio)
        if data_fim:
            p += 1; where.append(f"data::date <= ${p}::date"); params.append(data_fim)
        clause = " AND ".join(where) if where else "1=1"
        p += 1
        rows = await db.fetch(f"SELECT * FROM pdv_vendas WHERE {clause} ORDER BY data DESC LIMIT ${p}", *params, limit)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except: return []

def sangria(caixa_id: int, valor: float, motivo: str, operador: str, operador_id: int = None, senha: str = "") -> dict:
    erro = _exigir_operador(operador_id, senha, _ROLES_GERENCIAIS)
    if erro: return erro
    return create("sangrias", {"caixa_id": caixa_id, "valor": valor, "motivo": motivo, "operador": operador})

def suprimento(caixa_id: int, valor: float, motivo: str, operador: str, operador_id: int = None, senha: str = "") -> dict:
    erro = _exigir_operador(operador_id, senha, _ROLES_GERENCIAIS)
    if erro: return erro
    return create("suprimentos", {"caixa_id": caixa_id, "valor": valor, "motivo": motivo, "operador": operador})

def realizar_venda(caixa_id: int, itens: list, pagamentos: list, cliente="", operador="", operador_id=None, desconto=0.0) -> dict:
    total_itens = sum((i.get("quantidade",1) or 1) * (i.get("valor_unitario",0) or 0) for i in itens)
    total = round(total_itens - desconto, 2)

    # validar desconto maximo do operador
    if operador_id and desconto > 0 and total_itens > 0:
        op = _get("pdv_operadores", operador_id)
        if op and not op.get("error"):
            max_pct = float(op.get("desconto_maximo_percent") or 0)
            if max_pct > 0:
                pct_desconto = (desconto / total_itens) * 100
                if pct_desconto > max_pct:
                    return {"error": f"Desconto maximo permitido: {max_pct:.1f}% (tentativa: {pct_desconto:.1f}%)"}

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
