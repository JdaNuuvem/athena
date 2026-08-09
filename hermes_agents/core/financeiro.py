"""Financeiro Core — Fluxo Caixa, Receber, Pagar, Boletos, PIX, Conciliação, Banco, DRE"""
from decimal import Decimal
from core import get_db, run_async, log, hoje
from core.config import get_config

AGENT = "Financeiro Core"

def _row(row) -> dict:
    """asyncpg devolve coluna DECIMAL/NUMERIC como decimal.Decimal — o
    encoder JSON padrao do Flask serializa Decimal como STRING (nao
    float), entao todo valor monetario chegava no frontend como "100.00"
    em vez de 100.0. Isso quebrava silenciosamente: fmtBRL(string) nao
    formata (string tem .toLocaleString() mas nao faz nada especial), e
    somas tipo `0 + "100.00"` viravam concatenacao ("0100.00") em vez de
    soma numerica. Converte pra float logo na saida do banco, antes do
    dict virar JSON."""
    return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in dict(row).items()}

FIN_TABLES = ["fluxo_caixa", "contas_receber", "contas_pagar", "boletos", "pix", "conciliacao", "bancos", "centro_custo", "plano_contas", "dre"]

# ── Alçada de aprovação para pagamentos/recebimentos de valor alto ──
# Sem isso, qualquer usuario com permissao financeiro.criar/editar podia
# executar (marcar como pago/concluido) um lancamento de qualquer valor —
# a permissao financeiro.aprovar ja existia no RBAC mas nao era checada em
# lugar nenhum.
TABELAS_PAGAMENTO = {"contas_pagar", "boletos", "pix"}
STATUS_EXECUTADO = {"pago", "concluido", "compensado"}
STATUS_PADRAO_TABELA = {"contas_pagar": "pendente", "boletos": "pendente", "pix": "concluido"}
LIMITE_APROVACAO_PADRAO = 5000.0

def limite_aprovacao_pagamento() -> float:
    val = get_config("financeiro", "limite_aprovacao_pagamento")
    try:
        return float(val) if val not in (None, "") else LIMITE_APROVACAO_PADRAO
    except (TypeError, ValueError):
        return LIMITE_APROVACAO_PADRAO

