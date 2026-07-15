"""Entidades SSOT — Unificacao Clientes, Fornecedores, Vendedores, Lojas + Eventos cross-module"""
from core import get_db, run_async, log, hoje
import datetime

AGENT = "Entidades SSOT"

def _ensure_tables():
    async def _go():
        db = await get_db()
        # ── FK columns nas tabelas existentes (criadas apenas se nao existirem) ──
        alteracoes = [
            # Clientes
            ("vendas_pedidos", "cliente_id INT REFERENCES cad_clientes(id)"),
            ("pdv_vendas", "cliente_id INT REFERENCES cad_clientes(id)"),
            ("fiscal_notas_fiscais", "cliente_id INT REFERENCES cad_clientes(id)"),
            # Fornecedores
            ("compras_pedidos", "fornecedor_id INT REFERENCES cad_fornecedores(id)"),
            ("compras_cotacoes", "fornecedor_id INT REFERENCES cad_fornecedores(id)"),
            ("compras_notas_entrada", "fornecedor_id INT REFERENCES cad_fornecedores(id)"),
            # Vendedores
            ("vendas_pedidos", "vendedor_id INT REFERENCES cad_vendedores(id)"),
            ("producao_ops", "vendedor_id INT REFERENCES cad_vendedores(id)"),
            # Lojas
            ("pdv_caixas", "loja_id INT REFERENCES lojas(id)"),
            ("producao_ops", "loja_id INT REFERENCES lojas(id)"),
            ("cad_clientes", "empresa_id INT REFERENCES cad_empresas(id)"),
            # Produto FK (catalogo central)
            ("vendas_itens", "produto_id INT REFERENCES catalogo_produtos(id)"),
            ("pdv_itens", "produto_id INT REFERENCES catalogo_produtos(id)"),
            ("producao_ops", "produto_id INT REFERENCES catalogo_produtos(id)"),
            ("compras_itens", "produto_id INT REFERENCES catalogo_produtos(id)"),
            ("fiscal_nfe_itens", "produto_id INT REFERENCES catalogo_produtos(id)"),
        ]
        for tabela, col_def in alteracoes:
            col_nome = col_def.split()[0]
            try:
                col_exists = await db.fetchval(
                    "SELECT column_name FROM information_schema.columns WHERE table_name=$1 AND column_name=$2",
                    tabela, col_nome)
                if not col_exists:
                    await db.execute(f"ALTER TABLE {tabela} ADD COLUMN {col_def}")
                    log(AGENT, f"FK adicionada: {tabela}.{col_nome}")
            except Exception as e:
                log(AGENT, f"FK skip {tabela}.{col_nome}: {e}")
    try: run_async(_go())
    except Exception as e: log(AGENT, f"Erro entidades: {e}")

_ensure_tables()

# ─────────────────────────────────────────────────────────
# Integracao #2: Clientes — visao unificada
# ─────────────────────────────────────────────────────────

