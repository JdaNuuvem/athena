"""Cadastros Core — Empresas, Usuários, Clientes, Fornecedores, Transportadoras, Vendedores"""
from core import get_db, run_async, log, hoje

AGENT = "Cadastros Core"

CAD_TABLES = ["empresas", "usuarios", "clientes", "fornecedores", "transportadoras", "vendedores"]

def _ensure_tables():
    async def _go():
        db = await get_db()

        # ── Empresas ──
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_empresas (
            id SERIAL PRIMARY KEY, razao_social VARCHAR(200) NOT NULL,
            cnpj VARCHAR(20), ie VARCHAR(20), im VARCHAR(20),
            regime_tributario VARCHAR(50), porte VARCHAR(20),
            tipo VARCHAR(20) DEFAULT 'matriz', empresa_mae_id INT,
            endereco TEXT, telefone VARCHAR(30), email VARCHAR(100),
            status VARCHAR(20) DEFAULT 'ativa', created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_multiempresa (
            id SERIAL PRIMARY KEY, empresa_id INT REFERENCES cad_empresas(id),
            tipo_vinculo VARCHAR(30), created_at TIMESTAMP DEFAULT NOW()
        )""")

        # ── Usuários ──
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_usuarios (
            id SERIAL PRIMARY KEY, nome VARCHAR(200) NOT NULL,
            email VARCHAR(100) UNIQUE, senha_hash VARCHAR(200),
            perfil VARCHAR(50) DEFAULT 'usuario', grupo_id INT,
            mfa_ativo BOOLEAN DEFAULT FALSE, status VARCHAR(20) DEFAULT 'ativo',
            created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_permissoes (
            id SERIAL PRIMARY KEY, perfil VARCHAR(50) NOT NULL,
            modulo VARCHAR(50) NOT NULL, acesso VARCHAR(10) DEFAULT 'leitura',
            UNIQUE(perfil, modulo)
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_grupos (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL,
            perfil_padrao VARCHAR(50), created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_historico_acessos (
            id SERIAL PRIMARY KEY, usuario_id INT REFERENCES cad_usuarios(id),
            acao VARCHAR(100), ip VARCHAR(45), created_at TIMESTAMP DEFAULT NOW()
        )""")

        # ── Clientes ──
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_clientes (
            id SERIAL PRIMARY KEY, nome VARCHAR(200) NOT NULL,
            tipo CHAR(2) DEFAULT 'PF', documento VARCHAR(20),
            ie VARCHAR(20), im VARCHAR(20),
            limite_credito DECIMAL(12,2) DEFAULT 0, score INT DEFAULT 0,
            status VARCHAR(20) DEFAULT 'ativo', created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        # ponytail: sincronizar_contatos_bling() (core/entidades.py) grava email/telefone
        # direto aqui e faz ON CONFLICT (documento) — colunas e indice nunca existiram,
        # causando "column email does not exist" em todo sync de contato do Bling.
        await db.execute("ALTER TABLE cad_clientes ADD COLUMN IF NOT EXISTS email VARCHAR(200)")
        await db.execute("ALTER TABLE cad_clientes ADD COLUMN IF NOT EXISTS telefone VARCHAR(30)")
        await db.execute("ALTER TABLE cad_clientes ADD COLUMN IF NOT EXISTS whatsapp BOOLEAN DEFAULT FALSE")
        await db.execute("ALTER TABLE cad_clientes ADD COLUMN IF NOT EXISTS data_nascimento DATE")
        await db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_cad_clientes_documento_unico
            ON cad_clientes (documento) WHERE documento IS NOT NULL AND documento != ''""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_cliente_enderecos (
            id SERIAL PRIMARY KEY, cliente_id INT REFERENCES cad_clientes(id),
            logradouro VARCHAR(200), numero VARCHAR(10), complemento VARCHAR(100),
            bairro VARCHAR(100), cidade VARCHAR(100), uf CHAR(2), cep VARCHAR(10),
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_cliente_contatos (
            id SERIAL PRIMARY KEY, cliente_id INT REFERENCES cad_clientes(id),
            tipo VARCHAR(20), valor VARCHAR(100), whatsapp BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_cliente_historico (
            id SERIAL PRIMARY KEY, cliente_id INT REFERENCES cad_clientes(id),
            descricao TEXT, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_cliente_tags (
            id SERIAL PRIMARY KEY, cliente_id INT REFERENCES cad_clientes(id),
            tag VARCHAR(50), created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_cad_cliente_tags_cliente_id ON cad_cliente_tags (cliente_id)")

        # ── Fornecedores ──
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_fornecedores (
            id SERIAL PRIMARY KEY, nome VARCHAR(200) NOT NULL,
            tipo CHAR(2) DEFAULT 'PJ', documento VARCHAR(20),
            ie VARCHAR(20), im VARCHAR(20),
            limite_credito DECIMAL(12,2) DEFAULT 0, score INT DEFAULT 0,
            status VARCHAR(20) DEFAULT 'ativo', created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_fornecedor_enderecos (
            id SERIAL PRIMARY KEY, fornecedor_id INT REFERENCES cad_fornecedores(id),
            logradouro VARCHAR(200), numero VARCHAR(10), complemento VARCHAR(100),
            bairro VARCHAR(100), cidade VARCHAR(100), uf CHAR(2), cep VARCHAR(10),
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_fornecedor_contatos (
            id SERIAL PRIMARY KEY, fornecedor_id INT REFERENCES cad_fornecedores(id),
            tipo VARCHAR(20), valor VARCHAR(100), whatsapp BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_fornecedor_historico (
            id SERIAL PRIMARY KEY, fornecedor_id INT REFERENCES cad_fornecedores(id),
            descricao TEXT, valor_total DECIMAL(12,2), created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_fornecedor_tags (
            id SERIAL PRIMARY KEY, fornecedor_id INT REFERENCES cad_fornecedores(id),
            tag VARCHAR(50), created_at TIMESTAMP DEFAULT NOW()
        )""")

        # ── Transportadoras ──
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_transportadoras (
            id SERIAL PRIMARY KEY, nome VARCHAR(200) NOT NULL,
            cnpj VARCHAR(20), frota VARCHAR(50), regiao VARCHAR(100),
            status VARCHAR(20) DEFAULT 'ativa', created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_transp_frete (
            id SERIAL PRIMARY KEY, transportadora_id INT REFERENCES cad_transportadoras(id),
            origem VARCHAR(100), destino VARCHAR(100),
            valor DECIMAL(10,2), prazo VARCHAR(20),
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_transp_contatos (
            id SERIAL PRIMARY KEY, transportadora_id INT REFERENCES cad_transportadoras(id),
            nome VARCHAR(100), telefone VARCHAR(30), email VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW()
        )""")

        # ── Vendedores ──
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_vendedores (
            id SERIAL PRIMARY KEY, nome VARCHAR(200) NOT NULL,
            email VARCHAR(100), regiao VARCHAR(100),
            comissao_pct DECIMAL(4,2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_vendedor_metas (
            id SERIAL PRIMARY KEY, vendedor_id INT REFERENCES cad_vendedores(id),
            mes VARCHAR(7), meta_valor DECIMAL(12,2) DEFAULT 0,
            realizado DECIMAL(12,2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )""")

        # ── Seed ──
        count = await db.fetchval("SELECT COUNT(*) FROM cad_empresas")
        if count == 0:
            await db.execute("INSERT INTO cad_empresas (razao_social, cnpj, ie, im, regime_tributario, porte, tipo) VALUES ('Athena Tecnologia Ltda', '00.000.000/0001-00', '000.000.000.000', '00000000', 'Lucro Presumido', 'Médio', 'matriz')")
            await db.execute("INSERT INTO cad_empresas (razao_social, cnpj, tipo) VALUES ('Filial SP', '00.000.000/0002-00', 'filial'),('Filial RJ', '00.000.000/0003-00', 'filial')")
            await db.execute("INSERT INTO cad_multiempresa (empresa_id, tipo_vinculo) VALUES (1, 'Matriz'),(2, 'Filial SP')")

        count = await db.fetchval("SELECT COUNT(*) FROM cad_usuarios")
        if count == 0:
            await db.execute("INSERT INTO cad_usuarios (nome, email, perfil, mfa_ativo, status) VALUES ('Admin', 'admin@athena.com', 'Administrador', TRUE, 'ativo'),('Maria Gestora', 'maria@athena.com', 'Gestor', FALSE, 'ativo'),('João Vendas', 'joao@athena.com', 'Vendedor', TRUE, 'ativo'),('Ana RH', 'ana@athena.com', 'RH', FALSE, 'inativo')")
            await db.execute("INSERT INTO cad_permissoes (perfil, modulo, acesso) VALUES ('Administrador','RH','total'),('Administrador','Financeiro','total'),('Administrador','Vendas','total'),('Administrador','Estoque','total'),('Administrador','Fiscal','total'),('Gestor','RH','leitura'),('Gestor','Financeiro','total'),('Gestor','Vendas','total'),('Vendedor','Vendas','total'),('Vendedor','Estoque','leitura')")
            await db.execute("INSERT INTO cad_grupos (nome, perfil_padrao) VALUES ('Administradores','Administrador'),('Comercial','Vendedor'),('Operações','Gestor')")
            await db.execute("INSERT INTO cad_historico_acessos (usuario_id, acao, ip) VALUES (1,'Login','192.168.1.1'),(2,'Logout','192.168.1.2'),(1,'Alterou permissões','192.168.1.1')")

        count = await db.fetchval("SELECT COUNT(*) FROM cad_clientes")
        if count == 0:
            await db.execute("""INSERT INTO cad_clientes (nome, tipo, documento, limite_credito, score) VALUES
                ('Carlos Alberto', 'PF', '123.456.789-00', 5000, 720),
                ('Distribuidora ABC Ltda', 'PJ', '00.000.000/0001-99', 15000, 850),
                ('Marina Santos', 'PF', '987.654.321-00', 3000, 680),
                ('Comercial XYZ S.A.', 'PJ', '11.111.111/0001-11', 0, 450)""")
            await db.execute("INSERT INTO cad_cliente_tags (cliente_id, tag) VALUES (1,'VIP'),(1,'Recorrente'),(2,'Atacado'),(2,'Premium')")

        count = await db.fetchval("SELECT COUNT(*) FROM cad_fornecedores")
        if count == 0:
            await db.execute("""INSERT INTO cad_fornecedores (nome, tipo, documento, limite_credito, score) VALUES
                ('Fornecedor Alpha Ltda', 'PJ', '00.000.000/0001-AA', 50000, 800),
                ('Beta Distribuidora', 'PJ', '11.111.111/0001-BB', 25000, 750),
                ('Gamma Importação', 'PJ', '22.222.222/0001-CC', 0, 500)""")

        count = await db.fetchval("SELECT COUNT(*) FROM cad_transportadoras")
        if count == 0:
            await db.execute("INSERT INTO cad_transportadoras (nome, cnpj, frota, regiao) VALUES ('Transportadora Rápida', '00.000.000/0001-TR', '12 veículos', 'Sudeste'),('Loggi Express', '11.111.111/0001-LG', '8 veículos', 'Nacional')")
            await db.execute("INSERT INTO cad_transp_frete (transportadora_id, origem, destino, valor, prazo) VALUES (1,'São Paulo','Campinas',150,'1 dia'),(1,'São Paulo','Rio de Janeiro',350,'2 dias'),(2,'São Paulo','Campinas',120,'1 dia'),(2,'São Paulo','Rio de Janeiro',300,'2 dias')")
            await db.execute("INSERT INTO cad_transp_contatos (transportadora_id, nome, telefone, email) VALUES (1,'Gestor de Frota','(11) 3000-0000','frota@transportadorarapida.com'),(2,'Gestor de Frota','(11) 3000-0000','frota@loggiexpress.com')")

        count = await db.fetchval("SELECT COUNT(*) FROM cad_vendedores")
        if count == 0:
            await db.execute("""INSERT INTO cad_vendedores (nome, email, regiao, comissao_pct) VALUES
                ('João Vendas', 'joao@athena.com', 'São Paulo', 5.5),
                ('Roberta Comercial', 'roberta@athena.com', 'Campinas', 4.0),
                ('Felipe Atacado', 'felipe@athena.com', 'Rio de Janeiro', 3.5)""")
            await db.execute("""INSERT INTO cad_vendedor_metas (vendedor_id, mes, meta_valor, realizado) VALUES
                (1, '2026-07', 100000, 85000),
                (2, '2026-07', 80000, 62000),
                (3, '2026-07', 60000, 45000)""")
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao criar tabelas cadastros: {e}")

_ensure_tables()

# ── CRUD genérico ──

def _list(tabela: str, cols="*", order="id DESC", limit=100) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"SELECT {cols} FROM {tabela} ORDER BY {order} LIMIT {limit}")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"Erro list {tabela}: {e}"); return []

# campos-alvo de busca por tabela logica (nao a tabela SQL resolvida) — nomes
# fixos no codigo, nunca vindos do request, entao seguro interpolar na query;
# so' o termo buscado ($1) e' parametrizado.
_CAMPOS_BUSCA = {
    "clientes": ["nome", "documento", "email", "telefone"],
    "fornecedores": ["nome", "documento"],
    "empresas": ["razao_social", "cnpj"],
    "usuarios": ["nome", "email"],
    "transportadoras": ["nome", "cnpj"],
    "vendedores": ["nome", "email"],
}

def _count(tabela_sql: str, campos_busca=None, busca: str = None) -> int:
    async def _go():
        db = await get_db()
        if busca and campos_busca:
            where = " OR ".join(f"{c} ILIKE $1" for c in campos_busca)
            return await db.fetchval(f"SELECT COUNT(*) FROM {tabela_sql} WHERE {where}", f"%{busca}%")
        return await db.fetchval(f"SELECT COUNT(*) FROM {tabela_sql}")
    try: return run_async(_go()) or 0
    except Exception as e: log(AGENT, f"Erro count {tabela_sql}: {e}"); return 0

def _list_pagina(tabela_sql: str, order="id DESC", limit=50, offset=0, campos_busca=None, busca: str = None) -> list:
    async def _go():
        db = await get_db()
        if busca and campos_busca:
            where = " OR ".join(f"{c} ILIKE $1" for c in campos_busca)
            rows = await db.fetch(
                f"SELECT * FROM {tabela_sql} WHERE {where} ORDER BY {order} LIMIT {limit} OFFSET {offset}",
                f"%{busca}%")
        else:
            rows = await db.fetch(f"SELECT * FROM {tabela_sql} ORDER BY {order} LIMIT {limit} OFFSET {offset}")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"Erro list_pagina {tabela_sql}: {e}"); return []

def _get(tabela: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"SELECT * FROM {tabela} WHERE id = $1", id)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def _create(tabela: str, dados: dict) -> dict:
    # ponytail: NAO usar list(...) — este modulo define list(t) no nivel de
    # modulo, que sombreia o builtin para qualquer funcao neste arquivo.
    keys = [*dados.keys()]; vals = [*dados.values()]
    cols = ", ".join(keys); ph = ", ".join(f"${i+1}" for i in range(len(keys)))
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"INSERT INTO {tabela} ({cols}) VALUES ({ph}) RETURNING *", *vals)
        return dict(row) if row else {"error": "insert failed"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def _update(tabela: str, id: int, dados: dict) -> dict:
    sets = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(dados.keys()))
    vals = [*dados.values(), id]
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"UPDATE {tabela} SET {sets} WHERE id = ${len(vals)} RETURNING *", *vals)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def _delete(tabela: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        await db.execute(f"DELETE FROM {tabela} WHERE id = $1", id)
        return {"success": True}
    try: run_async(_go()); return {"success": True}
    except Exception as e: return {"error": str(e)}

# ── API helpers ──

TABLES_MAP = {
    "empresas": "cad_empresas",
    "usuarios": "cad_usuarios",
    "clientes": "cad_clientes",
    "fornecedores": "cad_fornecedores",
    "transportadoras": "cad_transportadoras",
    "vendedores": "cad_vendedores",
}

EXTRA_TABLES = [
    "permissoes", "grupos", "historico_acessos",
    "cliente_enderecos", "cliente_contatos", "cliente_historico", "cliente_tags",
    "fornecedor_enderecos", "fornecedor_contatos", "fornecedor_historico", "fornecedor_tags",
    "transp_frete", "transp_contatos",
    "vendedor_metas", "multiempresa",
]

EXTRA_MAP = {
    "permissoes": "cad_permissoes",
    "grupos": "cad_grupos",
    "historico_acessos": "cad_historico_acessos",
    "cliente_enderecos": "cad_cliente_enderecos",
    "cliente_contatos": "cad_cliente_contatos",
    "cliente_historico": "cad_cliente_historico",
    "cliente_tags": "cad_cliente_tags",
    "fornecedor_enderecos": "cad_fornecedor_enderecos",
    "fornecedor_contatos": "cad_fornecedor_contatos",
    "fornecedor_historico": "cad_fornecedor_historico",
    "fornecedor_tags": "cad_fornecedor_tags",
    "transp_frete": "cad_transp_frete",
    "transp_contatos": "cad_transp_contatos",
    "vendedor_metas": "cad_vendedor_metas",
    "multiempresa": "cad_multiempresa",
}

ALL_TABLES = list(TABLES_MAP.keys()) + EXTRA_TABLES

def _resolve(tabela: str) -> str:
    return TABLES_MAP.get(tabela) or EXTRA_MAP.get(tabela) or f"cad_{tabela}"

# campos que nunca devem sair pela API generica, mesmo para quem tem
# permissao de leitura na tabela — nao ha motivo legitimo para o frontend
# ler hash de senha de volta.
_CAMPOS_SENSIVEIS = {"usuarios": {"senha_hash"}}

def _sem_campos_sensiveis(tabela: str, registro):
    campos = _CAMPOS_SENSIVEIS.get(tabela)
    if not campos or not isinstance(registro, dict):
        return registro
    return {k: v for k, v in registro.items() if k not in campos}

def list(tabela: str): return [_sem_campos_sensiveis(tabela, r) for r in _list(_resolve(tabela))]

def list_paginado(tabela: str, pagina: int = 1, por_pagina: int = 50, busca: str = None) -> dict:
    pagina = max(1, pagina or 1)
    por_pagina = max(1, min(por_pagina or 50, 200))
    tabela_sql = _resolve(tabela)
    campos_busca = _CAMPOS_BUSCA.get(tabela)
    busca = (busca or "").strip() or None
    offset = (pagina - 1) * por_pagina
    dados = _list_pagina(tabela_sql, limit=por_pagina, offset=offset, campos_busca=campos_busca, busca=busca)
    total = _count(tabela_sql, campos_busca=campos_busca, busca=busca)
    total_paginas = max(1, -(-total // por_pagina)) if total else 1
    return {
        "data": [_sem_campos_sensiveis(tabela, r) for r in dados],
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": total_paginas,
    }

# ── Contatos: listagem filtrada com dados de remarketing ──
# Fica ao lado de list_paginado/_list_pagina/_count, sem alterá-las — as
# outras 5 tabelas de Cadastros continuam chamando list_paginado como hoje.

CLIENTES_SORT_MAP = {
    "id": "c.id",
    "nome": "c.nome",
    "ultima_compra": "compras.ultima_compra",
    "total_gasto": "compras.total_gasto",
}

_COMPRAS_LATERAL = """LEFT JOIN LATERAL (
        SELECT MAX(vp.data) AS ultima_compra, COALESCE(SUM(vp.total), 0) AS total_gasto, COUNT(*) AS qtd_pedidos
        FROM vendas_pedidos vp
        WHERE vp.cliente_id = c.id AND vp.status != 'cancelado'
    ) compras ON TRUE"""

_TAGS_LATERAL = """LEFT JOIN LATERAL (
        SELECT array_agg(t.tag ORDER BY t.tag) AS tags
        FROM cad_cliente_tags t
        WHERE t.cliente_id = c.id
    ) tags_agg ON TRUE"""

def listar_clientes_filtrado(pagina: int = 1, por_pagina: int = 50, busca: str = None,
                              sort: str = "id", order: str = "desc", status: str = None,
                              tag: str = None, whatsapp: bool = None, sem_comprar_dias: int = None) -> dict:
    pagina = max(1, pagina or 1)
    por_pagina = max(1, min(por_pagina or 50, 200))
    offset = (pagina - 1) * por_pagina
    sort_col = CLIENTES_SORT_MAP.get(sort, CLIENTES_SORT_MAP["id"])
    order_sql = "ASC" if str(order).lower() == "asc" else "DESC"
    busca = (busca or "").strip() or None

    where = []
    params = []

    def _param(v):
        params.append(v)
        return f"${len(params)}"

    if busca:
        p = _param(f"%{busca}%")
        where.append(f"(c.nome ILIKE {p} OR c.documento ILIKE {p} OR c.email ILIKE {p} OR c.telefone ILIKE {p})")
    if status:
        where.append(f"c.status = {_param(status)}")
    if whatsapp is not None:
        where.append(f"c.whatsapp = {_param(whatsapp)}")
    if tag:
        where.append(f"EXISTS (SELECT 1 FROM cad_cliente_tags t2 WHERE t2.cliente_id = c.id AND t2.tag = {_param(tag)})")
    if sem_comprar_dias is not None:
        where.append(f"(compras.ultima_compra IS NULL OR compras.ultima_compra < CURRENT_DATE - {_param(int(sem_comprar_dias))}::int)")

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    async def _go():
        db = await get_db()
        total_result = await db.fetchval(
            f"SELECT COUNT(*) FROM cad_clientes c {_COMPRAS_LATERAL} {where_sql}",
            *params)
        rows = await db.fetch(
            f"""SELECT c.*, compras.ultima_compra, compras.total_gasto, compras.qtd_pedidos,
                       COALESCE(tags_agg.tags, ARRAY[]::varchar[]) AS tags
                FROM cad_clientes c
                {_COMPRAS_LATERAL}
                {_TAGS_LATERAL}
                {where_sql}
                ORDER BY {sort_col} {order_sql} NULLS LAST
                LIMIT {por_pagina} OFFSET {offset}""",
            *params)
        return [dict(r) for r in rows], (total_result or 0)
    try:
        dados, total = run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro listar_clientes_filtrado: {e}")
        dados, total = [], 0
    total_paginas = max(1, -(-total // por_pagina)) if total else 1
    return {
        "data": [_sem_campos_sensiveis("clientes", r) for r in dados],
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": total_paginas,
    }

def tags_disponiveis() -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT DISTINCT tag FROM cad_cliente_tags WHERE tag IS NOT NULL ORDER BY tag")
        return [r["tag"] for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"Erro tags_disponiveis: {e}"); return []

def get(tabela: str, id: int): return _sem_campos_sensiveis(tabela, _get(_resolve(tabela), id))
def create(tabela: str, data: dict): return _sem_campos_sensiveis(tabela, _create(_resolve(tabela), data))
def update(tabela: str, id: int, data: dict): return _sem_campos_sensiveis(tabela, _update(_resolve(tabela), id, data))
def delete(tabela: str, id: int): return _delete(_resolve(tabela), id)

# ── Queries especiais ──

def permissoes_por_perfil() -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT perfil, modulo, acesso FROM cad_permissoes ORDER BY perfil, modulo")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def vendedor_comissao_resumo() -> dict:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT v.*, COALESCE(m.realizado,0) as total_vendas, m.meta_valor FROM cad_vendedores v LEFT JOIN cad_vendedor_metas m ON m.vendedor_id = v.id AND m.mes = to_char(CURRENT_DATE, 'YYYY-MM') ORDER BY v.id")
        total_comissoes = sum(float(r["total_vendas"] or 0) * float(r["comissao_pct"] or 0) / 100 for r in rows)
        return {"vendedores": [dict(r) for r in rows], "total_comissoes": total_comissoes}
    try: return run_async(_go())
    except Exception as e: return {"vendedores": [], "total_comissoes": 0}

def vendedor_metas(mes: str = None) -> list:
    m = mes or f"{hoje()[:7]}"
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT m.*, v.nome FROM cad_vendedor_metas m JOIN cad_vendedores v ON v.id = m.vendedor_id WHERE m.mes = $1 ORDER BY v.nome", m)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def fornecedor_resumo() -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT f.*, COALESCE(SUM(fh.valor_total),0) as total_compras FROM cad_fornecedores f LEFT JOIN cad_fornecedor_historico fh ON fh.fornecedor_id = f.id GROUP BY f.id ORDER BY f.nome")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []
