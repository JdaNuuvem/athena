"""BI Core — Dashboard, vendas por categoria, indicadores financeiros,
forecast e ML simples (outliers, segmentacao RFM, cross-sell).

Tudo aqui e' calculado a partir de dado real do banco (reaproveitando
core/relatorios.py e core/estoque_relatorios.py onde possivel). Onde o
indicador pedido pelo frontend depende de dado que este sistema nao
rastreia (ex: Liquidez Corrente, ROE, Indice de Endividamento — precisam
de Ativo/Passivo/Patrimonio Liquido, e este e' um ERP operacional, nao uma
contabilidade completa), o indicador e' omitido em vez de inventado."""
import statistics
from datetime import date, timedelta
from core import get_db, run_async, log

AGENT = "BI Core"


def _fmt_brl(v: float) -> str:
    s = f"{v:,.2f}"
    s = s.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {s}"


def _fmt_pct(v: float) -> str:
    return f"{v:.1f}%"


# ── Dashboard ──

def _variacao(atual: float, anterior: float):
    """None se nao da' pra comparar (sem historico no periodo anterior) — em vez
    de mostrar 0%/queda de 100% que enganaria o usuario."""
    if not anterior:
        return None
    pct = round((atual - anterior) / anterior * 100, 1)
    sinal = "+" if pct >= 0 else ""
    return {"pct": pct, "label": f"{sinal}{pct}% vs. mês anterior", "positiva": pct >= 0}


def dashboard() -> dict:
    from core.relatorios import vendas as rel_vendas, ticket_medio as rel_ticket, dre as rel_dre, previsao as rel_previsao
    v = rel_vendas(30)
    t = rel_ticket(30)
    d = rel_dre(30)
    p = rel_previsao(30)

    async def _comparativo_mensal():
        db = await get_db()
        receita_atual = await db.fetchval("""
            SELECT COALESCE(SUM(total),0) FROM (
                SELECT total FROM vendas_pedidos WHERE data >= CURRENT_DATE - 30 AND status != 'cancelado'
                UNION ALL SELECT total FROM pdv_vendas WHERE DATE(data) >= CURRENT_DATE - 30
            ) x
        """)
        receita_anterior = await db.fetchval("""
            SELECT COALESCE(SUM(total),0) FROM (
                SELECT total FROM vendas_pedidos WHERE data >= CURRENT_DATE - 60 AND data < CURRENT_DATE - 30 AND status != 'cancelado'
                UNION ALL SELECT total FROM pdv_vendas WHERE DATE(data) >= CURRENT_DATE - 60 AND DATE(data) < CURRENT_DATE - 30
            ) x
        """)
        qtd_atual = await db.fetchval("""
            SELECT COUNT(*) FROM (
                SELECT id FROM vendas_pedidos WHERE data >= CURRENT_DATE - 30 AND status != 'cancelado'
                UNION ALL SELECT id FROM pdv_vendas WHERE DATE(data) >= CURRENT_DATE - 30
            ) x
        """)
        qtd_anterior = await db.fetchval("""
            SELECT COUNT(*) FROM (
                SELECT id FROM vendas_pedidos WHERE data >= CURRENT_DATE - 60 AND data < CURRENT_DATE - 30 AND status != 'cancelado'
                UNION ALL SELECT id FROM pdv_vendas WHERE DATE(data) >= CURRENT_DATE - 60 AND DATE(data) < CURRENT_DATE - 30
            ) x
        """)
        return float(receita_atual or 0), float(receita_anterior or 0), qtd_atual or 0, qtd_anterior or 0
    try:
        receita_atual, receita_anterior, qtd_atual, qtd_anterior = run_async(_comparativo_mensal())
        var_receita = _variacao(receita_atual, receita_anterior)
        ticket_atual = receita_atual / max(qtd_atual, 1)
        ticket_anterior = receita_anterior / max(qtd_anterior, 1)
        var_ticket = _variacao(ticket_atual, ticket_anterior)
    except Exception as e:
        log(AGENT, f"Erro comparativo mensal dashboard: {e}")
        var_receita = var_ticket = None
    # Margem do periodo anterior nao e' calculavel com precisao (CMV via
    # fin_contas_pagar reflete status PENDENTE atual, nao o custo real daquele
    # periodo passado) — omitido em vez de estimado, mesma logica de indicadores().

    async def _churn():
        db = await get_db()
        ativos_90 = await db.fetchval("""
            SELECT COUNT(DISTINCT cliente_id) FROM (
                SELECT cliente_id FROM vendas_pedidos WHERE cliente_id IS NOT NULL AND data >= CURRENT_DATE - 90
                UNION SELECT cliente_id FROM pdv_vendas WHERE cliente_id IS NOT NULL AND DATE(data) >= CURRENT_DATE - 90
            ) x
        """)
        if not ativos_90:
            return None
        ativos_30 = await db.fetchval("""
            SELECT COUNT(DISTINCT cliente_id) FROM (
                SELECT cliente_id FROM vendas_pedidos WHERE cliente_id IS NOT NULL AND data >= CURRENT_DATE - 30
                UNION SELECT cliente_id FROM pdv_vendas WHERE cliente_id IS NOT NULL AND DATE(data) >= CURRENT_DATE - 30
            ) x
        """)
        return round((1 - (ativos_30 or 0) / ativos_90) * 100, 1)
    try:
        churn = run_async(_churn())
    except Exception as e:
        log(AGENT, f"Erro churn dashboard: {e}")
        churn = None

    return {"kpis": [
        {"label": "Receita (mês)", "value": _fmt_brl(v["total"]), "color": "text-emerald-400", "variacao": var_receita},
        {"label": "Ticket Médio", "value": _fmt_brl(t["ticket_medio"]), "color": "text-blue-400", "variacao": var_ticket},
        {"label": "Margem Média", "value": _fmt_pct(d["margem_bruta_pct"]), "color": "text-purple-400"},
        {"label": "Previsão (próx. mês)", "value": _fmt_brl(p["previsao_30d"]), "color": "text-indigo-400"},
        {"label": "ROI", "value": "--", "color": "text-neutral-500"},
        {"label": "Churn (30d)", "value": (f"{churn}%" if churn is not None else "--"),
         "color": "text-red-400" if (churn or 0) > 20 else "text-emerald-400"},
    ]}