def vincular_cliente_por_documento(tabela: str, registro_id: int) -> dict:
    """Tenta vincular um registro a um cad_clientes pelo documento (CNPJ/CPF)."""
    async def _go():
        db = await get_db()
        doc_col = {"vendas_pedidos": "cliente_documento", "fiscal_notas_fiscais": "contato_documento"}.get(tabela)
        if not doc_col: return {"error": "tabela nao suportada"}
        row = await db.fetchrow(f"SELECT {doc_col} FROM {tabela} WHERE id = $1", registro_id)
        if not row or not row[doc_col]: return {"error": "documento vazio"}
        doc = str(row[doc_col]).replace(".","").replace("/","").replace("-","").strip()
        cliente = await db.fetchrow("SELECT id FROM cad_clientes WHERE REPLACE(REPLACE(REPLACE(documento,'.',''),'/',''),'-','') = $1 LIMIT 1", doc)
        if not cliente: return {"vincular": False, "motivo": "cliente nao encontrado"}
        await db.execute(f"UPDATE {tabela} SET cliente_id = $1 WHERE id = $2", cliente["id"], registro_id)
        return {"vincular": True, "cliente_id": cliente["id"]}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def vincular_todos_clientes() -> dict:
    """Varre vendas_pedidos, pdv_vendas, fiscal_notas_fiscais e vincula por documento."""
    async def _go():
        db = await get_db()
        total = 0
        tabelas = [
            ("vendas_pedidos", "cliente_documento"),
            ("fiscal_notas_fiscais", "contato_documento"),
        ]
        for tab, doc_col in tabelas:
            rows = await db.fetch(f"SELECT id, {doc_col} FROM {tab} WHERE cliente_id IS NULL AND {doc_col} IS NOT NULL AND {doc_col} != '' LIMIT 1000")
            for r in rows:
                doc = str(r[doc_col]).replace(".","").replace("/","").replace("-","").strip()
                if not doc: continue
                cliente = await db.fetchrow("SELECT id FROM cad_clientes WHERE REPLACE(REPLACE(REPLACE(documento,'.',''),'/',''),'-','') = $1 LIMIT 1", doc)
                if cliente:
                    await db.execute(f"UPDATE {tab} SET cliente_id = $1 WHERE id = $2", cliente["id"], r["id"])
                    total += 1
        # PDV vendas: tentar vincular por nome do cliente
        pdv_rows = await db.fetch("SELECT id, cliente FROM pdv_vendas WHERE cliente_id IS NULL AND cliente IS NOT NULL AND cliente != '' LIMIT 500")
        for r in pdv_rows:
            nome = r["cliente"].strip().lower()
            cliente = await db.fetchrow("SELECT id FROM cad_clientes WHERE LOWER(nome) = $1 LIMIT 1", nome)
            if cliente:
                await db.execute("UPDATE pdv_vendas SET cliente_id = $1 WHERE id = $2", cliente["id"], r["id"])
                total += 1
        return {"vinculados": total}
    try: return run_async(_go())
    except: return {"vinculados": 0}

# ─────────────────────────────────────────────────────────
# Integracao #2b: Sync Contatos do Bling → cad_clientes
# ─────────────────────────────────────────────────────────

def sincronizar_contatos_bling(pagina: int = 1, limite: int = 100) -> dict:
    """Sync contatos do Bling para cad_clientes. Cria/atualiza clientes por documento ou nome."""
    from bling_erp import listar_contatos, get_access_token, get_auth_url
    token = get_access_token()
    if not token: return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}
    r = listar_contatos(pagina, limite)
    if r.get("error"): return r
    dados = r.get("data", [])
    if not dados: return {"sync": 0, "message": "sem dados"}
    async def _go():
        db = await get_db()
        total = 0
        for c in dados:
            try:
                doc = (c.get("numeroDocumento") or "").replace(".","").replace("/","").replace("-","").strip()
                nome = c.get("nome", "")
                email = c.get("email", "")
                telefone = c.get("telefone", "")
                tipo_pessoa = c.get("tipoPessoa", "F")
                existing = None
                if doc:
                    existing = await db.fetchrow("SELECT id FROM cad_clientes WHERE REPLACE(REPLACE(REPLACE(documento,'.',''),'/',''),'-','') = $1 LIMIT 1", doc)
                if existing:
                    await db.execute("""UPDATE cad_clientes SET nome=$1, email=$2, telefone=$3, tipo=$4, updated_at=NOW()
                        WHERE id=$5""", nome, email, telefone, "PJ" if tipo_pessoa == "J" else "PF", existing["id"])
                    total += 1
                else:
                    row = await db.fetchrow("""INSERT INTO cad_clientes (nome, tipo, documento, email, telefone, status)
                        VALUES ($1,$2,$3,$4,$5,'ativo') ON CONFLICT (documento) WHERE documento IS NOT NULL AND documento != ''
                        DO UPDATE SET nome=$1, email=$4, telefone=$5, updated_at=NOW() RETURNING id""",
                        nome, "PJ" if tipo_pessoa == "J" else "PF", c.get("numeroDocumento",""), email, telefone)
                    if row: total += 1
            except Exception as e:
                log(AGENT, f"Erro sync contato {c.get('nome')}: {e}")
        return {"sync": total}
    return run_async(_go())

# ─────────────────────────────────────────────────────────
# Integracao #3: Fornecedores — migrar compras_fornecedores → cad_fornecedores
# ─────────────────────────────────────────────────────────

