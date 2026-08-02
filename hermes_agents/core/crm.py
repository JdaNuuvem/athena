"""CRM Core — Leads, Contatos, Empresas, Negociacoes, Funil, Atividades, Propostas, Contratos"""
import asyncpg
import datetime
import re
from core import get_db, run_async, log, hoje

AGENT = "CRM Core"

_DATA_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$")

def _coerce_datas(dados: dict) -> dict:
    """Campos DATE (data_fechamento, data_envio, data_validade, data_assinatura...)
    chegam do frontend (<input type="date">) como string "YYYY-MM-DD" no JSON,
    e campos TIMESTAMP (data_agendada, data_realizada da agenda) chegam como
    "YYYY-MM-DDTHH:MM" (<input type="datetime-local">). asyncpg, ao contrario
    de outros drivers, nao converte string pra DATE/TIMESTAMP automaticamente
    — exige datetime.date/datetime.datetime de verdade, senao estoura
    "'str' object has no attribute 'toordinal'". String vazia vira NULL."""
    out = {}
    for k, v in dados.items():
        if isinstance(v, str) and _DATETIME_ISO_RE.match(v):
            try:
                v = datetime.datetime.fromisoformat(v.replace(" ", "T"))
            except ValueError:
                pass
        elif isinstance(v, str) and _DATA_ISO_RE.match(v):
            try:
                v = datetime.date.fromisoformat(v)
            except ValueError:
                pass
        elif isinstance(v, str) and k.startswith("data_") and not v.strip():
            v = None
        out[k] = v
    return out

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

def _list(tabela: str, cols="*", order="id DESC", limit=500) -> list:
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

_ERRO_FK_INVALIDA = "Referencia invalida: um dos vinculos informados (lead, contato, negociacao, empresa, etc) nao existe."

def _create(tabela: str, dados: dict) -> dict:
    # ponytail: NAO usar list(...) — este modulo define list(t) no nivel de
    # modulo, que sombreia o builtin para qualquer funcao neste arquivo.
    keys = [*dados.keys()]
    vals = [*dados.values()]
    placeholders = ", ".join(f"${i+1}" for i in range(len(keys)))
    cols = ", ".join(keys)
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"INSERT INTO {tabela} ({cols}) VALUES ({placeholders}) RETURNING *", *vals)
        return dict(row) if row else {"error": "insert failed"}
    try:
        return run_async(_go())
    except asyncpg.ForeignKeyViolationError:
        return {"error": _ERRO_FK_INVALIDA}
    except Exception as e:
        return {"error": str(e)}

def _update(tabela: str, id: int, dados: dict) -> dict:
    sets = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(dados.keys()))
    vals = [*dados.values(), id]
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"UPDATE {tabela} SET {sets} WHERE id = ${len(vals)} RETURNING *", *vals)
        return dict(row) if row else {"error": "not found"}
    try:
        return run_async(_go())
    except asyncpg.ForeignKeyViolationError:
        return {"error": _ERRO_FK_INVALIDA}
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
    except asyncpg.ForeignKeyViolationError:
        # ponytail: excluir uma empresa/lead/negociacao com filhos (leads,
        # contatos, negociacoes, propostas...) apontando pra ela quebrava
        # com o erro cru do Postgres ("violates foreign key constraint...")
        # direto na tela do usuario. Mensagem amigavel, igual ao padrao
        # ja usado em core/lojas.py para o mesmo tipo de erro.
        return {"error": "Nao e possivel excluir: existem outros registros do CRM vinculados a este item (leads, contatos, negociacoes, propostas, etc)."}
    except Exception as e:
        return {"error": str(e)}

# ── API helpers por entidade ──

CRM_TABLES = ["leads", "contatos", "empresas", "negociacoes", "atividades", "propostas", "contratos", "agenda"]

# "agenda" e' um alias de "atividades" — a pagina web/src/app/crm/agenda
# chama /api/crm/agenda, mas nunca existiu tabela crm_agenda nem entrada
# "agenda" em CRM_TABLES/CRM_COLUNAS, entao list/create/get/update/delete
# caiam sempre em 404 "Tabela invalida". O conceito de negocio (follow-ups
# agendados) ja e' coberto por crm_atividades.
_ALIAS_TABELA = {"agenda": "atividades"}

def _tabela_real(tabela: str) -> str:
    return _ALIAS_TABELA.get(tabela, tabela)

