"""Relatorios Core — 20 reports unificando Bling + PDV + Compras + Produção."""
import os
from core import get_db, run_async, log, hoje

AGENT = "Relatorios Core"

# ── Helper: UNION vendas Bling + PDV ──

def _loja_where_bling(loja_id, prefix="v"):
    """WHERE clause suffix for vendas_pedidos filtered by loja_id."""
    return f" AND {prefix}.loja_id = {int(loja_id)}" if loja_id else ""

def _loja_where_pdv(loja_id):
    """WHERE clause suffix for pdv_vendas filtered by loja_id via pdv_caixas."""
    if not loja_id: return ""
    return f" AND venda.caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = {int(loja_id)})"

def _loja_where_estoque(loja_id):
    """WHERE clause suffix for estoque_lojas, maps loja_id -> loja nome."""
    if not loja_id: return ""
    return f" AND e.loja = (SELECT nome FROM lojas WHERE id = {int(loja_id)})"

def _union_vendas(dias: int, loja_id=None):
    """Retorna total, qtd, e diarias unindo vendas_pedidos + pdv_vendas."""
    loja_bl = _loja_where_bling(loja_id)
    loja_pdv = _loja_where_pdv(loja_id)
    async def _go():
        db = await get_db()
        total_bling = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1 AND status != 'cancelado'{loja_bl}", dias)
        total_pdv = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM pdv_vendas venda WHERE DATE(data) >= CURRENT_DATE - $1{loja_pdv}", dias)
        qtd_bling = await db.fetchval(f"SELECT COUNT(*) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1{loja_bl}", dias)
        qtd_pdv = await db.fetchval(f"SELECT COUNT(*) FROM pdv_vendas venda WHERE DATE(data) >= CURRENT_DATE - $1{loja_pdv}", dias)
        diarias_bling = await db.fetch(f"SELECT DATE(data) as dia, COUNT(*) as qtd, SUM(total) as valor FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1 AND status != 'cancelado'{loja_bl} GROUP BY DATE(data)", dias)
        diarias_pdv = await db.fetch(f"SELECT DATE(data) as dia, COUNT(*) as qtd, SUM(total) as valor FROM pdv_vendas venda WHERE DATE(data) >= CURRENT_DATE - $1{loja_pdv} GROUP BY DATE(data)", dias)
        return {
            "total": float((total_bling or 0) + (total_pdv or 0)),
            "quantidade": (qtd_bling or 0) + (qtd_pdv or 0),
            "diarias_bling": [dict(r) for r in (diarias_bling or [])],
            "diarias_pdv": [dict(r) for r in (diarias_pdv or [])],
        }
    try: return run_async(_go())
    except Exception as e: return {"total":0,"quantidade":0,"diarias_bling":[],"diarias_pdv":[]}

# ── 1. Vendas ──

def vendas(dias=30, loja_id=None):
    r = _union_vendas(dias, loja_id)
    return {"total": r["total"], "quantidade": r["quantidade"], "diarias": r["diarias_bling"] + r["diarias_pdv"], "periodo_dias": dias}

# ── 2. Lucro e Margem ──

def lucro_margem(dias=30, loja_id=None):
    loja_bl = _loja_where_bling(loja_id)
    loja_pdv = _loja_where_pdv(loja_id)
    async def _go():
        db = await get_db()
        receita = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1 AND status != 'cancelado'{loja_bl}", dias)
        receita_pdv = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM pdv_vendas venda WHERE DATE(data) >= CURRENT_DATE - $1{loja_pdv}", dias)
        receita_total = float((receita or 0) + (receita_pdv or 0))
        custos_prod = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM producao_custos WHERE data >= CURRENT_DATE - $1", dias)
        compras_val = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM compras_pedidos WHERE data_emissao >= CURRENT_DATE - $1 AND status != 'cancelado'", dias)
        cp_val = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fin_contas_pagar WHERE origem='bling' AND status='pendente'")
        custos = float((custos_prod or 0) + (compras_val or 0) + (cp_val or 0))
        lucro = receita_total - custos
        margem = round((lucro / max(receita_total, 1)) * 100, 1)
        return {"receita": receita_total, "custos": custos, "lucro": round(lucro,2), "margem_pct": margem, "periodo_dias": dias}
    try: return run_async(_go())
    except Exception as e: return {"receita":0,"custos":0,"lucro":0,"margem_pct":0,"periodo_dias":dias}

