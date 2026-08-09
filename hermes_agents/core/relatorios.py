"""Relatorios Core — 20 reports unificando Bling + PDV + Compras + Produção."""
import os
from core import get_db, run_async, log, hoje
from core.lojas import loja_efetiva, _log_erro

AGENT = "Relatorios Core"

# ── Helper: UNION vendas Bling + PDV ──

def _loja_where_bling(loja_id, prefix=""):
    """WHERE clause suffix for vendas_pedidos filtered by loja_id. Sem alias por
    padrao — nenhuma das queries que usam isso aliasa vendas_pedidos; um prefixo
    default "v." gerava UndefinedTableError (mascarado pelo except generico,
    devolvendo zero) toda vez que um loja_id era passado."""
    p = f"{prefix}." if prefix else ""
    return f" AND {p}loja_id = {int(loja_id)}" if loja_id else ""

def _loja_where_pdv(loja_id):
    """WHERE clause suffix for pdv_vendas filtered by loja_id via pdv_caixas."""
    if not loja_id: return ""
    return f" AND venda.caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = {int(loja_id)})"

def _loja_where_estoque(loja_id):
    """WHERE clause suffix for estoque_lojas, maps loja_id -> loja nome efetivo (resolve vinculo)."""
    if not loja_id: return ""
    try:
        nome_efetivo = loja_efetiva(str(loja_id))
        if isinstance(nome_efetivo, str) and nome_efetivo and not nome_efetivo.isdigit():
            nome_escapado = nome_efetivo.replace("'", "''")
            return f" AND e.loja = '{nome_escapado}'"
        _log_erro(
            "relatorios._loja_where_estoque: resolver_loja_efetiva",
            ValueError(f"loja_id {loja_id} -> nao resolveu para um nome valido: {nome_efetivo!r}"))
    except Exception as e:
        _log_erro("relatorios._loja_where_estoque: resolver_loja_efetiva", e)
    return f" AND e.loja = (SELECT nome FROM lojas WHERE id = {int(loja_id)})"

def _union_vendas(dias: int, loja_id=None):
    """Retorna total, qtd, e diarias unindo vendas_pedidos + pdv_vendas.

    dias=1 e' tratado como "so' hoje" (filtro CURRENT_DATE, sem subtracao).
    O padrao generico "CURRENT_DATE - N" inclui o dia corrente MAIS N dias
    anteriores — com N=1 isso somaria hoje + ontem inteiro, dobrando o
    valor do card "Vendas hoje" (unico chamador que usa dias=1; todo o
    resto do modulo usa 30/60/90 e continua com o comportamento generico)."""
    janela = 0 if dias <= 1 else dias
    loja_bl = _loja_where_bling(loja_id)
    loja_pdv = _loja_where_pdv(loja_id)
    async def _go():
        db = await get_db()
        total_bling = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1::int AND status != 'cancelado'{loja_bl}", janela)
        total_pdv = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM pdv_vendas venda WHERE DATE(data) >= CURRENT_DATE - $1::int{loja_pdv}", janela)
        qtd_bling = await db.fetchval(f"SELECT COUNT(*) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1::int{loja_bl}", janela)
        qtd_pdv = await db.fetchval(f"SELECT COUNT(*) FROM pdv_vendas venda WHERE DATE(data) >= CURRENT_DATE - $1::int{loja_pdv}", janela)
        diarias_bling = await db.fetch(f"SELECT DATE(data) as dia, COUNT(*) as qtd, SUM(total) as valor FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1::int AND status != 'cancelado'{loja_bl} GROUP BY DATE(data)", janela)
        diarias_pdv = await db.fetch(f"SELECT DATE(data) as dia, COUNT(*) as qtd, SUM(total) as valor FROM pdv_vendas venda WHERE DATE(data) >= CURRENT_DATE - $1::int{loja_pdv} GROUP BY DATE(data)", janela)
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
    # Consolida por dia (Bling + PDV podem ambos vender no mesmo dia — sem
    # isso a lista tinha ate' 2 pontos por dia, e nenhuma das duas queries em
    # _union_vendas tem ORDER BY, entao o grafico de vendas do Dashboard saia
    # com o eixo X fora de ordem cronologica). Mesmo padrao ja usado em
    # core/bi.py::vendas_diarias().
    por_dia = {}
    for row in r["diarias_bling"] + r["diarias_pdv"]:
        d = row["dia"]
        chave = d.isoformat() if hasattr(d, "isoformat") else str(d)
        acc = por_dia.setdefault(chave, {"dia": chave, "qtd": 0, "valor": 0.0})
        acc["qtd"] += int(row["qtd"] or 0)
        acc["valor"] += float(row["valor"] or 0)
    diarias = [por_dia[k] for k in sorted(por_dia.keys())]
    return {"total": r["total"], "quantidade": r["quantidade"], "diarias": diarias, "periodo_dias": dias}

