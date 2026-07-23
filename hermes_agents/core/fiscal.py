"""Fiscal Core — Tributos, Obrigacoes, Notas Fiscais, Integracao Bling"""
import time
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
        try: await db.execute("ALTER TABLE fiscal_notas_fiscais ADD COLUMN IF NOT EXISTS dados_brutos_bling JSONB")
        except Exception as e: pass
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

# ── Listagem com filtro de data ──

DATE_FIELDS = {"notas_fiscais": "data_emissao", "obrigacoes": "data_vencimento", "contas_receber_bling": "vencimento", "contas_pagar_bling": "vencimento"}

def _list_filtered(t: str, date_field: str, data_inicio: str = "", data_fim: str = "", dias: int = 0, order: str = "id DESC", limit: int = 500) -> list:
    async def _go():
        db = await get_db()
        where = []
        params = []
        p = 1
        if data_inicio:
            where.append(f"{date_field} >= ${p}::date"); params.append(data_inicio); p += 1
        if data_fim:
            where.append(f"{date_field} <= ${p}::date"); params.append(data_fim); p += 1
        if dias > 0 and not (data_inicio or data_fim):
            where.append(f"{date_field} >= CURRENT_DATE - ${p}"); params.append(dias); p += 1
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        rows = await db.fetch(f"SELECT * FROM {t} {clause} ORDER BY {order} LIMIT {limit}", *params)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: log(AGENT, f"list_filtered {t}: {e}"); return []

def listar_filtrado(tabela: str, data_inicio: str = "", data_fim: str = "", dias: int = 0) -> dict:
    t = f"fiscal_{tabela}"
    field = DATE_FIELDS.get(tabela, "created_at")
    return {"data": _list_filtered(t, field, data_inicio, data_fim, dias)}

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
        receber_total = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fin_contas_receber WHERE status = 'pendente' AND origem = 'bling'")
        pagar_total = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fin_contas_pagar WHERE status = 'pendente' AND origem = 'bling'")
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
    except Exception as e: return {"nfs_mes":0,"nfs_total":0,"valor_mes":0,"obrigacoes_pendentes":0,"obrigacoes_atrasadas":0,"tributos_ativos":0,"contas_receber_pendentes":0,"contas_pagar_pendentes":0}

# ── Bling Sync ──

def _num(*candidatos) -> float:
    """Retorna o primeiro valor numerico nao-None entre varios caminhos possiveis de chave —
    usado para tolerar variacoes de nomenclatura da API do Bling sem quebrar a sincronizacao."""
    for c in candidatos:
        if c is not None:
            try: return float(c)
            except (TypeError, ValueError): continue
    return 0.0