def migrar_fornecedores_compras() -> dict:
    """Migra dados de compras_fornecedores para cad_fornecedores e atualiza FKs."""
    async def _go():
        db = await get_db()
        total = 0
        rows = await db.fetch("SELECT * FROM compras_fornecedores")
        for cf in rows:
            cf = dict(cf)
            doc = (cf.get("cnpj") or "").replace(".","").replace("/","").replace("-","").strip()
            # Buscar ou criar em cad_fornecedores
            existing = await db.fetchrow("SELECT id FROM cad_fornecedores WHERE REPLACE(REPLACE(REPLACE(documento,'.',''),'/',''),'-','') = $1 LIMIT 1", doc) if doc else None
            fid = existing["id"] if existing else None
            if not fid:
                row = await db.fetchrow(
                    "INSERT INTO cad_fornecedores (nome, tipo, documento, status) VALUES ($1, 'PJ', $2, $3) RETURNING id",
                    cf.get("nome",""), doc, cf.get("status","ativo"))
                fid = row["id"] if row else 0
            if fid:
                # Atualizar FKs em compras
                await db.execute("UPDATE compras_pedidos SET fornecedor_id = $1 WHERE fornecedor_id IS NULL AND id IN (SELECT id FROM compras_pedidos WHERE fornecedor_id = $2)", fid, cf["id"])
                # ponytail: atualiza cotacoes pelo id original do fornecedor
                try:
                    await db.execute("UPDATE compras_cotacoes SET fornecedor_id = $1 WHERE fornecedor_id = $2", fid, cf["id"])
                except: pass
                total += 1
        return {"migrados": total}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

# ─────────────────────────────────────────────────────────
# Integracao #4: Contas a Receber/Pagar unificadas
# ─────────────────────────────────────────────────────────

def migrar_contas_fiscal_para_financeiro() -> dict:
    """Migra fiscal_contas_receber_bling → fin_contas_receber e fiscal_contas_pagar_bling → fin_contas_pagar."""
    async def _go():
        db = await get_db()
        cr = await db.fetchval("SELECT COUNT(*) FROM fiscal_contas_receber_bling")
        cp = await db.fetchval("SELECT COUNT(*) FROM fiscal_contas_pagar_bling")
        # Adicionar colunas de origem nas tabelas financeiro
        for tab in ["fin_contas_receber", "fin_contas_pagar"]:
            for col, tipo in [("bling_id", "BIGINT"), ("origem", "VARCHAR(30) DEFAULT 'manual'")]:
                try:
                    exists = await db.fetchval("SELECT column_name FROM information_schema.columns WHERE table_name=$1 AND column_name=$2", tab, col)
                    if not exists:
                        await db.execute(f"ALTER TABLE {tab} ADD COLUMN {col} {tipo}")
                except: pass
        # Migrar contas a receber
        rows = await db.fetch("SELECT * FROM fiscal_contas_receber_bling")
        migrated_cr = 0
        for r in rows:
            r = dict(r)
            existing = await db.fetchval("SELECT id FROM fin_contas_receber WHERE bling_id = $1", r["bling_id"]) if r.get("bling_id") else None
            if not existing:
                await db.execute("""INSERT INTO fin_contas_receber (cliente, descricao, valor, vencimento, data_recebimento, status, forma_pagamento, bling_id, origem)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'bling')""",
                    r.get("contato_nome",""), r.get("descricao",""), float(r.get("valor",0) or 0),
                    r.get("vencimento"), r.get("data_recebimento"),
                    r.get("situacao","pendente"), r.get("forma_pagamento",""), r.get("bling_id"))
                migrated_cr += 1
        # Migrar contas a pagar
        rows = await db.fetch("SELECT * FROM fiscal_contas_pagar_bling")
        migrated_cp = 0
        for r in rows:
            r = dict(r)
            existing = await db.fetchval("SELECT id FROM fin_contas_pagar WHERE bling_id = $1", r["bling_id"]) if r.get("bling_id") else None
            if not existing:
                await db.execute("""INSERT INTO fin_contas_pagar (fornecedor, descricao, valor, vencimento, data_pagamento, status, forma_pagamento, bling_id, origem)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'bling')""",
                    r.get("fornecedor_nome",""), r.get("descricao",""), float(r.get("valor",0) or 0),
                    r.get("vencimento"), r.get("data_pagamento"),
                    r.get("situacao","pendente"), r.get("forma_pagamento",""), r.get("bling_id"))
                migrated_cp += 1
        return {"contas_receber_migradas": migrated_cr, "contas_pagar_migradas": migrated_cp, "origem_receber": cr, "origem_pagar": cp}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