# ── 2. Lucro e Margem ──

def lucro_margem(dias=30, loja_id=None):
    loja_bl = _loja_where_bling(loja_id)
    loja_pdv = _loja_where_pdv(loja_id)
    async def _go():
        db = await get_db()
        receita = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1::int AND status != 'cancelado'{loja_bl}", dias)
        receita_pdv = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM pdv_vendas venda WHERE DATE(data) >= CURRENT_DATE - $1::int{loja_pdv}", dias)
        receita_total = float((receita or 0) + (receita_pdv or 0))
        custos_prod = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM producao_custos WHERE data >= CURRENT_DATE - $1::int", dias)
        compras_val = await db.fetchval("SELECT COALESCE(SUM(valor_total),0) FROM compras_pedidos WHERE data_emissao >= CURRENT_DATE - $1::int AND status != 'cancelado'", dias)
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
        if loja_id:
            total = await db.fetchval(f"SELECT COUNT(DISTINCT e.sku) FROM estoque_lojas e WHERE e.quantidade > 0{loja_sql}")
        else:
            total = await db.fetchval("SELECT COUNT(*) FROM catalogo_produtos")
        baixo = await db.fetchval(f"SELECT COUNT(*) FROM estoque_lojas e JOIN catalogo_produtos c ON c.sku = e.sku WHERE e.quantidade < 10 AND e.quantidade > 0{loja_sql}")
        ruptura = await db.fetchval(f"SELECT COUNT(*) FROM estoque_lojas e WHERE e.quantidade <= 0{loja_sql}")
        return {"total_itens": total or 0, "baixo_estoque": baixo or 0, "ruptura": ruptura or 0}
    try: return run_async(_go())
    except Exception as e: return {"total_itens":0,"baixo_estoque":0,"ruptura":0}

# ── 4. Clientes ──

