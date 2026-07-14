import os
path = r"D:\JORGE CHARME E LEON\SISTEMAS\N8N AUTOMACOES\hermes_agents\core\fiscal.py"
content = '''"""Fiscal Core — Tributos, Obrigacoes, Notas Fiscais, Integracao Bling"""
from core import get_db, run_async, log, hoje

AGENT = "Fiscal Core"

TABLES = ["tributos","obrigacoes","notas_fiscais","nfe_itens","impostos_nota","contas_receber_bling","contas_pagar_bling"]

def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS fiscal_tributos (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL, sigla VARCHAR(10),
            aliquota DECIMAL(8,4) DEFAULT 0, aliquota_interestadual DECIMAL(8,4) DEFAULT 0,
            regime VARCHAR(30) DEFAULT 'normal', tipo VARCHAR(30) DEFAULT 'federal',
            incidencia VARCHAR(100), base_calculo VARCHAR(200),
            fato_gerador TEXT, contribuinte VARCHAR(100), observacoes TEXT,
            ativo BOOLEAN DEFAULT true, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fiscal_obrigacoes (
            id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL, sigla VARCHAR(15),
            descricao TEXT, periodicidade VARCHAR(30) DEFAULT 'mensal',
            data_vencimento DATE, competencia VARCHAR(7),
            orgao VARCHAR(100), regime VARCHAR(30) DEFAULT 'normal',
            status VARCHAR(30) DEFAULT 'pendente', responsavel VARCHAR(100),
            multa_por_atraso DECIMAL(12,2) DEFAULT 0, observacoes TEXT,
            created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fiscal_notas_fiscais (
            id SERIAL PRIMARY KEY, numero VARCHAR(30) NOT NULL, serie VARCHAR(5) DEFAULT '1',
            modelo VARCHAR(5) DEFAULT '55', chave_acesso VARCHAR(50),
            tipo VARCHAR(20) DEFAULT 'saida', data_emissao DATE, data_operacao DATE,
            natureza_operacao VARCHAR(200), cfop VARCHAR(5),
            contato_nome VARCHAR(200), contato_documento VARCHAR(20),
            valor_nf DECIMAL(12,2) DEFAULT 0, valor_produtos DECIMAL(12,2) DEFAULT 0,
            valor_frete DECIMAL(12,2) DEFAULT 0, valor_seguro DECIMAL(12,2) DEFAULT 0,
            valor_desconto DECIMAL(12,2) DEFAULT 0, valor_outros DECIMAL(12,2) DEFAULT 0,
            base_icms DECIMAL(12,2) DEFAULT 0, valor_icms DECIMAL(12,2) DEFAULT 0,
            base_icms_st DECIMAL(12,2) DEFAULT 0, valor_icms_st DECIMAL(12,2) DEFAULT 0,
            valor_ipi DECIMAL(12,2) DEFAULT 0, valor_pis DECIMAL(12,2) DEFAULT 0,
            valor_cofins DECIMAL(12,2) DEFAULT 0, valor_iss DECIMAL(12,2) DEFAULT 0,
            valor_ii DECIMAL(12,2) DEFAULT 0, valor_ir DECIMAL(12,2) DEFAULT 0,
            valor_csll DECIMAL(12,2) DEFAULT 0, valor_inss DECIMAL(12,2) DEFAULT 0,
            valor_total_tributos DECIMAL(12,2) DEFAULT 0,
            status VARCHAR(30) DEFAULT 'emitida', loja_id INT,
            xml_url VARCHAR(500), danfe_url VARCHAR(500),
            bling_id BIGINT, sincronizado_em TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fiscal_nfe_itens (
            id SERIAL PRIMARY KEY, nota_id INT REFERENCES fiscal_notas_fiscais(id),
            numero_item INT DEFAULT 1, codigo VARCHAR(50), descricao VARCHAR(200),
            ncm VARCHAR(10), cest VARCHAR(10), cfop VARCHAR(5),
            unidade VARCHAR(10) DEFAULT 'UN', quantidade DECIMAL(12,4) DEFAULT 0,
            valor_unitario DECIMAL(12,4) DEFAULT 0, valor_total DECIMAL(12,2) DEFAULT 0,
            valor_frete DECIMAL(12,2) DEFAULT 0, valor_desconto DECIMAL(12,2) DEFAULT 0,
            base_icms DECIMAL(12,2) DEFAULT 0, valor_icms DECIMAL(12,2) DEFAULT 0,
            aliquota_icms DECIMAL(8,4) DEFAULT 0,
            base_icms_st DECIMAL(12,2) DEFAULT 0, valor_icms_st DECIMAL(12,2) DEFAULT 0,
            valor_ipi DECIMAL(12,2) DEFAULT 0, valor_pis DECIMAL(12,2) DEFAULT 0,
            valor_cofins DECIMAL(12,2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fiscal_impostos_nota (
            id SERIAL PRIMARY KEY, nota_id INT REFERENCES fiscal_notas_fiscais(id),
            tributo_id INT REFERENCES fiscal_tributos(id),
            nome VARCHAR(100), sigla VARCHAR(10),
            base_calculo DECIMAL(12,2) DEFAULT 0, aliquota DECIMAL(8,4) DEFAULT 0,
            valor DECIMAL(12,2) DEFAULT 0, retido BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fiscal_contas_receber_bling (
            id SERIAL PRIMARY KEY, bling_id BIGINT,
            numero VARCHAR(50), descricao VARCHAR(200),
            contato_nome VARCHAR(200), contato_documento VARCHAR(20),
            valor DECIMAL(12,2) DEFAULT 0, valor_pago DECIMAL(12,2) DEFAULT 0,
            vencimento DATE, data_recebimento DATE, data_emissao DATE,
            situacao VARCHAR(30) DEFAULT 'pendente', forma_pagamento VARCHAR(50),
            portador VARCHAR(100), categoria VARCHAR(100),
            data_pagamento DATE, competencia VARCHAR(7),
            sincronizado_em TIMESTAMP DEFAULT NOW(), created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fiscal_contas_pagar_bling (
            id SERIAL PRIMARY KEY, bling_id BIGINT,
            numero VARCHAR(50), descricao VARCHAR(200),
            fornecedor_nome VARCHAR(200), fornecedor_documento VARCHAR(20),
            valor DECIMAL(12,2) DEFAULT 0, valor_pago DECIMAL(12,2) DEFAULT 0,
            vencimento DATE, data_pagamento DATE, data_emissao DATE,
            situacao VARCHAR(30) DEFAULT 'pendente', forma_pagamento VARCHAR(50),
            portador VARCHAR(100), categoria VARCHAR(100),
            competencia VARCHAR(7),
            sincronizado_em TIMESTAMP DEFAULT NOW(), created_at TIMESTAMP DEFAULT NOW()
        )""")
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro tabelas fiscal: {e}")

_ensure_tables()

# ── CRUD ──

def _list(t: str, cols="*", order="id DESC", limit=500) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"SELECT {cols} FROM {t} ORDER BY {order} LIMIT {limit}")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"list {t}: {e}"); return []

def _get(t: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"SELECT * FROM {t} WHERE id = $1", id)
        return dict(row) if row else {"error":"not found"}
    try: return run_async(_go())
    except Exception as e: return {"error":str(e)}

def _create(t: str, d: dict) -> dict:
    keys = list(d.keys()); vals = list(d.values())
    ph = ", ".join(f"${i+1}" for i in range(len(keys)))
    cols = ", ".join(keys)
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"INSERT INTO {t} ({cols}) VALUES ({ph}) RETURNING *", *vals)
        return dict(row) if row else {"error":"insert failed"}
    try: return run_async(_go())
    except Exception as e: return {"error":str(e)}

def _update(t: str, id: int, d: dict) -> dict:
    sets = ", ".join(f"{k}=${i+1}" for i,k in enumerate(d.keys()))
    vals = list(d.values())+[id]
    async def _go():
        db = await get_db()
        row = await db.fetchrow(f"UPDATE {t} SET {sets} WHERE id=${len(vals)} RETURNING *", *vals)
        return dict(row) if row else {"error":"not found"}
    try: return run_async(_go())
    except Exception as e: return {"error":str(e)}

def _delete(t: str, id: int) -> dict:
    async def _go():
        db = await get_db()
        await db.execute(f"DELETE FROM {t} WHERE id=$1", id)
        return {"success":True}
    try: run_async(_go()); return {"success":True}
    except Exception as e: return {"error":str(e)}

def list(t: str): return _list(f"fiscal_{t}")
def get(t: str, i: int): return _get(f"fiscal_{t}", i)
def create(t: str, d: dict): return _create(f"fiscal_{t}", d)
def update(t: str, i: int, d: dict): return _update(f"fiscal_{t}", i, d)
def delete(t: str, i: int): return _delete(f"fiscal_{t}", i)

# ── Tributos ──

def calcular_tributos_nota(nota_id: int) -> dict:
    async def _go():
        db = await get_db()
        nota = await db.fetchrow("SELECT * FROM fiscal_notas_fiscais WHERE id = $1", nota_id)
        if not nota: return {"error": "nota nao encontrada"}
        tributos = await db.fetch("SELECT * FROM fiscal_tributos WHERE ativo = true")
        total = 0
        calculated = []
        for trib in tributos:
            t = dict(trib)
            base = float(nota["valor_produtos"] or 0)
            aliq = float(t["aliquota"] or 0)
            valor = round(base * aliq / 100, 2)
            total += valor
            calculated.append({"nome": t["nome"], "sigla": t["sigla"], "aliquota_pct": aliq, "valor": valor})
        return {"nota_id": nota_id, "base_calculo": float(nota["valor_produtos"] or 0), "tributos": calculated, "total_tributos": round(total, 2)}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

# ── Obrigacoes ──

def obrigacoes_proximas(dias: int = 30) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT * FROM fiscal_obrigacoes WHERE data_vencimento BETWEEN CURRENT_DATE AND CURRENT_DATE + $1
            ORDER BY data_vencimento""", dias)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def obrigacoes_atrasadas() -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT * FROM fiscal_obrigacoes WHERE data_vencimento < CURRENT_DATE AND status = 'pendente'
            ORDER BY data_vencimento""")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def baixar_obrigacao(id: int) -> dict:
    return update("obrigacoes", id, {"status": "entregue"})

# ── Dashboard ──

def dashboard() -> dict:
    async def _go():
        db = await get_db()
        nfs_mes = await db.fetchval("SELECT COUNT(*) FROM fiscal_notas_fiscais WHERE DATE_TRUNC('month', COALESCE(data_emissao, created_at)) = DATE_TRUNC('month', CURRENT_DATE)")
        nfs_total = await db.fetchval("SELECT COUNT(*) FROM fiscal_notas_fiscais")
        valor_mes = await db.fetchval("SELECT COALESCE(SUM(valor_nf),0) FROM fiscal_notas_fiscais WHERE DATE_TRUNC('month', COALESCE(data_emissao, created_at)) = DATE_TRUNC('month', CURRENT_DATE)")
        obrigacoes_pendentes = await db.fetchval("SELECT COUNT(*) FROM fiscal_obrigacoes WHERE status = 'pendente'")
        obrigacoes_atrasadas = await db.fetchval("SELECT COUNT(*) FROM fiscal_obrigacoes WHERE data_vencimento < CURRENT_DATE AND status = 'pendente'")
        tributos_ativos = await db.fetchval("SELECT COUNT(*) FROM fiscal_tributos WHERE ativo = true")
        receber_total = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fiscal_contas_receber_bling WHERE situacao = 'pendente'")
        pagar_total = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fiscal_contas_pagar_bling WHERE situacao = 'pendente'")
        return {
            "nfs_mes": nfs_mes or 0, "nfs_total": nfs_total or 0,
            "valor_mes": float(valor_mes or 0),
            "obrigacoes_pendentes": obrigacoes_pendentes or 0,
            "obrigacoes_atrasadas": obrigacoes_atrasadas or 0,
            "tributos_ativos": tributos_ativos or 0,
            "contas_receber_pendentes": float(receber_total or 0),
            "contas_pagar_pendentes": float(pagar_total or 0),
        }
    try: return run_async(_go())
    except: return {"nfs_mes":0,"nfs_total":0,"valor_mes":0,"obrigacoes_pendentes":0,"obrigacoes_atrasadas":0,"tributos_ativos":0,"contas_receber_pendentes":0,"contas_pagar_pendentes":0}

# ── Bling Sync ──

def sincronizar_notas_fiscais_bling(pagina: int = 1, limite: int = 100) -> dict:
    from bling_erp import listar_notas_fiscais as bling_nfe, get_access_token, get_auth_url
    token = get_access_token()
    if not token: return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}
    r = bling_nfe(pagina, limite)
    if r.get("error"): return r
    dados = r.get("data", [])
    if not dados: return {"sync": 0, "message": "sem dados"}
    async def _go():
        db = await get_db()
        total = 0
        for nf in dados:
            try:
                bling_id = nf.get("id")
                if not bling_id: continue
                existing = await db.fetchval("SELECT id FROM fiscal_notas_fiscais WHERE bling_id = $1", bling_id)
                numero = str(nf.get("numero", ""))
                chave = nf.get("chaveAcesso", "")
                contato = nf.get("contato", {}) or {}
                natureza = nf.get("naturezaOperacao", {}) or {}
                loja = nf.get("loja", {}) or {}
                transporte = nf.get("transporte", {}) or {}
                volumes = transporte.get("volumes", []) or []
                total_frete = sum(float(v.get("fretePorConta", 0) or 0) for v in volumes)
                data_emissao = (nf.get("dataEmissao") or "")[:10] or None
                data_operacao = (nf.get("dataOperacao") or "")[:10] or None
                valor_nf = float(nf.get("total", 0) or 0)
                valor_produtos = float(nf.get("totalProdutos", 0) or 0)
                if existing:
                    await db.execute("""UPDATE fiscal_notas_fiscais SET
                        numero=$1, chave_acesso=$2, data_emissao=$3::date, data_operacao=$4::date,
                        contato_nome=$5, contato_documento=$6, natureza_operacao=$7,
                        valor_nf=$8, valor_produtos=$9, valor_frete=$10, status=$11,
                        cfop=$12, loja_id=$13, sincronizado_em=NOW()
                        WHERE bling_id=$14""",
                        numero, chave, data_emissao, data_operacao,
                        contato.get("nome",""), contato.get("numeroDocumento",""),
                        natureza.get("descricao",""), valor_nf, valor_produtos, total_frete,
                        {1:"emitida",2:"cancelada",3:"inutilizada",4:"denegada"}.get(nf.get("situacao",1),"emitida"),
                        natureza.get("cfop",""), loja.get("id"), bling_id)
                else:
                    await db.execute("""INSERT INTO fiscal_notas_fiscais
                        (numero, modelo, chave_acesso, tipo, data_emissao, data_operacao,
                         natureza_operacao, cfop, contato_nome, contato_documento,
                         valor_nf, valor_produtos, valor_frete, status, loja_id, bling_id, sincronizado_em)
                        VALUES ($1,$2,$3,$4,$5::date,$6::date,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,NOW())""",
                        numero, str(nf.get("modelo","55")), chave,
                        "saida" if nf.get("tipo",0) == 0 else "entrada",
                        data_emissao, data_operacao,
                        natureza.get("descricao",""), natureza.get("cfop",""),
                        contato.get("nome",""), contato.get("numeroDocumento",""),
                        valor_nf, valor_produtos, total_frete,
                        {1:"emitida",2:"cancelada",3:"inutilizada",4:"denegada"}.get(nf.get("situacao",1),"emitida"),
                        loja.get("id"), bling_id)
                # Sync itens
                nota_id = await db.fetchval("SELECT id FROM fiscal_notas_fiscais WHERE bling_id = $1", bling_id)
                if nota_id:
                    itens = nf.get("itens", []) or []
                    if itens and not existing:
                        for idx, item in enumerate(itens, 1):
                            await db.execute("""INSERT INTO fiscal_nfe_itens
                                (nota_id, numero_item, codigo, descricao, ncm, cfop, unidade,
                                 quantidade, valor_unitario, valor_total, base_icms, valor_icms, aliquota_icms)
                                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                                nota_id, idx,
                                item.get("codigo",""), item.get("descricao",""),
                                item.get("ncm",""), item.get("cfop",""),
                                item.get("unidade","UN"),
                                float(item.get("quantidade",0) or 0),
                                float(item.get("valorUnitario",0) or 0),
                                float(item.get("valorTotal",0) or 0),
                                float(item.get("baseICMS",0) or 0),
                                float(item.get("valorICMS",0) or 0),
                                float(item.get("aliquotaICMS",0) or 0))
                total += 1
            except Exception as e:
                log(AGENT, f"Erro sync NF {nf.get('numero')}: {e}")
        return {"sync": total}
    return run_async(_go())

def sincronizar_contas_receber_bling(pagina: int = 1, limite: int = 100) -> dict:
    from bling_erp import listar_contas_receber as bling_cr, get_access_token, get_auth_url
    token = get_access_token()
    if not token: return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}
    r = bling_cr(pagina, limite)
    if r.get("error"): return r
    dados = r.get("data", [])
    if not dados: return {"sync": 0, "message": "sem dados"}
    async def _go():
        db = await get_db()
        total = 0
        for cr in dados:
            try:
                bling_id = cr.get("id")
                if not bling_id: continue
                existing = await db.fetchval("SELECT id FROM fiscal_contas_receber_bling WHERE bling_id = $1", bling_id)
                contato = cr.get("contato", {}) or {}
                vencimento = (cr.get("vencimento") or cr.get("dataVencimento") or "")[:10] or None
                data_emissao = (cr.get("dataEmissao") or "")[:10] or None
                data_recebimento = (cr.get("dataRecebimento") or cr.get("dataPagamento") or "")[:10] or None
                if existing:
                    await db.execute("""UPDATE fiscal_contas_receber_bling SET
                        numero=$1, descricao=$2, contato_nome=$3, contato_documento=$4,
                        valor=$5, valor_pago=$6, vencimento=$7::date, data_recebimento=$8::date,
                        situacao=$9, forma_pagamento=$10, categoria=$11, sincronizado_em=NOW()
                        WHERE bling_id=$12""",
                        str(cr.get("numero","")), cr.get("descricao",""),
                        contato.get("nome",""), contato.get("numeroDocumento",""),
                        float(cr.get("valor",0) or 0), float(cr.get("valorPago",0) or 0),
                        vencimento, data_recebimento,
                        str(cr.get("situacao","pendente")), cr.get("formaPagamento",""),
                        cr.get("categoria",""), bling_id)
                else:
                    await db.execute("""INSERT INTO fiscal_contas_receber_bling
                        (bling_id, numero, descricao, contato_nome, contato_documento,
                         valor, valor_pago, vencimento, data_recebimento, data_emissao,
                         situacao, forma_pagamento, categoria, sincronizado_em)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8::date,$9::date,$10::date,$11,$12,$13,NOW())""",
                        bling_id, str(cr.get("numero","")), cr.get("descricao",""),
                        contato.get("nome",""), contato.get("numeroDocumento",""),
                        float(cr.get("valor",0) or 0), float(cr.get("valorPago",0) or 0),
                        vencimento, data_recebimento, data_emissao,
                        str(cr.get("situacao","pendente")), cr.get("formaPagamento",""),
                        cr.get("categoria",""))
                total += 1
            except Exception as e:
                log(AGENT, f"Erro sync CR: {e}")
        return {"sync": total}
    return run_async(_go())

def sincronizar_contas_pagar_bling(pagina: int = 1, limite: int = 100) -> dict:
    from bling_erp import _request as bling_request, get_access_token, get_auth_url
    token = get_access_token()
    if not token: return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}
    r = bling_request("contas/pagar", {"pagina": pagina, "limite": limite})
    if r.get("error"): return r
    dados = r.get("data", [])
    if not dados: return {"sync": 0, "message": "sem dados"}
    async def _go():
        db = await get_db()
        total = 0
        for cp in dados:
            try:
                bling_id = cp.get("id")
                if not bling_id: continue
                existing = await db.fetchval("SELECT id FROM fiscal_contas_pagar_bling WHERE bling_id = $1", bling_id)
                fornecedor = cp.get("fornecedor", cp.get("contato", {})) or {}
                vencimento = (cp.get("vencimento") or cp.get("dataVencimento") or "")[:10] or None
                data_emissao = (cp.get("dataEmissao") or "")[:10] or None
                data_pagamento = (cp.get("dataPagamento") or "")[:10] or None
                if existing:
                    await db.execute("""UPDATE fiscal_contas_pagar_bling SET
                        numero=$1, descricao=$2, fornecedor_nome=$3, fornecedor_documento=$4,
                        valor=$5, valor_pago=$6, vencimento=$7::date, data_pagamento=$8::date,
                        situacao=$9, forma_pagamento=$10, categoria=$11, sincronizado_em=NOW()
                        WHERE bling_id=$12""",
                        str(cp.get("numero","")), cp.get("descricao",""),
                        fornecedor.get("nome",""), fornecedor.get("numeroDocumento",""),
                        float(cp.get("valor",0) or 0), float(cp.get("valorPago",0) or 0),
                        vencimento, data_pagamento,
                        str(cp.get("situacao","pendente")), cp.get("formaPagamento",""),
                        cp.get("categoria",""), bling_id)
                else:
                    await db.execute("""INSERT INTO fiscal_contas_pagar_bling
                        (bling_id, numero, descricao, fornecedor_nome, fornecedor_documento,
                         valor, valor_pago, vencimento, data_pagamento, data_emissao,
                         situacao, forma_pagamento, categoria, sincronizado_em)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8::date,$9::date,$10::date,$11,$12,$13,NOW())""",
                        bling_id, str(cp.get("numero","")), cp.get("descricao",""),
                        fornecedor.get("nome",""), fornecedor.get("numeroDocumento",""),
                        float(cp.get("valor",0) or 0), float(cp.get("valorPago",0) or 0),
                        vencimento, data_pagamento, data_emissao,
                        str(cp.get("situacao","pendente")), cp.get("formaPagamento",""),
                        cp.get("categoria",""))
                total += 1
            except Exception as e:
                log(AGENT, f"Erro sync CP: {e}")
        return {"sync": total}
    return run_async(_go())

def sincronizar_tudo_bling() -> dict:
    r1 = sincronizar_notas_fiscais_bling()
    r2 = sincronizar_contas_receber_bling()
    r3 = sincronizar_contas_pagar_bling()
    return {"notas_fiscais": r1.get("sync",0), "contas_receber": r2.get("sync",0), "contas_pagar": r3.get("sync",0)}

# ── Seed ──

def _seed():
    async def _go():
        db = await get_db()
        count = await db.fetchval("SELECT COUNT(*) FROM fiscal_tributos")
        if count == 0:
            await db.execute("""INSERT INTO fiscal_tributos (nome, sigla, aliquota, tipo, regime, incidencia) VALUES
                ('ICMS','ICMS',18,'estadual','normal','Circulacao de mercadorias e servicos'),
                ('IPI','IPI',10,'federal','normal','Produtos industrializados'),
                ('PIS','PIS',1.65,'federal','nao_cumulativo','Faturamento mensal'),
                ('COFINS','COFINS',7.6,'federal','nao_cumulativo','Faturamento mensal'),
                ('ISS','ISS',5,'municipal','normal','Prestacao de servicos'),
                ('CSLL','CSLL',9,'federal','lucro_real','Lucro liquido'),
                ('IRPJ','IRPJ',15,'federal','lucro_real','Lucro liquido'),
                ('ICMS-ST','ICMS-ST',18,'estadual','normal','Substituicao tributaria'),
                ('Simples Nacional','SN',6,'federal','simples_nacional','Receita bruta'),
                ('PIS/COFINS Monofasico','PIS/COFINS-M',0,'federal','monofasico','Produtos especificos')""")
        count = await db.fetchval("SELECT COUNT(*) FROM fiscal_obrigacoes")
        if count == 0:
            hoje = __import__('datetime').date.today()
            await db.execute("""INSERT INTO fiscal_obrigacoes (nome, sigla, descricao, periodicidade, data_vencimento, orgao, regime, status) VALUES
                ('SPED Fiscal','SPED','Escrituracao Fiscal Digital','mensal',
                    $1::date + interval '15 days','SEFAZ','normal','pendente'),
                ('EFD-Contribuicoes','EFD','Escrituracao Fiscal Digital de PIS/COFINS','mensal',
                    $1::date + interval '10 days','Receita Federal','normal','pendente'),
                ('DCTF','DCTF','Declaracao de Debitos e Creditos Tributarios','mensal',
                    $1::date + interval '15 days','Receita Federal','normal','pendente'),
                ('DAS','DAS','Documento de Arrecadacao do Simples','mensal',
                    $1::date, 'Receita Federal','simples_nacional','pendente'),
                ('GIA','GIA','Guia de Informacao e Apuracao do ICMS','mensal',
                    $1::date + interval '14 days','SEFAZ','normal','pendente'),
                ('SINTEGRA','SINTEGRA','Sistema Integrado de Informacoes','mensal',
                    $1::date + interval '12 days','SEFAZ','normal','pendente')""",
                    hoje)
    try: run_async(_go())
    except Exception as e: log(AGENT, f"Erro seed fiscal: {e}")

_seed()
'''

with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
print(f"Fiscal Core: {len(content)} bytes")
