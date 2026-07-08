"""
AG-02: Analista de Lucratividade
Calcula o lucro REAL de cada SKU descontando:
custo de matéria-prima, mão de obra, taxa do marketplace, frete, impostos.
Identifica produtos que vendem muito mas dão pouco lucro.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log, hoje, pct, FactoryConfig

AGENT = "AG-02 | Analista de Lucratividade"

# ===========================================================================
# Cálculo de lucro real
# ===========================================================================

def calcular_lucro_real(preco_venda: float, custo_unitario: float,
                        taxa_marketplace_pct: float, frete: float,
                        imposto_pct: float = 8.0) -> dict:
    """
    Calcula lucro líquido real de uma venda.
    """
    taxa_valor = preco_venda * (taxa_marketplace_pct / 100)
    imposto_valor = preco_venda * (imposto_pct / 100)
    receita_liquida = preco_venda - taxa_valor - frete - imposto_valor
    lucro_liquido = receita_liquida - custo_unitario
    margem_pct = round((lucro_liquido / preco_venda) * 100, 1) if preco_venda else 0

    return {
        "preco_venda": round(preco_venda, 2),
        "custo_unitario": round(custo_unitario, 2),
        "taxa_marketplace": round(taxa_valor, 2),
        "frete": round(frete, 2),
        "impostos": round(imposto_valor, 2),
        "receita_liquida": round(receita_liquida, 2),
        "lucro_liquido": round(lucro_liquido, 2),
        "margem_pct": margem_pct,
    }

# ===========================================================================
# Análise por SKU
# ===========================================================================

def analisar_sku(sku: str, dias: int = 30) -> dict:
    """Analisa lucratividade de um SKU específico nos últimos N dias."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT
                COUNT(*) AS total_vendas,
                SUM(quantidade) AS qtd_total,
                SUM(receita_bruta) AS receita_total,
                AVG(taxa_marketplace_pct) AS taxa_media,
                SUM(taxa_marketplace_valor) AS taxas_total,
                SUM(frete) AS frete_total,
                SUM(impostos) AS impostos_total
            FROM vendas
            WHERE sku = $1 AND data >= CURRENT_DATE - make_interval(days => $2)
        """, sku, dias)

        if not rows or not rows[0]["total_vendas"]:
            return {"sku": sku, "erro": "Sem dados de venda no período"}

        r = rows[0]
        # Busca custo mais recente
        custo = await db.fetchrow("""
            SELECT custo_total FROM historico_custos
            WHERE sku = $1 ORDER BY data DESC LIMIT 1
        """, sku)
        custo_unitario = float(custo["custo_total"]) if custo else 0

        receita = float(r["receita_total"])
        taxas = float(r["taxas_total"] or 0)
        frete = float(r["frete_total"] or 0)
        impostos = float(r["impostos_total"] or 0)
        qtd = int(r["qtd_total"])

        custo_total = custo_unitario * qtd
        lucro = receita - taxas - frete - impostos - custo_total
        margem = pct(lucro, receita)

        cfg = FactoryConfig.load()
        status = "saudavel"
        if margem < cfg.margem_minima_pct:
            status = "deficit"
        elif margem < cfg.margem_minima_pct * 1.5:
            status = "alerta"

        return {
            "sku": sku,
            "periodo_dias": dias,
            "total_vendas": int(r["total_vendas"]),
            "qtd_vendida": qtd,
            "receita_total": round(receita, 2),
            "taxas_total": round(taxas, 2),
            "frete_total": round(frete, 2),
            "impostos_total": round(impostos, 2),
            "custo_total": round(custo_total, 2),
            "lucro_liquido": round(lucro, 2),
            "margem_pct": round(margem, 1),
            "custo_unitario": round(custo_unitario, 4),
            "status": status,
        }
    return run_async(_go())

# ===========================================================================
# Rankings
# ===========================================================================

def top_lucrativos(n: int = 10) -> list:
    """Top N SKUs mais lucrativos."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT sku, SUM(receita_bruta) AS receita,
                   SUM(receita_bruta - taxa_marketplace_valor - frete - impostos) AS receita_liquida
            FROM vendas
            WHERE data >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY sku
            ORDER BY receita_liquida DESC
            LIMIT $1
        """, n)
        return [dict(r) for r in rows]
    return run_async(_go())

def bottom_deficitarios(n: int = 10) -> list:
    """SKUs com pior margem ou deficitários."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT sku,
                   SUM(receita_bruta) AS receita_total,
                   SUM(taxa_marketplace_valor) + SUM(frete) + SUM(impostos) AS custos_variaveis,
                   COUNT(*) AS total_vendas
            FROM vendas
            WHERE data >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY sku
            HAVING SUM(receita_bruta) < SUM(taxa_marketplace_valor) + SUM(frete) + SUM(impostos)
            ORDER BY receita_total DESC
            LIMIT $1
        """, n)
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Relatório diário
# ===========================================================================

def relatorio_diario() -> dict:
    """Gera relatório de lucratividade do dia."""
    log(AGENT, "Gerando relatório diário...")
    async def _go():
        db = await get_db()
        today = await db.fetchrow("""
            SELECT
                COUNT(DISTINCT sku) AS skus_vendidos,
                SUM(quantidade) AS qtd_total,
                SUM(receita_bruta) AS receita_total,
                SUM(taxa_marketplace_valor) AS taxas,
                SUM(frete) AS fretes,
                SUM(impostos) AS impostos
            FROM vendas
            WHERE data = CURRENT_DATE
        """)
        return {
            "data": hoje(),
            "skus_vendidos": int(today["skus_vendidos"] or 0),
            "qtd_total": int(today["qtd_total"] or 0),
            "receita_total": round(float(today["receita_total"] or 0), 2),
            "taxas_total": round(float(today["taxas"] or 0), 2),
            "frete_total": round(float(today["fretes"] or 0), 2),
            "impostos_total": round(float(today["impostos"] or 0), 2),
        }
    return run_async(_go())

# ===========================================================================
# Alertas
# ===========================================================================

def verificar_alertas() -> list:
    """Verifica SKUs com margem abaixo do mínimo e gera alertas."""
    cfg = FactoryConfig.load()
    log(AGENT, f"Verificando alertas (margem mínima: {cfg.margem_minima_pct}%)...")

    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT sku, margem_pct, lucro_liquido
            FROM margens_diarias
            WHERE data = CURRENT_DATE AND margem_pct < $1
            ORDER BY margem_pct ASC
        """, cfg.margem_minima_pct)

        alertas = []
        for r in rows:
            msg = f"SKU {r['sku']} com margem de {r['margem_pct']}% — abaixo do mínimo de {cfg.margem_minima_pct}%"
            alertas.append({"sku": r["sku"], "margem": r["margem_pct"], "lucro": float(r["lucro_liquido"]), "mensagem": msg})

            await db.execute("""
                INSERT INTO alertas (tipo, sku, mensagem, gravidade)
                VALUES ('margem', $1, $2, 'alerta')
            """, r["sku"], msg)

        return alertas
    return run_async(_go())

# ===========================================================================
# Auto-teste
# ===========================================================================

if __name__ == "__main__":
    log(AGENT, "=== Auto-teste ===")

    # Teste de cálculo isolado
    resultado = calcular_lucro_real(
        preco_venda=49.90,
        custo_unitario=8.50,
        taxa_marketplace_pct=18.0,
        frete=5.00,
    )
    print("Cálculo isolado:", resultado)

    print("\nRelatório:", relatorio_diario())