def clientes(dias=90, loja_id=None):
    # ponytail: cad_clientes nao tem loja_id — "cliente desta loja" so' existe via
    # JOIN com vendas_pedidos.loja_id (cliente que comprou dessa loja).
    async def _go():
        db = await get_db()
        if loja_id:
            total = await db.fetchval("SELECT COUNT(DISTINCT v.cliente_id) FROM vendas_pedidos v WHERE v.loja_id = $1 AND v.cliente_id IS NOT NULL", loja_id)
            novos = await db.fetchval("SELECT COUNT(DISTINCT c.id) FROM cad_clientes c JOIN vendas_pedidos v ON v.cliente_id = c.id WHERE v.loja_id = $1 AND c.created_at >= CURRENT_DATE - $2::int", loja_id, dias)
            top = await db.fetch("SELECT c.nome as cliente, COUNT(v.id) as compras, COALESCE(SUM(v.total),0) as valor FROM cad_clientes c JOIN vendas_pedidos v ON v.cliente_id = c.id AND v.status != 'cancelado' AND v.loja_id = $1 GROUP BY c.id, c.nome ORDER BY valor DESC LIMIT 10", loja_id)
        else:
            total = await db.fetchval("SELECT COUNT(*) FROM cad_clientes")
            novos = await db.fetchval("SELECT COUNT(*) FROM cad_clientes WHERE created_at >= CURRENT_DATE - $1::int", dias)
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
        receita = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1::int AND status != 'cancelado'{loja_bl}", dias)
        receita_pdv = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM pdv_vendas venda WHERE DATE(data) >= CURRENT_DATE - $1::int{loja_pdv}", dias)
        receita_total = float((receita or 0) + (receita_pdv or 0))
        cmv = float(await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM producao_custos WHERE data >= CURRENT_DATE - $1::int", dias) or 0)
        cp_val = float(await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fin_contas_pagar WHERE vencimento >= CURRENT_DATE - $1::int AND status='pendente'", dias) or 0)
        lb = receita_total - cmv - (cp_val * 0.7)
        despesas = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fin_dre WHERE mes >= to_char(CURRENT_DATE - $1::int, 'YYYY-MM') AND tipo='despesa'", dias)
        return {"receita_bruta": receita_total, "cmv": cmv, "lucro_bruto": round(lb, 2), "despesas": float(despesas or 0), "margem_bruta_pct": round(lb/max(receita_total,1)*100,1), "periodo_dias": dias}
    try: return run_async(_go())
    except Exception as e: return {"receita_bruta":0,"cmv":0,"lucro_bruto":0,"despesas":0,"margem_bruta_pct":0,"periodo_dias":dias}

# ── 8. Fluxo de Caixa ──

def fluxo_caixa(dias=30, loja_id=None):
    loja_bl = _loja_where_bling(loja_id)
    loja_pdv = _loja_where_pdv(loja_id)
    async def _go():
        db = await get_db()
        entradas_bl = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1::int AND status IN ('faturado','concluido'){loja_bl}", dias)
        entradas_pdv = await db.fetchval(f"SELECT COALESCE(SUM(total),0) FROM pdv_vendas venda WHERE DATE(data) >= CURRENT_DATE - $1::int{loja_pdv}", dias)
        cr_recebido = await db.fetchval(f"SELECT COALESCE(SUM(valor),0) FROM fin_contas_receber WHERE data_recebimento >= CURRENT_DATE - $1::int AND status='pago'{loja_bl}", dias)
        entradas = float((entradas_bl or 0) + (entradas_pdv or 0) + (cr_recebido or 0))
        saidas_cp = await db.fetchval(f"SELECT COALESCE(SUM(valor),0) FROM fin_contas_pagar WHERE data_pagamento >= CURRENT_DATE - $1::int AND status='pago'{loja_bl}", dias)
        saidas_comp = await db.fetchval(f"SELECT COALESCE(SUM(valor_total),0) FROM compras_pedidos WHERE data_emissao >= CURRENT_DATE - $1::int{loja_bl}", dias)
        saidas = float((saidas_cp or 0) + (saidas_comp or 0))
        return {"entradas": entradas, "saidas": saidas, "saldo": round(entradas - saidas, 2), "periodo_dias": dias}
    try: return run_async(_go())
    except Exception as e: return {"entradas":0,"saidas":0,"saldo":0,"periodo_dias":dias}

# ── 9. Aging Financeiro ──
# Faixas de inadimplencia (contas VENCIDAS, nao a vencer) com valor somado —
# usado pelo card "Inadimplencia" do BI (core/bi.py::acoes_do_mes) alem da
# tela generica /relatorios/aging.

_FAIXAS_AGING = [("0-30 dias", 0, 30), ("31-60 dias", 31, 60), ("61-90 dias", 61, 90), ("90+ dias", 91, None)]

def aging_financeiro():
    # status != 'pago' (nao so' == 'pendente'): mesmo criterio ja usado pela
    # home do Financeiro (web/.../VisaoGeralTab.tsx, "Contas Atrasadas") —
    # linhas com status 'atrasado' (existe no seed de demonstracao, fora do
    # enum 'pendente'|'pago' documentado) tambem contam como divida em aberto.
    async def _go():
        db = await get_db()
        avencer = await db.fetchval("SELECT COUNT(*) FROM fin_contas_receber WHERE vencimento >= CURRENT_DATE AND status!='pago'")
        avencer_valor = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fin_contas_receber WHERE vencimento >= CURRENT_DATE AND status!='pago'")
        vencidas = await db.fetchval("SELECT COUNT(*) FROM fin_contas_receber WHERE vencimento < CURRENT_DATE AND status!='pago'")
        vencidas_valor = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fin_contas_receber WHERE vencimento < CURRENT_DATE AND status!='pago'")
        pagar_vencidas = await db.fetchval("SELECT COUNT(*) FROM fin_contas_pagar WHERE vencimento < CURRENT_DATE AND status!='pago'")
        pagar_vencidas_valor = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM fin_contas_pagar WHERE vencimento < CURRENT_DATE AND status!='pago'")

        por_faixa = await db.fetch("""
            SELECT
                CASE
                    WHEN CURRENT_DATE - vencimento BETWEEN 0 AND 30 THEN '0-30 dias'
                    WHEN CURRENT_DATE - vencimento BETWEEN 31 AND 60 THEN '31-60 dias'
                    WHEN CURRENT_DATE - vencimento BETWEEN 61 AND 90 THEN '61-90 dias'
                    ELSE '90+ dias'
                END AS faixa,
                COUNT(*) AS qtd, COALESCE(SUM(valor),0) AS valor
            FROM fin_contas_receber WHERE status!='pago' AND vencimento < CURRENT_DATE
            GROUP BY 1
        """)
        por_faixa_map = {r["faixa"]: {"qtd": r["qtd"], "valor": float(r["valor"] or 0)} for r in por_faixa}

        maiores = await db.fetch("""
            SELECT cliente, valor, vencimento, (CURRENT_DATE - vencimento) AS dias_vencido
            FROM fin_contas_receber WHERE status!='pago' AND vencimento < CURRENT_DATE
            ORDER BY valor DESC LIMIT 5
        """)
        return {
            "a_vencer": avencer or 0, "a_vencer_valor": float(avencer_valor or 0),
            "vencidas": vencidas or 0, "vencidas_valor": float(vencidas_valor or 0),
            "a_pagar_vencidas": pagar_vencidas or 0, "a_pagar_vencidas_valor": float(pagar_vencidas_valor or 0),
            "faixas": [
                {"faixa": nome, **por_faixa_map.get(nome, {"qtd": 0, "valor": 0.0})}
                for nome, _, _ in _FAIXAS_AGING
            ],
            "maiores_devedores": [
                {"cliente": r["cliente"], "valor": float(r["valor"] or 0),
                 "vencimento": r["vencimento"].isoformat() if r["vencimento"] else None,
                 "dias_vencido": r["dias_vencido"]}
                for r in (maiores or [])
            ],
        }
    try: return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro aging_financeiro: {e}")
        return {"a_vencer": 0, "vencidas": 0, "faixas": [{"faixa": nome, "qtd": 0, "valor": 0.0} for nome, _, _ in _FAIXAS_AGING], "maiores_devedores": []}

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
        pedidos = await db.fetchval("SELECT COUNT(*) FROM compras_pedidos WHERE data_emissao >= CURRENT_DATE - $1::int", dias)
        total_val = await db.fetchval("SELECT COALESCE(SUM(valor_total),0) FROM compras_pedidos WHERE data_emissao >= CURRENT_DATE - $1::int", dias)
        forn = await db.fetchval("SELECT COUNT(DISTINCT fornecedor_id) FROM compras_pedidos WHERE data_emissao >= CURRENT_DATE - $1::int", dias)
        return {"pedidos": pedidos or 0, "valor_total": float(total_val or 0), "fornecedores_unicos": forn or 0, "periodo_dias": dias}
    try: return run_async(_go())
    except Exception as e: return {"pedidos":0,"valor_total":0,"fornecedores_unicos":0,"periodo_dias":dias}

# ── 12. Impostos (via NF-e) ──

def impostos(dias=30):
    async def _go():
        db = await get_db()
        nf_entrada = await db.fetchval("SELECT COALESCE(SUM(valor_icms + valor_ipi + valor_pis + valor_cofins),0) FROM fiscal_notas_fiscais WHERE tipo='entrada' AND data_emissao >= CURRENT_DATE - $1::int", dias)
        nf_saida = await db.fetchval("SELECT COALESCE(SUM(valor_icms + valor_ipi + valor_pis + valor_cofins),0) FROM fiscal_notas_fiscais WHERE tipo='saida' AND data_emissao >= CURRENT_DATE - $1::int", dias)
        return {"impostos_entrada": float(nf_entrada or 0), "impostos_saida": float(nf_saida or 0), "total": float((nf_entrada or 0) + (nf_saida or 0)), "periodo_dias": dias}
    try: return run_async(_go())
    except Exception as e: return {"impostos_entrada":0,"impostos_saida":0,"total":0,"periodo_dias":dias}

# ── 13. Comissão ──

def comissao(dias=30):
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT vendedor, COUNT(*) as vendas, COALESCE(SUM(total),0) as valor
            FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1::int AND status != 'cancelado' AND vendedor IS NOT NULL AND vendedor != ''
            GROUP BY vendedor ORDER BY valor DESC LIMIT 10""", dias)
        return [dict(r) for r in (rows or [])]
    try: return run_async(_go())
    except Exception as e: return []

# ── 14. Marketplaces ──

def marketplaces(dias=30):
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT COALESCE(marketplace,'manual') as canal, COUNT(*) as vendas, COALESCE(SUM(total),0) as valor
            FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1::int AND status != 'cancelado'
            GROUP BY marketplace ORDER BY valor DESC""", dias)
        return [dict(r) for r in (rows or [])]
    try: return run_async(_go())
    except Exception as e: return []

# ── 15. Devoluções ──

def devolucoes(dias=30):
    async def _go():
        db = await get_db()
        total = await db.fetchval("SELECT COUNT(*) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1::int AND status='cancelado'", dias)
        taxa = await db.fetchval("SELECT ROUND(COUNT(*) FILTER(WHERE status='cancelado')::numeric / NULLIF(COUNT(*),0) * 100, 1) FROM vendas_pedidos WHERE data >= CURRENT_DATE - $1::int", dias)
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

def curvas(dias=90, loja_id=None):
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT vi.sku, vi.descricao, SUM(vi.valor_total) as valor_total, SUM(vi.quantidade) as qtd
            FROM vendas_itens vi JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE vp.data >= CURRENT_DATE - $1::int AND vp.status != 'cancelado'
              AND ($2::int IS NULL OR vp.loja_id = $2)
            GROUP BY vi.sku, vi.descricao ORDER BY valor_total DESC LIMIT 30""", dias, loja_id)
        items = [dict(r) for r in (rows or [])]
        for it in items:
            it["valor_total"] = float(it.get("valor_total", 0) or 0)
            it["qtd"] = float(it.get("qtd", 0) or 0)
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
            WHERE vp.data >= CURRENT_DATE - $1::int AND vp.status != 'cancelado'
            GROUP BY vi.sku, vi.descricao ORDER BY valor DESC LIMIT 20""", dias)
        return [dict(r) for r in (rows or [])]
    try: return run_async(_go())
    except Exception as e: return []