# ponytail: whitelist de colunas por tabela — _create/_update concatenam as
# CHAVES do dict recebido direto na string SQL (so' os valores sao
# parametrizados com $1, $2...). Sem essa whitelist, um cliente com permissao
# crm.criar/crm.editar poderia injetar SQL arbitrario via nome de campo no
# JSON (ex.: {"nome, x) VALUES ('a'); DROP TABLE crm_leads;--": "x"}).
CRM_COLUNAS = {
    "leads": {"nome", "email", "telefone", "empresa_id", "origem", "status", "funil_etapa", "valor_potencial", "observacoes"},
    "empresas": {"nome", "cnpj", "segmento", "porte", "telefone", "email", "website", "endereco", "observacoes"},
    "contatos": {"nome", "email", "telefone", "cargo", "empresa_id", "lead_id"},
    "negociacoes": {"titulo", "lead_id", "contato_id", "empresa_id", "valor", "etapa_funil", "probabilidade", "data_fechamento", "status", "observacoes"},
    "atividades": {"tipo", "descricao", "data_agendada", "data_realizada", "lead_id", "negociacao_id", "contato_id", "status"},
    "propostas": {"negociacao_id", "numero", "valor", "status", "data_envio", "data_validade", "conteudo"},
    "contratos": {"negociacao_id", "proposta_id", "numero", "valor", "status", "data_assinatura"},
}

def list(tabela: str): return _list(f"crm_{_tabela_real(tabela)}")
def get(tabela: str, id: int): return _get(f"crm_{_tabela_real(tabela)}", id)

# Ciclo de vida de uma proposta — rascunho (em edicao) -> enviada (mandada pro
# cliente) -> aceita/rejeitada (resposta do cliente) ou vencida (passou
# data_validade sem resposta). funil() ja conta "enviada" como o status
# significativo pro contador de propostas em aberto.
STATUS_PROPOSTA = ["rascunho", "enviada", "aceita", "rejeitada", "vencida"]

def _validar_campos(tabela: str, dados: dict, criando: bool) -> str | None:
    """Validacao de formato no boundary, antes de tocar o banco. Sem isso,
    um campo obrigatorio vazio ou invalido so' falhava (feio) na constraint
    do Postgres, sem mensagem util pro frontend."""
    if tabela == "atividades":
        if criando and not str(dados.get("tipo", "")).strip():
            return "Tipo e obrigatorio"
        if "tipo" in dados and not str(dados.get("tipo", "")).strip():
            return "Tipo nao pode ser vazio"
        return None
    if tabela == "propostas":
        if criando and not dados.get("negociacao_id"):
            return "Negociação é obrigatória"
        if "negociacao_id" in dados:
            try:
                if int(dados["negociacao_id"]) <= 0:
                    return "Negociação inválida"
            except (TypeError, ValueError):
                return "Negociação inválida"
        if dados.get("status") and dados["status"] not in STATUS_PROPOSTA:
            return f"Status inválido — use um de: {', '.join(STATUS_PROPOSTA)}"
        if "valor" in dados and dados["valor"] not in (None, ""):
            try:
                if float(dados["valor"]) < 0:
                    return "Valor não pode ser negativo"
            except (TypeError, ValueError):
                return "Valor inválido"
        if dados.get("data_validade") and dados.get("data_envio") and str(dados["data_validade"]) < str(dados["data_envio"]):
            return "Data de validade não pode ser anterior à data de envio"
        return None
    if tabela != "empresas":
        return None
    from core.validadores import validar_cnpj, validar_email
    if criando and not str(dados.get("nome", "")).strip():
        return "Nome e obrigatorio"
    if "nome" in dados and not str(dados.get("nome", "")).strip():
        return "Nome nao pode ser vazio"
    if dados.get("cnpj") and not validar_cnpj(dados["cnpj"]):
        return "CNPJ invalido"
    if dados.get("email") and not validar_email(dados["email"]):
        return "E-mail invalido"
    return None

def _gerar_numero_proposta(proposta_id: int) -> str:
    return f"PROP-{str(proposta_id).zfill(4)}"

def create(tabela: str, data: dict) -> dict:
    tabela_real = _tabela_real(tabela)
    colunas_validas = CRM_COLUNAS.get(tabela_real)
    if colunas_validas is None:
        return {"error": "Tabela invalida"}
    filtrado = {k: v for k, v in data.items() if k in colunas_validas}
    if not filtrado:
        return {"error": "Nenhum campo valido informado"}
    erro = _validar_campos(tabela_real, filtrado, criando=True)
    if erro:
        return {"error": erro}
    resultado = _create(f"crm_{tabela_real}", _coerce_datas(filtrado))
    # numero e' gerado a partir do proprio id (sequencial, sem corrida de uma
    # query de COUNT separada) — so' quando o caller nao mandou um explicito.
    if tabela_real == "propostas" and not resultado.get("error") and not filtrado.get("numero"):
        resultado = _update("crm_propostas", resultado["id"], {"numero": _gerar_numero_proposta(resultado["id"])})
    return resultado

