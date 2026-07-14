"""Financeiro Core — Fluxo Caixa, Receber, Pagar, Boletos, PIX, Conciliação, Banco, DRE"""
from core import get_db, run_async, log, hoje

AGENT = "Financeiro Core"

FIN_TABLES = ["fluxo_caixa", "contas_receber", "contas_pagar", "boletos", "pix", "conciliacao", "bancos", "centro_custo", "plano_contas", "dre"]

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_fluxo_caixa (
            id SERIAL PRIMARY KEY, data DATE NOT NULL, descricao VARCHAR(200),
            tipo VARCHAR(10) DEFAULT 'entrada', valor DECIMAL(12,2) DEFAULT 0,
            categoria VARCHAR(50), conta_id INT, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_contas_receber (
            id SERIAL PRIMARY KEY, cliente VARCHAR(200) NOT NULL, descricao VARCHAR(200),
            valor DECIMAL(12,2) DEFAULT 0, vencimento DATE, data_recebimento DATE,
            status VARCHAR(20) DEFAULT 'pendente', forma_pagamento VARCHAR(30),
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_contas_pagar (
            id SERIAL PRIMARY KEY, fornecedor VARCHAR(200) NOT NULL, descricao VARCHAR(200),
            valor DECIMAL(12,2) DEFAULT 0, vencimento DATE, data_pagamento DATE,
            status VARCHAR(20) DEFAULT 'pendente', forma_pagamento VARCHAR(30),
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_boletos (
            id SERIAL PRIMARY KEY, beneficiario VARCHAR(200), valor DECIMAL(12,2) DEFAULT 0,
            vencimento DATE, nosso_numero VARCHAR(30), codigo_barras VARCHAR(60),
            status VARCHAR(20) DEFAULT 'pendente', created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_pix (
            id SERIAL PRIMARY KEY, chave VARCHAR(100), tipo_chave VARCHAR(20),
            descricao VARCHAR(200), valor DECIMAL(12,2) DEFAULT 0,
            data_transacao TIMESTAMP DEFAULT NOW(), status VARCHAR(20) DEFAULT 'concluido',
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_conciliacao (
            id SERIAL PRIMARY KEY, banco_id INT, data DATE, descricao VARCHAR(200),
            valor_extrato DECIMAL(12,2) DEFAULT 0, valor_sistema DECIMAL(12,2) DEFAULT 0,
            status VARCHAR(20) DEFAULT 'pendente', created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_bancos (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL, agencia VARCHAR(10),
            conta VARCHAR(20), saldo DECIMAL(12,2) DEFAULT 0,
            status VARCHAR(20) DEFAULT 'ativa', created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_centro_custo (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL, codigo VARCHAR(20),
            descricao TEXT, status VARCHAR(20) DEFAULT 'ativo',
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_plano_contas (
            id SERIAL PRIMARY KEY, codigo VARCHAR(20) NOT NULL, nome VARCHAR(100) NOT NULL,
            tipo VARCHAR(20) DEFAULT 'analitica', natureza VARCHAR(10) DEFAULT 'credora',
            conta_pai_id INT, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_dre (
            id SERIAL PRIMARY KEY, mes VARCHAR(7) NOT NULL, descricao VARCHAR(100),
            valor DECIMAL(12,2) DEFAULT 0, tipo VARCHAR(10) DEFAULT 'receita',
            categoria VARCHAR(50), created_at TIMESTAMP DEFAULT NOW()
        )""")

        # Seed
        count = await db.fetchval("SELECT COUNT(*) FROM fin_fluxo_caixa")
        if count == 0:
            await db.execute("""INSERT INTO fin_fluxo_caixa (data, descricao, tipo, valor, categoria) VALUES
                (CURRENT_DATE - 3, 'Venda Loja Centro', 'entrada', 15000, 'Vendas'),
                (CURRENT_DATE - 2, 'Pagamento Fornecedor A', 'saida', 5000, 'Compras'),
                (CURRENT_DATE - 1, 'Recebimento Cliente B', 'entrada', 8000, 'Recebimentos'),
                (CURRENT_DATE, 'Aluguel', 'saida', 3500, 'Custos Fixos'),
                (CURRENT_DATE - 1, 'Venda Online', 'entrada', 12000, 'Vendas'),
                (CURRENT_DATE - 2, 'Salários', 'saida', 25000, 'Pessoal')""")
        count = await db.fetchval("SELECT COUNT(*) FROM fin_contas_receber")
        if count == 0:
            await db.execute("""INSERT INTO fin_contas_receber (cliente, descricao, valor, vencimento, status, forma_pagamento) VALUES
                ('Carlos Alberto', 'Pedido #1001', 3500, CURRENT_DATE + 15, 'pendente', 'boleto'),
                ('Distribuidora ABC', 'Pedido #1002', 12000, CURRENT_DATE + 7, 'pendente', 'pix'),
                ('Marina Santos', 'Pedido #1003', 1800, CURRENT_DATE - 3, 'pago', 'pix'),
                ('Comercial XYZ', 'Pedido #1004', 5500, CURRENT_DATE - 10, 'atrasado', 'boleto')""")
        count = await db.fetchval("SELECT COUNT(*) FROM fin_contas_pagar")
        if count == 0:
            await db.execute("""INSERT INTO fin_contas_pagar (fornecedor, descricao, valor, vencimento, status, forma_pagamento) VALUES
                ('Fornecedor Alpha', 'Matéria-prima', 8000, CURRENT_DATE + 5, 'pendente', 'boleto'),
                ('Beta Distribuidora', 'Embalagens', 3200, CURRENT_DATE + 10, 'pendente', 'pix'),
                ('Gamma Importação', 'Frete Marítimo', 15000, CURRENT_DATE - 2, 'pago', 'ted'),
                ('Fornecedor Alpha', 'Adiantamento', 5000, CURRENT_DATE - 15, 'atrasado', 'boleto')""")
        count = await db.fetchval("SELECT COUNT(*) FROM fin_boletos")
        if count == 0:
            await db.execute("""INSERT INTO fin_boletos (beneficiario, valor, vencimento, nosso_numero, codigo_barras, status) VALUES
                ('Fornecedor Alpha', 8000, CURRENT_DATE + 5, '001-00001', '34191.79001...', 'pendente'),
                ('Carlos Alberto', 3500, CURRENT_DATE + 15, '001-00002', '34191.79002...', 'pendente'),
                ('Comercial XYZ', 5500, CURRENT_DATE - 10, '001-00003', '34191.79003...', 'vencido'),
                ('Fornecedor Alpha', 5000, CURRENT_DATE - 15, '001-00004', '34191.79004...', 'pago')""")
        count = await db.fetchval("SELECT COUNT(*) FROM fin_pix")
        if count == 0:
            await db.execute("""INSERT INTO fin_pix (chave, tipo_chave, descricao, valor, status) VALUES
                ('athena@empresa.com', 'email', 'Recebimento Cliente Online', 250, 'concluido'),
                ('11912345678', 'celular', 'Pagamento Fornecedor', 1200, 'concluido'),
                ('000.000.000-00', 'cpf', 'Transferência Interna', 5000, 'concluido'),
                ('athenapix@empresa.com', 'aleatoria', 'Reembolso Despesas', 350, 'pendente')""")
        count = await db.fetchval("SELECT COUNT(*) FROM fin_conciliacao")
        if count == 0:
            await db.execute("""INSERT INTO fin_conciliacao (banco_id, data, descricao, valor_extrato, valor_sistema, status) VALUES
                (1, CURRENT_DATE - 1, 'Depósito Cliente', 3500, 3500, 'conciliado'),
                (1, CURRENT_DATE, 'Taxa Bancária', -25, 0, 'pendente'),
                (1, CURRENT_DATE, 'Transferência Recebida', 8000, 8000, 'conciliado')""")
        count = await db.fetchval("SELECT COUNT(*) FROM fin_bancos")
        if count == 0:
            await db.execute("INSERT INTO fin_bancos (nome, agencia, conta, saldo) VALUES ('Banco do Brasil', '0001', '12345-6', 85000),('Itaú', '0002', '67890-1', 42000),('Caixa', '0003', '54321-0', 15000)")
        count = await db.fetchval("SELECT COUNT(*) FROM fin_centro_custo")
        if count == 0:
            await db.execute("INSERT INTO fin_centro_custo (nome, codigo) VALUES ('Administrativo', 'CC-001'),('Comercial', 'CC-002'),('Operações', 'CC-003'),('TI', 'CC-004')")
        count = await db.fetchval("SELECT COUNT(*) FROM fin_plano_contas")
        if count == 0:
            await db.execute("""INSERT INTO fin_plano_contas (codigo, nome, tipo, natureza) VALUES
                ('1', 'ATIVO', 'sintetica', 'devedora'),('1.1', 'Ativo Circulante', 'sintetica', 'devedora'),('1.1.1', 'Caixa', 'analitica', 'devedora'),('1.1.2', 'Bancos', 'analitica', 'devedora'),
                ('2', 'PASSIVO', 'sintetica', 'credora'),('2.1', 'Passivo Circulante', 'sintetica', 'credora'),('2.1.1', 'Fornecedores', 'analitica', 'credora'),
                ('3', 'RECEITAS', 'sintetica', 'credora'),('3.1', 'Vendas', 'analitica', 'credora'),('4', 'DESPESAS', 'sintetica', 'devedora'),('4.1', 'Custos Fixos', 'analitica', 'devedora')""")
        count = await db.fetchval("SELECT COUNT(*) FROM fin_dre")
        if count == 0:
            mes = hoje()[:7]
            await db.execute(f"""INSERT INTO fin_dre (mes, descricao, valor, tipo, categoria) VALUES
                ('{mes}', 'Receita de Vendas', 150000, 'receita', 'Vendas'),
                ('{mes}', 'Receita de Serviços', 45000, 'receita', 'Serviços'),
                ('{mes}', 'CMV', -90000, 'despesa', 'Custos'),
                ('{mes}', 'Salários', -35000, 'despesa', 'Pessoal'),
                ('{mes}', 'Aluguel', -5000, 'despesa', 'Custos Fixos'),
                ('{mes}', 'Marketing', -8000, 'despesa', 'Marketing')""")
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao criar tabelas financeiro: {e}")

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

def list(tabela: str): return _list(f"fin_{tabela}")
def get(tabela: str, id: int): return _get(f"fin_{tabela}", id)
def create(tabela: str, data: dict): return _create(f"fin_{tabela}", data)
def update(tabela: str, id: int, data: dict): return _update(f"fin_{tabela}", id, data)
def delete(tabela: str, id: int): return _delete(f"fin_{tabela}", id)

# ── Queries especiais ──

def fluxo_caixa_resumo(dias=30) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            SELECT COALESCE(SUM(CASE WHEN tipo='entrada' THEN valor ELSE 0 END),0) as total_entradas,
                   COALESCE(SUM(CASE WHEN tipo='saida' THEN valor ELSE 0 END),0) as total_saidas
            FROM fin_fluxo_caixa WHERE data >= CURRENT_DATE - $1""", dias)
        rows = await db.fetch("SELECT data, SUM(CASE WHEN tipo='entrada' THEN valor ELSE 0 END) as entradas, SUM(CASE WHEN tipo='saida' THEN valor ELSE 0 END) as saidas FROM fin_fluxo_caixa WHERE data >= CURRENT_DATE - $1 GROUP BY data ORDER BY data", dias)
        return {"resumo": dict(row) if row else {}, "diario": [dict(r) for r in rows]}
    try: return run_async(_go())
    except Exception as e: return {"resumo": {}, "diario": []}

def dre_resumo(mes: str = None) -> dict:
    m = mes or f"{hoje()[:7]}"
    async def _go():
        db = await get_db()
        receitas = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fin_dre WHERE mes = $1 AND tipo = 'receita'", m)
        despesas = await db.fetchval("SELECT COALESCE(SUM(ABS(valor)),0) FROM fin_dre WHERE mes = $1 AND tipo = 'despesa'", m)
        items = await db.fetch("SELECT * FROM fin_dre WHERE mes = $1 ORDER BY tipo, id", m)
        resultado = float(receitas or 0) - float(despesas or 0)
        return {"receitas": float(receitas or 0), "despesas": float(despesas or 0), "resultado": resultado, "lucro": resultado > 0, "items": [dict(r) for r in items]}
    try: return run_async(_go())
    except Exception as e: return {"receitas": 0, "despesas": 0, "resultado": 0, "lucro": False, "items": []}