# ── Vendas: diarias e por categoria ──

def vendas_diarias(dias: int = 30) -> list:
    from core.relatorios import _union_vendas
    r = _union_vendas(dias)
    por_dia = {}
    for row in r["diarias_bling"] + r["diarias_pdv"]:
        d = row["dia"]
        chave = d.isoformat() if hasattr(d, "isoformat") else str(d)
        por_dia[chave] = por_dia.get(chave, 0) + float(row["valor"] or 0)
    saida = []
    for chave in sorted(por_dia.keys()):
        y, m, dd = chave.split("-")
        saida.append({"dia": f"{dd}/{m}", "valor": round(por_dia[chave], 2), "custo": 0, "margem": 0})
    return saida


def vendas_categorias(dias: int = 30, limite_produtos: int = 5) -> list:
    async def _go():
        db = await get_db()
        bling = await db.fetch(f"""
            SELECT COALESCE(NULLIF(c.categoria, ''), 'Sem categoria') AS categoria, i.sku,
                   COALESCE(c.descricao, i.descricao) AS nome,
                   SUM(i.quantidade) AS qtd, SUM(i.valor_total) AS valor,
                   MAX(c.preco_custo) AS preco_custo
            FROM vendas_itens i
            JOIN vendas_pedidos p ON p.id = i.pedido_id
            LEFT JOIN catalogo_produtos c ON c.sku = i.sku
            WHERE p.data >= CURRENT_DATE - $1::int AND p.status != 'cancelado'
            GROUP BY 1, i.sku, nome
        """, dias)
        pdv = await db.fetch(f"""
            SELECT COALESCE(NULLIF(c.categoria, ''), 'Sem categoria') AS categoria, i.produto_codigo AS sku,
                   COALESCE(c.descricao, i.descricao) AS nome,
                   SUM(i.quantidade) AS qtd, SUM(i.valor_total) AS valor,
                   MAX(c.preco_custo) AS preco_custo
            FROM pdv_itens i
            JOIN pdv_vendas v ON v.id = i.venda_id
            LEFT JOIN catalogo_produtos c ON c.sku = i.produto_codigo
            WHERE DATE(v.data) >= CURRENT_DATE - $1::int
            GROUP BY 1, i.produto_codigo, nome
        """, dias)
        return [dict(r) for r in bling] + [dict(r) for r in pdv]
    try:
        linhas = run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro vendas_categorias: {e}")
        return []

    produtos_por_sku = {}
    for linha in linhas:
        chave = (linha["categoria"], linha["sku"])
        acc = produtos_por_sku.setdefault(chave, {"categoria": linha["categoria"], "nome": linha["nome"] or linha["sku"] or "—",
                                                    "sku": linha["sku"] or "", "qtd": 0.0, "valor": 0.0, "preco_custo": linha["preco_custo"]})
        acc["qtd"] += float(linha["qtd"] or 0)
        acc["valor"] += float(linha["valor"] or 0)

    categorias = {}
    for (categoria, _sku), p in produtos_por_sku.items():
        custo_total = float(p["preco_custo"] or 0) * p["qtd"]
        margem = round((p["valor"] - custo_total) / p["valor"] * 100, 1) if p["valor"] and p["preco_custo"] is not None else 0
        produto = {"nome": p["nome"], "sku": p["sku"], "valor": round(p["valor"], 2), "qtd": round(p["qtd"], 2), "margem": margem}
        cat = categorias.setdefault(categoria, {"categoria": categoria, "valor": 0.0, "produtos": []})
        cat["valor"] += p["valor"]
        cat["produtos"].append(produto)

    total_geral = sum(c["valor"] for c in categorias.values()) or 1
    resultado = []
    for cat in categorias.values():
        cat["produtos"].sort(key=lambda p: p["valor"], reverse=True)
        cat["produtos"] = cat["produtos"][:limite_produtos]
        resultado.append({
            "categoria": cat["categoria"], "valor": round(cat["valor"], 2),
            "percentual": round(cat["valor"] / total_geral * 100, 1), "produtos": cat["produtos"],
        })
    resultado.sort(key=lambda c: c["valor"], reverse=True)
    return resultado