# ── 3. Estoque ──

def estoque(loja_id=None):
    loja_sql = _loja_where_estoque(loja_id)
    async def _go():
        db = await get_db()
        total = await db.fetchval("SELECT COUNT(*) FROM catalogo_produtos")
        baixo = await db.fetchval(f"SELECT COUNT(*) FROM estoque_lojas e JOIN catalogo_produtos c ON c.sku = e.sku WHERE e.quantidade < 10 AND e.quantidade > 0{loja_sql}")
        ruptura = await db.fetchval(f"SELECT COUNT(*) FROM estoque_lojas e WHERE e.quantidade <= 0{loja_sql}")
        return {"total_itens": total or 0, "baixo_estoque": baixo or 0, "ruptura": ruptura or 0}
    try: return run_async(_go())
    except Exception as e: return {"total_itens":0,"baixo_estoque":0,"ruptura":0}

# ── 4. Clientes ──

def clientes(dias=90, loja_id=None):
    # ponytail: top clientes via vendas_pedidos JOIN — loja filter on LEFT JOIN too fragile; skip until denormalized
    async def _go():
        db = await get_db()
        total = await db.fetchval("SELECT COUNT(*) FROM cad_clientes")
        novos = await db.fetchval("SELECT COUNT(*) FROM cad_clientes WHERE created_at >= CURRENT_DATE - $1", dias)
        top = await db.fetch("SELECT c.nome as cliente, COUNT(v.id) as compras, COALESCE(SUM(v.total),0) as valor FROM cad_clientes c LEFT JOIN vendas_pedidos v ON v.cliente_id = c.id AND v.status != 'cancelado' GROUP BY c.id, c.nome ORDER BY valor DESC LIMIT 10")
        return {"total": total or 0, "novos": novos or 0, "top": [dict(r) for r in (top or [])], "periodo_dias": dias}
    try: return run_async(_go())
    except Exception as e: return {"total":0,"novos":0,"top":[],"periodo_dias":dias}

# ── 5. Fornecedores ──

def fornecedores():
    async def _go():
        db = await get_db()
        total = await db.fetchval("SELECT COUNT(*) FROM cad_fornecedores")
        ativos = await db.fetchval("SELECT COUNT(*) FROM cad_fornecedores WHERE status='ativo'")
        top = await db.fetch("SELECT f.nome, COUNT(p.id) as pedidos, COALESCE(SUM(p.valor_total),0) as valor FROM cad_fornecedores f LEFT JOIN compras_pedidos p ON p.fornecedor_id=f.id GROUP BY f.id, f.nome ORDER BY valor DESC LIMIT 10")
        return {"total": total or 0, "ativos": ativos or 0, "top": [dict(r) for r in (top or [])]}
    try: return run_async(_go())
    except Exception as e: return {"total":0,"ativos":0,"top":[]}

# ── 6. Ticket Médio ──

def ticket_medio(dias=30, loja_id=None):
    r = _union_vendas(dias, loja_id)
    ticket = r["total"] / max(r["quantidade"], 1)
    return {"ticket_medio": round(ticket, 2), "total_vendas": r["total"], "qtd_vendas": r["quantidade"], "periodo_dias": dias}

# ── 7. DRE ──

