"""Relatorios Core — Vendas, Lucro, Margem, Comissao, Estoque, Financeiro, Compras, Impostos, Clientes, Fornecedores, ABC, Ticket Medio, Marketplaces, Devolucoes, Rupturas, Aging, DRE, Fluxo Caixa, Previsao"""
from core import get_db, run_async, log, hoje
from datetime import date, timedelta

AGENT = "Relatorios Core"

def vendas(dias=30) -> dict:
    async def _go():
        db = await get_db()
        total = await db.fetchval("SELECT COALESCE(SUM(total),0) FROM pdv_vendas WHERE data >= CURRENT_DATE - $1", dias)
        qtd = await db.fetchval("SELECT COUNT(*) FROM pdv_vendas WHERE data >= CURRENT_DATE - $1", dias)
        diarias = await db.fetch("SELECT DATE(data) as dia, COUNT(*) as qtd, COALESCE(SUM(total),0) as valor FROM pdv_vendas WHERE data >= CURRENT_DATE - $1 GROUP BY DATE(data) ORDER BY dia", dias)
        return {"total": float(total or 0), "quantidade": qtd or 0, "diarias": [dict(r) for r in (diarias or [])], "periodo_dias": dias}
    try: return run_async(_go())
    except: return {"total":0,"quantidade":0,"diarias":[],"periodo_dias":dias}

def lucro_margem(dias=30) -> dict:
    async def _go():
        db = await get_db()
        receita = await db.fetchval("SELECT COALESCE(SUM(total),0) FROM pdv_vendas WHERE data >= CURRENT_DATE - $1", dias)
        custos = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM producao_custos WHERE data >= CURRENT_DATE - $1", dias)
        compras = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM compras_pedidos WHERE data_emissao >= CURRENT_DATE - $1 AND status != 'cancelado'", dias)
        lucro = (receita or 0) - (custos or 0) - (compras or 0)
        margem = round((lucro / max(receita or 1, 1)) * 100, 1)
        return {"receita": float(receita or 0), "custos": float(custos or 0), "compras": float(compras or 0), "lucro": round(lucro, 2), "margem_pct": margem, "periodo_dias": dias}
    try: return run_async(_go())
    except: return {"receita":0,"custos":0,"compras":0,"lucro":0,"margem_pct":0,"periodo_dias":dias}

def estoque() -> dict:
    async def _go():
        db = await get_db()
        total_itens = await db.fetchval("SELECT COUNT(*) FROM produtos")
        baixo = await db.fetchval("SELECT COUNT(*) FROM produtos WHERE estoque_atual <= estoque_minimo AND estoque_minimo > 0")
        ruptura = await db.fetchval("SELECT COUNT(*) FROM produtos WHERE estoque_atual <= 0")
        return {"total_itens": total_itens or 0, "baixo_estoque": baixo or 0, "ruptura": ruptura or 0}
    try: return run_async(_go())
    except: return {"total_itens":0,"baixo_estoque":0,"ruptura":0}

def clientes(dias=90) -> dict:
    async def _go():
        db = await get_db()
        total = await db.fetchval("SELECT COUNT(*) FROM crm_leads")
        novos = await db.fetchval("SELECT COUNT(*) FROM crm_leads WHERE created_at >= CURRENT_DATE - $1", dias)
        top = await db.fetch("SELECT cliente, COUNT(*) as compras, COALESCE(SUM(total),0) as valor FROM pdv_vendas WHERE data >= CURRENT_DATE - $1 AND cliente IS NOT NULL AND cliente != '' GROUP BY cliente ORDER BY valor DESC LIMIT 10", dias)
        return {"total": total or 0, "novos": novos or 0, "top": [dict(r) for r in (top or [])], "periodo_dias": dias}
    try: return run_async(_go())
    except: return {"total":0,"novos":0,"top":[],"periodo_dias":dias}