def _mapear_nfe_detalhe(nf: dict) -> dict:
    """Mapeia o payload de detalhe do Bling (GET /nfe/{id}) para as colunas de
    fiscal_notas_fiscais. Os valores de tributos usam multiplas chaves candidatas
    (tributos.totalX / valorX no nivel raiz) pois o formato exato do bloco de impostos
    na resposta do Bling nao pode ser confirmado sem uma nota real ao vivo — o JSON
    bruto e' preservado em dados_brutos_bling para correcao posterior se necessario."""
    contato = nf.get("contato", {}) or {}
    natureza = nf.get("naturezaOperacao", {}) or {}
    loja = nf.get("loja", {}) or {}
    transporte = nf.get("transporte", {}) or {}
    volumes = transporte.get("volumes", []) or []
    tributos = nf.get("tributos", {}) or {}

    total_frete = _num(nf.get("valorFrete"), transporte.get("frete"),
                        sum(_num(v.get("fretePorConta")) for v in volumes) or None)

    return {
        "numero": str(nf.get("numero", "")),
        "chave_acesso": nf.get("chaveAcesso", ""),
        "tipo": "saida" if nf.get("tipo", 0) == 0 else "entrada",
        "data_emissao": (nf.get("dataEmissao") or "")[:10] or None,
        "data_operacao": (nf.get("dataOperacao") or "")[:10] or None,
        "natureza_operacao": natureza.get("descricao", ""),
        "cfop": natureza.get("cfop", ""),
        "contato_nome": contato.get("nome", ""),
        "contato_documento": contato.get("numeroDocumento", ""),
        "valor_nf": _num(nf.get("total")),
        "valor_produtos": _num(nf.get("totalProdutos")),
        "valor_frete": total_frete,
        "valor_seguro": _num(nf.get("valorSeguro"), transporte.get("valorSeguro")),
        "valor_desconto": _num(nf.get("desconto"), nf.get("valorDesconto")),
        "valor_outros": _num(nf.get("outrasDespesas"), nf.get("valorOutros")),
        "base_icms": _num(tributos.get("baseICMS"), nf.get("baseICMS")),
        "valor_icms": _num(tributos.get("totalICMS"), tributos.get("valorICMS"), nf.get("valorICMS")),
        "base_icms_st": _num(tributos.get("baseICMSST"), nf.get("baseICMSST")),
        "valor_icms_st": _num(tributos.get("totalICMSST"), nf.get("valorICMSST")),
        "valor_ipi": _num(tributos.get("totalIPI"), nf.get("valorIPI")),
        "valor_pis": _num(tributos.get("totalPIS"), nf.get("valorPIS")),
        "valor_cofins": _num(tributos.get("totalCOFINS"), nf.get("valorCOFINS")),
        "valor_iss": _num(tributos.get("totalISS"), nf.get("valorISS")),
        "valor_ii": _num(tributos.get("totalII"), nf.get("valorII")),
        "valor_ir": _num(tributos.get("totalIR"), nf.get("valorIR")),
        "valor_csll": _num(tributos.get("totalCSLL"), nf.get("valorCSLL")),
        "valor_inss": _num(tributos.get("totalINSS"), nf.get("valorINSS")),
        "valor_total_tributos": _num(tributos.get("totalTributos"), nf.get("valorTotalTributos")),
        "status": {1: "emitida", 2: "cancelada", 3: "inutilizada", 4: "denegada"}.get(nf.get("situacao", 1), "emitida"),
        "loja_id": loja.get("id"),
        "xml_url": nf.get("xml") or nf.get("linkXml") or "",
        "danfe_url": nf.get("danfe") or nf.get("linkDanfe") or "",
        "modelo": str(nf.get("modelo", "55")),
    }