# ── 18b. Ranking de produtos por lucro/vendas (todos os canais) ──

SHOPEE_COMISSAO_PCT = 12  # mesma taxa default de shopee/pricing.calcular_margem_produto

def ranking_produtos(dias=30, loja_id=None):
    """Lucro/vendas por SKU somando Bling+marketplaces (vendas_itens/vendas_pedidos,
    mesma fonte unificada de produtos()/curvas() acima) e PDV loja fisica
    (pdv_itens/pdv_vendas, canal direto sem sync). Comissao de marketplace so'
    e' deduzida do canal 'shopee' (taxa conhecida via env var/config); demais
    marketplaces sincronizados via Bling entram brutos de comissao por falta
    de taxa cadastrada por canal — nao inventa numero. PDV e' de fato sem
    comissao (venda direta), entao 0 ali e' o valor correto, nao uma lacuna.

    loja_id opcional: filtra so' os pedidos daquela loja. Bling/Shopee ja
    grava loja_id resolvido no sync (shop_id->loja), i9Logic idem
    (filial->loja) — filtrar por loja_id ja' separa Shopee de i9Logic sem
    precisar checar tipo de loja em lugar nenhum."""
    async def _go():
        db = await get_db()
        vendas_rows = await db.fetch(f"""
            SELECT sku, SUM(quantidade) AS quantidade, SUM(valor_total) AS receita,
                   SUM(CASE WHEN canal = 'shopee' THEN valor_total * {SHOPEE_COMISSAO_PCT} / 100.0 ELSE 0 END) AS comissao,
                   SUM(frete_alocado) AS frete
            FROM (
                SELECT vi.sku AS sku, vi.quantidade AS quantidade, vi.valor_total AS valor_total,
                       COALESCE(vp.marketplace, 'bling') AS canal,
                       CASE WHEN vp.total > 0 THEN vi.valor_total / vp.total * COALESCE(vp.frete, 0) ELSE 0 END AS frete_alocado
                FROM vendas_itens vi JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
                WHERE vp.data >= CURRENT_DATE - $1::int AND vp.status != 'cancelado'
                  AND ($2::int IS NULL OR vp.loja_id = $2)
                -- branch PDV intencionalmente sem filtro de loja: tabela morta (0 linhas em producao)
                UNION ALL
                SELECT pi.produto_codigo AS sku, pi.quantidade AS quantidade, pi.valor_total AS valor_total,
                       'pdv' AS canal, 0 AS frete_alocado
                FROM pdv_itens pi JOIN pdv_vendas pv ON pv.id = pi.venda_id
                WHERE pv.data >= CURRENT_DATE - $1::int AND pv.status != 'cancelada'
            ) unificado
            WHERE sku IS NOT NULL AND sku != ''
            GROUP BY sku
        """, dias, loja_id)
        if not vendas_rows:
            return []
        skus = [r["sku"] for r in vendas_rows]
        custo_rows = await db.fetch(
            "SELECT sku, descricao, COALESCE(preco_custo, 0) AS preco_custo FROM catalogo_produtos WHERE sku = ANY($1::text[])",
            skus)
        custos = {r["sku"]: r for r in custo_rows}
        itens = []
        for r in vendas_rows:
            sku = r["sku"]
            info = custos.get(sku, {})
            receita = float(r["receita"] or 0)
            quantidade = float(r["quantidade"] or 0)
            custo_unit = float(info.get("preco_custo", 0) or 0)
            custo_total = round(custo_unit * quantidade, 2)
            comissao = round(float(r["comissao"] or 0), 2)
            frete = round(float(r["frete"] or 0), 2)
            lucro = round(receita - custo_total - comissao - frete, 2)
            itens.append({
                "sku": sku,
                "descricao": info.get("descricao") or sku,
                "quantidade": quantidade,
                "receita": round(receita, 2),
                "custo": custo_total,
                "comissao": comissao,
                "frete": frete,
                "lucro": lucro,
                "margem_pct": round((lucro / receita * 100) if receita > 0 else 0, 1),
                "custo_cadastrado": custo_unit > 0,
            })
        return itens
    try: return run_async(_go())
    except Exception as e: return []