def dre(dias=30, loja_id=None):
    loja_bl = _loja_where_bling(loja_id)
    loja_pdv = _loja_where_pdv(loja_id)
    async def _go():
        db = await get_db()
        receita = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1 AND status != 'cancelado'{loja_bl}", dias)
        receita_pdv = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM pdv_vendas venda WHERE DATE(data) >= CURRENT_DATE - $1{loja_pdv}", dias)
        receita_total = float((receita or 0) + (receita_pdv or 0))
        cmv = float(await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM producao_custos WHERE data >= CURRENT_DATE - $1", dias) or 0)
        cp_val = float(await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fin_contas_pagar WHERE vencimento >= CURRENT_DATE - $1 AND status='pendente'", dias) or 0)
        lb = receita_total - cmv - (cp_val * 0.7)
        despesas = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fin_dre WHERE mes >= to_char(CURRENT_DATE - $1, 'YYYY-MM') AND tipo='despesa'", dias)
        return {"receita_bruta": receita_total, "cmv": cmv, "lucro_bruto": round(lb, 2), "despesas": float(despesas or 0), "margem_bruta_pct": round(lb/max(receita_total,1)*100,1), "periodo_dias": dias}
    try: return run_async(_go())
    except Exception as e: return {"receita_bruta":0,"cmv":0,"lucro_bruto":0,"despesas":0,"margem_bruta_pct":0,"periodo_dias":dias}

# ── 8. Fluxo de Caixa ──

def fluxo_caixa(dias=30, loja_id=None):
    loja_bl = _loja_where_bling(loja_id)
    loja_pdv = _loja_where_pdv(loja_id)
    async def _go():
        db = await get_db()
        entradas_bl = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1 AND status IN ('faturado','concluido'){loja_bl}", dias)
        entradas_pdv = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM pdv_vendas venda WHERE DATE(data) >= CURRENT_DATE - $1{loja_pdv}", dias)
        cr_recebido = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fin_contas_receber WHERE data_recebimento >= CURRENT_DATE - $1 AND status='pago'", dias)
        entradas = float((entradas_bl or 0) + (entradas_pdv or 0) + (cr_recebido or 0))
        saidas_cp = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fin_contas_pagar WHERE data_pagamento >= CURRENT_DATE - $1 AND status='pago'", dias)
        saidas_comp = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM compras_pedidos WHERE data_emissao >= CURRENT_DATE - $1", dias)
        saidas = float((saidas_cp or 0) + (saidas_comp or 0))
        return {"entradas": entradas, "saidas": saidas, "saldo": round(entradas - saidas, 2), "periodo_dias": dias}
    try: return run_async(_go())
    except Exception as e: return {"entradas":0,"saidas":0,"saldo":0,"periodo_dias":dias}

# ── 9. Aging Financeiro ──

def aging_financeiro():
    async def _go():
        db = await get_db()
        avencer = await db.fetchval("SELECT COUNT(*) FROM fin_contas_receber WHERE vencimento >= CURRENT_DATE AND status='pendente'")
        vencidas = await db.fetchval("SELECT COUNT(*) FROM fin_contas_receber WHERE vencimento < CURRENT_DATE AND status='pendente'")
        faixa1 = await db.fetchval("SELECT COUNT(*) FROM fin_contas_receber WHERE vencimento BETWEEN CURRENT_DATE AND CURRENT_DATE + 7 AND status='pendente'")
        faixa2 = await db.fetchval("SELECT COUNT(*) FROM fin_contas_receber WHERE vencimento BETWEEN CURRENT_DATE + 8 AND CURRENT_DATE + 30 AND status='pendente'")
        return {"a_vencer": avencer or 0, "vencidas": vencidas or 0, "faixas": [
            {"faixa":"Vencidas","qtd":vencidas or 0},
            {"faixa":"7 dias","qtd":faixa1 or 0},
            {"faixa":"30 dias","qtd":faixa2 or 0},
            {"faixa":"31+ dias","qtd":max((avencer or 0) - (faixa1 or 0) - (faixa2 or 0), 0)},
        ]}
    try: return run_async(_go())
    except Exception as e: return {"a_vencer":0,"vencidas":0,"faixas":[{"faixa":"Sem dados","qtd":0}]}

# ── 10. Previsão ──

def previsao(dias=30, loja_id=None):
    loja_bl = _loja_where_bling(loja_id)
    loja_pdv = _loja_where_pdv(loja_id)
    async def _go():
        db = await get_db()
        media = await db.fetchval(f"SELECT COALESCE(AVG(daily),0) FROM (SELECT DATE(data) as d, SUM(total) as daily FROM vendas_pedidos WHERE data >= CURRENT_DATE - 60 AND status != 'cancelado'{loja_bl} GROUP BY DATE(data)) sub")
        media_pdv = await db.fetchval(f"SELECT COALESCE(AVG(daily),0) FROM (SELECT DATE(data) as d, SUM(total) as daily FROM pdv_vendas venda WHERE DATE(data) >= CURRENT_DATE - 60{loja_pdv} GROUP BY DATE(data)) sub")
        media_total = float((media or 0) + (media_pdv or 0))
        return {"media_diaria": round(media_total, 2), "previsao_30d": round(media_total * 30, 2)}
    try: return run_async(_go())
    except Exception as e: return {"media_diaria":0,"previsao_30d":0}

# ── 11. Compras ──

def compras(dias=30):
    async def _go():
        db = await get_db()
        pedidos = await db.fetchval("SELECT COUNT(*) FROM compras_pedidos WHERE data_emissao >= CURRENT_DATE - $1", dias)
        total_val = await db.fetchval("SELECT COALESCE(SUM(valor_total),0) FROM compras_pedidos WHERE data_emissao >= CURRENT_DATE - $1", dias)
        forn = await db.fetchval("SELECT COUNT(DISTINCT fornecedor_id) FROM compras_pedidos WHERE data_emissao >= CURRENT_DATE - $1", dias)
        return {"pedidos": pedidos or 0, "valor_total": float(total_val or 0), "fornecedores_unicos": forn or 0, "periodo_dias": dias}
    try: return run_async(_go())
    except Exception as e: return {"pedidos":0,"valor_total":0,"fornecedores_unicos":0,"periodo_dias":dias}

# ── 12. Impostos (via NF-e) ──

def impostos(dias=30):
    async def _go():
        db = await get_db()
        nf_entrada = await db.fetchval("SELECT COALESCE(SUM(valor_icms + valor_ipi + valor_pis + valor_cofins),0) FROM fiscal_notas_fiscais WHERE tipo='entrada' AND data_emissao >= CURRENT_DATE - $1", dias)
        nf_saida = await db.fetchval("SELECT COALESCE(SUM(valor_icms + valor_ipi + valor_pis + valor_cofins),0) FROM fiscal_notas_fiscais WHERE tipo='saida' AND data_emissao >= CURRENT_DATE - $1", dias)
        return {"impostos_entrada": float(nf_entrada or 0), "impostos_saida": float(nf_saida or 0), "total": float((nf_entrada or 0) + (nf_saida or 0)), "periodo_dias": dias}
    try: return run_async(_go())
    except Exception as e: return {"impostos_entrada":0,"impostos_saida":0,"total":0,"periodo_dias":dias}

# ── 13. Comissão ──

def comissao(dias=30):
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT vendedor, COUNT(*) as vendas, COALESCE(SUM(total),0) as valor
            FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1 AND status != 'cancelado' AND vendedor IS NOT NULL AND vendedor != ''
            GROUP BY vendedor ORDER BY valor DESC LIMIT 10""", dias)
        return [dict(r) for r in (rows or [])]
    try: return run_async(_go())
    except Exception as e: return []

# ── 14. Marketplaces ──

def marketplaces(dias=30):
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT COALESCE(marketplace,'manual') as canal, COUNT(*) as vendas, COALESCE(SUM(total),0) as valor
            FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1 AND status != 'cancelado'
            GROUP BY marketplace ORDER BY valor DESC""", dias)
        return [dict(r) for r in (rows or [])]
    try: return run_async(_go())
    except Exception as e: return []

# ── 15. Devoluções ──

def devolucoes(dias=30):
    async def _go():
        db = await get_db()
        total = await db.fetchval("SELECT COUNT(*) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1 AND status='cancelado'", dias)
        taxa = await db.fetchval("SELECT ROUND(COUNT(*) FILTER(WHERE status='cancelado')::numeric / NULLIF(COUNT(*),0) * 100, 1) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1", dias)
        return {"total_devolucoes": total or 0, "taxa_pct": float(taxa or 0), "periodo_dias": dias}
    try: return run_async(_go())
    except Exception as e: return {"total_devolucoes":0,"taxa_pct":0,"periodo_dias":dias}

# ── 16. Rupturas ──

def rupturas():
    async def _go():
        db = await get_db()
        total = await db.fetchval("SELECT COUNT(*) FROM estoque_lojas WHERE quantidade <= 0")
        rows = await db.fetch("SELECT sku, quantidade FROM estoque_lojas WHERE quantidade <= 0 ORDER BY sku LIMIT 20")
        return {"total_rupturas": total or 0, "produtos": [dict(r) for r in (rows or [])]}
    try: return run_async(_go())
    except Exception as e: return {"total_rupturas":0,"produtos":[]}

# ── 17. Curva ABC ──

def curvas(dias=90):
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT vi.sku, vi.descricao, SUM(vi.valor_total) as valor_total, SUM(vi.quantidade) as qtd
            FROM vendas_itens vi JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE vp.data >= CURRENT_DATE - $1 AND vp.status != 'cancelado'
            GROUP BY vi.sku, vi.descricao ORDER BY valor_total DESC LIMIT 30""", dias)
        items = [dict(r) for r in (rows or [])]
        total = sum(float(r.get("valor_total",0) or 0) for r in items) or 1
        acum = 0
        for it in items:
            acum += float(it.get("valor_total",0) or 0)
            it["pct"] = round(float(it.get("valor_total",0) or 0) / total * 100, 1)
            it["pct_acum"] = round(acum / total * 100, 1)
            it["classe"] = "A" if it["pct_acum"] <= 80 else "B" if it["pct_acum"] <= 95 else "C"
        return {"total_valor": round(total, 2), "total_itens": len(items), "itens": items}
    try: return run_async(_go())
    except Exception as e: return {"total_valor":0,"total_itens":0,"itens":[]}

# ── 18. Produtos ──

def produtos(dias=30):
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT vi.sku, vi.descricao, SUM(vi.quantidade) as qtd, SUM(vi.valor_total) as valor
            FROM vendas_itens vi JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE vp.data >= CURRENT_DATE - $1 AND vp.status != 'cancelado'
            GROUP BY vi.sku, vi.descricao ORDER BY valor DESC LIMIT 20""", dias)
        return [dict(r) for r in (rows or [])]
    try: return run_async(_go())
    except Exception as e: return []