def update(tabela: str, id: int, data: dict) -> dict:
    tabela_real = _tabela_real(tabela)
    colunas_validas = CRM_COLUNAS.get(tabela_real)
    if colunas_validas is None:
        return {"error": "Tabela invalida"}
    filtrado = {k: v for k, v in data.items() if k in colunas_validas}
    if not filtrado:
        return {"error": "Nenhum campo valido informado"}
    erro = _validar_campos(tabela_real, filtrado, criando=False)
    if erro:
        return {"error": erro}
    return _update(f"crm_{tabela_real}", id, _coerce_datas(filtrado))

def delete(tabela: str, id: int): return _delete(f"crm_{_tabela_real(tabela)}", id)

def importar_contatos_bling() -> dict:
    """Importa contatos do Bling para o CRM (empresas, contatos, leads).
       tipo C=cliente vira lead+contato, tipo F=fornecedor vira empresa+contato."""
    from bling_erp import listar_contatos, get_access_token, get_auth_url
    token = get_access_token()
    if not token:
        return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}

    _ensure_tables()
    async def _go():
        db = await get_db()
        res = {"empresas": 0, "contatos": 0, "leads": 0, "total": 0}
        pagina = 1
        while True:
            r = listar_contatos(pagina=pagina, limite=100)
            dados = r.get("data", [])
            if not dados or r.get("error"):
                break
            for c in dados:
                nome = (c.get("nome") or "").strip()
                if not nome:
                    continue
                email = (c.get("email") or "").strip().lower() or None
                tel = (c.get("telefone") or c.get("celular") or "").strip() or None
                tipo = (c.get("tipo") or "").upper()
                doc = (c.get("numeroDocumento") or "").strip()

                # ponytail: dedupe por email cobre a maioria dos casos, mas
                # contatos sem email (comum em fornecedores/clientes do Bling
                # sem email cadastrado) sempre caiam nesse if como False e
                # duplicavam a cada sincronizacao — sem fallback, o CRM
                # acumulava um lead/contato novo por contato sem email a
                # cada reimportacao. Fallback por (nome+telefone) ou so' nome.
                if email:
                    exists = await db.fetchval("SELECT id FROM crm_contatos WHERE email = $1", email)
                elif tel:
                    exists = await db.fetchval("SELECT id FROM crm_contatos WHERE telefone = $1 AND nome = $2", tel, nome)
                else:
                    exists = await db.fetchval("SELECT id FROM crm_contatos WHERE nome = $1 AND email IS NULL AND telefone IS NULL", nome)
                if exists:
                    res["total"] += 1
                    continue

                if tipo == "F":
                    if doc:
                        empresa_exists = await db.fetchval("SELECT id FROM crm_empresas WHERE cnpj = $1", doc)
                    else:
                        empresa_exists = await db.fetchval("SELECT id FROM crm_empresas WHERE nome = $1", nome)
                    if not empresa_exists:
                        row = await db.fetchrow(
                            "INSERT INTO crm_empresas (nome, cnpj, telefone, email) VALUES ($1, $2, $3, $4) RETURNING id",
                            nome, doc, tel, email)
                        empresa_id = row["id"] if row else None
                        res["empresas"] += 1
                    else:
                        empresa_id = empresa_exists
                    if empresa_id:
                        await db.execute(
                            "INSERT INTO crm_contatos (nome, email, telefone, empresa_id) VALUES ($1, $2, $3, $4)",
                            nome, email, tel, empresa_id)
                        res["contatos"] += 1
                else:
                    lead_row = await db.fetchrow(
                        "INSERT INTO crm_leads (nome, email, telefone, origem, status) VALUES ($1, $2, $3, 'bling', 'novo') RETURNING id",
                        nome, email, tel)
                    if lead_row:
                        res["leads"] += 1
                        await db.execute(
                            "INSERT INTO crm_contatos (nome, email, telefone, lead_id) VALUES ($1, $2, $3, $4)",
                            nome, email, tel, lead_row["id"])
                        res["contatos"] += 1
                res["total"] += 1
            if len(dados) < 100:
                break
            pagina += 1
        return res
    try:
        return run_async(_go())
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    log(AGENT, "Auto-teste CRM")
    print("Funil:", funil())
    print("Leads:", len(list("leads")))
