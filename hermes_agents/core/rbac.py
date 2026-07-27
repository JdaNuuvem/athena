"""RBAC Core — Roles, Permissoes, Usuarios, Middleware de Autorizacao"""
from core import get_db, run_async, log, hoje
from functools import wraps
from flask import request, jsonify
from datetime import datetime, timedelta, timezone
import hashlib, os as _os, jwt as _jwt

AGENT = "RBAC Core"

# ── Sessao por usuario (JWT) ──
# ponytail: antes, TODO login (independente do usuario/role) gravava o mesmo
# API_TOKEN global no cookie auth_token — qualquer usuario logado normalmente
# batia com o "token master" e pulava qualquer checagem de permissao por
# usuario em requer_permissao(). Agora cada login gera um JWT assinado e
# unico, com user_id/role dentro do payload (nao falsificavel sem a chave).

JWT_ALGORITHM = "HS256"
JWT_EXPIRACAO_HORAS = 24 * 30  # 30 dias — mesma duracao do cookie anterior

def _jwt_secret() -> str:
    """Chave de assinatura do JWT — dedicada (ATHENA_JWT_SECRET), com fallback
    para ATHENA_TOKEN por compatibilidade com deploys que so' tem esse configurado.
    ponytail: SEM fallback hardcoded — se nenhum dos dois estiver configurado,
    assinar/verificar token com uma chave publica no codigo-fonte permitiria
    qualquer um forjar sessoes validas. Falha alto e visivel em vez disso."""
    secret = _os.environ.get("ATHENA_JWT_SECRET", "") or _os.environ.get("ATHENA_TOKEN", "")
    if not secret:
        raise RuntimeError("ATHENA_JWT_SECRET (ou ATHENA_TOKEN) nao configurado — sessao JWT desabilitada")
    return secret

def gerar_token_sessao(user_id, email: str, role: str, is_master: bool = False) -> str:
    """Gera um JWT de sessao assinado e unico por usuario."""
    payload = {
        "user_id": user_id, "email": email, "role": role, "is_master": is_master,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRACAO_HORAS),
        "iat": datetime.now(timezone.utc),
    }
    return _jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)

def verificar_token_sessao(token: str):
    """Decodifica e valida um token de sessao. Retorna o payload (dict) ou None se invalido/expirado."""
    if not token:
        return None
    try:
        return _jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except Exception:
        return None