# ── 19. Financeiro ──

def financeiro(dias=30):
    async def _go():
        db = await get_db()
        cr_total = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fin_contas_receber WHERE status='pendente'")
        cp_total = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fin_contas_pagar WHERE status='pendente'")
        cr_qtd = await db.fetchval("SELECT COUNT(*) FROM fin_contas_receber WHERE status='pendente'")
        cp_qtd = await db.fetchval("SELECT COUNT(*) FROM fin_contas_pagar WHERE status='pendente'")
        return {"contas_receber_total": float(cr_total or 0), "contas_pagar_total": float(cp_total or 0), "contas_receber_qtd": cr_qtd or 0, "contas_pagar_qtd": cp_qtd or 0, "periodo_dias": dias}
    try: return run_async(_go())
    except Exception as e: return {"contas_receber_total":0,"contas_pagar_total":0,"contas_receber_qtd":0,"contas_pagar_qtd":0,"periodo_dias":dias}

# ── 20. Fiscal Dashboard resumo ──

def fiscal_resumo(dias=30):
    async def _go():
        db = await get_db()
        nf_total = await db.fetchval("SELECT COUNT(*) FROM fiscal_notas_fiscais WHERE data_emissao >= CURRENT_DATE - $1", dias)
        nf_valor = await db.fetchval("SELECT COALESCE(SUM(valor_nf),0) FROM fiscal_notas_fiscais WHERE data_emissao >= CURRENT_DATE - $1", dias)
        return {"nfs_periodo": nf_total or 0, "valor_periodo": float(nf_valor or 0), "periodo_dias": dias}
    try: return run_async(_go())
    except Exception as e: return {"nfs_periodo":0,"valor_periodo":0,"periodo_dias":dias}