# ─────────────────────────────────────────────────────────
# Integracao #5-13: Event Hooks
# ─────────────────────────────────────────────────────────

def ao_faturar_pedido(pedido_id: int) -> dict:
    """Orquestrador: quando um pedido e faturado, dispara todos os eventos downstream."""
    async def _go():
        db = await get_db()
        pedido = await db.fetchrow("SELECT * FROM vendas_pedidos WHERE id = $1", pedido_id)
        if not pedido: return {"error": "pedido nao encontrado"}
        resultados = {}
        # 5) Baixar estoque
        try:
            itens = await db.fetch("SELECT * FROM vendas_itens WHERE pedido_id = $1", pedido_id)
            for item in itens:
                item = dict(item)
                sku = item.get("sku","")
                qtd = float(item.get("quantidade",0) or 0)
                if sku and qtd > 0:
                    await db.execute("INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao) VALUES ($1, 'principal', -$2, NOW()) ON CONFLICT (sku, loja) DO UPDATE SET quantidade = estoque_lojas.quantidade - $2, data_atualizacao = NOW()", sku, qtd)
                    # Atualizar catalogo FK
                    from core.catalogo import buscar_por_sku_ou_criar
                    pid = buscar_por_sku_ou_criar(sku, item.get("descricao",""))
                    if pid:
                        await db.execute("UPDATE vendas_itens SET produto_id = $1 WHERE id = $2", pid, item["id"])
            resultados["estoque"] = "baixado"
        except Exception as e: resultados["estoque"] = f"erro: {e}"
        # 7) Gerar conta a receber (se pagamento a prazo)
        try:
            pagamentos = await db.fetch("SELECT * FROM vendas_pagamentos WHERE pedido_id = $1", pedido_id)
            total = float(pedido["total"] or 0)
            for pg in pagamentos:
                pg = dict(pg)
                forma = str(pg.get("forma","")).lower()
                if forma in ("boleto", "cartao", "crediario"):
                    parcelas = int(pg.get("parcelas", 1) or 1)
                    valor_parcela = round(float(pg.get("valor", total) or 0) / parcelas, 2)
                    for p in range(parcelas):
                        venc = (datetime.date.today() + datetime.timedelta(days=30*(p+1))).isoformat()
                        await db.execute(
                            "INSERT INTO fin_contas_receber (cliente, descricao, valor, vencimento, status, forma_pagamento, origem) VALUES ($1,$2,$3,$4,'pendente',$5,'venda')",
                            pedido["cliente"], f"Pedido #{pedido_id} parcela {p+1}/{parcelas}", valor_parcela, venc, forma)
            resultados["financeiro"] = "contas geradas"
        except Exception as e: resultados["financeiro"] = f"erro: {e}"
        # 9) Vincular cliente por documento
        try:
            vincular_cliente_por_documento("vendas_pedidos", pedido_id)
            resultados["cliente"] = "vinculado"
        except Exception as e: resultados["cliente"] = f"erro: {e}"
        # 19) Registrar no CRM (historico do cliente)
        try:
            if pedido["cliente_id"]:
                await db.execute("INSERT INTO cad_cliente_historico (cliente_id, descricao, valor_total) VALUES ($1, $2, $3)",
                    pedido["cliente_id"], f"Pedido #{pedido_id} faturado", pedido["total"])
                resultados["crm"] = "historico registrado"
        except Exception as e: resultados["crm"] = f"erro: {e}"
        return resultados
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def ao_receber_compra(recebimento_id: int) -> dict:
    """Quando uma compra e recebida: entrada no estoque + contas a pagar."""
    async def _go():
        db = await get_db()
        rec = await db.fetchrow("SELECT * FROM compras_recebimentos WHERE id = $1", recebimento_id)
        if not rec: return {"error": "recebimento nao encontrado"}
        pid = rec["pedido_id"]
        itens = await db.fetch("SELECT * FROM compras_itens WHERE pedido_id = $1", pid)
        resultados = {}
        # 10) Entrada no estoque
        try:
            for item in itens:
                item = dict(item)
                sku = item.get("produto_codigo","")
                qtd = float(item.get("quantidade",0) or 0)
                if sku and qtd > 0:
                    await db.execute("INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao) VALUES ($1, 'principal', $2, NOW()) ON CONFLICT (sku, loja) DO UPDATE SET quantidade = estoque_lojas.quantidade + $2, data_atualizacao = NOW()", sku, qtd)
                    from core.catalogo import buscar_por_sku_ou_criar
                    pid_cat = buscar_por_sku_ou_criar(sku, item.get("descricao",""))
                    if pid_cat:
                        await db.execute("UPDATE compras_itens SET produto_id = $1 WHERE id = $2", pid_cat, item["id"])
            resultados["estoque"] = "entrada"
        except Exception as e: resultados["estoque"] = f"erro: {e}"
        # 12) Contas a pagar
        try:
            nf = await db.fetchrow("SELECT * FROM compras_notas_entrada WHERE pedido_id = $1 ORDER BY id DESC LIMIT 1", pid)
            if nf:
                nf = dict(nf)
                pedido = await db.fetchrow("SELECT * FROM compras_pedidos WHERE id = $1", pid)
                fornecedor_nome = ""
                if pedido and pedido["fornecedor_id"]:
                    forn = await db.fetchrow("SELECT nome FROM cad_fornecedores WHERE id = $1", pedido["fornecedor_id"])
                    fornecedor_nome = forn["nome"] if forn else ""
                await db.execute(
                    "INSERT INTO fin_contas_pagar (fornecedor, descricao, valor, vencimento, status, forma_pagamento, origem) VALUES ($1,$2,$3,CURRENT_DATE+30,'pendente','boleto','compra')",
                    fornecedor_nome, f"NF {nf.get('numero_nf','')} Compra #{pid}", float(nf.get("valor",0) or 0))
                resultados["financeiro"] = "contas geradas"
        except Exception as e: resultados["financeiro"] = f"erro: {e}"
        return resultados
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def ao_finalizar_producao(op_id: int) -> dict:
    """Quando uma OP e finalizada: entrada do produto acabado no estoque + baixa de componentes."""
    async def _go():
        db = await get_db()
        op = await db.fetchrow("SELECT * FROM producao_ops WHERE id = $1", op_id)
        if not op: return {"error": "op nao encontrada"}
        resultados = {}
        # 8) Entrada do produto acabado
        try:
            sku = op["produto_codigo"]
            qtd = float(op["quantidade"] or 0)
            if sku and qtd > 0:
                await db.execute("INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao) VALUES ($1, 'producao', $2, NOW()) ON CONFLICT (sku, loja) DO UPDATE SET quantidade = estoque_lojas.quantidade + $2, data_atualizacao = NOW()", sku, qtd)
                from core.catalogo import buscar_por_sku_ou_criar
                pid = buscar_por_sku_ou_criar(sku, op.get("descricao",""))
                if pid:
                    await db.execute("UPDATE producao_ops SET produto_id = $1 WHERE id = $2", pid, op_id)
            resultados["estoque_acabado"] = "entrada"
        except Exception as e: resultados["estoque_acabado"] = f"erro: {e}"
        # 12) Baixa de componentes do BOM
        try:
            bom = await db.fetch("SELECT * FROM producao_bom WHERE op_id = $1", op_id)
            for comp in bom:
                comp = dict(comp)
                csku = comp["componente_codigo"]
                cqtd = float(comp["quantidade"] or 0)
                if csku and cqtd > 0:
                    await db.execute("INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao) VALUES ($1, 'producao', -$2, NOW()) ON CONFLICT (sku, loja) DO UPDATE SET quantidade = estoque_lojas.quantidade - $2, data_atualizacao = NOW()", csku, cqtd)
            resultados["consumo_componentes"] = "baixado"
        except Exception as e: resultados["consumo_componentes"] = f"erro: {e}"
        # 13) Custos no financeiro
        try:
            custos = await db.fetch("SELECT COALESCE(SUM(valor),0) as total FROM producao_custos WHERE op_id = $1", op_id)
            if custos:
                total = float(custos[0]["total"] or 0)
                mes = datetime.date.today().strftime("%Y-%m")
                await db.execute("INSERT INTO fin_dre (mes, descricao, valor, tipo, categoria) VALUES ($1,$2,$3,'despesa','producao') ON CONFLICT DO NOTHING",
                    mes, f"Custos OP #{op_id}", total)
                resultados["custos"] = "registrados"
        except Exception as e: resultados["custos"] = f"erro: {e}"
        return resultados
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def ao_fechar_caixa_pdv(caixa_id: int) -> dict:
    """Quando um caixa PDV e fechado: lancar no fluxo de caixa."""
    async def _go():
        db = await get_db()
        caixa = await db.fetchrow("SELECT * FROM pdv_caixas WHERE id = $1", caixa_id)
        if not caixa: return {"error": "caixa nao encontrado"}
        total_vendas = await db.fetchval("SELECT COALESCE(SUM(total),0) FROM pdv_vendas WHERE caixa_id = $1 AND status = 'finalizada'", caixa_id)
        sangrias = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM pdv_sangrias WHERE caixa_id = $1", caixa_id)
        suprimentos = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM pdv_suprimentos WHERE caixa_id = $1", caixa_id)
        hoje_str = datetime.date.today().isoformat()
        await db.execute("INSERT INTO fin_fluxo_caixa (data, descricao, tipo, valor, categoria) VALUES ($1,$2,'entrada',$3,'Vendas PDV')", hoje_str, f"Caixa #{caixa_id}", float(total_vendas or 0))
        if float(sangrias or 0) > 0:
            await db.execute("INSERT INTO fin_fluxo_caixa (data, descricao, tipo, valor, categoria) VALUES ($1,$2,'saida',$3,'Sangria PDV')", hoje_str, f"Sangria Caixa #{caixa_id}", float(sangrias or 0))
        if float(suprimentos or 0) > 0:
            await db.execute("INSERT INTO fin_fluxo_caixa (data, descricao, tipo, valor, categoria) VALUES ($1,$2,'entrada',$3,'Suprimento PDV')", hoje_str, f"Suprimento Caixa #{caixa_id}", float(suprimentos or 0))
        return {"total_vendas": float(total_vendas or 0), "sangrias": float(sangrias or 0), "suprimentos": float(suprimentos or 0)}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def ao_converter_lead(lead_id: int) -> dict:
    """Quando um lead CRM e convertido em cliente: cria cad_clientes e vincula."""
    async def _go():
        db = await get_db()
        lead = await db.fetchrow("SELECT * FROM crm_leads WHERE id = $1", lead_id)
        if not lead: return {"error": "lead nao encontrado"}
        doc = (lead.get("documento") or lead.get("cnpj") or "").replace(".","").replace("/","").replace("-","").strip()
        existing = await db.fetchrow("SELECT id FROM cad_clientes WHERE REPLACE(REPLACE(REPLACE(documento,'.',''),'/',''),'-','') = $1 LIMIT 1", doc) if doc else None
        cid = existing["id"] if existing else None
        if not cid:
            row = await db.fetchrow(
                "INSERT INTO cad_clientes (nome, tipo, documento, status) VALUES ($1, 'PF', $2, 'ativo') RETURNING id",
                lead["nome"], doc)
            cid = row["id"] if row else 0
        if cid:
            await db.execute("UPDATE crm_leads SET empresa_id = $1, status = 'convertido' WHERE id = $2", cid, lead_id)
        return {"cliente_id": cid}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def ao_converter_negociacao(negociacao_id: int) -> dict:
    """Quando uma negociacao CRM e ganha: cria vendas_pedidos."""
    async def _go():
        db = await get_db()
        neg = await db.fetchrow("SELECT * FROM crm_negociacoes WHERE id = $1", negociacao_id)
        if not neg: return {"error": "negociacao nao encontrada"}
        lead = await db.fetchrow("SELECT * FROM crm_leads WHERE id = $1", neg["lead_id"]) if neg.get("lead_id") else None
        cliente_nome = lead["nome"] if lead else neg.get("titulo","")
        cliente_id = lead.get("empresa_id") if lead else None
        row = await db.fetchrow(
            "INSERT INTO vendas_pedidos (cliente, cliente_id, total, status, data, marketplace, origem) VALUES ($1,$2,$3,'aberto',CURRENT_DATE,'manual','crm') RETURNING id",
            cliente_nome, cliente_id, float(neg.get("valor",0) or 0))
        vid = row["id"] if row else 0
        return {"pedido_id": vid}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

