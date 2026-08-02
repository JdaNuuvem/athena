"""
Shopee Kits — cross-sell kit suggestions.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core import log, run_async, get_db

AGENT = "AG-03 | Shopee Kits"


def sugerir_kits(dias: int = 90, min_ocorrencias: int = 3) -> list:
    """Analisa vendas Shopee e sugere kits com base em produtos comprados juntos
    no mesmo pedido. Retorna lista de { sku_a, nome_a, sku_b, nome_b, qtd_juntos, confianca_pct }

    ponytail: a versao anterior lia de vendas_itens/vendas_pedidos — tabelas que
    o sync da Shopee NUNCA escreve (so' CRM manual e i9Logic/fisico gravam la'),
    entao esta funcao sempre retornava vazio pra vendas Shopee reais, por mais
    pedidos que existissem. `vendas` (marketplace='shopee', agrupada por
    shopee_order_sn) e' a tabela que o sync realmente popula — ver shopee_sync.
    sync_pedidos(). Tambem corrigido: o self-join sem `b.sku > a.sku` gerava
    (A,B) E (B,A) como linhas separadas, e o dedup em Python rodava DEPOIS do
    LIMIT — pares genuinos podiam ficar de fora se os 50 primeiros slots
    fossem consumidos por duplicatas simetricas. E o calculo de confianca era
    nao-deterministico (dependia de qual das duas linhas simetricas sobrevivia
    ao dedup). Nomes e totais tambem foram batchados (eram N+1 queries, uma
    pra cada resultado)."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT a.sku AS sku_a, b.sku AS sku_b, COUNT(DISTINCT a.shopee_order_sn) AS juntos
            FROM vendas a
            JOIN vendas b ON b.shopee_order_sn = a.shopee_order_sn AND b.sku > a.sku AND b.marketplace = 'shopee'
            WHERE a.marketplace = 'shopee' AND a.shopee_order_sn IS NOT NULL
              AND a.data >= CURRENT_DATE - $1
            GROUP BY a.sku, b.sku
            HAVING COUNT(DISTINCT a.shopee_order_sn) >= $2
            ORDER BY juntos DESC
            LIMIT 30
        """, dias, min_ocorrencias)
        if not rows:
            return []
        skus = sorted({r["sku_a"] for r in rows} | {r["sku_b"] for r in rows})
        nomes_rows = await db.fetch("SELECT sku, descricao FROM catalogo_produtos WHERE sku = ANY($1::text[])", skus)
        nomes = {r["sku"]: r["descricao"] for r in nomes_rows}
        totais_rows = await db.fetch("""
            SELECT sku, COUNT(DISTINCT shopee_order_sn) AS total
            FROM vendas WHERE marketplace = 'shopee' AND shopee_order_sn IS NOT NULL
              AND sku = ANY($1::text[]) AND data >= CURRENT_DATE - $2
            GROUP BY sku
        """, skus, dias)
        totais = {r["sku"]: r["total"] for r in totais_rows}
        resultado = []
        for r in rows:
            total_a = totais.get(r["sku_a"], 0)
            confianca = round((r["juntos"] / total_a * 100) if total_a else 0, 1)
            resultado.append({
                "sku_a": r["sku_a"], "nome_a": nomes.get(r["sku_a"]) or r["sku_a"],
                "sku_b": r["sku_b"], "nome_b": nomes.get(r["sku_b"]) or r["sku_b"],
                "qtd_juntos": r["juntos"],
                "confianca_pct": confianca,
            })
        return resultado
    try: return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro sugerir_kits: {e}")
        return []