# ── Indicadores financeiros ──
# So' os que dao pra calcular com dado real (sem balanco patrimonial nao da'
# pra ter liquidez/ROE/ROI/endividamento — ficariam inventados).

def indicadores() -> list:
    from core.relatorios import dre as rel_dre, lucro_margem as rel_lucro

    async def _go():
        db = await get_db()
        d90 = rel_dre(90)
        custos_periodo = float((await db.fetchval(
            "SELECT COALESCE(SUM(valor_total),0) FROM compras_pedidos WHERE data_emissao >= CURRENT_DATE - 90"
        )) or 0) + float((await db.fetchval(
            "SELECT COALESCE(SUM(valor),0) FROM producao_custos WHERE data >= CURRENT_DATE - 90"
        )) or 0)
        estoque_valor = float((await db.fetchval(
            "SELECT COALESCE(SUM(e.quantidade * COALESCE(c.preco_custo,0)),0) FROM estoque_lojas e JOIN catalogo_produtos c ON c.sku = e.sku"
        )) or 0)
        giro = round((custos_periodo * (365 / 90)) / estoque_valor, 1) if estoque_valor else None

        prazo_receb = await db.fetchval(
            "SELECT AVG(vencimento - created_at::date) FROM fin_contas_receber WHERE created_at >= NOW() - INTERVAL '90 days'"
        )
        prazo_pagto = await db.fetchval(
            "SELECT AVG(vencimento - created_at::date) FROM fin_contas_pagar WHERE created_at >= NOW() - INTERVAL '90 days'"
        )

        receita_atual = await db.fetchval("""
            SELECT COALESCE(SUM(total),0) FROM (
                SELECT total FROM vendas_pedidos WHERE data >= CURRENT_DATE - 30 AND status != 'cancelado'
                UNION ALL SELECT total FROM pdv_vendas WHERE DATE(data) >= CURRENT_DATE - 30
            ) x
        """)
        receita_anterior = await db.fetchval("""
            SELECT COALESCE(SUM(total),0) FROM (
                SELECT total FROM vendas_pedidos WHERE data >= CURRENT_DATE - 60 AND data < CURRENT_DATE - 30 AND status != 'cancelado'
                UNION ALL SELECT total FROM pdv_vendas WHERE DATE(data) >= CURRENT_DATE - 60 AND DATE(data) < CURRENT_DATE - 30
            ) x
        """)
        crescimento = round((float(receita_atual or 0) - float(receita_anterior or 0)) / float(receita_anterior) * 100, 1) if receita_anterior else None

        return d90, giro, prazo_receb, prazo_pagto, crescimento
    try:
        d90, giro, prazo_receb, prazo_pagto, crescimento = run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro indicadores: {e}")
        return []

    lm = rel_lucro(90)

    def _linha(id_, nome, valor, unidade, referencia, limite_bom, limite_atencao=None, menor_e_melhor=False):
        if valor is None:
            return None
        if menor_e_melhor:
            status = "good" if valor <= limite_bom else ("warning" if limite_atencao is None or valor <= limite_atencao else "danger")
        else:
            status = "good" if valor >= limite_bom else ("warning" if limite_atencao is None or valor >= limite_atencao else "danger")
        return {"id": id_, "nome": nome, "valor": round(valor, 1), "unidade": unidade,
                "tendencia": "stable", "tendenciaValor": 0, "referencia": referencia, "status": status}

    linhas = [
        _linha("margem-bruta", "Margem Bruta", d90.get("margem_bruta_pct"), "%", "> 45%", 45, 30),
        _linha("margem-liquida", "Margem Líquida (aprox.)", lm.get("margem_pct"), "%", "> 15%", 15, 5),
        _linha("giro-estoque", "Giro de Estoque", giro, "x/ano", "> 6.0", 6, 3),
        _linha("prazo-medio-receb", "Prazo Médio de Recebimento", float(prazo_receb) if prazo_receb is not None else None,
               "dias", "< 30 dias", 30, 45, menor_e_melhor=True),
        _linha("prazo-medio-pagto", "Prazo Médio de Pagamento", float(prazo_pagto) if prazo_pagto is not None else None,
               "dias", "informativo — maior prazo ajuda o caixa", 0),
        _linha("crescimento-receita", "Crescimento de Receita (30d vs. 30d anteriores)", crescimento, "%", "> 0%", 0, -10),
    ]
    return [l for l in linhas if l is not None]