def _exige_aprovacao(tabela: str, valor: float, status: str) -> bool:
    return (tabela in TABELAS_PAGAMENTO
            and str(status or "").lower() in STATUS_EXECUTADO
            and valor >= limite_aprovacao_pagamento())

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_fluxo_caixa (
            id SERIAL PRIMARY KEY, data DATE NOT NULL, descricao VARCHAR(200),
            tipo VARCHAR(10) DEFAULT 'entrada', valor DECIMAL(12,2) DEFAULT 0,
            categoria VARCHAR(50), conta_id INT, created_at TIMESTAMP DEFAULT NOW()
        )""")
        # pedido_id: rastreia de qual vendas_pedidos.id um lancamento de venda
        # a vista (Shopee/i9Logic — ver core/entidades.py::ao_concluir_venda_avista)
        # veio, pra sync periodico (a cada 5-10min) nao duplicar lancamento a
        # cada rodada que reprocessa o mesmo pedido ja concluido.
        try: await db.execute("ALTER TABLE fin_fluxo_caixa ADD COLUMN IF NOT EXISTS pedido_id INT")
        except Exception: pass
        try:
            await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_fin_fluxo_caixa_pedido_id ON fin_fluxo_caixa (pedido_id) WHERE pedido_id IS NOT NULL")
        except Exception: pass
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_contas_receber (
            id SERIAL PRIMARY KEY, cliente VARCHAR(200) NOT NULL, descricao VARCHAR(200),
            valor DECIMAL(12,2) DEFAULT 0, vencimento DATE, data_recebimento DATE,
            status VARCHAR(20) DEFAULT 'pendente', forma_pagamento VARCHAR(30),
            bling_id BIGINT, origem VARCHAR(30) DEFAULT 'manual',
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_contas_pagar (
            id SERIAL PRIMARY KEY, fornecedor VARCHAR(200) NOT NULL, descricao VARCHAR(200),
            valor DECIMAL(12,2) DEFAULT 0, vencimento DATE, data_pagamento DATE,
            status VARCHAR(20) DEFAULT 'pendente', forma_pagamento VARCHAR(30),
            bling_id BIGINT, origem VARCHAR(30) DEFAULT 'manual',
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        # ponytail: loja_id pra filtro por loja no fluxo de caixa.
        # contas_pagar/compras sao centralizadas hoje (sem selecao de loja na
        # UI) — default = loja principal. contas_receber vem de venda (essa
        # sim tem loja de verdade) — backfill via "Pedido #N" na descricao
        # ligado a vendas_pedidos.loja_id; sem match fica NULL (nao adivinha).
        try: await db.execute("ALTER TABLE fin_contas_receber ADD COLUMN IF NOT EXISTS loja_id INT")
        except Exception: pass
        try: await db.execute("ALTER TABLE fin_contas_pagar ADD COLUMN IF NOT EXISTS loja_id INT")
        except Exception: pass
        try:
            from core.lojas import LOJA_PRINCIPAL_ID
            if LOJA_PRINCIPAL_ID:
                await db.execute("UPDATE fin_contas_pagar SET loja_id = $1 WHERE loja_id IS NULL", LOJA_PRINCIPAL_ID)
        except Exception as e:
            log(AGENT, f"Erro backfill loja_id fin_contas_pagar: {e}")
        try:
            await db.execute("""
                UPDATE fin_contas_receber fcr SET loja_id = vp.loja_id
                FROM vendas_pedidos vp
                WHERE fcr.loja_id IS NULL AND vp.loja_id IS NOT NULL
                  AND fcr.descricao ~ 'Pedido #\\d+'
                  AND vp.id = substring(fcr.descricao from 'Pedido #(\\d+)')::int
            """)
        except Exception as e:
            log(AGENT, f"Erro backfill loja_id fin_contas_receber: {e}")
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

        # ponytail: fluxo_caixa/contas_receber/contas_pagar/boletos/pix/conciliacao
        # tinham seed fake aqui (clientes/fornecedores ficticios tipo "Comercial
        # XYZ") — removido. Dado real agora vem de core.entidades.ao_concluir_venda_avista
        # (Shopee/i9Logic, disparado pelos syncs periodicos) e ao_faturar_pedido/
        # ao_fechar_caixa_pdv (ja existentes). Sem seed, essas tabelas ficam
        # vazias ate a primeira venda real sincronizar.
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
        for _tabela in ("fin_contas_pagar", "fin_boletos", "fin_pix"):
            try: await db.execute(f"ALTER TABLE {_tabela} ADD COLUMN IF NOT EXISTS aprovado_por VARCHAR(100)")
            except Exception: pass
            try: await db.execute(f"ALTER TABLE {_tabela} ADD COLUMN IF NOT EXISTS aprovado_por_id INT")
            except Exception: pass
        # ponytail: bling_id/origem sao lidos/gravados por 3 fluxos diferentes
        # (webhook do Bling em bling_erp.py, sync manual em core/fiscal.py,
        # migracao em core/entidades.py) mas so' 2 deles faziam o ALTER TABLE
        # de seguranca antes de usar a coluna — o webhook nao fazia, entao
        # num banco novo (CREATE TABLE aqui ainda nao tinha essas colunas) o
        # primeiro webhook recebido quebrava com "column does not exist".
        # Fonte unica de verdade agora: garantido aqui, sempre, no boot.
        for _tabela in ("fin_contas_receber", "fin_contas_pagar"):
            try: await db.execute(f"ALTER TABLE {_tabela} ADD COLUMN IF NOT EXISTS bling_id BIGINT")
            except Exception: pass
            try: await db.execute(f"ALTER TABLE {_tabela} ADD COLUMN IF NOT EXISTS origem VARCHAR(30) DEFAULT 'manual'")
            except Exception: pass

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
        return [_row(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"Erro list {tabela}: {e}"); return []

def _get(tabela: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"SELECT * FROM {tabela} WHERE id = $1", id)
        return _row(row) if row else {"error": "not found"}
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
        return _row(row) if row else {"error": "insert failed"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def _update(tabela: str, id: int, dados: dict) -> dict:
    sets = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(dados.keys()))
    vals = [*dados.values(), id]
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"UPDATE {tabela} SET {sets} WHERE id = ${len(vals)} RETURNING *", *vals)
        return _row(row) if row else {"error": "not found"}
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

# ponytail: whitelist de colunas por tabela — _create/_update concatenam as
# CHAVES do dict recebido direto na string SQL (so' os valores sao
# parametrizados com $1, $2...). Sem essa whitelist, um cliente com permissao
# financeiro.criar/financeiro.editar poderia injetar SQL arbitrario via nome
# de campo no JSON (mesma classe de bug ja corrigida em core/crm.py e
# core/atendimento.py).
FIN_COLUNAS = {
    "fluxo_caixa": {"data", "descricao", "tipo", "valor", "categoria", "conta_id"},
    "contas_receber": {"cliente", "descricao", "valor", "vencimento", "data_recebimento",
                        "status", "forma_pagamento", "bling_id", "origem"},
    "contas_pagar": {"fornecedor", "descricao", "valor", "vencimento", "data_pagamento",
                      "status", "forma_pagamento", "bling_id", "origem"},
    "boletos": {"beneficiario", "valor", "vencimento", "nosso_numero", "codigo_barras", "status"},
    "pix": {"chave", "tipo_chave", "descricao", "valor", "data_transacao", "status"},
    "conciliacao": {"banco_id", "data", "descricao", "valor_extrato", "valor_sistema", "status"},
    "bancos": {"nome", "agencia", "conta", "saldo", "status"},
    "centro_custo": {"nome", "codigo", "descricao", "status"},
    "plano_contas": {"codigo", "nome", "tipo", "natureza", "conta_pai_id"},
    "dre": {"mes", "descricao", "valor", "tipo", "categoria"},
}

# aprovado_por/aprovado_por_id NAO entram no whitelist acima de proposito —
# sao gravados so' pela injecao server-side em criar_pagamento/
# atualizar_pagamento (ver _CAMPOS_SERVIDOR abaixo), nunca a partir do que o
# cliente manda. Ficam numa whitelist separada, usada so' internamente por
# create()/update() depois que a alcada ja validou quem aprovou de verdade.
_COLUNAS_APROVACAO = {"aprovado_por", "aprovado_por_id"}

def list(tabela: str): return _list(f"fin_{tabela}")
def get(tabela: str, id: int): return _get(f"fin_{tabela}", id)

def create(tabela: str, data: dict, colunas_extras: set = frozenset()) -> dict:
    colunas_validas = FIN_COLUNAS.get(tabela)
    if colunas_validas is None:
        return {"error": "Tabela invalida"}
    permitidas = colunas_validas | colunas_extras
    filtrado = {k: v for k, v in data.items() if k in permitidas}
    if not filtrado:
        return {"error": "Nenhum campo valido informado"}
    return _create(f"fin_{tabela}", filtrado)

def update(tabela: str, id: int, data: dict, colunas_extras: set = frozenset()) -> dict:
    colunas_validas = FIN_COLUNAS.get(tabela)
    if colunas_validas is None:
        return {"error": "Tabela invalida"}
    permitidas = colunas_validas | colunas_extras
    filtrado = {k: v for k, v in data.items() if k in permitidas}
    if not filtrado:
        return {"error": "Nenhum campo valido informado"}
    return _update(f"fin_{tabela}", id, filtrado)

def delete(tabela: str, id: int): return _delete(f"fin_{tabela}", id)

# ── Criação/atualização com alçada ──

def criar_pagamento(tabela: str, dados: dict, usuario_id=None, usuario_nome: str = "", tem_permissao_aprovar: bool = False) -> dict:
    # ponytail: strip aprovado_por/aprovado_por_id vindos do cliente ANTES de
    # decidir se precisa de aprovacao — sem isso, um usuario so' com
    # financeiro.criar (sem financeiro.aprovar) podia mandar
    # {"aprovado_por_id": 1, ...} num lancamento abaixo do limite (que nunca
    # passa por _exige_aprovacao) e forjar um registro com aprovador falso,
    # sem nenhuma aprovacao real ter acontecido.
    dados = {k: v for k, v in dados.items() if k not in _COLUNAS_APROVACAO}
    valor = float(dados.get("valor") or 0)
    status = dados.get("status") or STATUS_PADRAO_TABELA.get(tabela, "")
    if _exige_aprovacao(tabela, valor, status):
        if not tem_permissao_aprovar:
            return {"error": f"Lancamento de R$ {valor:.2f} exige aprovacao (limite: R$ {limite_aprovacao_pagamento():.2f})"}
        dados = {**dados, "aprovado_por": usuario_nome, "aprovado_por_id": usuario_id}
    return create(tabela, dados, colunas_extras=_COLUNAS_APROVACAO)

def atualizar_pagamento(tabela: str, id: int, dados: dict, usuario_id=None, usuario_nome: str = "", tem_permissao_aprovar: bool = False) -> dict:
    dados = {k: v for k, v in dados.items() if k not in _COLUNAS_APROVACAO}
    if "status" in dados or "valor" in dados:
        atual = get(tabela, id)
        if atual.get("error"):
            return atual
        status = dados.get("status") if "status" in dados else atual.get("status")
        valor = float(dados.get("valor") if dados.get("valor") is not None else (atual.get("valor") or 0))
        if _exige_aprovacao(tabela, valor, status):
            if not tem_permissao_aprovar:
                return {"error": f"Lancamento de R$ {valor:.2f} exige aprovacao (limite: R$ {limite_aprovacao_pagamento():.2f})"}
            dados = {**dados, "aprovado_por": usuario_nome, "aprovado_por_id": usuario_id}
    return update(tabela, id, dados, colunas_extras=_COLUNAS_APROVACAO)

# ── Queries especiais ──

def fluxo_caixa_resumo(dias=30) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            SELECT COALESCE(SUM(CASE WHEN tipo='entrada' THEN valor ELSE 0 END),0) as total_entradas,
                   COALESCE(SUM(CASE WHEN tipo='saida' THEN valor ELSE 0 END),0) as total_saidas
            FROM fin_fluxo_caixa WHERE data >= CURRENT_DATE - $1::int""", dias)
        rows = await db.fetch("SELECT data, SUM(CASE WHEN tipo='entrada' THEN valor ELSE 0 END) as entradas, SUM(CASE WHEN tipo='saida' THEN valor ELSE 0 END) as saidas FROM fin_fluxo_caixa WHERE data >= CURRENT_DATE - $1::int GROUP BY data ORDER BY data", dias)
        return {"resumo": _row(row) if row else {}, "diario": [_row(r) for r in rows]}
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
        return {"receitas": float(receitas or 0), "despesas": float(despesas or 0), "resultado": resultado, "lucro": resultado > 0, "items": [_row(r) for r in items]}
    try: return run_async(_go())
    except Exception as e: return {"receitas": 0, "despesas": 0, "resultado": 0, "lucro": False, "items": []}