# ── 18c. Tendencia e risco de ruptura por produto ──

def produtos_tendencia(dias=30, loja_id=None):
    """Crescimento de vendas por SKU: periodo atual vs periodo anterior de
    mesmo tamanho. anterior=0 com atual>0 vira crescimento_pct=None (produto
    novo/reativado, sem base de comparacao pra inventar percentual) — mesma
    filosofia anti-numero-fabricado de core/bi.py::_variacao()."""
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"""
            SELECT vi.sku,
                   MAX(vi.descricao) AS descricao,
                   SUM(CASE WHEN vp.data >= CURRENT_DATE - $1::int THEN vi.quantidade ELSE 0 END) AS qtd_atual,
                   SUM(CASE WHEN vp.data < CURRENT_DATE - $1::int THEN vi.quantidade ELSE 0 END) AS qtd_anterior
            FROM vendas_itens vi JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE vp.data >= CURRENT_DATE - $1::int * 2 AND vp.status != 'cancelado'
              AND vi.sku IS NOT NULL AND vi.sku != ''
              AND ($2::int IS NULL OR vp.loja_id = $2)
            GROUP BY vi.sku
        """, dias, loja_id)
        return [dict(r) for r in (rows or [])]
    try:
        linhas = run_async(_go())
    except Exception as e:
        return []

    resultado = []
    for r in linhas:
        atual = float(r["qtd_atual"] or 0)
        anterior = float(r["qtd_anterior"] or 0)
        if atual == 0 and anterior == 0:
            continue
        crescimento = round((atual - anterior) / anterior * 100, 1) if anterior else None
        resultado.append({
            "sku": r["sku"], "descricao": r["descricao"] or r["sku"],
            "quantidade_atual": round(atual, 2), "quantidade_anterior": round(anterior, 2),
            "crescimento_pct": crescimento,
        })
    return resultado