# ── Forecast: historico real + projecao estatistica simples (media movel) ──
# Nao e' um modelo de ML — e' uma extrapolacao transparente da media/desvio
# historico. Rotulado assim no frontend para nao parecer mais sofisticado
# do que e'.

def forecast(dias_historico: int = 60, dias_previsao: int = 30) -> dict:
    from core.relatorios import _union_vendas
    r = _union_vendas(dias_historico)
    por_dia = {}
    for row in r["diarias_bling"] + r["diarias_pdv"]:
        d = row["dia"]
        chave = d.isoformat() if hasattr(d, "isoformat") else str(d)
        por_dia[chave] = por_dia.get(chave, 0) + float(row["valor"] or 0)

    valores = [por_dia[k] for k in sorted(por_dia.keys())]
    media = statistics.fmean(valores) if valores else 0
    desvio = statistics.pstdev(valores) if len(valores) > 1 else 0

    pontos = []
    for chave in sorted(por_dia.keys()):
        y, m, dd = chave.split("-")
        pontos.append({"periodo": f"{dd}/{m}", "historico": round(por_dia[chave], 2)})
    hoje_ref = date.today()
    for i in range(1, dias_previsao + 1):
        d = hoje_ref + timedelta(days=i)
        pontos.append({
            "periodo": d.strftime("%d/%m"), "previsao": round(media, 2),
            "limiteInferior": round(max(media - desvio, 0), 2), "limiteSuperior": round(media + desvio, 2),
        })

    receita_projetada = round(media * dias_previsao, 2)
    receita_anterior_periodo = round(sum(valores[-dias_previsao:]) if len(valores) >= dias_previsao else sum(valores), 2)
    crescimento = round((receita_projetada - receita_anterior_periodo) / receita_anterior_periodo * 100, 1) if receita_anterior_periodo else 0
    confianca = round(max(0, 100 - (desvio / media * 100 if media else 100)), 0)

    return {
        "pontos": pontos,
        "resumo": {
            "receitaProjetada": receita_projetada,
            "crescimentoEsperado": crescimento,
            "confianca": confianca,
            "cenarios": {
                "otimista": round((media + desvio) * dias_previsao, 2),
                "esperado": receita_projetada,
                "pessimista": round(max(media - desvio, 0) * dias_previsao, 2),
            },
            "fatores": [
                {"nome": "Média diária (histórico)", "impacto": "neutro", "valor": _fmt_brl(media)},
                {"nome": "Variação diária (desvio padrão)", "impacto": "neutro", "valor": _fmt_brl(desvio)},
            ],
        },
    }