def sincronizar_notas_fiscais_bling(pagina: int = 1, limite: int = 100) -> dict:
    """Sync completo: lista todas as paginas de notas fiscais e busca o DETALHE de
    cada uma (GET /nfe/{id}) para importar itens e impostos reais — a listagem
    (GET /nfe) traz apenas um resumo, sem itens nem tributos."""
    from bling_erp import listar_notas_fiscais as bling_nfe, get_nfe_completa, get_access_token, get_auth_url
    import json as _json
    token = get_access_token()
    if not token: return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}

    MAX_PAGINAS = 50  # limite de seguranca: evita loop/chamadas ilimitadas em contas com muitas notas
    notas_resumo = []
    erros = []
    pag = pagina
    mais_paginas = False
    for _ in range(MAX_PAGINAS):
        r = bling_nfe(pag, limite)
        dados = r.get("data", [])
        if not dados or r.get("error"):
            if r.get("error"): erros.append(f"pag {pag}: {r['error']}")
            break
        notas_resumo.extend(dados)
        if len(dados) < limite:
            break
        pag += 1
    else:
        mais_paginas = True  # atingiu MAX_PAGINAS sem esgotar a listagem — rode de novo para continuar
    if not notas_resumo:
        return {"sync": 0, "message": "sem dados", "erros": erros}

    async def _go():
        db = await get_db()
        total = 0
        for nf_resumo in notas_resumo:
            bling_id = nf_resumo.get("id")
            if not bling_id:
                continue
            detalhe = None
            for attempt in range(3):
                r_detalhe = get_nfe_completa(bling_id)
                if not r_detalhe.get("error"):
                    detalhe = r_detalhe.get("data", {})
                    break
                if r_detalhe.get("status_code") == 429:
                    time.sleep(2 ** attempt)
                    continue
                erros.append(f"nota {bling_id}: {r_detalhe['error']}")
                break
            if not detalhe:
                detalhe = nf_resumo  # fallback: usa ao menos o resumo da listagem

            try:
                existing = await db.fetchval("SELECT id FROM fiscal_notas_fiscais WHERE bling_id = $1", bling_id)
                campos = _mapear_nfe_detalhe(detalhe)
                raw = _json.dumps(detalhe, ensure_ascii=False)
                if existing:
                    await db.execute("""UPDATE fiscal_notas_fiscais SET
                        numero=$1, chave_acesso=$2, data_emissao=$3::date, data_operacao=$4::date,
                        contato_nome=$5, contato_documento=$6, natureza_operacao=$7,
                        valor_nf=$8, valor_produtos=$9, valor_frete=$10, status=$11,
                        cfop=$12, loja_id=$13, valor_seguro=$14, valor_desconto=$15, valor_outros=$16,
                        base_icms=$17, valor_icms=$18, base_icms_st=$19, valor_icms_st=$20,
                        valor_ipi=$21, valor_pis=$22, valor_cofins=$23, valor_iss=$24,
                        valor_ii=$25, valor_ir=$26, valor_csll=$27, valor_inss=$28, valor_total_tributos=$29,
                        xml_url=$30, danfe_url=$31, dados_brutos_bling=$32::jsonb, sincronizado_em=NOW()
                        WHERE bling_id=$33""",
                        campos["numero"], campos["chave_acesso"], campos["data_emissao"], campos["data_operacao"],
                        campos["contato_nome"], campos["contato_documento"], campos["natureza_operacao"],
                        campos["valor_nf"], campos["valor_produtos"], campos["valor_frete"], campos["status"],
                        campos["cfop"], campos["loja_id"], campos["valor_seguro"], campos["valor_desconto"], campos["valor_outros"],
                        campos["base_icms"], campos["valor_icms"], campos["base_icms_st"], campos["valor_icms_st"],
                        campos["valor_ipi"], campos["valor_pis"], campos["valor_cofins"], campos["valor_iss"],
                        campos["valor_ii"], campos["valor_ir"], campos["valor_csll"], campos["valor_inss"], campos["valor_total_tributos"],
                        campos["xml_url"], campos["danfe_url"], raw, bling_id)
                    nota_id = existing
                    await db.execute("DELETE FROM fiscal_nfe_itens WHERE nota_id = $1", nota_id)
                else:
                    nota_id = await db.fetchval("""INSERT INTO fiscal_notas_fiscais
                        (numero, modelo, chave_acesso, tipo, data_emissao, data_operacao,
                         natureza_operacao, cfop, contato_nome, contato_documento,
                         valor_nf, valor_produtos, valor_frete, valor_seguro, valor_desconto, valor_outros,
                         base_icms, valor_icms, base_icms_st, valor_icms_st, valor_ipi, valor_pis, valor_cofins,
                         valor_iss, valor_ii, valor_ir, valor_csll, valor_inss, valor_total_tributos,
                         status, loja_id, xml_url, danfe_url, dados_brutos_bling, bling_id, sincronizado_em)
                        VALUES ($1,$2,$3,$4,$5::date,$6::date,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,
                                $20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31,$32,$33,$34::jsonb,$35,NOW())
                        RETURNING id""",
                        campos["numero"], campos["modelo"], campos["chave_acesso"], campos["tipo"],
                        campos["data_emissao"], campos["data_operacao"], campos["natureza_operacao"], campos["cfop"],
                        campos["contato_nome"], campos["contato_documento"], campos["valor_nf"], campos["valor_produtos"],
                        campos["valor_frete"], campos["valor_seguro"], campos["valor_desconto"], campos["valor_outros"],
                        campos["base_icms"], campos["valor_icms"], campos["base_icms_st"], campos["valor_icms_st"],
                        campos["valor_ipi"], campos["valor_pis"], campos["valor_cofins"], campos["valor_iss"],
                        campos["valor_ii"], campos["valor_ir"], campos["valor_csll"], campos["valor_inss"],
                        campos["valor_total_tributos"], campos["status"], campos["loja_id"],
                        campos["xml_url"], campos["danfe_url"], raw, bling_id)

                itens = detalhe.get("itens", []) or []
                for idx, item in enumerate(itens, 1):
                    await db.execute("""INSERT INTO fiscal_nfe_itens
                        (nota_id, numero_item, codigo, descricao, ncm, cest, cfop, unidade,
                         quantidade, valor_unitario, valor_total, valor_desconto, base_icms, valor_icms, aliquota_icms,
                         base_icms_st, valor_icms_st, valor_ipi, valor_pis, valor_cofins)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)""",
                        nota_id, idx,
                        item.get("codigo", ""), item.get("descricao", ""),
                        item.get("ncm", ""), item.get("cest", ""), item.get("cfop", ""),
                        item.get("unidade", "UN"),
                        _num(item.get("quantidade")), _num(item.get("valorUnitario")), _num(item.get("valor"), item.get("valorTotal")),
                        _num(item.get("valorDesconto")), _num(item.get("baseICMS")), _num(item.get("valorICMS")), _num(item.get("aliquotaICMS")),
                        _num(item.get("baseICMSST")), _num(item.get("valorICMSST")), _num(item.get("valorIPI")),
                        _num(item.get("valorPIS")), _num(item.get("valorCOFINS")))
                total += 1
            except Exception as e:
                log(AGENT, f"Erro sync NF {nf_resumo.get('numero')}: {e}")
        return {"sync": total, "erros": erros, "mais_paginas": mais_paginas}
    return run_async(_go())