def risco_ruptura(dias=30, loja_id=None):
    """Produtos vendendo bem MAS com estoque acabando — velocidade de venda
    alta, estoque baixo. Diferente de 'parado' (zero venda) e de rupturas()
    (zero estoque, ja consumada) — aqui e' o alerta ANTES de zerar."""
    dias = max(1, int(dias or 30))
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"""
            SELECT vi.sku, MAX(vi.descricao) AS descricao, SUM(vi.quantidade) AS qtd_vendida,
                   (SELECT COALESCE(SUM(e.quantidade), 0) FROM estoque_lojas e
                    WHERE e.sku = vi.sku AND ($2::int IS NULL OR e.loja_id = $2)) AS estoque_atual
            FROM vendas_itens vi JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE vp.data >= CURRENT_DATE - $1::int AND vp.status != 'cancelado'
              AND vi.sku IS NOT NULL AND vi.sku != ''
              AND ($2::int IS NULL OR vp.loja_id = $2)
            GROUP BY vi.sku
        """, dias, loja_id)
        return [dict(r) for r in (rows or [])]
    try:
        linhas = run_async(_go())
    except Exception as e:
        return []

    resultado = []
    for r in linhas:
        qtd_vendida = float(r["qtd_vendida"] or 0)
        estoque_atual = float(r["estoque_atual"] or 0)
        velocidade_diaria = qtd_vendida / dias
        if velocidade_diaria <= 0 or estoque_atual <= 0:
            continue
        resultado.append({
            "sku": r["sku"], "descricao": r["descricao"] or r["sku"],
            "estoque_atual": round(estoque_atual, 2), "quantidade_vendida": round(qtd_vendida, 2),
            "velocidade_diaria": round(velocidade_diaria, 3),
            "dias_restantes": round(estoque_atual / velocidade_diaria, 1),
        })
    resultado.sort(key=lambda p: p["dias_restantes"])
    return resultado[:15]

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
        nf_total = await db.fetchval("SELECT COUNT(*) FROM fiscal_notas_fiscais WHERE data_emissao >= CURRENT_DATE - $1::int", dias)
        nf_valor = await db.fetchval("SELECT COALESCE(SUM(valor_nf),0) FROM fiscal_notas_fiscais WHERE data_emissao >= CURRENT_DATE - $1::int", dias)
        return {"nfs_periodo": nf_total or 0, "valor_periodo": float(nf_valor or 0), "periodo_dias": dias}
    try: return run_async(_go())
    except Exception as e: return {"nfs_periodo":0,"valor_periodo":0,"periodo_dias":dias}

# ── 22. Vendas por Loja (grade dias x lojas) ──
# Equivalente da planilha VENDAS MES LOJAS.xlsx — mesma base de dados de
# vendas() (_union_vendas), so' que quebrada por loja e agregada num
# intervalo de datas livre em vez de "ultimos N dias".