# ── ML simples: anomalias, segmentacao RFM, cross-sell ──
# Estatistica transparente (z-score, RFM, co-ocorrencia) — nao e' deep
# learning, mas e' real: nenhum numero aqui e' inventado.

def ml_anomalias(dias: int = 30) -> list:
    from core.relatorios import _union_vendas
    from core.estoque_relatorios import por_loja as discrepancias_por_loja
    anomalias = []

    r = _union_vendas(dias)
    por_dia = {}
    for row in r["diarias_bling"] + r["diarias_pdv"]:
        d = row["dia"]
        chave = d.isoformat() if hasattr(d, "isoformat") else str(d)
        por_dia[chave] = por_dia.get(chave, 0) + float(row["valor"] or 0)
    valores = list(por_dia.values())
    if len(valores) >= 5:
        media = statistics.fmean(valores)
        desvio = statistics.pstdev(valores) or 1
        aid = 1
        for chave, valor in por_dia.items():
            z = (valor - media) / desvio
            if abs(z) >= 2:
                anomalias.append({
                    "id": aid, "tipo": "venda", "severidade": "critico" if abs(z) >= 3 else "moderado",
                    "descricao": f"Venda de {chave} {'muito acima' if z > 0 else 'muito abaixo'} da média ({_fmt_brl(valor)} vs. média {_fmt_brl(media)})",
                    "valor": round(valor, 2), "impacto": f"{'+' if z > 0 else ''}{round(z, 1)} desvios-padrão",
                    "data": chave, "recomendacao": "Verificar se foi promoção/evento pontual ou erro de lançamento.",
                })
                aid += 1

    try:
        discrepancias = discrepancias_por_loja(dias)
    except Exception:
        discrepancias = []
    aid = len(anomalias) + 1
    for d in discrepancias:
        if d["unidades_falta_contagem"] > 0:
            anomalias.append({
                "id": aid, "tipo": "estoque", "severidade": "critico" if d["unidades_falta_contagem"] > 50 else "moderado",
                "descricao": f"Loja {d['loja']}: {d['unidades_falta_contagem']:.0f} unidades de falta em contagens nos últimos {dias} dias",
                "valor": d["unidades_falta_contagem"], "impacto": f"{d['contagens_com_falta']} contagem(ns) com discrepância",
                "data": date.today().isoformat(), "recomendacao": "Cruzar com histórico de saídas aprovadas e câmeras, se houver.",
            })
            aid += 1
    return anomalias