def sincronizar_contas_receber_bling(pagina: int = 1, limite: int = 100) -> dict:
    """Sync contas a receber do Bling → fin_contas_receber (tabela unificada SSOT)."""
    from bling_erp import listar_contas_receber as bling_cr, get_access_token, get_auth_url
    token = get_access_token()
    if not token: return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}
    r = bling_cr(pagina, limite)
    if r.get("error"): return r
    dados = r.get("data", [])
    if not dados: return {"sync": 0, "message": "sem dados"}
    async def _go():
        db = await get_db()
        # Ensure bling_id + origem columns on fin_contas_receber
        for col, ct in [("bling_id", "BIGINT"), ("origem", "VARCHAR(30) DEFAULT 'manual'")]:
            try:
                exists = await db.fetchval("SELECT column_name FROM information_schema.columns WHERE table_name='fin_contas_receber' AND column_name=$1", col)
                if not exists: await db.execute(f"ALTER TABLE fin_contas_receber ADD COLUMN {col} {ct}")
            except Exception as e: pass
        total = 0
        for cr in dados:
            try:
                bling_id = cr.get("id")
                if not bling_id: continue
                existing = await db.fetchval("SELECT id FROM fin_contas_receber WHERE bling_id = $1", bling_id)
                contato = cr.get("contato", {}) or {}
                vencimento = (cr.get("vencimento") or cr.get("dataVencimento") or "")[:10] or None
                data_recebimento = (cr.get("dataRecebimento") or cr.get("dataPagamento") or "")[:10] or None
                if existing:
                    await db.execute("""UPDATE fin_contas_receber SET
                        cliente=$1, descricao=$2, valor=$3, vencimento=$4::date, data_recebimento=$5::date,
                        status=$6, forma_pagamento=$7, origem='bling'
                        WHERE bling_id=$8""",
                        contato.get("nome",""), cr.get("descricao",""),
                        float(cr.get("valor",0) or 0), vencimento, data_recebimento,
                        str(cr.get("situacao","pendente")), cr.get("formaPagamento",""), bling_id)
                else:
                    await db.execute("""INSERT INTO fin_contas_receber
                        (cliente, descricao, valor, vencimento, data_recebimento, status, forma_pagamento, bling_id, origem)
                        VALUES ($1,$2,$3,$4::date,$5::date,$6,$7,$8,'bling')""",
                        contato.get("nome",""), cr.get("descricao",""),
                        float(cr.get("valor",0) or 0), vencimento, data_recebimento,
                        str(cr.get("situacao","pendente")), cr.get("formaPagamento",""), bling_id)
                total += 1
            except Exception as e:
                log(AGENT, f"Erro sync CR: {e}")
        return {"sync": total}
    return run_async(_go())