def usuario_atual_da_request() -> dict:
    """Extrai {user_id, nome, email, role, is_master} do token da request atual,
    para gravar em movimentacoes de estoque (rastreabilidade — quem fez o que).
    Retorna dict com valores None/vazio se nao autenticado ou usando o token master."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    cookie_token = request.cookies.get("auth_token", "")
    auth_token = token or cookie_token
    master_token = _os.environ.get("ATHENA_TOKEN", "")
    if master_token and auth_token == master_token:
        return {"user_id": None, "nome": "Admin (token master)", "email": "", "role": "admin", "is_master": True}
    payload = verificar_token_sessao(auth_token)
    if not payload:
        return {"user_id": None, "nome": "", "email": "", "role": "", "is_master": False}
    email = payload.get("email", "")
    return {
        "user_id": payload.get("user_id"),
        "nome": email.split("@")[0] if email else "",
        "email": email,
        "role": payload.get("role", ""),
        "is_master": bool(payload.get("is_master")),
    }

# ── Modulos e Acoes ──

MODULOS = [
    "dashboard", "cadastros", "produtos", "estoque", "compras", "vendas", "pdv",
    "financeiro", "fiscal", "crm", "atendimento", "producao", "rh", "bi",
    "documentos", "automacoes", "relatorios", "configuracoes", "bling", "agentes",
]

ACOES_PADRAO = [
    ("ver", "Visualizar"), ("criar", "Criar"), ("editar", "Editar"),
    ("excluir", "Excluir"), ("aprovar", "Aprovar"), ("exportar", "Exportar"),
]

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS rbac_permissoes (
            id SERIAL PRIMARY KEY, codigo VARCHAR(100) UNIQUE NOT NULL,
            descricao VARCHAR(200), modulo VARCHAR(50), acao VARCHAR(30),
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS rbac_roles (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) UNIQUE NOT NULL,
            descricao VARCHAR(200), created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS rbac_role_permissoes (
            role_id INT REFERENCES rbac_roles(id) ON DELETE CASCADE,
            permissao_id INT REFERENCES rbac_permissoes(id) ON DELETE CASCADE,
            PRIMARY KEY (role_id, permissao_id)
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS rbac_usuarios (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL, password_hash VARCHAR(200) NOT NULL,
            role_id INT REFERENCES rbac_roles(id), ativo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        # Seed permissoes
        count = await db.fetchval("SELECT COUNT(*) FROM rbac_permissoes")
        if count == 0:
            for modulo in MODULOS:
                for acao, acao_desc in ACOES_PADRAO:
                    codigo = f"{modulo}.{acao}"
                    descricao = f"{acao_desc} - {modulo.capitalize()}"
                    await db.execute("INSERT INTO rbac_permissoes (codigo,descricao,modulo,acao) VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING", codigo, descricao, modulo, acao)
            await db.execute("INSERT INTO rbac_permissoes (codigo,descricao,modulo,acao) VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING", "pdv.operar", "Operar PDV", "pdv", "operar")
            await db.execute("INSERT INTO rbac_permissoes (codigo,descricao,modulo,acao) VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING", "bling.sincronizar", "Sincronizar Bling", "bling", "sincronizar")
        # Seed roles
        count_r = await db.fetchval("SELECT COUNT(*) FROM rbac_roles")
        if count_r == 0:
            roles = [
                ("Admin", "Acesso total ao sistema", None),
                ("Financeiro", "Financeiro e relatorios", ["dashboard.ver","produtos.ver","vendas.ver","financeiro.ver","financeiro.criar","financeiro.editar","financeiro.excluir","financeiro.aprovar","financeiro.exportar","fiscal.ver","fiscal.criar","fiscal.editar","fiscal.excluir","fiscal.aprovar","relatorios.ver","relatorios.exportar","crm.ver","compras.ver","compras.aprovar","bi.ver","bi.exportar"]),
                ("Operador Loja", "PDV e vendas basicas", ["dashboard.ver","pdv.ver","pdv.operar","pdv.criar","produtos.ver","estoque.ver","vendas.ver","vendas.criar","atendimento.ver","atendimento.criar","crm.ver","crm.criar"]),
                ("Gerente", "Gestao de loja", ["dashboard.ver","cadastros.ver","cadastros.criar","cadastros.editar","produtos.ver","produtos.criar","produtos.editar","estoque.ver","estoque.criar","estoque.editar","estoque.aprovar","compras.ver","compras.criar","compras.editar","compras.aprovar","vendas.ver","vendas.criar","vendas.editar","vendas.aprovar","pdv.ver","pdv.operar","pdv.criar","pdv.aprovar","financeiro.ver","crm.ver","crm.criar","crm.editar","atendimento.ver","atendimento.criar","atendimento.editar","relatorios.ver","relatorios.exportar"]),
            ]
            for nome, desc, perms in roles:
                row = await db.fetchrow("INSERT INTO rbac_roles (nome,descricao) VALUES ($1,$2) RETURNING id", nome, desc)
                role_id = row["id"]
                if nome == "Admin":
                    all_perms = await db.fetch("SELECT id FROM rbac_permissoes")
                    for p in all_perms:
                        await db.execute("INSERT INTO rbac_role_permissoes (role_id,permissao_id) VALUES ($1,$2)", role_id, p["id"])
                elif perms:
                    for codigo in perms:
                        p_row = await db.fetchrow("SELECT id FROM rbac_permissoes WHERE codigo=$1", codigo)
                        if p_row:
                            await db.execute("INSERT INTO rbac_role_permissoes (role_id,permissao_id) VALUES ($1,$2)", role_id, p_row["id"])
        # Fix-up idempotente: garante permissoes novas no role Gerente mesmo em
        # bancos onde o seed de roles ja rodou antes delas existirem
        # (o bloco acima so' roda "if count_r == 0", nao repete em bancos existentes).
        for codigo_permissao in ("estoque.aprovar", "pdv.aprovar", "compras.excluir", "rh.ver", "rh.criar", "rh.editar"):
            try:
                gerente = await db.fetchrow("SELECT id FROM rbac_roles WHERE nome = 'Gerente'")
                perm = await db.fetchrow("SELECT id FROM rbac_permissoes WHERE codigo = $1", codigo_permissao)
                if gerente and perm:
                    await db.execute(
                        "INSERT INTO rbac_role_permissoes (role_id,permissao_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                        gerente["id"], perm["id"])
            except Exception as e:
                log(AGENT, f"Fix-up {codigo_permissao} falhou: {e}")

        # Seed usuarios padrao (senhas via env vars, sem fallback hardcoded)
        count_u = await db.fetchval("SELECT COUNT(*) FROM rbac_usuarios")
        admin_pw = _os.environ.get("ATHENA_ADMIN_PW") or _os.environ.get("ATHENA_TOKEN", "")
        dev_mode = _os.environ.get("ATHENA_DEV_MODE", "").lower() == "true"
        salt = _os.urandom(16).hex()
        if count_u == 0:
            users = [
                ("Admin","admin@athena.local", admin_pw or "", "Admin"),
            ] if admin_pw or dev_mode else []
            if dev_mode and not users:
                users = [
                    ("Admin","admin@athena.local", "admin", "Admin"),
                ]
            for nome, email, senha, role_nome in users:
                pw_hash = hashlib.sha256(f"{senha}:{salt}".encode()).hexdigest()
                role_row = await db.fetchrow("SELECT id FROM rbac_roles WHERE nome=$1", role_nome)
                await db.execute("INSERT INTO rbac_usuarios (nome,email,password_hash,role_id) VALUES ($1,$2,$3,$4)",
                    nome, email, f"{salt}:{pw_hash}", role_row["id"] if role_row else None)
        elif admin_pw:
            # ponytail: atualiza senha do admin existente em todo boot
            pw_hash = hashlib.sha256(f"{admin_pw}:{salt}".encode()).hexdigest()
            await db.execute("UPDATE rbac_usuarios SET password_hash=$1 WHERE email='admin@athena.local'",
                f"{salt}:{pw_hash}")
    try:
        run_async(_go())
        log(AGENT, "RBAC tables seeded")
    except Exception as e:
        log(AGENT, f"Erro RBAC seed: {e}")

_ensure_tables()

# ── Auth functions ──

def autenticar(email: str, senha: str) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM rbac_usuarios WHERE email=$1 AND ativo=TRUE", email.lower().strip())
        if not row:
            return {"error": "Usuario nao encontrado"}
        parts = row["password_hash"].split(":", 1)
        if len(parts) != 2:
            return {"error": "Hash invalido"}
        salt, stored = parts
        computed = hashlib.sha256(f"{senha}:{salt}".encode()).hexdigest()
        if computed != stored:
            return {"error": "Senha incorreta"}
        role = await db.fetchrow("SELECT id,nome FROM rbac_roles WHERE id=$1", row["role_id"])
        permissoes = await db.fetch("SELECT p.codigo FROM rbac_role_permissoes rp JOIN rbac_permissoes p ON p.id=rp.permissao_id WHERE rp.role_id=$1", row["role_id"])
        return {
            "id": row["id"], "nome": row["nome"], "email": row["email"],
            "role": role["nome"] if role else "sem_role",
            "permissoes": [p["codigo"] for p in (permissoes or [])],
            "autenticado": True,
        }
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def get_permissoes_por_usuario(user_id: int) -> list:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT role_id FROM rbac_usuarios WHERE id=$1", user_id)
        if not row: return []
        perms = await db.fetch("SELECT p.codigo FROM rbac_role_permissoes rp JOIN rbac_permissoes p ON p.id=rp.permissao_id WHERE rp.role_id=$1", row["role_id"])
        return [p["codigo"] for p in (perms or [])]
    try: return run_async(_go())
    except Exception as e: return []

# ── CRUD ──

def _list(t, order="id DESC", limit=500):
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"SELECT * FROM {t} ORDER BY {order} LIMIT {limit}")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def list_roles(): return _list("rbac_roles")
def list_permissoes(): return _list("rbac_permissoes")
def list_usuarios(): return _list("rbac_usuarios")

def criar_role(nome: str, descricao: str = "", permissoes: list = None) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("INSERT INTO rbac_roles (nome,descricao) VALUES ($1,$2) RETURNING *", nome, descricao)
        if row and permissoes:
            for codigo in (permissoes or []):
                p = await db.fetchrow("SELECT id FROM rbac_permissoes WHERE codigo=$1", codigo)
                if p: await db.execute("INSERT INTO rbac_role_permissoes (role_id,permissao_id) VALUES ($1,$2)", row["id"], p["id"])
        return dict(row) if row else {"error": "erro ao criar"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def atualizar_role(role_id: int, nome: str = None, descricao: str = None, permissoes: list = None) -> dict:
    async def _go():
        db = await get_db()
        if nome: await db.execute("UPDATE rbac_roles SET nome=$1 WHERE id=$2", nome, role_id)
        if descricao: await db.execute("UPDATE rbac_roles SET descricao=$1 WHERE id=$2", descricao, role_id)
        if permissoes is not None:
            await db.execute("DELETE FROM rbac_role_permissoes WHERE role_id=$1", role_id)
            for codigo in permissoes:
                p = await db.fetchrow("SELECT id FROM rbac_permissoes WHERE codigo=$1", codigo)
                if p: await db.execute("INSERT INTO rbac_role_permissoes (role_id,permissao_id) VALUES ($1,$2)", role_id, p["id"])
        row = await db.fetchrow("SELECT * FROM rbac_roles WHERE id=$1", role_id)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def deletar_role(role_id: int) -> dict:
    async def _go():
        db = await get_db()
        await db.execute("DELETE FROM rbac_roles WHERE id=$1", role_id)
        return {"success": True}
    try: run_async(_go()); return {"success": True}
    except Exception as e: return {"error": str(e)}

def criar_usuario(nome: str, email: str, senha: str, role_nome: str) -> dict:
    async def _go():
        db = await get_db()
        role = await db.fetchrow("SELECT id FROM rbac_roles WHERE nome=$1", role_nome)
        salt = _os.urandom(16).hex()
        pw_hash = hashlib.sha256(f"{senha}:{salt}".encode()).hexdigest()
        row = await db.fetchrow("INSERT INTO rbac_usuarios (nome,email,password_hash,role_id) VALUES ($1,$2,$3,$4) RETURNING id,nome,email,role_id,ativo",
            nome, email.lower().strip(), f"{salt}:{pw_hash}", role["id"] if role else None)
        return dict(row) if row else {"error": "erro ao criar"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def atualizar_usuario(user_id: int, nome: str = None, role_nome: str = None, ativo: bool = None) -> dict:
    async def _go():
        db = await get_db()
        if nome: await db.execute("UPDATE rbac_usuarios SET nome=$1 WHERE id=$2", nome, user_id)
        if role_nome:
            role = await db.fetchrow("SELECT id FROM rbac_roles WHERE nome=$1", role_nome)
            if role: await db.execute("UPDATE rbac_usuarios SET role_id=$1 WHERE id=$2", role["id"], user_id)
        if ativo is not None: await db.execute("UPDATE rbac_usuarios SET ativo=$1 WHERE id=$2", ativo, user_id)
        row = await db.fetchrow("SELECT id,nome,email,role_id,ativo FROM rbac_usuarios WHERE id=$1", user_id)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

# ── Decorator de permissao ──

def usuario_tem_permissao(codigo: str) -> bool:
    """Checagem booleana de permissao do usuario da request atual (mesma logica
    de requer_permissao, sem interromper a request) — usada quando uma rota
    libera a acao basica para todos, mas exige uma permissao extra so' acima
    de algum limiar (ex: alcada de aprovacao financeira por valor)."""
    token = request.headers.get("Authorization","").replace("Bearer ","")
    cookie_token = request.cookies.get("auth_token","")
    auth_token = token or cookie_token
    # token master via env (bypass administrativo/scripts — nao usado pelo login normal)
    master_token = _os.environ.get("ATHENA_TOKEN", "")
    if master_token and auth_token == master_token:
        return True
    # ponytail: user_id vem do JWT assinado (payload), NUNCA de um cookie separado
    # nao-assinado — um cookie user_id solto poderia ser trocado pelo cliente para
    # qualquer valor e se passar por outro usuario.
    payload = verificar_token_sessao(auth_token)
    if not payload:
        return False
    if payload.get("is_master"):
        return True
    user_id = payload.get("user_id")
    if not user_id:
        return False
    return codigo in get_permissoes_por_usuario(int(user_id))

def requer_permissao(codigo: str):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if usuario_tem_permissao(codigo):
                return f(*args, **kwargs)
            return jsonify({"error": "Permissao negada", "required": codigo}), 403
        return wrapper
    return decorator

if __name__ == "__main__":
    log(AGENT, "Auto-teste RBAC")
    print("Roles:", len(list_roles()))
    print("Permissoes:", len(list_permissoes()))
    print("Usuarios:", len(list_usuarios()))