def ml_segmentos() -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT c.id, c.nome, MAX(v.data) AS ultima_compra, COUNT(v.id) AS freq, COALESCE(SUM(v.total),0) AS monetario
            FROM cad_clientes c
            LEFT JOIN (
                SELECT cliente_id, data, total FROM vendas_pedidos WHERE status != 'cancelado'
                UNION ALL SELECT cliente_id, data, total FROM pdv_vendas
            ) v ON v.cliente_id = c.id
            WHERE c.status = 'ativo'
            GROUP BY c.id, c.nome
        """)
        return [dict(r) for r in rows]
    try:
        clientes = run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ml_segmentos: {e}")
        return []
    if not clientes:
        return []

    hoje_ref = date.today()
    segmentos = {
        "Campeões": {"clientes": [], "descricao": "Compraram recentemente, com frequência e alto valor."},
        "Fiéis": {"clientes": [], "descricao": "Compram com regularidade, valor moderado."},
        "Em risco": {"clientes": [], "descricao": "Já compraram bastante, mas sumiram nos últimos meses."},
        "Novos": {"clientes": [], "descricao": "Primeira(s) compra(s) recente(s), ainda sem histórico."},
        "Inativos": {"clientes": [], "descricao": "Sem nenhuma compra registrada ou há muito tempo sem comprar."},
    }
    for c in clientes:
        freq = c["freq"] or 0
        monetario = float(c["monetario"] or 0)
        if not c["ultima_compra"]:
            segmentos["Inativos"]["clientes"].append(c); continue
        recencia = (hoje_ref - c["ultima_compra"]).days
        if recencia > 180:
            segmentos["Inativos"]["clientes"].append(c)
        elif recencia > 90:
            segmentos["Em risco"]["clientes"].append(c)
        elif freq <= 1:
            segmentos["Novos"]["clientes"].append(c)
        elif freq >= 4 and monetario >= 1000:
            segmentos["Campeões"]["clientes"].append(c)
        else:
            segmentos["Fiéis"]["clientes"].append(c)

    total = len(clientes) or 1
    resultado = []
    for nome, dados in segmentos.items():
        membros = dados["clientes"]
        if not membros:
            continue
        churn_membros = sum(1 for m in membros if not m["ultima_compra"] or (hoje_ref - m["ultima_compra"]).days > 90)
        top_membros = sorted(membros, key=lambda m: float(m["monetario"] or 0), reverse=True)[:5]
        resultado.append({
            "segmento": nome,
            "percentual": round(len(membros) / total * 100, 1),
            "receitaMedia": round(sum(float(m["monetario"] or 0) for m in membros) / len(membros), 2),
            "churn": round(churn_membros / len(membros) * 100, 1),
            "descricao": dados["descricao"],
            "qtd_clientes": len(membros),
            "clientes": [
                {"nome": m["nome"], "valor": round(float(m["monetario"] or 0), 2),
                 "dias_sem_comprar": (hoje_ref - m["ultima_compra"]).days if m["ultima_compra"] else None}
                for m in top_membros
            ],
        })
    resultado.sort(key=lambda s: s["percentual"], reverse=True)
    return resultado


def ml_recomendacoes(dias: int = 90, minimo_ocorrencias: int = 3) -> list:
    """Cross-sell por co-ocorrencia real (produtos comprados juntos no mesmo
    pedido) — confianca = P(B comprado | A comprado), suporte classico de
    regra de associacao, nao e' um numero de confianca inventado."""
    async def _go():
        db = await get_db()
        pares = await db.fetch(f"""
            SELECT a.sku AS sku_a, b.sku AS sku_b, COUNT(*) AS juntos, SUM(a.valor_total + b.valor_total) AS receita
            FROM vendas_itens a
            JOIN vendas_itens b ON b.pedido_id = a.pedido_id AND b.sku > a.sku
            JOIN vendas_pedidos p ON p.id = a.pedido_id
            WHERE p.data >= CURRENT_DATE - $1::int AND p.status != 'cancelado' AND a.sku IS NOT NULL AND b.sku IS NOT NULL
            GROUP BY a.sku, b.sku
            HAVING COUNT(*) >= $2
            ORDER BY juntos DESC LIMIT 10
        """, dias, minimo_ocorrencias)
        totais_sku = await db.fetch(f"""
            SELECT sku, COUNT(DISTINCT pedido_id) AS pedidos FROM vendas_itens i
            JOIN vendas_pedidos p ON p.id = i.pedido_id
            WHERE p.data >= CURRENT_DATE - $1::int AND p.status != 'cancelado' AND sku IS NOT NULL
            GROUP BY sku
        """, dias)
        nomes = await db.fetch("SELECT sku, descricao FROM catalogo_produtos")
        return [dict(r) for r in pares], {r["sku"]: r["pedidos"] for r in totais_sku}, {r["sku"]: r["descricao"] for r in nomes}
    try:
        pares, totais_sku, nomes = run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ml_recomendacoes: {e}")
        return []

    recomendacoes = []
    for i, par in enumerate(pares, start=1):
        total_a = totais_sku.get(par["sku_a"], 0) or 1
        confianca = round(par["juntos"] / total_a * 100, 1)
        nome_a = nomes.get(par["sku_a"], par["sku_a"])
        nome_b = nomes.get(par["sku_b"], par["sku_b"])
        recomendacoes.append({
            "id": i, "tipo": "cross-sell",
            "descricao": f"Quem compra \"{nome_a}\" também costuma levar \"{nome_b}\" ({par['juntos']}x nos últimos {dias} dias)",
            "confianca": confianca, "receitaEstimada": round(float(par["receita"] or 0), 2),
            "acao": f"Sugerir \"{nome_b}\" no checkout/atendimento ao vender \"{nome_a}\"",
        })
    return recomendacoes