def sincronizar_contas_pagar_bling(pagina: int = 1, limite: int = 100) -> dict:
    """Sync contas a pagar do Bling → fin_contas_pagar (tabela unificada SSOT)."""
    from bling_erp import listar_contas_pagar as bling_cp, get_access_token, get_auth_url
    token = get_access_token()
    if not token: return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}
    r = bling_cp(pagina, limite)
    if r.get("error"): return r
    dados = r.get("data", [])
    if not dados: return {"sync": 0, "message": "sem dados"}
    async def _go():
        db = await get_db()
        for col, ct in [("bling_id", "BIGINT"), ("origem", "VARCHAR(30) DEFAULT 'manual'")]:
            try:
                exists = await db.fetchval("SELECT column_name FROM information_schema.columns WHERE table_name='fin_contas_pagar' AND column_name=$1", col)
                if not exists: await db.execute(f"ALTER TABLE fin_contas_pagar ADD COLUMN {col} {ct}")
            except Exception as e: pass
        total = 0
        for cp in dados:
            try:
                bling_id = cp.get("id")
                if not bling_id: continue
                existing = await db.fetchval("SELECT id FROM fin_contas_pagar WHERE bling_id = $1", bling_id)
                fornecedor = cp.get("fornecedor", cp.get("contato", {})) or {}
                vencimento = (cp.get("vencimento") or cp.get("dataVencimento") or "")[:10] or None
                data_pagamento = (cp.get("dataPagamento") or "")[:10] or None
                if existing:
                    await db.execute("""UPDATE fin_contas_pagar SET
                        fornecedor=$1, descricao=$2, valor=$3, vencimento=$4::date, data_pagamento=$5::date,
                        status=$6, forma_pagamento=$7, origem='bling'
                        WHERE bling_id=$8""",
                        fornecedor.get("nome",""), cp.get("descricao",""),
                        float(cp.get("valor",0) or 0), vencimento, data_pagamento,
                        str(cp.get("situacao","pendente")), cp.get("formaPagamento",""), bling_id)
                else:
                    await db.execute("""INSERT INTO fin_contas_pagar
                        (fornecedor, descricao, valor, vencimento, data_pagamento, status, forma_pagamento, bling_id, origem)
                        VALUES ($1,$2,$3,$4::date,$5::date,$6,$7,$8,'bling')""",
                        fornecedor.get("nome",""), cp.get("descricao",""),
                        float(cp.get("valor",0) or 0), vencimento, data_pagamento,
                        str(cp.get("situacao","pendente")), cp.get("formaPagamento",""), bling_id)
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

# ── Apuração de Impostos ──

def apuracao_impostos(ano: int = None, mes: int = None, dias: int = 365) -> dict:
    """Apuração consolidada de ICMS, PIS, COFINS, IPI por período (mensal ou últimos N dias)."""
    async def _go():
        db = await get_db()
        where = []
        if ano and mes:
            where.append(f"EXTRACT(YEAR FROM COALESCE(data_emissao, created_at)) = {ano}")
            where.append(f"EXTRACT(MONTH FROM COALESCE(data_emissao, created_at)) = {mes}")
        elif dias:
            where.append(f"COALESCE(data_emissao, created_at) >= CURRENT_DATE - {dias}")
        clause = ("WHERE " + " AND ".join(where)) if where else ""

        row = await db.fetchrow(f"""
            SELECT
                COUNT(*) as total_notas,
                COALESCE(SUM(valor_nf), 0) as valor_total,
                COALESCE(SUM(valor_produtos), 0) as valor_produtos,
                COALESCE(SUM(base_icms), 0) as base_icms,
                COALESCE(SUM(valor_icms), 0) as total_icms,
                COALESCE(SUM(valor_ipi), 0) as total_ipi,
                COALESCE(SUM(valor_pis), 0) as total_pis,
                COALESCE(SUM(valor_cofins), 0) as total_cofins,
                COALESCE(SUM(valor_iss), 0) as total_iss,
                COALESCE(SUM(valor_total_tributos), 0) as total_tributos
            FROM fiscal_notas_fiscais
            {clause}
        """)

        monthly = await db.fetch(f"""
            SELECT
                EXTRACT(YEAR FROM COALESCE(data_emissao, created_at))::int as ano,
                EXTRACT(MONTH FROM COALESCE(data_emissao, created_at))::int as mes,
                COUNT(*) as total_notas,
                COALESCE(SUM(valor_nf), 0) as valor_total,
                COALESCE(SUM(valor_icms), 0) as icms,
                COALESCE(SUM(valor_pis), 0) as pis,
                COALESCE(SUM(valor_cofins), 0) as cofins,
                COALESCE(SUM(valor_ipi), 0) as ipi,
                COALESCE(SUM(valor_total_tributos), 0) as total_tributos
            FROM fiscal_notas_fiscais
            {clause}
            GROUP BY ano, mes
            ORDER BY ano DESC, mes DESC
            LIMIT 24
        """)

        return {
            "resumo": dict(row) if row else {},
            "mensal": [dict(r) for r in (monthly or [])],
        }
    try:
        return run_async(_go())
    except Exception as e:
        return {"error": str(e), "resumo": {}, "mensal": []}


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
