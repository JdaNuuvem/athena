"""
Shopee Kits — cross-sell kit suggestions.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core import log, run_async, get_db

AGENT = "AG-03 | Shopee Kits"


def sugerir_kits(dias: int = 90, min_ocorrencias: int = 3) -> list:
    """Analisa vendas e sugere kits com base em produtos comprados juntos.
    Retorna lista de { sku_a, nome_a, sku_b, nome_b, qtd_juntos, confianca_pct }"""
    async def _go():
        db = await get_db()
        # ponytail: pares de SKUs no mesmo pedido nos ultimos N dias
        rows = await db.fetch("""
            SELECT a.sku AS sku_a, b.sku AS sku_b, COUNT(DISTINCT a.pedido_id) AS juntos
            FROM vendas_itens a
            JOIN vendas_itens b ON b.pedido_id = a.pedido_id AND b.sku != a.sku
            JOIN vendas_pedidos v ON v.id = a.pedido_id
            WHERE v.data >= CURRENT_DATE - $1 AND v.status != 'cancelado'
            GROUP BY a.sku, b.sku
            HAVING COUNT(DISTINCT a.pedido_id) >= $2
            ORDER BY juntos DESC
            LIMIT 50
        """, dias, min_ocorrencias)
        resultado = []
        for r in rows:
            # buscar nomes dos produtos
            na = await db.fetchval("SELECT descricao FROM catalogo_produtos WHERE sku = $1", r["sku_a"])
            nb = await db.fetchval("SELECT descricao FROM catalogo_produtos WHERE sku = $1", r["sku_b"])
            total_a = await db.fetchval("SELECT COUNT(DISTINCT pedido_id) FROM vendas_itens WHERE sku = $1", r["sku_a"])
            confianca = round((r["juntos"] / total_a * 100) if total_a else 0, 1)
            resultado.append({
                "sku_a": r["sku_a"], "nome_a": na or r["sku_a"],
                "sku_b": r["sku_b"], "nome_b": nb or r["sku_b"],
                "qtd_juntos": r["juntos"],
                "confianca_pct": confianca,
            })
        # remover duplicatas invertidas (A,B e B,A)
        visto = set()
        unicos = []
        for r in resultado:
            par = tuple(sorted([r["sku_a"], r["sku_b"]]))
            if par not in visto:
                visto.add(par)
                unicos.append(r)
        return unicos[:30]
    try: return run_async(_go())
    except Exception as e: return []
