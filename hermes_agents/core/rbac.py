"""RBAC Core — Roles, Permissoes, Usuarios, Middleware de Autorizacao"""
from core import get_db, run_async, log, hoje
from functools import wraps
from flask import request, jsonify
from datetime import datetime, timedelta, timezone
import hashlib, hmac, os as _os, jwt as _jwt

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
    """Decodifica e valida um token de sessao. Retorna o payload (dict) ou None se invalido/expirado.
    ponytail: rejeita qualquer payload com claim `typ` — os tokens do OAuth
    provider (core/oauth_provider.py: `oauth_code`/`oauth_access`) sao JWTs
    assinados com esse mesmo ATHENA_JWT_SECRET e carregam user_id, mas sao
    validos so' pra uma troca pontual (code) ou pro /oauth/userinfo (access
    token). Sem essa checagem, um access_token OAuth de 1h viraria uma sessao
    completa do Hermes em qualquer /api/* — o access_token so' foi pensado
    pra autorizar UMA chamada ao /oauth/userinfo. Tokens de sessao normais
    (gerar_token_sessao) nunca setam `typ`."""
    if not token:
        return None
    try:
        payload = _jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except Exception:
        return None
    if payload.get("typ"):
        return None
    return payload

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

# Papeis alem dos 4 originais (Admin/Financeiro/Operador Loja/Gerente),
# cobrindo as funcoes reais do negocio (fabrica + 5 lojas + marketplace).
# Criados via fix-up idempotente em _ensure_tables — nao apagam nem duplicam
# papeis existentes, so' adicionam os que ainda nao existem pelo nome.
ROLES_EXTRAS = [
    ("Estoquista", "Controle de estoque fisico da loja",
     ["dashboard.ver", "produtos.ver", "estoque.ver", "estoque.criar", "estoque.editar", "compras.ver", "pdv.ver"]),
    ("Comprador", "Compra de fornecedores e manutencao de estoque da loja",
     ["dashboard.ver", "cadastros.ver", "produtos.ver", "produtos.criar", "produtos.editar",
      "compras.ver", "compras.criar", "compras.editar", "compras.aprovar",
      "estoque.ver", "estoque.criar", "estoque.editar", "relatorios.ver"]),
    ("Contador", "Compliance fiscal e contabil",
     ["dashboard.ver", "fiscal.ver", "fiscal.criar", "fiscal.editar", "fiscal.exportar",
      "financeiro.ver", "financeiro.exportar", "relatorios.ver", "relatorios.exportar", "bi.ver"]),
    ("RH", "Gestao de pessoal",
     ["dashboard.ver", "rh.ver", "rh.criar", "rh.editar", "rh.excluir", "documentos.ver", "documentos.criar", "cadastros.ver"]),
    ("Administracao", "Back-office administrativo e financeiro operacional",
     ["dashboard.ver", "financeiro.ver", "financeiro.criar", "financeiro.editar", "financeiro.aprovar",
      "cadastros.ver", "cadastros.criar", "cadastros.editar", "rh.ver",
      "documentos.ver", "documentos.criar", "compras.ver", "compras.aprovar",
      "relatorios.ver", "relatorios.exportar"]),
    ("Producao", "Chao de fabrica: ordens, apontamento e maquinas",
     ["dashboard.ver", "producao.ver", "producao.criar", "producao.editar", "estoque.ver"]),
    ("E-commerce", "Marketplaces, precos e catalogo online",
     ["dashboard.ver", "produtos.ver", "produtos.editar", "vendas.ver", "bling.sincronizar", "relatorios.ver"]),
    ("Atendimento", "SAC e relacionamento com cliente",
     ["dashboard.ver", "atendimento.ver", "atendimento.criar", "atendimento.editar", "crm.ver", "crm.criar"]),
    ("Diretor", "Visao executiva — leitura ampla, sem operacao do dia a dia",
     ["dashboard.ver", "cadastros.ver", "produtos.ver", "estoque.ver", "compras.ver", "vendas.ver",
      "pdv.ver", "financeiro.ver", "fiscal.ver", "crm.ver", "atendimento.ver", "producao.ver",
      "rh.ver", "bi.ver", "bi.exportar", "documentos.ver", "automacoes.ver",
      "relatorios.ver", "relatorios.exportar", "configuracoes.ver"]),
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
        # ponytail: PIN/cracha para autorizacao gerencial fora do PDV (ex: aprovar
        # pagamento grande no financeiro sem precisar trocar de sessao) — mesmo
        # padrao ja usado em pdv_operadores, aplicado aos usuarios do RBAC principal.
        try: await db.execute("ALTER TABLE rbac_usuarios ADD COLUMN IF NOT EXISTS pin_hash VARCHAR(200)")
        except Exception: pass
        try: await db.execute("ALTER TABLE rbac_usuarios ADD COLUMN IF NOT EXISTS codigo_barras_hash VARCHAR(200)")
        except Exception: pass
        # ponytail: PIN tem so' 4-6 digitos (10 mil a 1 milhao de combinacoes) —
        # sem bloqueio por tentativas, /api/rbac/autorizar vira um oraculo de
        # forca bruta contra qualquer usuario alvo. Cracha nao precisa disso
        # (segredo de 64 bits gerado aleatoriamente, forca bruta inviavel).
        await db.execute("""CREATE TABLE IF NOT EXISTS rbac_autorizacao_tentativas (
            user_id INT PRIMARY KEY, tentativas INT DEFAULT 0, bloqueado_ate TIMESTAMP
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
            await db.execute("INSERT INTO rbac_permissoes (codigo,descricao,modulo,acao) VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING", "lojas.ver_todas", "Ver todas as lojas (ignora restricao de usuario_lojas)", "lojas", "ver_todas")
            await db.execute("INSERT INTO rbac_permissoes (codigo,descricao,modulo,acao) VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING", "lojas.excluir_forcado", "Excluir loja com dado vinculado (irreversivel)", "lojas", "excluir_forcado")
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
        # Fix-up idempotente: garante que "lojas.ver_todas" exista e esteja
        # no Admin mesmo em bancos onde o seed de roles ja rodou antes dela
        # existir. Sem isso, o Admin ficaria restrito por usuario_lojas igual
        # qualquer outro usuario assim que essa fase for ativada.
        try:
            await db.execute("INSERT INTO rbac_permissoes (codigo,descricao,modulo,acao) VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING",
                              "lojas.ver_todas", "Ver todas as lojas (ignora restricao de usuario_lojas)", "lojas", "ver_todas")
            admin_role = await db.fetchrow("SELECT id FROM rbac_roles WHERE nome = 'Admin'")
            perm_ver_todas = await db.fetchrow("SELECT id FROM rbac_permissoes WHERE codigo = 'lojas.ver_todas'")
            if admin_role and perm_ver_todas:
                await db.execute("INSERT INTO rbac_role_permissoes (role_id,permissao_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                                  admin_role["id"], perm_ver_todas["id"])
        except Exception as e:
            log(AGENT, f"Fix-up lojas.ver_todas falhou: {e}")

        # Fix-up idempotente: garante que "lojas.excluir_forcado" exista e
        # esteja no Admin mesmo em bancos onde o seed de roles ja rodou antes
        # dela existir — mesmo padrao do fix-up de "lojas.ver_todas" acima.
        try:
            await db.execute("INSERT INTO rbac_permissoes (codigo,descricao,modulo,acao) VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING",
                              "lojas.excluir_forcado", "Excluir loja com dado vinculado (irreversivel)", "lojas", "excluir_forcado")
            admin_role = await db.fetchrow("SELECT id FROM rbac_roles WHERE nome = 'Admin'")
            perm_excluir_forcado = await db.fetchrow("SELECT id FROM rbac_permissoes WHERE codigo = 'lojas.excluir_forcado'")
            if admin_role and perm_excluir_forcado:
                await db.execute("INSERT INTO rbac_role_permissoes (role_id,permissao_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                                  admin_role["id"], perm_excluir_forcado["id"])
        except Exception as e:
            log(AGENT, f"Fix-up lojas.excluir_forcado falhou: {e}")

        # Fix-up idempotente: garante permissoes novas no role Gerente mesmo em
        # bancos onde o seed de roles ja rodou antes delas existirem
        # (o bloco acima so' roda "if count_r == 0", nao repete em bancos existentes).
        for codigo_permissao in ("estoque.aprovar", "pdv.aprovar", "compras.excluir", "rh.ver", "rh.criar", "rh.editar", "cadastros.excluir", "vendas.excluir", "crm.excluir", "atendimento.excluir", "producao.ver", "producao.criar", "producao.editar", "bi.ver"):
            try:
                gerente = await db.fetchrow("SELECT id FROM rbac_roles WHERE nome = 'Gerente'")
                perm = await db.fetchrow("SELECT id FROM rbac_permissoes WHERE codigo = $1", codigo_permissao)
                if gerente and perm:
                    await db.execute(
                        "INSERT INTO rbac_role_permissoes (role_id,permissao_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                        gerente["id"], perm["id"])
            except Exception as e:
                log(AGENT, f"Fix-up {codigo_permissao} falhou: {e}")

        # Fix-up idempotente: renomeia "Operador Loja" para "Vendedor" (nome
        # real usado no negocio) preservando permissoes e usuarios ja
        # atribuidos, e cria os papeis novos (ROLES_EXTRAS) que ainda nao
        # existirem pelo nome.
        try:
            op_loja = await db.fetchrow("SELECT id FROM rbac_roles WHERE nome = 'Operador Loja'")
            vendedor_ja_existe = await db.fetchrow("SELECT id FROM rbac_roles WHERE nome = 'Vendedor'")
            if op_loja and not vendedor_ja_existe:
                await db.execute("UPDATE rbac_roles SET nome = 'Vendedor' WHERE id = $1", op_loja["id"])
        except Exception as e:
            log(AGENT, f"Renomear Operador Loja -> Vendedor falhou: {e}")

        for nome_role, desc_role, perms_role in ROLES_EXTRAS:
            try:
                existente = await db.fetchrow("SELECT id FROM rbac_roles WHERE nome = $1", nome_role)
                if existente:
                    continue
                row = await db.fetchrow("INSERT INTO rbac_roles (nome, descricao) VALUES ($1,$2) RETURNING id", nome_role, desc_role)
                role_id = row["id"]
                for codigo in perms_role:
                    p_row = await db.fetchrow("SELECT id FROM rbac_permissoes WHERE codigo=$1", codigo)
                    if p_row:
                        await db.execute("INSERT INTO rbac_role_permissoes (role_id,permissao_id) VALUES ($1,$2) ON CONFLICT DO NOTHING", role_id, p_row["id"])
            except Exception as e:
                log(AGENT, f"Fix-up role {nome_role} falhou: {e}")

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

# ── PIN / crachá (autorização gerencial fora do PDV) ──
# ponytail: mesmo padrão scrypt já usado em pdv_operadores (core/pdv.py) — aqui
# aplicado aos usuários do RBAC principal, para permitir que um gerente autorize
# uma ação sensível (ex: aprovar pagamento grande) sem precisar trocar de sessão.

_SCRYPT_PARAMS = dict(n=2**14, r=8, p=1, dklen=32)

def _hash_secreto(valor: str, salt: str = None) -> tuple:
    if salt is None:
        salt = _os.urandom(16).hex()
    h = hashlib.scrypt(valor.encode(), salt=bytes.fromhex(salt), **_SCRYPT_PARAMS).hex()
    return salt, h

def _verificar_secreto(valor: str, salt: str, hash_armazenado: str) -> bool:
    candidato = hashlib.scrypt(valor.encode(), salt=bytes.fromhex(salt), **_SCRYPT_PARAMS).hex()
    return hmac.compare_digest(candidato, hash_armazenado)

def definir_pin(user_id: int, pin: str) -> dict:
    if not pin or not pin.isdigit() or not (4 <= len(pin) <= 6):
        return {"error": "PIN deve ter de 4 a 6 digitos numericos"}
    salt, h = _hash_secreto(pin)
    async def _go():
        db = await get_db()
        row = await db.fetchrow("UPDATE rbac_usuarios SET pin_hash=$1 WHERE id=$2 AND ativo=TRUE RETURNING id", f"{salt}:{h}", user_id)
        return dict(row) if row else None
    try:
        r = run_async(_go())
        return {"ok": True} if r else {"error": "Usuario nao encontrado ou inativo"}
    except Exception as e:
        return {"error": str(e)}

def gerar_codigo_barras_usuario(user_id: int) -> dict:
    """Gera um codigo novo (cracha fisico) para o usuario — o codigo em texto
    so' e' devolvido nesta chamada, para imprimir na hora; depois so' o hash fica salvo."""
    async def _existe():
        db = await get_db()
        return await db.fetchrow("SELECT id FROM rbac_usuarios WHERE id=$1 AND ativo=TRUE", user_id)
    try:
        if not run_async(_existe()):
            return {"error": "Usuario nao encontrado ou inativo"}
    except Exception as e:
        return {"error": str(e)}
    codigo = _os.urandom(8).hex().upper()
    salt, h = _hash_secreto(codigo)
    async def _go():
        db = await get_db()
        await db.execute("UPDATE rbac_usuarios SET codigo_barras_hash=$1 WHERE id=$2", f"{salt}:{h}", user_id)
    try:
        run_async(_go())
        return {"ok": True, "codigo_barras": codigo}
    except Exception as e:
        return {"error": str(e)}

_PIN_ERRO_GENERICO = "PIN invalido"
_PIN_MAX_TENTATIVAS = 5
_PIN_BLOQUEIO_MINUTOS = 15

def _pin_bloqueado(user_id: int) -> bool:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT bloqueado_ate FROM rbac_autorizacao_tentativas WHERE user_id=$1", user_id)
        return dict(row) if row else None
    try:
        row = run_async(_go())
    except Exception:
        return False
    if not row or not row.get("bloqueado_ate"):
        return False
    from datetime import datetime, timezone
    bloqueado_ate = row["bloqueado_ate"]
    if bloqueado_ate.tzinfo is None:
        bloqueado_ate = bloqueado_ate.replace(tzinfo=timezone.utc)
    return bloqueado_ate > datetime.now(timezone.utc)

def _registrar_tentativa_pin(user_id: int, sucesso: bool):
    async def _go():
        db = await get_db()
        if sucesso:
            await db.execute("DELETE FROM rbac_autorizacao_tentativas WHERE user_id=$1", user_id)
            return
        row = await db.fetchrow("SELECT tentativas FROM rbac_autorizacao_tentativas WHERE user_id=$1", user_id)
        tentativas = (row["tentativas"] if row else 0) + 1
        bloqueio_sql = f"NOW() + INTERVAL '{_PIN_BLOQUEIO_MINUTOS} minutes'" if tentativas >= _PIN_MAX_TENTATIVAS else "NULL"
        await db.execute(f"""
            INSERT INTO rbac_autorizacao_tentativas (user_id, tentativas, bloqueado_ate)
            VALUES ($1, $2, {bloqueio_sql})
            ON CONFLICT (user_id) DO UPDATE SET tentativas = $2, bloqueado_ate = {bloqueio_sql}
        """, user_id, tentativas)
    try: run_async(_go())
    except Exception as e: log(AGENT, f"Erro ao registrar tentativa de PIN: {e}")

def verificar_pin_usuario(user_id: int, pin: str, permissao_necessaria: str = "") -> dict:
    """Mensagem de erro sempre generica (nunca diferencia 'nao encontrado' de
    'PIN errado') para nao virar oraculo de enumeracao de usuario; bloqueia
    apos varias tentativas erradas seguidas para o mesmo user_id, ja que um
    PIN de 4-6 digitos e' forca-bruteavel sem esse limite."""
    if _pin_bloqueado(user_id):
        return {"error": "Muitas tentativas — tente novamente em alguns minutos"}
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM rbac_usuarios WHERE id=$1 AND ativo=TRUE", user_id)
        return dict(row) if row else None
    try:
        row = run_async(_go())
    except Exception as e:
        return {"error": str(e)}
    valido = False
    if row:
        stored = row.get("pin_hash") or ""
        parts = stored.split(":", 1)
        if len(parts) == 2:
            valido = _verificar_secreto(pin, parts[0], parts[1])
    _registrar_tentativa_pin(user_id, valido)
    if not valido:
        return {"error": _PIN_ERRO_GENERICO}
    if permissao_necessaria and permissao_necessaria not in get_permissoes_por_usuario(user_id):
        return {"error": _PIN_ERRO_GENERICO}
    return {"ok": True, "id": row["id"], "nome": row["nome"]}

def verificar_codigo_barras_usuario(codigo: str, permissao_necessaria: str = "") -> dict:
    if not codigo:
        return {"error": "codigo de barras obrigatorio"}
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM rbac_usuarios WHERE ativo=TRUE AND codigo_barras_hash IS NOT NULL")
        return [dict(r) for r in rows]
    try:
        candidatos = run_async(_go())
    except Exception as e:
        return {"error": str(e)}
    for row in candidatos:
        stored = row.get("codigo_barras_hash") or ""
        parts = stored.split(":", 1)
        if len(parts) != 2:
            continue
        salt, h = parts
        if _verificar_secreto(codigo, salt, h):
            if permissao_necessaria and permissao_necessaria not in get_permissoes_por_usuario(row["id"]):
                return {"error": "Codigo de barras nao autorizado para esta operacao"}
            return {"ok": True, "id": row["id"], "nome": row["nome"]}
    return {"error": "Codigo de barras nao reconhecido"}

def autorizar_com_permissao(permissao: str, usuario_pin_id: int = None, pin: str = "", codigo_barras: str = "") -> dict:
    """Autorizacao gerencial generica (fora do PDV): o codigo de barras
    identifica automaticamente quem tem a permissao pedida; o PIN exige que o
    usuario/gerente ja tenha sido selecionado na tela (mesma logica do PDV,
    aplicada aos usuarios do RBAC principal)."""
    if codigo_barras:
        return verificar_codigo_barras_usuario(codigo_barras, permissao)
    if usuario_pin_id and pin:
        return verificar_pin_usuario(usuario_pin_id, pin, permissao)
    return {"error": "Informe PIN ou codigo de barras"}

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

def list_roles_com_permissoes() -> list:
    """Igual list_roles(), mas com os codigos de permissao de cada papel
    embutidos — usado pela tela de Cargos para mostrar/editar o que cada
    papel pode fazer sem uma chamada extra por papel."""
    async def _go():
        db = await get_db()
        roles = await db.fetch("SELECT * FROM rbac_roles ORDER BY id")
        resultado = []
        for r in roles:
            perms = await db.fetch(
                "SELECT p.codigo FROM rbac_role_permissoes rp JOIN rbac_permissoes p ON p.id = rp.permissao_id WHERE rp.role_id = $1 ORDER BY p.codigo",
                r["id"])
            resultado.append({**dict(r), "permissoes": [p["codigo"] for p in perms]})
        return resultado
    try: return run_async(_go())
    except Exception as e: return []

# campos que nunca devem sair pela API — nao ha motivo legitimo para o
# frontend ler hash de senha/PIN/cracha de volta (mesmo padrao aplicado a
# cad_usuarios em core/cadastros.py).
_CAMPOS_SENSIVEIS_USUARIO = {"password_hash", "pin_hash", "codigo_barras_hash"}

def list_usuarios():
    return [{k: v for k, v in u.items() if k not in _CAMPOS_SENSIVEIS_USUARIO} for u in _list("rbac_usuarios")]

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


def _loja_id_da_request(kwargs) -> int:
    """Acha o loja_id da chamada atual, na ordem: path param da rota Flask
    (<int:loja_id>), query string (?loja_id= ou ?loja=), corpo JSON."""
    if kwargs.get("loja_id") is not None:
        return kwargs["loja_id"]
    v = request.args.get("loja_id", type=int)
    if v is not None:
        return v
    v = request.args.get("loja", type=int)
    if v is not None:
        return v
    if request.is_json:
        body = request.get_json(silent=True) or {}
        v = body.get("loja_id")
        if v is not None:
            try: return int(v)
            except (TypeError, ValueError): return None
    return None


def requer_acesso_loja(f):
    """Bloqueia com 403 quando a request pede uma loja fora das permitidas
    pro usuario (usuario_lojas — ver core/rbac_lojas.py). Sem loja_id
    identificavel na request, deixa passar (rota nao e' escopada por loja).
    Token master e usuarios com "lojas.ver_todas" sempre passam."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        loja_id = _loja_id_da_request(kwargs)
        if loja_id is None:
            return f(*args, **kwargs)
        usuario = usuario_atual_da_request()
        if usuario["is_master"] or not usuario["user_id"]:
            return f(*args, **kwargs)
        from core.rbac_lojas import lojas_permitidas
        permitidas = lojas_permitidas(usuario["user_id"])
        if permitidas is not None and int(loja_id) not in permitidas:
            return jsonify({"error": "Sem acesso a esta loja", "loja_id": loja_id}), 403
        return f(*args, **kwargs)
    return wrapper


if __name__ == "__main__":
    log(AGENT, "Auto-teste RBAC")
    print("Roles:", len(list_roles()))
    print("Permissoes:", len(list_permissoes()))
    print("Usuarios:", len(list_usuarios()))