# ── 21. DRE por Loja (Lucro Real por Canal) ──

def dre_por_loja(dias: int = 30) -> list:
    """Retorna DRE (receita, comissao, frete, lucro) por loja Shopee + PDV.
    SOLID: DIP via FinanceiroRepository — injetavel via set_financeiro_repo()."""
    comissao_pct = float(os.environ.get("SHOPEE_COMISSAO_PCT", "")) if os.environ.get("SHOPEE_COMISSAO_PCT") else 14.0
    try:
        from core.repositories_postgres import get_financeiro_repo
        return _dre_via_repo(get_financeiro_repo(), dias, comissao_pct)
    except Exception:
        return _dre_via_query(dias, comissao_pct)


def _dre_via_repo(repo, dias: int, comissao_pct: float) -> list:
    async def _go():
        rows = await repo.listar_receita_por_loja(dias)
        resultado = []
        for r in rows:
            receita = r.receita_online + r.receita_pdv
            comissao_valor = round(receita * comissao_pct / 100, 2)
            lucro = round(receita - comissao_valor - r.frete - r.custos_producao, 2)
            margem_pct = round((lucro / receita * 100) if receita > 0 else 0, 1)
            resultado.append({
                "loja_id": r.loja_id, "loja_nome": r.loja_nome,
                "receita": receita, "qtd_vendas": r.qtd_vendas,
                "comissao_pct": comissao_pct, "comissao_valor": comissao_valor,
                "frete": r.frete, "custos_producao": r.custos_producao,
                "lucro": lucro, "margem_pct": margem_pct,
                "periodo_dias": dias,
            })
        resultado.sort(key=lambda x: x["lucro"], reverse=True)
        return resultado
    try: return run_async(_go())
    except Exception as e: return []