# ─────────────────────────────────────────────────────────
# Integracao #16: Fiscal Obrigacoes → Alertas
# ─────────────────────────────────────────────────────────

def gerar_alertas_obrigacoes() -> dict:
    """Gera alertas para obrigacoes vencendo hoje e atrasadas."""
    async def _go():
        db = await get_db()
        vencendo = await db.fetch("SELECT * FROM fiscal_obrigacoes WHERE data_vencimento = CURRENT_DATE AND status = 'pendente'")
        atrasadas = await db.fetch("SELECT * FROM fiscal_obrigacoes WHERE data_vencimento < CURRENT_DATE AND status = 'pendente'")
        return {"vencendo_hoje": len(vencendo), "atrasadas": len(atrasadas),
            "alertas": [dict(r) for r in (vencendo + atrasadas)]}
    try: return run_async(_go())
    except: return {"vencendo_hoje": 0, "atrasadas": 0, "alertas": []}

# ─────────────────────────────────────────────────────────
# Integracao #17: Pipeline completo do Webhook Bling
# ─────────────────────────────────────────────────────────

def processar_webhook_bling_completo(evento: str, payload: dict) -> dict:
    """Processamento completo de webhook Bling com todos os downstreams."""
    from bling_erp import processar_evento_webhook
    base = processar_evento_webhook(evento, payload)
    resultados = {"base": base}
    try:
        if evento.startswith("pedido") or evento.startswith("order"):
            async def _go():
                db = await get_db()
                bling_id = (payload.get("pedido", payload)).get("id")
                if bling_id:
                    vid = await db.fetchval("SELECT id FROM vendas_pedidos WHERE bling_id = $1", bling_id)
                    if vid:
                        r = ao_faturar_pedido(vid)
                        resultados["downstream"] = r
            run_async(_go())
    except Exception as e:
        resultados["downstream"] = {"error": str(e)}
    return resultados

