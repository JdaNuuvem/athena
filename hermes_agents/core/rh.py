"""RH Core — Funcionários, Ponto, Férias, Escala, Folha, Benefícios"""
from core import get_db, run_async, log, hoje

AGENT = "RH Core"

RH_TABLES = ["funcionarios", "ponto", "ferias", "escala", "folha", "beneficios", "avaliacoes", "avaliacao_competencias", "treinamentos", "treinamento_participantes"]

# ponytail: whitelist de colunas por tabela — _create/_update concatenam as
# CHAVES do dict recebido direto na string SQL (so' os valores sao
# parametrizados com $1, $2...). Sem essa whitelist, um cliente com permissao
# rh.criar/rh.editar poderia injetar SQL arbitrario via nome de campo no
# JSON (mesma classe de bug ja corrigida em core/crm.py, core/financeiro.py,
# core/compras.py e core/cadastros.py nesta sessao).
RH_COLUNAS = {
    "funcionarios": {"nome", "cargo", "departamento", "email", "telefone", "data_admissao", "status"},
    "ponto": {"funcionario_id", "data", "entrada", "saida_almoco", "volta_almoco", "saida"},
    "ferias": {"funcionario_id", "periodo_aquisitivo", "dias", "inicio", "fim", "status"},
    "escala": {"funcionario_id", "turno", "horario", "dias_semana", "inicio"},
    "folha": {"funcionario_id", "mes", "salario", "beneficios", "descontos", "liquido", "status"},
    "beneficios": {"nome", "tipo", "valor_empresa", "valor_funcionario"},
    "avaliacoes": {"funcionario_id", "avaliador_nome", "periodo", "tipo", "nota_geral",
                    "pontos_fortes", "pontos_melhoria", "plano_acao", "status", "data_avaliacao"},
    "avaliacao_competencias": {"avaliacao_id", "competencia", "nota", "comentario"},
    "treinamentos": {"nome", "descricao", "categoria", "carga_horaria", "instrutor",
                      "data_inicio", "data_fim", "status"},
    "treinamento_participantes": {"treinamento_id", "funcionario_id", "presenca",
                                   "nota_avaliacao", "certificado_emitido"},
}

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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rh_avaliacoes (
                id SERIAL PRIMARY KEY,
                funcionario_id INT NOT NULL REFERENCES rh_funcionarios(id),
                avaliador_nome VARCHAR(200),
                periodo VARCHAR(20) NOT NULL,
                tipo VARCHAR(20) DEFAULT 'desempenho',
                nota_geral DECIMAL(3,1),
                pontos_fortes TEXT, pontos_melhoria TEXT, plano_acao TEXT,
                status VARCHAR(20) DEFAULT 'pendente',
                data_avaliacao DATE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rh_avaliacao_competencias (
                id SERIAL PRIMARY KEY,
                avaliacao_id INT NOT NULL REFERENCES rh_avaliacoes(id),
                competencia VARCHAR(100) NOT NULL,
                nota DECIMAL(3,1), comentario TEXT
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_rh_avaliacao_competencias_avaliacao_id ON rh_avaliacao_competencias (avaliacao_id)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rh_treinamentos (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(200) NOT NULL, descricao TEXT,
                categoria VARCHAR(50), carga_horaria INT DEFAULT 0, instrutor VARCHAR(200),
                data_inicio DATE, data_fim DATE,
                status VARCHAR(20) DEFAULT 'planejado',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rh_treinamento_participantes (
                id SERIAL PRIMARY KEY,
                treinamento_id INT NOT NULL REFERENCES rh_treinamentos(id),
                funcionario_id INT NOT NULL REFERENCES rh_funcionarios(id),
                presenca VARCHAR(20) DEFAULT 'pendente',
                nota_avaliacao DECIMAL(3,1), certificado_emitido BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_rh_treinamento_participantes_treinamento_id ON rh_treinamento_participantes (treinamento_id)")
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
                (4,1),(4,2),(4,3)
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

# campos-alvo de busca por tabela — usado pelo FkPicker (ex.: funcionario_id
# em ponto/ferias/folha/avaliacoes/treinamento_participantes) pra buscar por
# nome em vez de exigir o id de cor.
_CAMPOS_BUSCA = {
    "funcionarios": ["nome", "cargo", "departamento"],
    "treinamentos": ["nome", "categoria", "instrutor"],
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

def list_paginado(tabela: str, pagina: int = 1, por_pagina: int = 50, busca: str = None) -> dict:
    pagina = max(1, pagina or 1)
    por_pagina = max(1, min(por_pagina or 50, 200))
    tabela_sql = f"rh_{tabela}"
    campos_busca = _CAMPOS_BUSCA.get(tabela)
    busca = (busca or "").strip() or None
    offset = (pagina - 1) * por_pagina
    dados = _list_pagina(tabela_sql, limit=por_pagina, offset=offset, campos_busca=campos_busca, busca=busca)
    total = _count(tabela_sql, campos_busca=campos_busca, busca=busca)
    total_paginas = max(1, -(-total // por_pagina)) if total else 1
    return {"data": dados, "total": total, "pagina": pagina, "por_pagina": por_pagina, "total_paginas": total_paginas}

def _create(tabela: str, dados: dict) -> dict:
    # ponytail: NAO usar list(...) — este modulo define list(t) no nivel de
    # modulo, que sombreia o builtin para qualquer funcao neste arquivo.
    keys = [*dados.keys()]
    vals = [*dados.values()]
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
    vals = [*dados.values(), id]
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

def create(tabela: str, data: dict) -> dict:
    colunas_validas = RH_COLUNAS.get(tabela)
    if colunas_validas is None:
        return {"error": "Tabela invalida"}
    filtrado = {k: v for k, v in data.items() if k in colunas_validas}
    if not filtrado:
        return {"error": "Nenhum campo valido informado"}
    return _create(tabela, filtrado)

def update(tabela: str, id: int, data: dict) -> dict:
    colunas_validas = RH_COLUNAS.get(tabela)
    if colunas_validas is None:
        return {"error": "Tabela invalida"}
    filtrado = {k: v for k, v in data.items() if k in colunas_validas}
    if not filtrado:
        return {"error": "Nenhum campo valido informado"}
    return _update(tabela, id, filtrado)

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

# ── Dashboard ──

def dashboard() -> dict:
    async def _go():
        db = await get_db()
        total_func = await db.fetchval("SELECT COUNT(*) FROM rh_funcionarios")
        ativos = await db.fetchval("SELECT COUNT(*) FROM rh_funcionarios WHERE status = 'ativo'")
        ferias = await db.fetchval("SELECT COUNT(*) FROM rh_funcionarios WHERE status = 'ferias'")
        afastados = await db.fetchval("SELECT COUNT(*) FROM rh_funcionarios WHERE status = 'afastado'")
        folha_mes = await db.fetchval("SELECT COALESCE(SUM(liquido),0) FROM rh_folha WHERE mes = TO_CHAR(CURRENT_DATE, 'YYYY-MM')")
        ponto_hoje = await db.fetchval("SELECT COUNT(*) FROM rh_ponto WHERE data = CURRENT_DATE")
        ferias_proximas = await db.fetch("SELECT f.nome, r.inicio, r.fim FROM rh_ferias r JOIN rh_funcionarios f ON f.id = r.funcionario_id WHERE r.inicio >= CURRENT_DATE ORDER BY r.inicio LIMIT 5")
        return {
            "total_funcionarios": total_func or 0, "ativos": ativos or 0,
            "ferias": ferias or 0, "afastados": afastados or 0,
            "folha_mes": float(folha_mes or 0), "ponto_hoje": ponto_hoje or 0,
            "ferias_proximas": [dict(r) for r in (ferias_proximas or [])],
        }
    try: return run_async(_go())
    except Exception as e: return {"total_funcionarios":0,"ativos":0,"ferias":0,"afastados":0,"folha_mes":0,"ponto_hoje":0,"ferias_proximas":[]}

# ── Listagem com filtro ──

def listar_filtrado(tabela: str, data_inicio: str = "", data_fim: str = "", status: str = "") -> dict:
    date_fields = {"ferias": "inicio", "folha": "mes", "ponto": "data"}
    field = date_fields.get(tabela, "created_at")
    async def _go():
        db = await get_db()
        where = []
        params = []
        p = 1
        if data_inicio and field != "mes":
            where.append(f"{field} >= ${p}::date"); params.append(data_inicio); p += 1
        if data_fim and field != "mes":
            where.append(f"{field} <= ${p}::date"); params.append(data_fim); p += 1
        if data_inicio and field == "mes":
            where.append(f"{field} >= ${p}"); params.append(data_inicio); p += 1
        if data_fim and field == "mes":
            where.append(f"{field} <= ${p}"); params.append(data_fim); p += 1
        if status:
            where.append(f"status = ${p}"); params.append(status); p += 1
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        rows = await db.fetch(f"SELECT * FROM rh_{tabela} {clause} ORDER BY id DESC LIMIT 500", *params)
        return {"data": [dict(r) for r in rows]}
    try: return run_async(_go())
    except Exception as e: return {"data": []}

# ── Funcionário completo ──

def funcionario_detalhe(id: int) -> dict:
    async def _go():
        db = await get_db()
        func = await db.fetchrow("SELECT * FROM rh_funcionarios WHERE id = $1", id)
        if not func: return {"error": "not found"}
        ponto = await db.fetch("SELECT * FROM rh_ponto WHERE funcionario_id = $1 ORDER BY data DESC LIMIT 30", id)
        ferias = await db.fetch("SELECT * FROM rh_ferias WHERE funcionario_id = $1 ORDER BY inicio DESC", id)
        folha = await db.fetch("SELECT * FROM rh_folha WHERE funcionario_id = $1 ORDER BY mes DESC LIMIT 12", id)
        beneficios = await db.fetch("""SELECT b.*, fb.ativo FROM rh_beneficios b
            JOIN rh_funcionario_beneficio fb ON fb.beneficio_id = b.id WHERE fb.funcionario_id = $1""", id)
        escala = await db.fetchrow("SELECT * FROM rh_escala WHERE funcionario_id = $1 LIMIT 1", id)
        avaliacoes = await db.fetch("SELECT * FROM rh_avaliacoes WHERE funcionario_id = $1 ORDER BY data_avaliacao DESC NULLS LAST, id DESC", id)
        treinamentos = await db.fetch("""
            SELECT t.*, p.presenca, p.nota_avaliacao, p.certificado_emitido
            FROM rh_treinamento_participantes p JOIN rh_treinamentos t ON t.id = p.treinamento_id
            WHERE p.funcionario_id = $1 ORDER BY t.data_inicio DESC NULLS LAST, t.id DESC
        """, id)
        return {
            "funcionario": dict(func),
            "ponto": [dict(r) for r in ponto],
            "ferias": [dict(r) for r in ferias],
            "folha": [dict(r) for r in folha],
            "beneficios": [dict(r) for r in beneficios],
            "escala": dict(escala) if escala else None,
            "avaliacoes": [dict(r) for r in avaliacoes],
            "treinamentos": [dict(r) for r in treinamentos],
        }
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

# ── Avaliação de Desempenho ──

def avaliacao_detalhe(id: int) -> dict:
    async def _go():
        db = await get_db()
        aval = await db.fetchrow("""
            SELECT a.*, f.nome AS funcionario_nome FROM rh_avaliacoes a
            JOIN rh_funcionarios f ON f.id = a.funcionario_id WHERE a.id = $1
        """, id)
        if not aval: return {"error": "not found"}
        competencias = await db.fetch("SELECT * FROM rh_avaliacao_competencias WHERE avaliacao_id = $1 ORDER BY id", id)
        return {"avaliacao": dict(aval), "competencias": [dict(r) for r in competencias]}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def relatorio_desempenho(funcionario_id: int = None, periodo: str = None) -> dict:
    """Nota media por funcionario/departamento — base do relatorio
    exportavel de desempenho."""
    async def _go():
        db = await get_db()
        where, params = [], []
        if funcionario_id:
            params.append(funcionario_id); where.append(f"a.funcionario_id = ${len(params)}")
        if periodo:
            params.append(periodo); where.append(f"a.periodo = ${len(params)}")
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        rows = await db.fetch(f"""
            SELECT f.id AS funcionario_id, f.nome, f.departamento, f.cargo,
                   a.periodo, a.tipo, a.nota_geral, a.status, a.data_avaliacao, a.avaliador_nome
            FROM rh_avaliacoes a JOIN rh_funcionarios f ON f.id = a.funcionario_id
            {where_sql} ORDER BY a.data_avaliacao DESC NULLS LAST, a.id DESC
        """, *params)
        por_departamento = await db.fetch(f"""
            SELECT f.departamento, ROUND(AVG(a.nota_geral), 2) AS nota_media, COUNT(*) AS total_avaliacoes
            FROM rh_avaliacoes a JOIN rh_funcionarios f ON f.id = a.funcionario_id
            {where_sql} GROUP BY f.departamento ORDER BY nota_media DESC NULLS LAST
        """, *params)
        return {"avaliacoes": [dict(r) for r in rows], "por_departamento": [dict(r) for r in por_departamento]}
    try: return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro relatorio_desempenho: {e}")
        return {"avaliacoes": [], "por_departamento": []}

# ── Treinamentos ──

def treinamento_detalhe(id: int) -> dict:
    async def _go():
        db = await get_db()
        trein = await db.fetchrow("SELECT * FROM rh_treinamentos WHERE id = $1", id)
        if not trein: return {"error": "not found"}
        participantes = await db.fetch("""
            SELECT p.*, f.nome AS funcionario_nome FROM rh_treinamento_participantes p
            JOIN rh_funcionarios f ON f.id = p.funcionario_id
            WHERE p.treinamento_id = $1 ORDER BY f.nome
        """, id)
        return {"treinamento": dict(trein), "participantes": [dict(r) for r in participantes]}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def relatorio_treinamentos(funcionario_id: int = None) -> dict:
    """Horas de treino e certificados por funcionario — base do relatorio
    exportavel de treinamentos."""
    async def _go():
        db = await get_db()
        where, params = [], []
        if funcionario_id:
            params.append(funcionario_id); where.append(f"p.funcionario_id = ${len(params)}")
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        rows = await db.fetch(f"""
            SELECT f.id AS funcionario_id, f.nome, f.departamento,
                   COUNT(*) AS treinamentos_participados,
                   COALESCE(SUM(t.carga_horaria) FILTER (WHERE p.presenca = 'presente'), 0) AS horas_treino,
                   COUNT(*) FILTER (WHERE p.certificado_emitido) AS certificados_emitidos
            FROM rh_treinamento_participantes p
            JOIN rh_funcionarios f ON f.id = p.funcionario_id
            JOIN rh_treinamentos t ON t.id = p.treinamento_id
            {where_sql}
            GROUP BY f.id, f.nome, f.departamento ORDER BY horas_treino DESC
        """, *params)
        return {"por_funcionario": [dict(r) for r in rows]}
    try: return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro relatorio_treinamentos: {e}")
        return {"por_funcionario": []}

# ── Vale / Adiantamento ──

def _ensure_vale():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS rh_vales (
            id SERIAL PRIMARY KEY, funcionario_id INT, nome VARCHAR(100),
            valor DECIMAL(12,2) DEFAULT 0, motivo TEXT, data DATE DEFAULT CURRENT_DATE,
            status VARCHAR(20) DEFAULT 'pendente', created_at TIMESTAMP DEFAULT NOW()
        )""")
    try: run_async(_go())
    except Exception as e: pass

_ensure_vale()

def list_vale() -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM rh_vales ORDER BY id DESC LIMIT 100")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def criar_vale(func_id: int, nome: str, valor: float, motivo: str = "") -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("INSERT INTO rh_vales (funcionario_id, nome, valor, motivo) VALUES ($1,$2,$3,$4) RETURNING *", func_id, nome, valor, motivo)
        return dict(row) if row else {"error": "erro"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def atualizar_vale(vale_id: int, status: str) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("UPDATE rh_vales SET status=$1 WHERE id=$2 RETURNING *", status, vale_id)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

# ── Comissoes ──

def _ensure_comissoes():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS rh_comissoes (
            id SERIAL PRIMARY KEY, vendedor_id INT, nome VARCHAR(100),
            total_vendas DECIMAL(12,2) DEFAULT 0, comissao_pct DECIMAL(5,2) DEFAULT 0,
            total_comissoes DECIMAL(12,2) DEFAULT 0, mes VARCHAR(10),
            status VARCHAR(20) DEFAULT 'pendente', created_at TIMESTAMP DEFAULT NOW()
        )""")
    try: run_async(_go())
    except Exception as e: pass

_ensure_comissoes()

def list_comissoes() -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM rh_comissoes ORDER BY id DESC LIMIT 100")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def criar_comissao(vendedor_id: int, nome: str, mes: str, total_vendas: float, comissao_pct: float, total_comissoes: float) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("INSERT INTO rh_comissoes (vendedor_id, nome, total_vendas, comissao_pct, total_comissoes, mes) VALUES ($1,$2,$3,$4,$5,$6) RETURNING *", vendedor_id, nome, total_vendas, comissao_pct, total_comissoes, mes)
        return dict(row) if row else {"error": "erro"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def atualizar_comissao(comissao_id: int, status: str) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("UPDATE rh_comissoes SET status=$1 WHERE id=$2 RETURNING *", status, comissao_id)
        return dict(row) if row else {"error": "not found"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}