def _dre_via_query(dias: int, comissao_pct: float) -> list:
    """Fallback: query direta se repositorio nao disponivel."""
    async def _go():
        db = await get_db()
        lojas = await db.fetch("SELECT id, nome FROM lojas WHERE ativa = TRUE ORDER BY nome")

        resultado = []
        for loja in lojas:
            lid = loja["id"]
            # receita Shopee/Bling (vendas_pedidos)
            rec_online = await db.fetchval("""
                SELECT COALESCE(SUM(total),0) FROM vendas_pedidos
                WHERE loja_id = $1 AND data >= CURRENT_DATE - $2 AND status != 'cancelado'
            """, lid, dias)
            # receita PDV (pdv_vendas via pdv_caixas.loja_id)
            rec_pdv = await db.fetchval("""
                SELECT COALESCE(SUM(v.total),0) FROM pdv_vendas v
                JOIN pdv_caixas c ON c.id = v.caixa_id
                WHERE c.loja_id = $1 AND DATE(v.data) >= CURRENT_DATE - $2 AND v.status = 'finalizada'
            """, lid, dias)
            receita = float(rec_online or 0) + float(rec_pdv or 0)

            frete = float((await db.fetchval("SELECT COALESCE(SUM(frete),0) FROM vendas_pedidos WHERE loja_id = $1 AND data >= CURRENT_DATE - $2 AND status != 'cancelado'", lid, dias)) or 0)
            custos = float((await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM producao_custos WHERE loja_id = $1 AND data >= CURRENT_DATE - $2", lid, dias)) or 0)
            qtd_vendas = int((await db.fetchval("SELECT COUNT(*) FROM vendas_pedidos WHERE loja_id = $1 AND data >= CURRENT_DATE - $2 AND status != 'cancelado'", lid, dias)) or 0)

            comissao_valor = round(receita * comissao_pct / 100, 2)
            lucro = round(receita - comissao_valor - frete - custos, 2)
            margem_pct = round((lucro / receita * 100) if receita > 0 else 0, 1)

            resultado.append({
                "loja_id": lid, "loja_nome": loja["nome"],
                "receita": receita, "qtd_vendas": qtd_vendas,
                "comissao_pct": comissao_pct, "comissao_valor": comissao_valor,
                "frete": frete, "custos_producao": custos,
                "lucro": lucro, "margem_pct": margem_pct,
                "periodo_dias": dias,
            })

        # ordenar por lucro descendente
        resultado.sort(key=lambda x: x["lucro"], reverse=True)
        return resultado
    try: return run_async(_go())
    except Exception as e: return []
