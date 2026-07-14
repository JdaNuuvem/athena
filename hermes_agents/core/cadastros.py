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

def _get(tabela: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"SELECT * FROM {tabela} WHERE id = $1", id)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def _create(tabela: str, dados: dict) -> dict:
    keys = list(dados.keys()); vals = list(dados.values())
    cols = ", ".join(keys); ph = ", ".join(f"${i+1}" for i in range(len(keys)))
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"INSERT INTO {tabela} ({cols}) VALUES ({ph}) RETURNING *", *vals)
        return dict(row) if row else {"error": "insert failed"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def _update(tabela: str, id: int, dados: dict) -> dict:
    sets = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(dados.keys()))
    vals = list(dados.values()) + [id]
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

def list(tabela: str): return _list(_resolve(tabela))
def get(tabela: str, id: int): return _get(_resolve(tabela), id)
def create(tabela: str, data: dict): return _create(_resolve(tabela), data)
def update(tabela: str, id: int, data: dict): return _update(_resolve(tabela), id, data)
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
