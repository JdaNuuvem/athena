"""PDV Core — Vendas, Caixa, Pagamentos, Sangria, Suprimento, Fechamento"""
from datetime import datetime
from core import get_db, run_async, log
from core.estoque import saida_async, entrada_async
from core.estoque_saldos import SaldoError, _ensure_async as _ensure_saldos_async
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


def definir_senha(operador_id: int, senha: str) -> dict:
    """Define/atualiza a senha de login de um operador. So' pode ser chamada
    por quem ja' tem sessao autenticada no sistema principal (rota gated por
    configuracoes.editar) — e' o unico jeito de destravar um operador recem
    criado ou recem-seedado, que nasce sem senha de proposito (ver comentario
    do seed do Admin em _ensure_tabelas)."""
    if not senha or len(senha) < 6:
        return {"error": "Senha deve ter no minimo 6 caracteres"}
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT id FROM pdv_operadores WHERE id = $1 AND ativo = TRUE", operador_id)
        if not row:
            return {"error": "Operador nao encontrado ou inativo"}
        salt, senha_hash = _hash_senha(senha)
        await db.execute("UPDATE pdv_operadores SET senha = $1 WHERE id = $2", f"{salt}:{senha_hash}", operador_id)
        return {"ok": True}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def definir_pin(operador_id: int, pin: str) -> dict:
    """Define/atualiza o PIN numerico de um operador (tipicamente Gerente/Admin)."""
    if not pin or not pin.isdigit() or not (4 <= len(pin) <= 6):
        return {"error": "PIN deve ter de 4 a 6 digitos numericos"}
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT id FROM pdv_operadores WHERE id = $1 AND ativo = TRUE", operador_id)
        if not row:
            return {"error": "Operador nao encontrado ou inativo"}
        salt, pin_hash = _hash_senha(pin)
        await db.execute("UPDATE pdv_operadores SET pin_hash = $1 WHERE id = $2", f"{salt}:{pin_hash}", operador_id)
        return {"ok": True}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def verificar_pin_gerencial(gerente_id: int, pin: str, roles_permitidas: set = None) -> dict:
    """Valida que gerente_id e' um operador ativo, com role permitida, e que o
    PIN informado bate com o PIN cadastrado — usado quando um operador comum
    esta operando o PDV e chama um gerente para autorizar uma acao sensivel
    sem precisar fazer logout/login completo."""
    if not gerente_id:
        return {"error": "gerente_id obrigatorio"}
    if not pin:
        return {"error": "PIN obrigatorio"}
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM pdv_operadores WHERE id = $1 AND ativo = TRUE", gerente_id)
        if not row:
            return {"error": "Operador nao encontrado ou inativo"}
        if roles_permitidas and row["role"] not in roles_permitidas:
            return {"error": f"PIN de autorizacao restrito a: {', '.join(sorted(roles_permitidas))}"}
        stored = row.get("pin_hash") or ""
        if not stored:
            return {"error": "Operador sem PIN cadastrado — defina um PIN em Cadastros > Operadores"}
        parts = stored.split(":", 1)
        if len(parts) != 2:
            return {"error": "Hash de PIN invalido"}
        salt, hs = parts
        valido, _ = _verificar_senha(pin, salt, hs)
        if not valido:
            return {"error": "PIN incorreto"}
        return {"ok": True, "id": row["id"], "nome": row["nome"], "role": row["role"]}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def gerar_codigo_barras(operador_id: int) -> dict:
    """Gera um codigo unico para cracha/etiqueta fisica — funciona como um
    'PIN fisico': bipar esse codigo de barras autoriza igual ao PIN digitado,
    mas identificando o gerente automaticamente (sem selecionar da lista).
    So' o hash e' salvo — o codigo em texto e' devolvido UMA VEZ nesta
    chamada, mesmo padrao de senha (se perder o cracha, gera um novo)."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT id FROM pdv_operadores WHERE id = $1 AND ativo = TRUE", operador_id)
        if not row:
            return {"error": "Operador nao encontrado ou inativo"}
        codigo = _os.urandom(8).hex().upper()
        salt, codigo_hash = _hash_senha(codigo)
        await db.execute("UPDATE pdv_operadores SET codigo_barras_hash = $1 WHERE id = $2", f"{salt}:{codigo_hash}", operador_id)
        return {"ok": True, "codigo_barras": codigo}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}


def verificar_codigo_barras_gerencial(codigo: str, roles_permitidas: set = None) -> dict:
    """Busca entre os operadores ativos (com role permitida, se informado)
    qual tem esse codigo de barras cadastrado — ao contrario do PIN, nao
    exige saber de antemao qual gerente esta autorizando."""
    if not codigo:
        return {"error": "codigo de barras obrigatorio"}
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM pdv_operadores WHERE ativo = TRUE AND codigo_barras_hash IS NOT NULL")
        return [dict(r) for r in rows]
    try:
        candidatos = run_async(_go())
    except Exception as e:
        return {"error": str(e)}
    for row in candidatos:
        if roles_permitidas and row["role"] not in roles_permitidas:
            continue
        stored = row.get("codigo_barras_hash") or ""
        parts = stored.split(":", 1)
        if len(parts) != 2:
            continue
        salt, hs = parts
        valido, _ = _verificar_senha(codigo, salt, hs)
        if valido:
            return {"ok": True, "id": row["id"], "nome": row["nome"], "role": row["role"]}
    return {"error": "Codigo de barras nao reconhecido"}


def _autorizar_gerencial(operador_id: int = None, senha: str = "", gerente_pin_id: int = None,
                          pin: str = "", codigo_barras: str = "", roles_permitidas: set = None) -> dict:
    """Autoriza uma acao sensivel de tres formas: (1) o proprio operador logado
    ja tem a role exigida e informa sua senha normal, (2) um operador comum
    esta operando e um gerente autoriza via PIN numerico curto (gerente_pin_id
    + pin), ou (3) o gerente bipa o codigo de barras do seu cracha (identifica
    automaticamente quem e', sem precisar selecionar da lista) — nenhuma das
    duas ultimas exige logout/login. Retorna dict de erro, ou o dict do
    autorizador (id/nome/role) se autorizado."""
    if codigo_barras:
        return verificar_codigo_barras_gerencial(codigo_barras, roles_permitidas)
    if gerente_pin_id and pin:
        return verificar_pin_gerencial(gerente_pin_id, pin, roles_permitidas)
    v = verificar_operador(operador_id, senha)
    if v.get("error"): return v
    if roles_permitidas and v.get("role") not in roles_permitidas:
        return {"error": f"Operacao restrita a: {', '.join(sorted(roles_permitidas))}"}
    return v


def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_caixas (
            id SERIAL PRIMARY KEY, numero VARCHAR(20), operador VARCHAR(100),
            saldo_inicial DECIMAL(12,2) DEFAULT 0, saldo_final DECIMAL(12,2) DEFAULT 0,
            status VARCHAR(20) DEFAULT 'aberto', data_abertura TIMESTAMP DEFAULT NOW(),
            data_fechamento TIMESTAMP, observacoes TEXT
        )""")
        # Diferenca (quebra de caixa) — antes so' era calculada e devolvida na
        # resposta HTTP do fechamento, nunca persistida; sem isso nao ha
        # historico consultavel de quebras recorrentes por operador/loja.
        try: await db.execute("ALTER TABLE pdv_caixas ADD COLUMN IF NOT EXISTS diferenca DECIMAL(12,2)")
        except Exception as e: pass
        try: await db.execute("ALTER TABLE pdv_caixas ADD COLUMN IF NOT EXISTS operador_fechamento VARCHAR(100)")
        except Exception as e: pass
        # loja_id tambem e' adicionado por core.entidades (migracao incremental) —
        # IF NOT EXISTS torna essa duplicidade segura independente da ordem de import.
        try: await db.execute("ALTER TABLE pdv_caixas ADD COLUMN IF NOT EXISTS loja_id INT REFERENCES lojas(id)")
        except Exception as e: pass
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_vendas (
            id SERIAL PRIMARY KEY, caixa_id INT REFERENCES pdv_caixas(id),
            numero VARCHAR(30), cliente VARCHAR(100), cliente_id INT,
            total DECIMAL(12,2) DEFAULT 0,
            desconto DECIMAL(12,2) DEFAULT 0, status VARCHAR(20) DEFAULT 'finalizada',
            tipo VARCHAR(20) DEFAULT 'venda', data TIMESTAMP DEFAULT NOW(),
            operador VARCHAR(100), observacoes TEXT
        )""")
        try: await db.execute("ALTER TABLE pdv_vendas ADD COLUMN IF NOT EXISTS cliente_id INT")
        except Exception as e: pass
        # Marca se a baixa de estoque real foi de fato executada na venda (loja_id
        # resolvido no momento da venda) -- sem isso, vendas antigas (anteriores a
        # esta feature, que nunca decrementaram estoque) ficariam elegiveis para
        # restauracao assim que loja_id passasse a ser preenchido em caixas novos,
        # inflando estoque no cancelamento/devolucao de vendas pre-existentes.
        try: await db.execute("ALTER TABLE pdv_vendas ADD COLUMN IF NOT EXISTS estoque_baixado BOOLEAN DEFAULT FALSE")
        except Exception as e: pass
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_itens (
            id SERIAL PRIMARY KEY, venda_id INT REFERENCES pdv_vendas(id),
            produto_codigo VARCHAR(50), descricao VARCHAR(200),
            quantidade DECIMAL(12,3) DEFAULT 1, unidade VARCHAR(10) DEFAULT 'UN',
            valor_unitario DECIMAL(12,2) DEFAULT 0, desconto DECIMAL(12,2) DEFAULT 0,
            valor_total DECIMAL(12,2) DEFAULT 0
        )""")
        try: await db.execute("ALTER TABLE pdv_itens ADD COLUMN IF NOT EXISTS desconto DECIMAL(12,2) DEFAULT 0")
        except Exception as e: pass
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_pagamentos (
            id SERIAL PRIMARY KEY, venda_id INT REFERENCES pdv_vendas(id),
            forma VARCHAR(30) NOT NULL, valor DECIMAL(12,2) DEFAULT 0,
            bandeira VARCHAR(30), parcelas INT DEFAULT 1,
            autorizacao VARCHAR(50), data TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("ALTER TABLE pdv_pagamentos ADD COLUMN IF NOT EXISTS maquineta VARCHAR(50)")
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
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_caixa_contagem (
            id SERIAL PRIMARY KEY,
            caixa_id INT NOT NULL REFERENCES pdv_caixas(id),
            denominacao VARCHAR(10) NOT NULL,
            quantidade INT NOT NULL DEFAULT 0,
            subtotal DECIMAL(10,2) GENERATED ALWAYS AS (quantidade * denominacao::numeric) STORED,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_caixa_conferencia (
            id SERIAL PRIMARY KEY,
            caixa_id INT NOT NULL REFERENCES pdv_caixas(id),
            maquineta VARCHAR(50) NOT NULL,
            forma_pagamento VARCHAR(30) NOT NULL,
            valor_sistema DECIMAL(12,2) NOT NULL DEFAULT 0,
            valor_conferido DECIMAL(12,2),
            diferenca DECIMAL(12,2) GENERATED ALWAYS AS (COALESCE(valor_conferido,0) - valor_sistema) STORED,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        
        await db.execute("""CREATE TABLE IF NOT EXISTS pdv_operadores (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL, senha VARCHAR(200),
            role VARCHAR(50) DEFAULT 'operador', ativo BOOLEAN DEFAULT TRUE,
            desconto_maximo_percent DECIMAL(5,2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        try: await db.execute("ALTER TABLE pdv_operadores ADD COLUMN IF NOT EXISTS desconto_maximo_percent DECIMAL(5,2) DEFAULT 0")
        except Exception as e: pass
        try: await db.execute("ALTER TABLE pdv_operadores ALTER COLUMN senha TYPE VARCHAR(200)")
        except Exception as e: pass
        # PIN numerico curto (4-6 digitos), separado da senha de login — usado
        # para um operador comum "chamar o gerente" e autorizar uma acao
        # sensivel (cancelamento, devolucao, sangria, desconto acima do limite)
        # sem precisar fazer logout/login completo no meio do atendimento.
        try: await db.execute("ALTER TABLE pdv_operadores ADD COLUMN IF NOT EXISTS pin_hash VARCHAR(200)")
        except Exception as e: pass
        # Codigo de barras (cracha fisico) — mesmo papel do PIN, mas lido por
        # um leitor USB/Bluetooth em vez de digitado: bipar ja identifica o
        # gerente automaticamente (nao precisa selecionar da lista antes).
        try: await db.execute("ALTER TABLE pdv_operadores ADD COLUMN IF NOT EXISTS codigo_barras_hash VARCHAR(200)")
        except Exception as e: pass
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

    try: run_async(_go())
    except Exception as e: log(AGENT, f"Erro tabelas PDV: {e}")

_ensure_tables()

# ── CRUD ──

def _list(t: str, where: str = "", params: list = None, cols="*", order="id DESC", limit=500) -> list:
    async def _go():
        db = await get_db()
        clause = f"WHERE {where}" if where else ""
        q = f"SELECT {cols} FROM {t} {clause} ORDER BY {order} LIMIT {limit}"
        rows = await db.fetch(q, *(params or []))
        result = []
        for r in rows:
            d = dict(r)
            if d.get('preco'): d['preco'] = float(d['preco'])
            if d.get('estoque_atual'): d['estoque_atual'] = int(d['estoque_atual'])
            result.append(d)
        return result
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"list {t}: {e}"); return []

def _list_filtro(t: str, where: str = "", params: list = None) -> list:
    extra = {"operadores":"pdv_operadores","turnos":"pdv_turnos","devolucoes":"pdv_devolucoes"}
    return _list(extra.get(t, f"pdv_{t}"), where=where, params=params)

def _get(t: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"SELECT * FROM {t} WHERE id = $1", id)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def _create(t: str, d: dict) -> dict:
    # ponytail: NAO usar list(...) aqui — este modulo define uma funcao
    # `list(t)` no nivel de modulo (linha ~246) que sombreia o builtin para
    # QUALQUER funcao neste arquivo (resolucao de nomes e' por escopo do
    # modulo, nao por ordem de definicao). list(d.keys()) chamaria
    # list(t: str) com um dict_keys, quebrando com TypeError.
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
    vals = [*d.values(), id]  # ver nota em _create sobre o shadowing de list()
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

TABLES = ["caixas","vendas","itens","pagamentos","sangrias","suprimentos","operadores","turnos","devolucoes"]

# operadores guarda hash de senha/PIN/codigo de barras — o CRUD generico nunca
# pode ler nem escrever esses campos direto (leitura vazaria hash pro cliente;
# escrita gravaria senha em texto puro, sem hash, corrompendo o login). Senha/
# PIN/codigo tem rotas dedicadas (definir_senha, definir_pin, gerar_codigo_barras)
# que fazem o hash corretamente.
_OPERADOR_CAMPOS_SENSIVEIS = {"senha", "pin_hash", "codigo_barras_hash"}
_OPERADOR_CAMPOS_EDITAVEIS = {"nome", "role", "desconto_maximo_percent", "ativo"}

def _operador_sem_sensiveis(d: dict) -> dict:
    if not isinstance(d, dict):
        return d
    return {k: v for k, v in d.items() if k not in _OPERADOR_CAMPOS_SENSIVEIS}

def list(t: str):
    extra = {"operadores":"pdv_operadores","turnos":"pdv_turnos","devolucoes":"pdv_devolucoes"}
    tbl = extra.get(t, f"pdv_{t}")
    if t == "operadores":
        return _list(tbl, cols="id, nome, role, ativo, desconto_maximo_percent, created_at, "
                               "(senha IS NOT NULL) AS tem_senha, (pin_hash IS NOT NULL) AS tem_pin, "
                               "(codigo_barras_hash IS NOT NULL) AS tem_codigo_barras")
    return _list(tbl)
def get(t: str, i: int):
    extra = {"operadores":"pdv_operadores","turnos":"pdv_turnos","devolucoes":"pdv_devolucoes"}
    r = _get(extra.get(t, f"pdv_{t}"), i)
    return _operador_sem_sensiveis(r) if t == "operadores" else r
def create(t: str, d: dict):
    extra = {"operadores":"pdv_operadores","turnos":"pdv_turnos","devolucoes":"pdv_devolucoes"}
    if t == "operadores":
        d = {k: v for k, v in d.items() if k in _OPERADOR_CAMPOS_EDITAVEIS}
    r = _create(extra.get(t, f"pdv_{t}"), d)
    return _operador_sem_sensiveis(r) if t == "operadores" else r
def update(t: str, i: int, d: dict):
    extra = {"operadores":"pdv_operadores","turnos":"pdv_turnos","devolucoes":"pdv_devolucoes"}
    if t == "operadores":
        d = {k: v for k, v in d.items() if k in _OPERADOR_CAMPOS_EDITAVEIS}
    r = _update(extra.get(t, f"pdv_{t}"), i, d)
    return _operador_sem_sensiveis(r) if t == "operadores" else r
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

async def _resolver_loja_da_venda(conn, caixa_id):
    """Resolve o nome da loja fisica de uma venda a partir do caixa_id
    (pdv_caixas.loja_id -> lojas.nome). Retorna None se o caixa nao tiver
    loja_id definido ou a loja nao existir -- fail-open: quem chama decide
    pular a baixa/restauracao de estoque nesse caso, sem bloquear a operacao
    de PDV por falta de configuracao de loja no caixa (caixas antigos podem
    nao ter loja_id setado)."""
    if not caixa_id:
        return None
    caixa = await conn.fetchrow("SELECT loja_id FROM pdv_caixas WHERE id = $1", caixa_id)
    if not caixa or not caixa["loja_id"]:
        return None
    loja_row = await conn.fetchrow("SELECT nome FROM lojas WHERE id = $1", caixa["loja_id"])
    return loja_row["nome"] if loja_row else None

def abrir_caixa(operador: str, saldo_inicial: float = 0, operador_id: int = None, senha: str = "", loja_id: int = None) -> dict:
    erro = _exigir_operador(operador_id, senha)
    if erro: return erro
    campos = {"operador": operador, "saldo_inicial": saldo_inicial, "status": "aberto", "data_abertura": datetime.now()}
    if loja_id:
        campos["loja_id"] = loja_id
    return create("caixas", campos)

def fechar_caixa(caixa_id: int, saldo_final: float, operador_id: int = None, senha: str = "",
                  gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    fechador = _autorizar_gerencial(operador_id, senha, gerente_pin_id, pin, codigo_barras, _ROLES_GERENCIAIS)
    if fechador.get("error"): return fechador
    nome_fechador = fechador.get("nome", "")
    async def _go():
        db = await get_db()
        total_vendas = await db.fetchval("SELECT COALESCE(SUM(total),0) FROM pdv_vendas WHERE caixa_id = $1 AND status = 'finalizada'", caixa_id)
        sangrias = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM pdv_sangrias WHERE caixa_id = $1", caixa_id)
        suprimentos = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM pdv_suprimentos WHERE caixa_id = $1", caixa_id)
        # vendas em dinheiro (unica forma com troco fisico)
        vendas_dinheiro = await db.fetchval("""
            SELECT COALESCE(SUM(p.valor),0) FROM pdv_pagamentos p
            JOIN pdv_vendas v ON v.id = p.venda_id
            WHERE v.caixa_id = $1 AND v.status = 'finalizada' AND p.forma = 'dinheiro'
        """, caixa_id)
        # Segregacao de funcao: quem fecha nao deveria ser o unico operador que
        # vendeu no turno — so' avisa (nao bloqueia, lojas pequenas podem ter
        # so' 1-2 pessoas por turno).
        operadores_venda = await db.fetch(
            "SELECT DISTINCT operador FROM pdv_vendas WHERE caixa_id = $1 AND status = 'finalizada'", caixa_id)
        nomes_vendedores = {r["operador"] for r in operadores_venda if r["operador"]}
        aviso_segregacao = bool(nome_fechador) and nomes_vendedores == {nome_fechador}

        saldo_inicial_row = await db.fetchval("SELECT saldo_inicial FROM pdv_caixas WHERE id = $1", caixa_id)
        saldo_inicial = float(saldo_inicial_row or 0)
        saldo_esperado_cash = saldo_inicial + float(vendas_dinheiro or 0) - float(sangrias or 0) + float(suprimentos or 0)
        diferenca = round(float(saldo_final) - saldo_esperado_cash, 2)
        row = await db.fetchrow("""UPDATE pdv_caixas SET status='fechado', saldo_final=$1, diferenca=$2,
            operador_fechamento=$3, data_fechamento=NOW() WHERE id=$4 RETURNING *""",
            saldo_final, diferenca, nome_fechador, caixa_id)
        return {
            "caixa": dict(row) if row else {},
            "total_vendas": float(total_vendas or 0),
            "vendas_dinheiro": float(vendas_dinheiro or 0),
            "sangrias": float(sangrias or 0),
            "suprimentos": float(suprimentos or 0),
            "saldo_esperado_cash": round(saldo_esperado_cash, 2),
            "diferenca": diferenca,
            "aviso_segregacao": aviso_segregacao,
        }
    try:
        result = run_async(_go())
        try:
            from core.entidades import ao_fechar_caixa_pdv
            ao_fechar_caixa_pdv(caixa_id)
        except Exception as e: pass
        return result
    except Exception as e: return {"error": str(e)}


def historico_quebras(loja_id: int = None, operador: str = "", dias: int = 90, loja_ids: list = None) -> list:
    """Historico de quebra de caixa (diferenca) por fechamento, agregavel no
    frontend por operador_fechamento/loja_id — sem isso, uma quebra pequena
    recorrente do mesmo operador passa despercebida (cada fechamento e' visto
    isoladamente). loja_ids (Fase 4, RBAC por loja): so' usado quando
    loja_id nao foi pedido explicitamente — modo suave, nunca bloqueia."""
    _ensure_tables()
    async def _go():
        db = await get_db()
        where = ["status = 'fechado'", f"data_fechamento >= NOW() - INTERVAL '{int(dias)} days'"]
        params = []
        if loja_id:
            where.append(f"loja_id = ${len(params) + 1}")
            params.append(loja_id)
        elif loja_ids is not None:
            params.append(loja_ids)
            where.append(f"loja_id = ANY(${len(params)})")
        if operador:
            where.append(f"operador_fechamento = ${len(params) + 1}")
            params.append(operador)
        sql_where = " AND ".join(where)
        rows = await db.fetch(f"""
            SELECT id, numero, operador_fechamento, loja_id, saldo_inicial, saldo_final,
                   diferenca, data_abertura, data_fechamento
            FROM pdv_caixas
            WHERE {sql_where}
            ORDER BY data_fechamento DESC LIMIT 200
        """, *params)
        return [dict(r, saldo_inicial=float(r["saldo_inicial"] or 0), saldo_final=float(r["saldo_final"] or 0),
                     diferenca=float(r["diferenca"]) if r["diferenca"] is not None else 0.0)
                for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def resumo_fechamento(caixa_id: int) -> dict:
    """Retorna quebra do caixa: saldo inicial, vendas por forma, sangrias, suprimentos, saldo esperado."""
    async def _go():
        db = await get_db()
        caixa = await db.fetchrow("SELECT * FROM pdv_caixas WHERE id = $1", caixa_id)
        if not caixa: return {"error": "Caixa nao encontrado"}
        inicial = float(caixa["saldo_inicial"] or 0)
        sangrias = float((await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM pdv_sangrias WHERE caixa_id = $1", caixa_id)) or 0)
        suprimentos = float((await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM pdv_suprimentos WHERE caixa_id = $1", caixa_id)) or 0)
        # Totais por forma de pagamento
        pgto_rows = await db.fetch("""
            SELECT p.forma, COALESCE(SUM(p.valor),0) AS total
            FROM pdv_pagamentos p
            JOIN pdv_vendas v ON v.id = p.venda_id
            WHERE v.caixa_id = $1 AND v.status = 'finalizada'
            GROUP BY p.forma ORDER BY total DESC
        """, caixa_id)
        vendas_por_forma = {r["forma"]: float(r["total"]) for r in pgto_rows}
        total_vendas = sum(vendas_por_forma.values())
        dinheiro_esperado = inicial + vendas_por_forma.get("dinheiro", 0) - sangrias + suprimentos
        return {
            "caixa_id": caixa_id,
            "saldo_inicial": inicial,
            "vendas_por_forma": vendas_por_forma,
            "total_vendas": total_vendas,
            "sangrias": sangrias,
            "suprimentos": suprimentos,
            "saldo_esperado_dinheiro": round(dinheiro_esperado, 2),
        }
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}



def abrir_turno(caixa_id: int, operador_id: int = None, operador_nome: str = "", saldo_abertura: float = 0) -> dict:
    return create("turnos", {"caixa_id": caixa_id, "operador_id": operador_id, "operador": operador_nome,
        "saldo_abertura": saldo_abertura, "status": "aberto", "aberto_em": datetime.now()})

def fechar_turno(turno_id: int, saldo_fechamento: float, observacoes: str = "") -> dict:
    return update("turnos", turno_id, {"status": "fechado", "saldo_fechamento": saldo_fechamento,
        "fechado_em": datetime.now(), "observacoes": observacoes})

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
    except Exception as e: return []

def buscar_clientes(q: str, limit: int = 10) -> list:
    """Autocomplete de clientes: busca por nome, documento, telefone"""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT id, nome, tipo, documento, telefone, email
            FROM cad_clientes
            WHERE status = 'ativo' AND (
                nome ILIKE $1 OR documento ILIKE $2 OR telefone ILIKE $2
            )
            ORDER BY nome LIMIT $3
        """, f"%{q}%", f"%{q.replace('.','').replace('-','').replace('/','')}%", limit)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def cancelar_venda(venda_id: int, motivo: str = "", operador: str = "", operador_id: int = None, senha: str = "",
                    gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    autorizador = _autorizar_gerencial(operador_id, senha, gerente_pin_id, pin, codigo_barras, _ROLES_GERENCIAIS)
    if autorizador.get("error"): return autorizador
    operador_registro = autorizador.get("nome") or operador
    async def _go():
        await _ensure_saldos_async()
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                venda = await conn.fetchrow("SELECT * FROM pdv_vendas WHERE id = $1 FOR UPDATE", venda_id)
                if not venda: return {"error": "Venda nao encontrada"}
                if venda["status"] == "cancelada": return {"error": "Venda ja cancelada"}
                itens = await conn.fetch("SELECT produto_codigo, quantidade FROM pdv_itens WHERE venda_id = $1", venda_id)
                loja = await _resolver_loja_da_venda(conn, venda["caixa_id"])
                if loja and venda.get("estoque_baixado"):
                    for item in itens:
                        r = await entrada_async(conn, item["produto_codigo"], loja, float(item["quantidade"]), "devolucao_cliente",
                                                usuario_id=autorizador.get("id"), usuario_nome=operador_registro)
                        if r.get("erro"):
                            raise SaldoError(f"Erro ao restaurar estoque de {item['produto_codigo']}: {r['erro']}")
                await conn.execute("UPDATE pdv_vendas SET status = 'cancelada', observacoes = $2 WHERE id = $1", venda_id, f"Cancelada: {motivo}" if motivo else "Cancelada")
                # Registrar devolucao
                await conn.execute("INSERT INTO pdv_devolucoes (venda_id, motivo, valor, operador) VALUES ($1,$2,$3,$4)",
                    venda_id, motivo, float(venda["total"] or 0), operador_registro)
                return {"success": True, "venda_id": venda_id}
    try: return run_async(_go())
    except SaldoError as e: return {"error": str(e)}
    except Exception as e: return {"error": str(e)}

def devolver_item_venda(item_id: int, quantidade: float, motivo: str = "", operador: str = "", operador_id: int = None, senha: str = "",
                         gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    """Devolucao parcial: remove qtd de um item da venda, ajusta total, registra devolucao,
    restaura a quantidade devolvida no estoque real da loja fisica.
    Exige autorizacao gerencial (senha do proprio gerente logado, PIN ou
    codigo de barras de um gerente chamado ao caixa) — cancelamento/devolucao
    e' forma comum de fraude ("desconta" a venda depois que o cliente ja
    pagou e saiu)."""
    autorizador = _autorizar_gerencial(operador_id, senha, gerente_pin_id, pin, codigo_barras, _ROLES_GERENCIAIS)
    if autorizador.get("error"): return autorizador
    operador_registro = autorizador.get("nome") or operador
    if quantidade is None or quantidade <= 0:
        return {"error": "Quantidade a devolver deve ser maior que zero"}
    async def _go():
        await _ensure_saldos_async()
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                item = await conn.fetchrow(
                    "SELECT i.*, v.status AS venda_status, v.caixa_id, v.estoque_baixado FROM pdv_itens i JOIN pdv_vendas v ON v.id = i.venda_id WHERE i.id = $1", item_id)
                if not item: return {"error": "Item nao encontrado"}
                if item["venda_status"] == "cancelada": return {"error": "Venda ja cancelada"}
                valor_unitario = float(item["valor_unitario"] or 0)
                valor_devolvido = round(quantidade * valor_unitario, 2)
                # UPDATE atomico: a condicao "quantidade >= $1" no WHERE garante que a checagem de
                # estoque disponivel e' feita no mesmo statement que o decremento, evitando que duas
                # devolucoes concorrentes do mesmo item leiam a mesma quantidade e se sobrescrevam.
                atualizado = await conn.fetchrow("""
                    UPDATE pdv_itens SET quantidade = quantidade - $1,
                        valor_total = ROUND((quantidade - $1) * valor_unitario, 2)
                    WHERE id = $2 AND quantidade >= $1
                    RETURNING quantidade
                """, quantidade, item_id)
                if not atualizado:
                    return {"error": f"Quantidade insuficiente (max: {item['quantidade']})"}
                if float(atualizado["quantidade"]) <= 0:
                    await conn.execute("DELETE FROM pdv_itens WHERE id = $1", item_id)
                await conn.execute("UPDATE pdv_vendas SET total = GREATEST(0, total - $1) WHERE id = $2", valor_devolvido, item["venda_id"])
                await conn.execute("INSERT INTO pdv_devolucoes (venda_id, motivo, valor, operador) VALUES ($1,$2,$3,$4)",
                    item["venda_id"], f"Item #{item_id}: {motivo}" if motivo else f"Devolucao parcial item #{item_id}",
                    valor_devolvido, operador_registro)
                loja = await _resolver_loja_da_venda(conn, item["caixa_id"])
                if loja and item.get("estoque_baixado"):
                    r = await entrada_async(conn, item["produto_codigo"], loja, quantidade, "devolucao_cliente",
                                            usuario_id=autorizador.get("id"), usuario_nome=operador_registro)
                    if r.get("erro"):
                        raise SaldoError(f"Erro ao restaurar estoque de {item['produto_codigo']}: {r['erro']}")
                return {"success": True, "item_id": item_id, "quantidade_devolvida": quantidade, "valor_devolvido": valor_devolvido}
    try: return run_async(_go())
    except SaldoError as e: return {"error": str(e)}
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
    except Exception as e: return []

def _aplicar_sangria(caixa_id: int, valor: float, motivo: str, operador: str) -> dict:
    """Aplica a sangria diretamente, sem checar alcada — usado pela sangria
    livre (abaixo do limite) e por core.pdv_aprovacoes.aprovar() apos
    aprovacao gerencial de uma sangria acima do limite."""
    return create("sangrias", {"caixa_id": caixa_id, "valor": valor, "motivo": motivo, "operador": operador})


def sangria(caixa_id: int, valor: float, motivo: str, operador: str, operador_id: int = None, senha: str = "",
            gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    v = _autorizar_gerencial(operador_id, senha, gerente_pin_id, pin, codigo_barras, _ROLES_GERENCIAIS)
    if v.get("error"): return v
    from core.pdv_aprovacoes import MOTIVOS_SANGRIA, precisa_aprovacao, solicitar as solicitar_aprovacao
    if motivo not in MOTIVOS_SANGRIA:
        return {"error": f"Motivo invalido. Use um de: {', '.join(MOTIVOS_SANGRIA)}"}
    nome_operador = v.get("nome") or operador
    if precisa_aprovacao(valor):
        return solicitar_aprovacao(caixa_id, valor, motivo, v.get("id"), nome_operador)
    return _aplicar_sangria(caixa_id, valor, motivo, nome_operador)

def suprimento(caixa_id: int, valor: float, motivo: str, operador: str, operador_id: int = None, senha: str = "",
               gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    v = _autorizar_gerencial(operador_id, senha, gerente_pin_id, pin, codigo_barras, _ROLES_GERENCIAIS)
    if v.get("error"): return v
    return create("suprimentos", {"caixa_id": caixa_id, "valor": valor, "motivo": motivo, "operador": v.get("nome") or operador})

def _validar_desconto_operador(operador_id, itens: list, desconto: float, total_itens: float,
                                gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    """Valida desconto maximo do operador — total agregado E por item
    individual (so' validar o total permitia burlar o limite concentrando o
    desconto inteiro em um item). Reusada por realizar_venda, criar_orcamento
    e converter_orcamento — as tres portas que geram uma venda finalizada;
    validar so' em realizar_venda deixava orcamento->conversao como um
    caminho para contornar o limite sem passar pela checagem.
    Um gerente pode autorizar acima do limite via PIN ou codigo de barras,
    sem o operador precisar fazer logout/login. Retorna {} se ok, ou
    {"error": ...} se o desconto exceder o limite sem autorizacao."""
    if not operador_id:
        return {}
    op = _get("pdv_operadores", operador_id)
    max_pct = float(op.get("desconto_maximo_percent") or 0) if op and not op.get("error") else 0
    if max_pct <= 0:
        return {}
    autorizado_por_gerente = False
    if codigo_barras:
        v = verificar_codigo_barras_gerencial(codigo_barras, _ROLES_GERENCIAIS)
        autorizado_por_gerente = not v.get("error")
    elif gerente_pin_id and pin:
        v = verificar_pin_gerencial(gerente_pin_id, pin, _ROLES_GERENCIAIS)
        autorizado_por_gerente = not v.get("error")
    if autorizado_por_gerente:
        return {}
    if desconto > 0 and total_itens > 0:
        pct_desconto = (desconto / total_itens) * 100
        if pct_desconto > max_pct:
            return {"error": f"Desconto maximo permitido: {max_pct:.1f}% (tentativa: {pct_desconto:.1f}%)"}
    for item in itens:
        item_desconto = item.get("desconto", 0) or 0
        subtotal_item = (item.get("quantidade", 1) or 1) * (item.get("valor_unitario", 0) or 0)
        if item_desconto > 0 and subtotal_item > 0:
            pct_item = (item_desconto / subtotal_item) * 100
            if pct_item > max_pct:
                return {"error": f"Desconto maximo permitido: {max_pct:.1f}% (item '{item.get('descricao','')}' com {pct_item:.1f}%)"}
    return {}


def realizar_venda(caixa_id: int, itens: list, pagamentos: list, cliente="", cliente_id=None, operador="", operador_id=None,
                    desconto=0.0, gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    total_itens = sum((i.get("quantidade",1) or 1) * (i.get("valor_unitario",0) or 0) - (i.get("desconto",0) or 0) for i in itens)
    total = round(total_itens - desconto, 2)

    erro = _validar_desconto_operador(operador_id, itens, desconto, total_itens, gerente_pin_id, pin, codigo_barras)
    if erro: return erro

    # Sem essa checagem, uma venda fecha "finalizada" mesmo com soma dos
    # pagamentos menor que o total — quebra de caixa silenciosa, descoberta
    # so' no fechamento (ou nunca). Sobrepagamento e' permitido (vira troco).
    total_pago = round(sum((pg.get("valor", 0) or 0) for pg in pagamentos), 2)
    if total_pago < total - 0.01:
        falta = round(total - total_pago, 2)
        return {"error": f"Pagamento insuficiente: faltam R$ {falta:.2f} para cobrir o total de R$ {total:.2f}"}

    # ponytail: transacao atomica — se item/pgto/baixa-de-estoque falhar, venda inteira rollback
    async def _go():
        await _ensure_saldos_async()
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                loja = await _resolver_loja_da_venda(conn, caixa_id)
                row = await conn.fetchrow("""INSERT INTO pdv_vendas (caixa_id, cliente, cliente_id, total, desconto, operador, data, estoque_baixado)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *""",
                    caixa_id, cliente, cliente_id, total, desconto, operador, datetime.now(), bool(loja))
                vid = row["id"]
                for item in itens:
                    item_desconto = item.get("desconto",0) or 0
                    item_total = round((item.get("quantidade",1) or 1) * (item.get("valor_unitario",0) or 0) - item_desconto, 2)
                    await conn.execute("INSERT INTO pdv_itens (venda_id, produto_codigo, descricao, quantidade, valor_unitario, desconto, valor_total) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                        vid, item.get("codigo",""), item.get("descricao",""),
                        item.get("quantidade",1), item.get("valor_unitario",0),
                        item_desconto, item_total)
                    if loja:
                        sku = item.get("codigo","")
                        r = await saida_async(conn, sku, loja, item.get("quantidade",1) or 1, "venda_pdv",
                                              usuario_id=operador_id, usuario_nome=operador)
                        if r.get("erro"):
                            raise SaldoError(f"Estoque insuficiente para {sku}: {r['erro']}")
                for pg in pagamentos:
                    await conn.execute("INSERT INTO pdv_pagamentos (venda_id, forma, valor, parcelas) VALUES ($1,$2,$3,$4)",
                        vid, pg.get("forma","dinheiro"), pg.get("valor",total), pg.get("parcelas",1))
                return {"venda": dict(row), "total": total}
    try:
        result = run_async(_go())
    except SaldoError as e:
        return {"error": str(e)}
    if result and not result.get("error"):
        try:
            from core.automacoes import disparar_webhooks
            from threading import Thread
            v = result.get("venda", {})
            Thread(target=lambda: disparar_webhooks("venda.criada", {
                "venda_id": str(v.get("id", "")),
                "total": str(result.get("total", "")),
                "cliente": str(cliente),
                "operador": str(operador),
            }), daemon=True).start()
        except Exception: pass
    return result

def relatorio_descontos_por_operador(dias: int = 30) -> list:
    """Quanto cada operador desconta e quao perto do proprio limite maximo
    fica — desconto proximo do teto e' uma forma comum de fraude (vender por
    menos para um conhecido, dividir o troco com o cliente)."""
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"""
            SELECT v.operador,
                   COUNT(*) AS qtd_vendas,
                   SUM(v.total + v.desconto) AS subtotal_bruto,
                   SUM(v.desconto) AS desconto_total
            FROM pdv_vendas v
            WHERE v.status = 'finalizada' AND v.data >= NOW() - INTERVAL '{int(dias)} days'
                AND v.operador IS NOT NULL AND v.operador != ''
            GROUP BY v.operador
        """)
        out = []
        for r in rows:
            bruto = float(r["subtotal_bruto"] or 0)
            desc = float(r["desconto_total"] or 0)
            pct_medio = round((desc / bruto * 100) if bruto > 0 else 0, 2)
            op_row = await db.fetchrow("SELECT desconto_maximo_percent FROM pdv_operadores WHERE nome = $1", r["operador"])
            limite = float(op_row["desconto_maximo_percent"] or 0) if op_row else 0
            out.append({
                "operador": r["operador"], "qtd_vendas": r["qtd_vendas"],
                "desconto_total": desc, "pct_medio_desconto": pct_medio,
                "limite_desconto_pct": limite,
                "proximo_do_limite": limite > 0 and pct_medio >= limite * 0.8,
            })
        out.sort(key=lambda x: x["pct_medio_desconto"], reverse=True)
        return out
    try: return run_async(_go())
    except Exception as e: return []


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
    except Exception as e: return {"caixa_aberto": None, "vendas_hoje": 0, "qtd_hoje": 0}

# ── Orcamento / Pre-venda ──

def criar_orcamento(cliente: str = "", cliente_id=None, itens: list = None, operador: str = "", operador_id=None, desconto: float = 0,
                     gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    """Cria venda com status 'orcamento' — igual a venda normal, mas sem caixa_id.
    Valida o mesmo limite de desconto de realizar_venda — sem isso, orcamento
    virava uma porta lateral para aplicar qualquer desconto e depois converter
    em venda finalizada sem nunca passar pela checagem."""
    itens = itens or []
    total_itens = sum((i.get("quantidade",1) or 1) * (i.get("valor_unitario",0) or 0) - (i.get("desconto",0) or 0) for i in itens)
    total = round(total_itens - desconto, 2)

    erro = _validar_desconto_operador(operador_id, itens, desconto, total_itens, gerente_pin_id, pin, codigo_barras)
    if erro: return erro

    async def _go():
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow("""INSERT INTO pdv_vendas (cliente, cliente_id, total, desconto, operador, status, tipo, data)
                    VALUES ($1,$2,$3,$4,$5,'orcamento','orcamento',$6) RETURNING *""",
                    cliente, cliente_id, total, desconto, operador, datetime.now())
                vid = row["id"]
                for item in (itens or []):
                    item_desconto = item.get("desconto",0) or 0
                    item_total = round((item.get("quantidade",1) or 1) * (item.get("valor_unitario",0) or 0) - item_desconto, 2)
                    await conn.execute("INSERT INTO pdv_itens (venda_id, produto_codigo, descricao, quantidade, valor_unitario, desconto, valor_total) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                        vid, item.get("codigo",""), item.get("descricao",""),
                        item.get("quantidade",1), item.get("valor_unitario",0), item_desconto, item_total)
                return {"orcamento": dict(row), "total": total}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def converter_orcamento(venda_id: int, caixa_id: int, pagamentos: list, operador: str = "", operador_id=None,
                         gerente_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    """Converte orcamento em venda finalizada, vinculando ao caixa e registrando pagamentos.
    Revalida o limite de desconto do operador (o orcamento pode ter sido
    criado por outra sessao, ou o limite do operador pode ter mudado desde
    a criacao) — defesa em profundidade alem da checagem em criar_orcamento."""
    async def _buscar():
        db = await get_db()
        venda = await db.fetchrow("SELECT * FROM pdv_vendas WHERE id = $1", venda_id)
        itens = await db.fetch("SELECT * FROM pdv_itens WHERE venda_id = $1", venda_id)
        return venda, [dict(i) for i in itens]
    venda_atual, itens_atuais = run_async(_buscar())
    if not venda_atual:
        return {"error": "Orcamento nao encontrado"}
    if venda_atual["status"] != "orcamento":
        return {"error": "Venda nao e um orcamento"}
    desconto_total = float(venda_atual["desconto"] or 0)
    total_itens_atual = sum(float(i.get("valor_unitario") or 0) * float(i.get("quantidade") or 1) for i in itens_atuais)
    itens_para_validar = [{"descricao": i.get("descricao", ""), "quantidade": float(i.get("quantidade") or 1),
                            "valor_unitario": float(i.get("valor_unitario") or 0), "desconto": float(i.get("desconto") or 0)}
                           for i in itens_atuais]
    erro = _validar_desconto_operador(operador_id, itens_para_validar, desconto_total, total_itens_atual,
                                       gerente_pin_id, pin, codigo_barras)
    if erro: return erro

    total_pago = round(sum((pg.get("valor", 0) or 0) for pg in pagamentos), 2)
    total_orcamento = float(venda_atual["total"] or 0)
    if total_pago < total_orcamento - 0.01:
        falta = round(total_orcamento - total_pago, 2)
        return {"error": f"Pagamento insuficiente: faltam R$ {falta:.2f} para cobrir o total de R$ {total_orcamento:.2f}"}

    async def _go():
        db = await get_db()
        venda = await db.fetchrow("SELECT * FROM pdv_vendas WHERE id = $1", venda_id)
        if not venda: return {"error": "Orcamento nao encontrado"}
        if venda["status"] != "orcamento": return {"error": "Venda nao e um orcamento"}
        total = float(venda["total"] or 0)
        async with db.acquire() as conn:
            async with conn.transaction():
                await conn.execute("UPDATE pdv_vendas SET caixa_id=$1, status='finalizada', tipo='venda', data=NOW() WHERE id=$2",
                    caixa_id, venda_id)
                for pg in pagamentos:
                    await conn.execute("INSERT INTO pdv_pagamentos (venda_id, forma, valor, parcelas) VALUES ($1,$2,$3,$4)",
                        venda_id, pg.get("forma","dinheiro"), pg.get("valor",total), pg.get("parcelas",1))
                return {"venda_id": venda_id, "total": total, "convertido": True}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}
