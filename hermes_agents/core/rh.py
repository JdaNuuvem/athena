"""RH Core — Funcionários, Ponto, Férias, Escala, Folha, Benefícios"""
from core import get_db, run_async, log, hoje

AGENT = "RH Core"

RH_TABLES = ["funcionarios", "ponto", "ferias", "escala", "folha", "beneficios"]

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rh_funcionarios (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(200) NOT NULL,
                cargo VARCHAR(100),
                departamento VARCHAR(100),
                email VARCHAR(100),
                telefone VARCHAR(30),
                data_admissao DATE,
                status VARCHAR(20) DEFAULT 'ativo',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rh_ponto (
                id SERIAL PRIMARY KEY,
                funcionario_id INT REFERENCES rh_funcionarios(id),
                data DATE NOT NULL,
                entrada TIME,
                saida_almoco TIME,
                volta_almoco TIME,
                saida TIME,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rh_ferias (
                id SERIAL PRIMARY KEY,
                funcionario_id INT REFERENCES rh_funcionarios(id),
                periodo_aquisitivo VARCHAR(20),
                dias INT DEFAULT 30,
                inicio DATE NOT NULL,
                fim DATE NOT NULL,
                status VARCHAR(20) DEFAULT 'agendada',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rh_escala (
                id SERIAL PRIMARY KEY,
                funcionario_id INT REFERENCES rh_funcionarios(id),
                turno VARCHAR(50),
                horario VARCHAR(30),
                dias_semana TEXT[],
                inicio DATE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rh_folha (
                id SERIAL PRIMARY KEY,
                funcionario_id INT REFERENCES rh_funcionarios(id),
                mes VARCHAR(7) NOT NULL,
                salario DECIMAL(12,2) DEFAULT 0,
                beneficios DECIMAL(12,2) DEFAULT 0,
                descontos DECIMAL(12,2) DEFAULT 0,
                liquido DECIMAL(12,2) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'pendente',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rh_beneficios (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                tipo VARCHAR(50),
                valor_empresa DECIMAL(12,2) DEFAULT 0,
                valor_funcionario DECIMAL(12,2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rh_funcionario_beneficio (
                id SERIAL PRIMARY KEY,
                funcionario_id INT REFERENCES rh_funcionarios(id),
                beneficio_id INT REFERENCES rh_beneficios(id),
                ativo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Seed data if empty
        count = await db.fetchval("SELECT COUNT(*) FROM rh_funcionarios")
        if count == 0:
            await db.execute("""
                INSERT INTO rh_funcionarios (nome, cargo, departamento, email, telefone, data_admissao, status) VALUES
                ('Ana Silva', 'Gerente de RH', 'RH', 'ana@empresa.com', '(11) 91234-5678', '2020-03-15', 'ativo'),
                ('Carlos Oliveira', 'Analista Financeiro', 'Financeiro', 'carlos@empresa.com', '(11) 92345-6789', '2021-01-10', 'ferias'),
                ('Marina Souza', 'Desenvolvedora', 'TI', 'marina@empresa.com', '(11) 93456-7890', '2022-06-20', 'ativo'),
                ('Pedro Santos', 'Vendedor', 'Comercial', 'pedro@empresa.com', '(11) 94567-8901', '2023-02-05', 'afastado')
            """)
            # Ponto
            await db.execute("""
                INSERT INTO rh_ponto (funcionario_id, data, entrada, saida_almoco, volta_almoco, saida) VALUES
                (1, CURRENT_DATE, '08:00', '12:00', '13:00', '17:00'),
                (2, CURRENT_DATE, '08:15', '12:00', '13:00', '17:00'),
                (3, CURRENT_DATE, '07:55', '11:30', '12:30', '17:00')
            """)
            # Férias
            await db.execute("""
                INSERT INTO rh_ferias (funcionario_id, periodo_aquisitivo, dias, inicio, fim, status) VALUES
                (2, '2025-2026', 30, '2026-07-01', '2026-07-30', 'andamento'),
                (1, '2024-2025', 20, '2026-08-15', '2026-09-03', 'agendada'),
                (3, '2024-2025', 15, '2026-01-10', '2026-01-24', 'concluida')
            """)
            # Escala
            await db.execute("""
                INSERT INTO rh_escala (funcionario_id, turno, horario, dias_semana, inicio) VALUES
                (1, 'Administrativo', '08:00 - 17:00', ARRAY['Seg','Ter','Qua','Qui','Sex'], '2026-01-01'),
                (2, 'Administrativo', '08:00 - 17:00', ARRAY['Seg','Ter','Qua','Qui','Sex'], '2026-01-01'),
                (3, 'Flexível', '09:00 - 18:00', ARRAY['Seg','Ter','Qua','Qui','Sex'], '2026-03-01'),
                (4, 'Comercial', '10:00 - 19:00', ARRAY['Ter','Qua','Qui','Sex','Sáb'], '2026-02-05')
            """)
            # Folha
            await db.execute("""
                INSERT INTO rh_folha (funcionario_id, mes, salario, beneficios, descontos, liquido, status) VALUES
                (1, '2026-07', 8500, 1200, 2100, 7600, 'pago'),
                (2, '2026-07', 5200, 800, 1300, 4700, 'pago'),
                (3, '2026-07', 7200, 1000, 1800, 6400, 'pendente'),
                (4, '2026-07', 3200, 500, 800, 2900, 'pendente')
            """)
            # Benefícios
            await db.execute("""
                INSERT INTO rh_beneficios (nome, tipo, valor_empresa, valor_funcionario) VALUES
                ('Plano de Saúde', 'Saúde', 450, 150),
                ('Vale Refeição', 'Alimentação', 600, 0),
                ('Vale Transporte', 'Transporte', 0, 200),
                ('Seguro de Vida', 'Seguro', 120, 0),
                ('Gympass', 'Bem-estar', 80, 40)
            """)
            await db.execute("""
                INSERT INTO rh_funcionario_beneficio (funcionario_id, beneficio_id) VALUES
                (1,1),(1,2),(1,3),(1,4),(1,5),
                (2,1),(2,2),(2,4),
                (3,1),(3,2),(3,4),
                (4,1),(4,2),(3,4)
            """)
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao criar tabelas RH: {e}")

_ensure_tables()

# ── CRUD genérico ──

def _list(tabela: str, cols="*", order="id DESC", limit=100) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"SELECT {cols} FROM rh_{tabela} ORDER BY {order} LIMIT {limit}")
        return [dict(r) for r in rows]
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro list {tabela}: {e}")
        return []

def _get(tabela: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"SELECT * FROM rh_{tabela} WHERE id = $1", id)
        return dict(row) if row else {"error": "not found"}
    try:
        return run_async(_go())
    except Exception as e:
        return {"error": str(e)}

def _create(tabela: str, dados: dict) -> dict:
    keys = list(dados.keys())
    vals = list(dados.values())
    placeholders = ", ".join(f"${i+1}" for i in range(len(keys)))
    cols = ", ".join(keys)
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"INSERT INTO rh_{tabela} ({cols}) VALUES ({placeholders}) RETURNING *", *vals)
        return dict(row) if row else {"error": "insert failed"}
    try:
        return run_async(_go())
    except Exception as e:
        return {"error": str(e)}

def _update(tabela: str, id: int, dados: dict) -> dict:
    sets = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(dados.keys()))
    vals = list(dados.values()) + [id]
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"UPDATE rh_{tabela} SET {sets} WHERE id = ${len(vals)} RETURNING *", *vals)
        return dict(row) if row else {"error": "not found"}
    try:
        return run_async(_go())
    except Exception as e:
        return {"error": str(e)}

def _delete(tabela: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        await db.execute(f"DELETE FROM rh_{tabela} WHERE id = $1", id)
        return {"success": True}
    try:
        run_async(_go())
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}

# ── API helpers ──

def list(tabela: str): return _list(tabela)
def get(tabela: str, id: int): return _get(tabela, id)
def create(tabela: str, data: dict): return _create(tabela, data)
def update(tabela: str, id: int, data: dict): return _update(tabela, id, data)
def delete(tabela: str, id: int): return _delete(tabela, id)

# ── Queries especiais ──

def ponto_por_data(data_str: str) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT p.*, f.nome as funcionario,
                   (saida - entrada - (volta_almoco - saida_almoco)) as total
            FROM rh_ponto p
            JOIN rh_funcionarios f ON f.id = p.funcionario_id
            WHERE p.data = $1::date
            ORDER BY f.nome
        """, data_str)
        return [dict(r) for r in rows]
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ponto_por_data: {e}")
        return []

def folha_resumo(mes: str) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            SELECT COUNT(*) as total_funcionarios,
                   COALESCE(SUM(salario),0) as total_salarios,
                   COALESCE(SUM(beneficios),0) as total_beneficios,
                   COALESCE(SUM(descontos),0) as total_descontos,
                   COALESCE(SUM(liquido),0) as total_liquido
            FROM rh_folha WHERE mes = $1
        """, mes)
        return dict(row) if row else {}
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro folha_resumo: {e}")
        return {}

def beneficios_resumo() -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            SELECT COALESCE(SUM(valor_empresa),0) as total_empresa,
                   COALESCE(SUM(valor_funcionario),0) as total_funcionario
            FROM rh_beneficios
        """)
        beneficios = await db.fetch("""
            SELECT b.*, COUNT(fb.funcionario_id) as funcionarios_ativos
            FROM rh_beneficios b
            LEFT JOIN rh_funcionario_beneficio fb ON fb.beneficio_id = b.id AND fb.ativo = TRUE
            GROUP BY b.id ORDER BY b.id
        """)
        return {
            "total_empresa": float(row["total_empresa"]) if row else 0,
            "total_funcionario": float(row["total_funcionario"]) if row else 0,
            "beneficios": [dict(r) for r in beneficios],
        }
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro beneficios_resumo: {e}")
        return {"total_empresa": 0, "total_funcionario": 0, "beneficios": []}
