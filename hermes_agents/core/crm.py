"""CRM Core — Leads, Contatos, Empresas, Negociacoes, Funil, Atividades, Propostas, Contratos"""
from core import get_db, run_async, log, hoje

AGENT = "CRM Core"

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crm_empresas (
                id SERIAL PRIMARY KEY, nome VARCHAR(200) NOT NULL,
                cnpj VARCHAR(20), segmento VARCHAR(100), porte VARCHAR(20),
                telefone VARCHAR(30), email VARCHAR(100), website VARCHAR(200),
                endereco TEXT, observacoes TEXT, created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crm_leads (
                id SERIAL PRIMARY KEY, nome VARCHAR(200) NOT NULL,
                email VARCHAR(100), telefone VARCHAR(30), empresa_id INT REFERENCES crm_empresas(id),
                origem VARCHAR(50) DEFAULT 'site', status VARCHAR(30) DEFAULT 'novo',
                funil_etapa VARCHAR(50) DEFAULT 'captacao',
                valor_potencial DECIMAL(12,2) DEFAULT 0,
                observacoes TEXT, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crm_contatos (
                id SERIAL PRIMARY KEY, nome VARCHAR(200) NOT NULL,
                email VARCHAR(100), telefone VARCHAR(30), cargo VARCHAR(100),
                empresa_id INT REFERENCES crm_empresas(id),
                lead_id INT REFERENCES crm_leads(id),
                created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crm_negociacoes (
                id SERIAL PRIMARY KEY, titulo VARCHAR(200) NOT NULL,
                lead_id INT REFERENCES crm_leads(id),
                contato_id INT REFERENCES crm_contatos(id),
                empresa_id INT REFERENCES crm_empresas(id),
                valor DECIMAL(12,2) DEFAULT 0,
                etapa_funil VARCHAR(50) DEFAULT 'prospeccao',
                probabilidade INT DEFAULT 10,
                data_fechamento DATE, status VARCHAR(30) DEFAULT 'aberta',
                observacoes TEXT, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crm_atividades (
                id SERIAL PRIMARY KEY, tipo VARCHAR(30) NOT NULL,
                descricao TEXT, data_agendada TIMESTAMP, data_realizada TIMESTAMP,
                lead_id INT REFERENCES crm_leads(id),
                negociacao_id INT REFERENCES crm_negociacoes(id),
                contato_id INT REFERENCES crm_contatos(id),
                status VARCHAR(20) DEFAULT 'pendente',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crm_propostas (
                id SERIAL PRIMARY KEY, negociacao_id INT REFERENCES crm_negociacoes(id),
                numero VARCHAR(30), valor DECIMAL(12,2) DEFAULT 0,
                status VARCHAR(30) DEFAULT 'rascunho',
                data_envio DATE, data_validade DATE,
                conteudo TEXT, created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crm_contratos (
                id SERIAL PRIMARY KEY, negociacao_id INT REFERENCES crm_negociacoes(id),
                proposta_id INT REFERENCES crm_propostas(id),
                numero VARCHAR(30), valor DECIMAL(12,2) DEFAULT 0,
                status VARCHAR(30) DEFAULT 'pendente',
                data_assinatura DATE, created_at TIMESTAMP DEFAULT NOW()
            )
        """)
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao criar tabelas CRM: {e}")

_ensure_tables()

# ── Funil ──

def funil() -> dict:
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT etapa_funil, COUNT(*) as total, COALESCE(SUM(valor),0) as valor_total
            FROM crm_negociacoes WHERE status != 'perdida' GROUP BY etapa_funil ORDER BY COUNT(*) DESC""")
        categorias = []
        series = []
        for r in (rows or []):
            categorias.append(r["etapa_funil"])
            series.append({"name": r["etapa_funil"], "total": r["total"], "valor": float(r["valor_total"])})
        total_leads = await db.fetchval("SELECT COUNT(*) FROM crm_leads")
        total_negociacoes = await db.fetchval("SELECT COUNT(*) FROM crm_negociacoes WHERE status = 'aberta'")
        total_propostas = await db.fetchval("SELECT COUNT(*) FROM crm_propostas WHERE status = 'enviada'")
        return {
            "categorias": categorias, "series": series,
            "total_leads": total_leads or 0, "total_negociacoes": total_negociacoes or 0,
            "total_propostas": total_propostas or 0,
            "etapas": ["captacao", "qualificacao", "prospeccao", "proposta", "negociacao", "fechamento"],
        }
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro funil: {e}")
        return {"categorias": [], "series": [], "total_leads": 0, "total_negociacoes": 0, "total_propostas": 0, "etapas": []}

# ── CRUD generico ──

def _list(tabela: str, cols="*", order="id DESC", limit=100) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"SELECT {cols} FROM {tabela} ORDER BY {order} LIMIT {limit}")
        return [dict(r) for r in rows]
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro list {tabela}: {e}")
        return []

def _get(tabela: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"SELECT * FROM {tabela} WHERE id = $1", id)
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
        row = await db.fetchrow(f"INSERT INTO {tabela} ({cols}) VALUES ({placeholders}) RETURNING *", *vals)
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
        row = await db.fetchrow(f"UPDATE {tabela} SET {sets} WHERE id = ${len(vals)} RETURNING *", *vals)
        return dict(row) if row else {"error": "not found"}
    try:
        return run_async(_go())
    except Exception as e:
        return {"error": str(e)}

def _delete(tabela: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        await db.execute(f"DELETE FROM {tabela} WHERE id = $1", id)
        return {"success": True}
    try:
        run_async(_go())
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}

# ── API helpers por entidade ──

CRM_TABLES = ["leads", "contatos", "empresas", "negociacoes", "atividades", "propostas", "contratos"]

def list(tabela: str): return _list(f"crm_{tabela}")
def get(tabela: str, id: int): return _get(f"crm_{tabela}", id)
def create(tabela: str, data: dict): return _create(f"crm_{tabela}", data)
def update(tabela: str, id: int, data: dict): return _update(f"crm_{tabela}", id, data)
def delete(tabela: str, id: int): return _delete(f"crm_{tabela}", id)

if __name__ == "__main__":
    log(AGENT, "Auto-teste CRM")
    print("Funil:", funil())
    print("Leads:", len(list("leads")))