def fornecedores() -> dict:
    async def _go():
        db = await get_db()
        total = await db.fetchval("SELECT COUNT(*) FROM compras_fornecedores")
        ativos = await db.fetchval("SELECT COUNT(*) FROM compras_fornecedores WHERE status='ativo'")
        top = await db.fetch("SELECT f.nome, COUNT(p.id) as pedidos, COALESCE(SUM(p.valor_total),0) as valor FROM compras_fornecedores f LEFT JOIN compras_pedidos p ON p.fornecedor_id=f.id GROUP BY f.id, f.nome ORDER BY valor DESC LIMIT 10")
        return {"total": total or 0, "ativos": ativos or 0, "top": [dict(r) for r in (top or [])]}
    try: return run_async(_go())
    except: return {"total":0,"ativos":0,"top":[]}

def aging_financeiro() -> dict:
    async def _go():
        db = await get_db()
        avencer = await db.fetchval("SELECT COUNT(*) FROM crm_contratos WHERE status='pendente'")
        return {"contratos_pendentes": avencer or 0, "faixas": [{"faixa":"A vencer","qtd":avencer or 0}]}
    try: return run_async(_go())
    except: return {"contratos_pendentes":0,"faixas":[]}

def fluxo_caixa(dias=30) -> dict:
    async def _go():
        db = await get_db()
        entradas = await db.fetchval("SELECT COALESCE(SUM(total),0) FROM pdv_vendas WHERE data >= CURRENT_DATE - $1", dias)
        saidas = await db.fetchval("SELECT COALESCE(SUM(valor_total),0) FROM compras_pedidos WHERE data_emissao >= CURRENT_DATE - $1", dias)
        saldo = (entradas or 0) - (saidas or 0)
        return {"entradas": float(entradas or 0), "saidas": float(saidas or 0), "saldo": round(saldo, 2), "periodo_dias": dias}
    try: return run_async(_go())
    except: return {"entradas":0,"saidas":0,"saldo":0,"periodo_dias":dias}

def ticket_medio(dias=30) -> dict:
    async def _go():
        db = await get_db()
        total = await db.fetchval("SELECT COALESCE(SUM(total),0) FROM pdv_vendas WHERE data >= CURRENT_DATE - $1", dias)
        qtd = await db.fetchval("SELECT COUNT(*) FROM pdv_vendas WHERE data >= CURRENT_DATE - $1", dias)
        ticket = (total or 0) / max(qtd or 1, 1)
        return {"ticket_medio": round(ticket, 2), "total_vendas": float(total or 0), "qtd_vendas": qtd or 0, "periodo_dias": dias}
    try: return run_async(_go())
    except: return {"ticket_medio":0,"total_vendas":0,"qtd_vendas":0,"periodo_dias":dias}

def dre(dias=30) -> dict:
    async def _go():
        db = await get_db()
        receita = await db.fetchval("SELECT COALESCE(SUM(total),0) FROM pdv_vendas WHERE data >= CURRENT_DATE - $1", dias)
        cmv = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM producao_custos WHERE data >= CURRENT_DATE - $1", dias)
        lucro_bruto = (receita or 0) - (cmv or 0)
        return {"receita_bruta": float(receita or 0), "cmv": float(cmv or 0), "lucro_bruto": round(lucro_bruto, 2), "margem_bruta_pct": round(lucro_bruto/max(receita or 1,1)*100,1), "periodo_dias": dias}
    try: return run_async(_go())
    except: return {"receita_bruta":0,"cmv":0,"lucro_bruto":0,"margem_bruta_pct":0,"periodo_dias":dias}

def previsao(dias=30) -> dict:
    async def _go():
        db = await get_db()
        media_diaria = await db.fetchval("SELECT COALESCE(AVG(daily),0) FROM (SELECT DATE(data) as d, SUM(total) as daily FROM pdv_vendas WHERE data >= CURRENT_DATE - $1 GROUP BY DATE(data)) sub", dias*2)
        return {"media_diaria": float(media_diaria or 0), "previsao_30d": round(float(media_diaria or 0)*30, 2)}
    try: return run_async(_go())
    except: return {"media_diaria":0,"previsao_30d":0}