# ── Capital parado em estoque ──

def estoque_parado(dias: int = 60, limite: int = 10) -> list:
    """Produtos com saldo em estoque mas sem nenhuma venda nos ultimos `dias` —
    capital imobilizado parado, calculado cruzando saldo real (estoque_lojas)
    com historico real de venda (vendas_itens/pdv_itens), nada estimado."""
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"""
            SELECT e.sku, MAX(c.descricao) AS nome, SUM(e.quantidade) AS quantidade, MAX(c.preco_custo) AS preco_custo
            FROM estoque_lojas e
            JOIN catalogo_produtos c ON c.sku = e.sku
            WHERE e.quantidade > 0
              AND e.sku NOT IN (
                  SELECT DISTINCT i.sku FROM vendas_itens i JOIN vendas_pedidos p ON p.id = i.pedido_id
                  WHERE p.data >= CURRENT_DATE - $1::int AND p.status != 'cancelado' AND i.sku IS NOT NULL
                  UNION
                  SELECT DISTINCT i.produto_codigo FROM pdv_itens i JOIN pdv_vendas v ON v.id = i.venda_id
                  WHERE DATE(v.data) >= CURRENT_DATE - $1::int AND i.produto_codigo IS NOT NULL
              )
            GROUP BY e.sku
        """, dias)
        return [dict(r) for r in rows]
    try:
        linhas = run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro estoque_parado: {e}")
        return []

    resultado = []
    for r in linhas:
        preco_custo = float(r["preco_custo"] or 0)
        quantidade = float(r["quantidade"] or 0)
        resultado.append({
            "sku": r["sku"], "nome": r["nome"] or r["sku"],
            "quantidade": round(quantidade, 2), "valor_imobilizado": round(quantidade * preco_custo, 2),
            "dias_sem_venda": dias,
        })
    resultado.sort(key=lambda p: p["valor_imobilizado"], reverse=True)
    return resultado[:limite]


# ── Acoes do mes: alertas acionaveis cruzando os sinais acima ──
# Cada bloco so' aparece se houver dado real por tras — nenhum card e' mostrado
# vazio/zerado so' pra preencher espaco.

def acoes_do_mes() -> dict:
    from core.relatorios import aging_financeiro as rel_aging

    parados = estoque_parado(dias=60, limite=5)
    capital_parado = {
        "total_valor": round(sum(p["valor_imobilizado"] for p in parados), 2),
        "itens": parados,
    } if parados else None

    aging = rel_aging()
    inadimplencia = {
        "total_valor": aging.get("vencidas_valor", 0),
        "total_qtd": aging.get("vencidas", 0),
        "maiores_devedores": aging.get("maiores_devedores", []),
    } if aging.get("vencidas") else None

    segmentos = ml_segmentos()
    em_risco = next((s for s in segmentos if s["segmento"] == "Em risco"), None)
    clientes_em_risco = {
        "qtd_clientes": em_risco["qtd_clientes"], "clientes": em_risco["clientes"],
    } if em_risco and em_risco.get("clientes") else None

    anomalias = ml_anomalias(dias=30)
    maior_anomalia = None
    if anomalias:
        maior_anomalia = sorted(anomalias, key=lambda a: 2 if a["severidade"] == "critico" else 1, reverse=True)[0]

    return {
        "capital_parado": capital_parado,
        "inadimplencia": inadimplencia,
        "clientes_em_risco": clientes_em_risco,
        "maior_anomalia": maior_anomalia,
    }