def vendas_por_loja(de: str, ate: str) -> dict:
    async def _go():
        db = await get_db()
        lojas_rows = await db.fetch("SELECT id, nome FROM lojas WHERE ativa ORDER BY nome")
        lojas = [dict(r) for r in lojas_rows]
        bling = await db.fetch("""
            SELECT loja_id, DATE(data) AS dia, COALESCE(SUM(total),0) AS valor
            FROM vendas_pedidos
            WHERE data >= $1 AND data <= $2 AND status != 'cancelado' AND loja_id IS NOT NULL
            GROUP BY loja_id, DATE(data)
        """, de, ate)
        pdv = await db.fetch("""
            SELECT c.loja_id, DATE(v.data) AS dia, COALESCE(SUM(v.total),0) AS valor
            FROM pdv_vendas v JOIN pdv_caixas c ON c.id = v.caixa_id
            WHERE DATE(v.data) >= $1 AND DATE(v.data) <= $2 AND c.loja_id IS NOT NULL
            GROUP BY c.loja_id, DATE(v.data)
        """, de, ate)
        por_dia_loja = {}
        for r in list(bling) + list(pdv):
            chave = (r["dia"], r["loja_id"])
            por_dia_loja[chave] = por_dia_loja.get(chave, 0) + float(r["valor"] or 0)
        dias_ordenados = sorted({dia for (dia, _lid) in por_dia_loja})
        grade = []
        totais_por_loja = {l["id"]: 0.0 for l in lojas}
        for dia in dias_ordenados:
            valores = {}
            total_dia = 0.0
            for l in lojas:
                v = round(por_dia_loja.get((dia, l["id"]), 0.0), 2)
                valores[l["id"]] = v
                total_dia += v
                totais_por_loja[l["id"]] = round(totais_por_loja[l["id"]] + v, 2)
            grade.append({"data": dia.isoformat(), "valores_por_loja": valores, "total_dia": round(total_dia, 2)})
        return {"lojas": lojas, "dias": grade, "totais_por_loja": totais_por_loja}
    try: return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro vendas_por_loja: {e}")
        return {"lojas": [], "dias": [], "totais_por_loja": {}}

# ── 23. Movimento Diário por Loja (receita por forma x despesa por categoria) ──
# Equivalente da planilha MOV LOJA LEON.xlsx. Despesa vem do Cofre
# (fin_cofre_movimentos, tipo=saida_despesa) — decisao consciente de escopo,
# nao ha' rastreio de despesa fora do cofre por loja hoje.

def movimento_diario_por_loja(de: str, ate: str, loja_id: int) -> dict:
    async def _go():
        db = await get_db()
        receita_rows = await db.fetch("""
            SELECT DATE(v.data) AS dia, p.forma, COALESCE(SUM(p.valor),0) AS valor
            FROM pdv_pagamentos p
            JOIN pdv_vendas v ON v.id = p.venda_id
            JOIN pdv_caixas c ON c.id = v.caixa_id
            WHERE c.loja_id = $1 AND DATE(v.data) >= $2 AND DATE(v.data) <= $3 AND v.status = 'finalizada'
            GROUP BY DATE(v.data), p.forma
        """, loja_id, de, ate)
        despesa_rows = await db.fetch("""
            SELECT m.data AS dia, m.categoria, COALESCE(SUM(m.valor),0) AS valor
            FROM fin_cofre_movimentos m
            JOIN fin_cofre cf ON cf.id = m.cofre_id
            WHERE cf.loja_id = $1 AND m.tipo = 'saida_despesa' AND m.data >= $2 AND m.data <= $3
            GROUP BY m.data, m.categoria
        """, loja_id, de, ate)
        por_dia = {}
        for r in receita_rows:
            d = por_dia.setdefault(r["dia"], {"receita_por_forma": {}, "despesa_por_categoria": {}})
            d["receita_por_forma"][r["forma"] or "outros"] = float(r["valor"] or 0)
        for r in despesa_rows:
            d = por_dia.setdefault(r["dia"], {"receita_por_forma": {}, "despesa_por_categoria": {}})
            d["despesa_por_categoria"][r["categoria"] or "outros"] = float(abs(r["valor"] or 0))
        resultado = []
        for dia in sorted(por_dia.keys()):
            v = por_dia[dia]
            receita_total = round(sum(v["receita_por_forma"].values()), 2)
            despesa_total = round(sum(v["despesa_por_categoria"].values()), 2)
            resultado.append({
                "data": dia.isoformat(),
                "receita_por_forma": v["receita_por_forma"],
                "despesa_por_categoria": v["despesa_por_categoria"],
                "receita_total": receita_total,
                "despesa_total": despesa_total,
                "total_liquido": round(receita_total - despesa_total, 2),
            })
        return {"loja_id": loja_id, "dias": resultado}
    try: return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro movimento_diario_por_loja loja {loja_id}: {e}")
        return {"loja_id": loja_id, "dias": []}