# ─────────────────────────────────────────────────────────
# Integracao #18: Event Bus
# ─────────────────────────────────────────────────────────

def publicar_evento(tipo: str, entidade: str, entidade_id: int, payload: dict = None) -> dict:
    """Publica um evento no autom_eventos para processamento assincrono."""
    import json
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "INSERT INTO autom_eventos (nome, gatilho, origem, destino, regras, ativo) VALUES ($1,$2,$3,$4,$5::jsonb,true) RETURNING id",
            f"{tipo}_{entidade}_{entidade_id}", tipo, entidade, "*", json.dumps(payload or {}, ensure_ascii=False))
        return {"evento_id": row["id"] if row else 0}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def processar_eventos_pendentes(limit: int = 10) -> dict:
    """Processa eventos pendentes da fila autom_eventos."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM autom_eventos WHERE ativo = true ORDER BY id LIMIT $1", limit)
        processados = 0
        for ev in rows:
            ev = dict(ev)
            try:
                gatilho = ev.get("gatilho","")
                origem = ev.get("origem","")
                if gatilho == "venda.faturada":
                    pedido_id = (ev.get("regras") or {}).get("pedido_id")
                    if pedido_id: ao_faturar_pedido(pedido_id)
                elif gatilho == "compra.recebida":
                    rec_id = (ev.get("regras") or {}).get("recebimento_id")
                    if rec_id: ao_receber_compra(rec_id)
                elif gatilho == "producao.finalizada":
                    op_id = (ev.get("regras") or {}).get("op_id")
                    if op_id: ao_finalizar_producao(op_id)
                await db.execute("UPDATE autom_eventos SET ativo = false, execucoes = COALESCE(execucoes,0) + 1 WHERE id = $1", ev["id"])
                processados += 1
            except Exception as e:
                log(AGENT, f"Erro evento {ev['id']}: {e}")
        return {"processados": processados, "total": len(rows)}
    try: return run_async(_go())
    except: return {"processados": 0, "total": 0}
