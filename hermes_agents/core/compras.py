"""Compras Core — Solicitacoes, Cotacoes, Pedidos, Recebimento, Fornecedores, Aprovacoes"""
from core import get_db, run_async, log, hoje

AGENT = "Compras Core"

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS compras_fornecedores (
            id SERIAL PRIMARY KEY, nome VARCHAR(200) NOT NULL, cnpj VARCHAR(20),
            telefone VARCHAR(30), email VARCHAR(100), contato VARCHAR(100),
            endereco TEXT, prazo_entrega_dias INT DEFAULT 7, condicoes_pgto VARCHAR(100),
            status VARCHAR(20) DEFAULT 'ativo', created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS compras_solicitacoes (
            id SERIAL PRIMARY KEY, numero VARCHAR(30), descricao TEXT NOT NULL,
            solicitante VARCHAR(100), departamento VARCHAR(100), urgencia VARCHAR(20) DEFAULT 'normal',
            status VARCHAR(30) DEFAULT 'pendente', aprovado_por VARCHAR(100), aprovado_em TIMESTAMP,
            observacoes TEXT, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        try: await db.execute("ALTER TABLE compras_solicitacoes ADD COLUMN IF NOT EXISTS aprovado_por_id INT")
        except Exception: pass
        await db.execute("""CREATE TABLE IF NOT EXISTS compras_cotacoes (
            id SERIAL PRIMARY KEY, solicitacao_id INT REFERENCES compras_solicitacoes(id),
            fornecedor_id INT REFERENCES compras_fornecedores(id),
            valor_unitario DECIMAL(12,2), valor_frete DECIMAL(12,2) DEFAULT 0,
            prazo_entrega INT, condicoes TEXT, status VARCHAR(20) DEFAULT 'enviada',
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS compras_pedidos (
            id SERIAL PRIMARY KEY, numero VARCHAR(30), solicitacao_id INT REFERENCES compras_solicitacoes(id),
            fornecedor_id INT REFERENCES compras_fornecedores(id), cotacao_id INT REFERENCES compras_cotacoes(id),
            valor_total DECIMAL(12,2) DEFAULT 0, status VARCHAR(30) DEFAULT 'emitido',
            data_emissao DATE, data_entrega_prevista DATE, aprovado_por VARCHAR(100),
            observacoes TEXT, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        # ponytail: compra e' centralizada (sem selecao de loja na UI/fluxo hoje)
        # — loja_id default = loja principal, so' pra permitir filtro por loja
        # no fluxo de caixa sem inventar um conceito de "compra por loja" que
        # o produto nao tem ainda.
        try: await db.execute("ALTER TABLE compras_pedidos ADD COLUMN IF NOT EXISTS loja_id INT")
        except Exception: pass
        # ── Sync Bling: bling_id identifica o pedido de compra no Bling pra
        # permitir upsert idempotente; idx unico parcial (WHERE bling_id IS
        # NOT NULL) deixa pedidos manuais (bling_id NULL) livres de conflito.
        try: await db.execute("ALTER TABLE compras_pedidos ADD COLUMN IF NOT EXISTS bling_id BIGINT")
        except Exception: pass
        try: await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_compras_pedidos_bling_id ON compras_pedidos (bling_id) WHERE bling_id IS NOT NULL")
        except Exception: pass
        try: await db.execute("ALTER TABLE compras_itens ADD COLUMN IF NOT EXISTS bling_item_id BIGINT")
        except Exception: pass
        try:
            from core.lojas import LOJA_PRINCIPAL_ID
            if LOJA_PRINCIPAL_ID:
                await db.execute("UPDATE compras_pedidos SET loja_id = $1 WHERE loja_id IS NULL", LOJA_PRINCIPAL_ID)
        except Exception as e:
            log(AGENT, f"Erro backfill loja_id compras_pedidos: {e}")
        await db.execute("""CREATE TABLE IF NOT EXISTS compras_itens (
            id SERIAL PRIMARY KEY, pedido_id INT REFERENCES compras_pedidos(id),
            solicitacao_id INT REFERENCES compras_solicitacoes(id),
            produto_codigo VARCHAR(50), descricao VARCHAR(200), quantidade DECIMAL(12,3) DEFAULT 0,
            unidade VARCHAR(10) DEFAULT 'UN', valor_unitario DECIMAL(12,2) DEFAULT 0, valor_total DECIMAL(12,2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS compras_recebimentos (
            id SERIAL PRIMARY KEY, pedido_id INT REFERENCES compras_pedidos(id),
            numero VARCHAR(30), data_recebimento DATE DEFAULT CURRENT_DATE,
            conferido_por VARCHAR(100), status VARCHAR(30) DEFAULT 'pendente',
            divergencias TEXT, observacoes TEXT, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS compras_notas_entrada (
            id SERIAL PRIMARY KEY, pedido_id INT REFERENCES compras_pedidos(id),
            recebimento_id INT REFERENCES compras_recebimentos(id),
            numero_nf VARCHAR(50), chave_acesso VARCHAR(50), valor DECIMAL(12,2) DEFAULT 0,
            data_emissao DATE, data_recebimento DATE, arquivo_url VARCHAR(500),
            status VARCHAR(30) DEFAULT 'pendente', created_at TIMESTAMP DEFAULT NOW()
        )""")

        # ── Reparo: fornecedor_id apontava pra compras_fornecedores (tabela
        # legada e orfa desde que a UI de fornecedores migrou pro cadastro
        # unico cad_fornecedores; core/relatorios.py ja assume cad_fornecedores
        # ha' tempo) — troca a FK fisica pra cad_fornecedores nas 3 tabelas
        # que referenciam fornecedor. Idempotente: seguro rodar em todo boot.
        tabelas_fk_fornecedor = ("compras_pedidos", "compras_cotacoes", "compras_notas_entrada")
        for tabela_fk in tabelas_fk_fornecedor:
            try:
                constraints = await db.fetch(
                    "SELECT conname, pg_get_constraintdef(oid) AS def FROM pg_constraint WHERE conrelid = $1::regclass AND contype = 'f'",
                    tabela_fk)
                for c in constraints:
                    if "fornecedor_id" in c["def"] and "compras_fornecedores" in c["def"]:
                        await db.execute(f"ALTER TABLE {tabela_fk} DROP CONSTRAINT {c['conname']}")
                        log(AGENT, f"FK antiga removida: {tabela_fk}.fornecedor_id -> compras_fornecedores")
            except Exception as e:
                log(AGENT, f"Erro drop FK antiga {tabela_fk}.fornecedor_id: {e}")

        try:
            from core.entidades import migrar_fornecedores_compras
            migrar_fornecedores_compras()
        except Exception as e:
            log(AGENT, f"Erro migrar_fornecedores_compras: {e}")

        for tabela_fk in tabelas_fk_fornecedor:
            try:
                # limpa qualquer fornecedor_id orfao que a migracao de dados
                # nao conseguiu casar (ex.: sem CNPJ pra parear) — senao o
                # ADD CONSTRAINT abaixo falha por violacao de integridade.
                await db.execute(
                    f"UPDATE {tabela_fk} SET fornecedor_id = NULL WHERE fornecedor_id IS NOT NULL AND fornecedor_id NOT IN (SELECT id FROM cad_fornecedores)")
                constraints = await db.fetch(
                    "SELECT pg_get_constraintdef(oid) AS def FROM pg_constraint WHERE conrelid = $1::regclass AND contype = 'f'",
                    tabela_fk)
                ja_tem_fk_nova = any("fornecedor_id" in c["def"] and "cad_fornecedores" in c["def"] for c in constraints)
                if not ja_tem_fk_nova:
                    await db.execute(
                        f"ALTER TABLE {tabela_fk} ADD CONSTRAINT {tabela_fk}_fornecedor_id_cad_fkey FOREIGN KEY (fornecedor_id) REFERENCES cad_fornecedores(id)")
                    log(AGENT, f"FK nova criada: {tabela_fk}.fornecedor_id -> cad_fornecedores")
            except Exception as e:
                log(AGENT, f"Erro criar FK nova {tabela_fk}.fornecedor_id: {e}")
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro tabelas compras: {e}")

_ensure_tables()

# ── CRUD generico ──

def _list(tabela: str, cols="*", order="id DESC", limit=100) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"SELECT {cols} FROM {tabela} ORDER BY {order} LIMIT {limit}")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"list {tabela}: {e}"); return []

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
    ph = ", ".join(f"${i+1}" for i in range(len(keys)))
    cols = ", ".join(keys)
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

# campos-alvo de busca por tabela logica — nomes fixos no codigo, nunca vindos
# do request, entao seguro interpolar na query; so' o termo buscado e' parametrizado.
_CAMPOS_BUSCA = {
    "pedidos": ["numero"],
    "solicitacoes": ["descricao", "solicitante"],
    "recebimentos": ["conferido_por"],
    "notas_entrada": ["numero_nf"],
    "itens": ["descricao", "produto_codigo"],
}

# tabelas logicas com coluna pedido_id — unicas que aceitam o filtro extra
# ?pedido_id= (usado pelo modal de itens/recebimentos/notas de um pedido).
_TEM_PEDIDO_ID = {"itens", "recebimentos", "notas_entrada"}

def _count(tabela_sql: str, campos_busca=None, busca: str = None, pedido_id: int = None) -> int:
    async def _go():
        db = await get_db()
        where, params = [], []
        if busca and campos_busca:
            or_clause = " OR ".join(f"{c} ILIKE ${len(params) + 1}" for c in campos_busca)
            params.append(f"%{busca}%")
            where.append(f"({or_clause})")
        if pedido_id is not None:
            params.append(pedido_id)
            where.append(f"pedido_id = ${len(params)}")
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        return await db.fetchval(f"SELECT COUNT(*) FROM {tabela_sql} {where_sql}", *params)
    try: return run_async(_go()) or 0
    except Exception as e: log(AGENT, f"Erro count {tabela_sql}: {e}"); return 0

def _list_pagina(tabela_sql: str, order="id DESC", limit=50, offset=0, campos_busca=None, busca: str = None, pedido_id: int = None) -> list:
    async def _go():
        db = await get_db()
        where, params = [], []
        if busca and campos_busca:
            or_clause = " OR ".join(f"{c} ILIKE ${len(params) + 1}" for c in campos_busca)
            params.append(f"%{busca}%")
            where.append(f"({or_clause})")
        if pedido_id is not None:
            params.append(pedido_id)
            where.append(f"pedido_id = ${len(params)}")
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        rows = await db.fetch(
            f"SELECT * FROM {tabela_sql} {where_sql} ORDER BY {order} LIMIT {limit} OFFSET {offset}", *params)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"Erro list_pagina {tabela_sql}: {e}"); return []

def list_paginado(tabela: str, pagina: int = 1, por_pagina: int = 50, busca: str = None, pedido_id: int = None) -> dict:
    pagina = max(1, pagina or 1)
    por_pagina = max(1, min(por_pagina or 50, 200))
    tabela_sql = f"compras_{tabela}"
    campos_busca = _CAMPOS_BUSCA.get(tabela)
    busca = (busca or "").strip() or None
    pedido_id = pedido_id if tabela in _TEM_PEDIDO_ID else None
    offset = (pagina - 1) * por_pagina
    dados = _list_pagina(tabela_sql, limit=por_pagina, offset=offset, campos_busca=campos_busca, busca=busca, pedido_id=pedido_id)
    total = _count(tabela_sql, campos_busca=campos_busca, busca=busca, pedido_id=pedido_id)
    total_paginas = max(1, -(-total // por_pagina)) if total else 1
    return {"data": dados, "total": total, "pagina": pagina, "por_pagina": por_pagina, "total_paginas": total_paginas}

TABLES = ["solicitacoes","cotacoes","pedidos","itens","recebimentos","notas_entrada"]
def list(t: str): return _list(f"compras_{t}")
def get(t: str, i: int): return _get(f"compras_{t}", i)
def create(t: str, d: dict):
    if t == "pedidos" and "loja_id" not in d:
        from core.lojas import LOJA_PRINCIPAL_ID
        d = {**d, "loja_id": LOJA_PRINCIPAL_ID}
    return _create(f"compras_{t}", d)
def update(t: str, i: int, d: dict): return _update(f"compras_{t}", i, d)
def delete(t: str, i: int): return _delete(f"compras_{t}", i)

# ── Aprovacao ──

def aprovar_solicitacao(id: int, aprovador_id, aprovador_nome: str) -> dict:
    """aprovador_id/aprovador_nome devem vir do usuario autenticado da request
    (usuario_atual_da_request), nunca de texto livre enviado pelo cliente —
    senao qualquer pessoa logada poderia "aprovar como" qualquer nome."""
    return update("solicitacoes", id, {
        "status": "aprovada", "aprovado_por": aprovador_nome,
        "aprovado_por_id": aprovador_id, "aprovado_em": hoje(),
    })

def confirmar_recebimento(id: int) -> dict:
    r = update("recebimentos", id, {"status": "confirmado"})
    try:
        from core.entidades import ao_receber_compra
        ao_receber_compra(id)
    except Exception as e: pass
    return r

def sincronizar_pedidos_compra_bling(pagina: int = 1, limite: int = 100) -> dict:
    """Sync de pedidos de compra do Bling -> compras_pedidos/compras_itens (upsert por
    bling_id). Resolve fornecedor por documento em cad_fornecedores, criando se nao existir —
    mesmo padrao de core.entidades.migrar_fornecedores_compras."""
    from bling_erp import listar_pedidos_compra, get_pedido_compra_detalhe, get_access_token, get_auth_url
    token = get_access_token()
    if not token:
        return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}
    r = listar_pedidos_compra(pagina, limite)
    if r.get("error"):
        return r
    resumos = r.get("data", [])
    if not resumos:
        return {"sync": 0, "message": "sem dados"}

    async def _go():
        db = await get_db()
        # coluna pode nao existir ainda (deploy antigo / boot que falhou) —
        # garante idempotentemente antes de gravar, sem depender so' do
        # _ensure_tables rodado no import do modulo.
        col_exists = await db.fetchval(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'compras_pedidos' AND column_name = 'bling_id'")
        if not col_exists:
            try: await db.execute("ALTER TABLE compras_pedidos ADD COLUMN IF NOT EXISTS bling_id BIGINT")
            except Exception: pass
            try: await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_compras_pedidos_bling_id ON compras_pedidos (bling_id) WHERE bling_id IS NOT NULL")
            except Exception: pass
            try: await db.execute("ALTER TABLE compras_itens ADD COLUMN IF NOT EXISTS bling_item_id BIGINT")
            except Exception: pass

        total = 0
        erros = []
        for resumo in resumos:
            bling_id = resumo.get("id")
            if not bling_id:
                continue
            r_detalhe = get_pedido_compra_detalhe(bling_id)
            if r_detalhe.get("error"):
                erros.append(f"pedido {bling_id}: {r_detalhe['error']}")
                continue
            detalhe = r_detalhe.get("data", {})
            try:
                fornecedor = detalhe.get("fornecedor", {}) or {}
                doc = (fornecedor.get("numeroDocumento") or "").replace(".", "").replace("/", "").replace("-", "").strip()
                fornecedor_id = None
                if doc:
                    fornecedor_id = await db.fetchval(
                        "SELECT id FROM cad_fornecedores WHERE REPLACE(REPLACE(REPLACE(documento,'.',''),'/',''),'-','') = $1 LIMIT 1", doc)
                    if not fornecedor_id:
                        fornecedor_id = await db.fetchval(
                            "INSERT INTO cad_fornecedores (nome, tipo, documento, status) VALUES ($1,'PJ',$2,'ativo') RETURNING id",
                            fornecedor.get("nome", ""), doc)

                numero = str(detalhe.get("numero", ""))
                valor_total = float(detalhe.get("total", 0) or 0)
                situacao = (detalhe.get("situacao") or {}).get("nome", "")
                data_emissao = (detalhe.get("data") or "")[:10] or None
                data_prevista = (detalhe.get("dataPrevista") or "")[:10] or None

                pedido_id = await db.fetchval("SELECT id FROM compras_pedidos WHERE bling_id = $1", bling_id)
                if pedido_id:
                    await db.execute("""UPDATE compras_pedidos SET
                        numero=$1, fornecedor_id=$2, valor_total=$3, status=$4,
                        data_emissao=$5::date, data_entrega_prevista=$6::date, updated_at=NOW()
                        WHERE bling_id=$7""",
                        numero, fornecedor_id, valor_total, situacao,
                        data_emissao, data_prevista, bling_id)
                else:
                    await db.execute("""INSERT INTO compras_pedidos
                        (numero, fornecedor_id, valor_total, status, data_emissao,
                         data_entrega_prevista, bling_id)
                        VALUES ($1,$2,$3,$4,$5::date,$6::date,$7)""",
                        numero, fornecedor_id, valor_total, situacao,
                        data_emissao, data_prevista, bling_id)
                    pedido_id = await db.fetchval("SELECT id FROM compras_pedidos WHERE bling_id = $1", bling_id)

                await db.execute("DELETE FROM compras_itens WHERE pedido_id = $1", pedido_id)
                for item in detalhe.get("itens", []) or []:
                    await db.execute("""INSERT INTO compras_itens
                        (pedido_id, produto_codigo, descricao, quantidade, valor_unitario, valor_total)
                        VALUES ($1,$2,$3,$4,$5,$6)""",
                        pedido_id, item.get("codigo", ""), item.get("descricao", ""),
                        float(item.get("quantidade", 0) or 0), float(item.get("valor", 0) or 0),
                        float(item.get("quantidade", 0) or 0) * float(item.get("valor", 0) or 0))
                total += 1
            except Exception as e:
                erros.append(f"pedido {bling_id}: {e}")
                log(AGENT, f"Erro ao sincronizar pedido de compra {bling_id}: {e}")
        return {"sync": total, "erros": erros}

    try:
        return run_async(_go())
    except Exception as e:
        return {"error": str(e)}

def dashboard() -> dict:
    async def _go():
        db = await get_db()
        pendentes = await db.fetchval("SELECT COUNT(*) FROM compras_solicitacoes WHERE status = 'pendente'")
        pedidos_abertos = await db.fetchval("SELECT COUNT(*) FROM compras_pedidos WHERE status IN ('emitido','enviado')")
        total_recebido = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM compras_notas_entrada WHERE status = 'confirmada'")
        return {"pendentes": pendentes or 0, "pedidos_abertos": pedidos_abertos or 0, "total_recebido": float(total_recebido or 0)}
    try: return run_async(_go())
    except Exception as e: return {"pendentes":0,"pedidos_abertos":0,"total_recebido":0}