# ── 21. DRE por Loja (Lucro Real por Canal) ──

def dre_por_loja(dias: int = 30) -> list:
    """Retorna DRE (receita, comissao, frete, lucro) por loja Shopee + PDV.
    SOLID: DIP via FinanceiroRepository — injetavel via set_financeiro_repo().

    comissao_pct segue a mesma cadeia de shopee/pricing.calcular_margem_produto
    (env var -> config salva -> default 12%) — antes esta funcao tinha seu
    proprio fallback hardcoded de 14%, uma segunda fonte de verdade divergente
    pro mesmo numero."""
    from core.config import get_config
    comissao_pct = float(os.environ.get("SHOPEE_COMISSAO_PCT") or get_config("shopee", "comissao_pct") or 12)
    from core.repositories_postgres import get_financeiro_repo
    return _dre_via_repo(get_financeiro_repo(), dias, comissao_pct)


def _dre_com_extras(base: list, dias: int) -> list:
    """Enriquece o DRE por loja com quebra de caixa acumulada e discrepancia
    de estoque — visao unificada por loja, sem precisar abrir varias telas
    para achar onde o processo de uma loja esta pior."""
    try:
        from core.pdv import historico_quebras
        from core.estoque_relatorios import por_loja as discrepancias_por_loja
        quebras = historico_quebras(dias=dias)
        # estoque_aprovacoes/transferencias/contagens guardam loja como nome
        # livre (VARCHAR), nao loja_id — join por string normalizada
        # (trim + lowercase) pra nao perder o match so' por diferenca de
        # maiuscula/espaco. Nao elimina 100% o risco de nome divergente
        # (ex: abreviacao), mas cobre o caso mais comum.
        discrepancias = {(d["loja"] or "").strip().lower(): d for d in discrepancias_por_loja(dias)}
        quebra_por_loja = {}
        for q in quebras:
            lid = q.get("loja_id")
            if lid is None: continue
            quebra_por_loja[lid] = quebra_por_loja.get(lid, 0) + float(q.get("diferenca") or 0)
        for item in base:
            item["quebra_caixa_acumulada"] = round(quebra_por_loja.get(item["loja_id"], 0), 2)
            disc = discrepancias.get((item["loja_nome"] or "").strip().lower(), {})
            item["discrepancia_unidades_falta"] = disc.get("unidades_falta_contagem", 0)
    except Exception as e:
        log(AGENT, f"Erro _dre_com_extras: {e}")
        for item in base:
            item.setdefault("quebra_caixa_acumulada", 0)
            item.setdefault("discrepancia_unidades_falta", 0)
    return base


def _dre_via_repo(repo, dias: int, comissao_pct: float) -> list:
    async def _go():
        rows = await repo.listar_receita_por_loja(dias)
        resultado = []
        for r in rows:
            receita = r.receita_online + r.receita_pdv
            # comissao de marketplace incide so' sobre receita Shopee de fato —
            # vendas_pedidos tambem tem pedidos Bling/i9Logic (loja fisica), que
            # nao pagam comissao de Shopee. custos_producao ja vem alocado
            # proporcionalmente pelo repositorio (nao ha rastreio real por
            # loja — fabrica e' unica, sem coluna loja_id em producao_custos).
            comissao_valor = round(r.receita_shopee * comissao_pct / 100, 2)
            lucro = round(receita - comissao_valor - r.frete - r.custos_producao, 2)
            margem_pct = round((lucro / receita * 100) if receita > 0 else 0, 1)
            qtd_total = r.qtd_vendas + r.qtd_vendas_pdv
            ticket_medio = round(receita / qtd_total, 2) if qtd_total > 0 else 0
            resultado.append({
                "loja_id": r.loja_id, "loja_nome": r.loja_nome,
                "receita": receita, "receita_online": r.receita_online,
                "receita_shopee": r.receita_shopee, "receita_pdv": r.receita_pdv,
                "qtd_vendas": qtd_total, "ticket_medio": ticket_medio,
                "comissao_pct": comissao_pct, "comissao_valor": comissao_valor,
                "frete": r.frete, "custos_producao": r.custos_producao,
                "custos_producao_alocado": True,
                "lucro": lucro, "margem_pct": margem_pct,
                "periodo_dias": dias,
            })
        resultado.sort(key=lambda x: x["lucro"], reverse=True)
        return _dre_com_extras(resultado, dias)
    try: return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro dre_por_loja: {e}")
        return []
