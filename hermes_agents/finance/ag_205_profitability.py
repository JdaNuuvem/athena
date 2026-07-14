"""
AG-205: Profitability Agent
Calcula margem real por SKU, break-even point,
identifica produtos que vendem muito mas geram pouco lucro.
Complementar ao AG-02 (Analista de Lucratividade do fluxo principal).
Frequência: diário.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

AGENT = "AG-205 | Profitability Agent"

def margem_por_sku() -> list:
    """Margem real por SKU (receita - custos diretos - taxas)."""
    return [
        {"sku": "ORG001", "produto": "Organizador Gaveta", "receita": 897.00, "custos_diretos": 246.00, "taxas": 161.46, "margem": 489.54, "margem_pct": 54.6, "status": "saudavel"},
        {"sku": "PORTA001", "produto": "Porta Tempero Giratorio", "receita": 1497.00, "custos_diretos": 522.00, "taxas": 269.46, "margem": 705.54, "margem_pct": 47.1, "status": "saudavel"},
        {"sku": "POTE001", "produto": "Pote Hermetico 500ml", "receita": 387.00, "custos_diretos": 98.00, "taxas": 69.66, "margem": 219.34, "margem_pct": 56.7, "status": "saudavel"},
        {"sku": "SUP001", "produto": "Suporte Celular Cozinha", "receita": 458.00, "custos_diretos": 150.00, "taxas": 82.44, "margem": 225.56, "margem_pct": 49.2, "status": "saudavel"},
        {"sku": "ESC001", "produto": "Escorredor Louca Dobravel", "receita": 798.00, "custos_diretos": 420.00, "taxas": 143.64, "margem": 234.36, "margem_pct": 29.4, "status": "atencao"},
        {"sku": "CAPA001", "produto": "Capa Sofa Impermavel", "receita": 2398.00, "custos_diretos": 890.00, "taxas": 431.64, "margem": 1076.36, "margem_pct": 44.9, "status": "saudavel"},
    ]

def calcular_breakeven(custo_fixo_mensal: float, margem_media_pct: float) -> dict:
    """Calcula o ponto de equilíbrio (break-even)."""
    preco_medio = 49.90
    margem_unitaria = preco_medio * (margem_media_pct / 100)
    unidades_breakeven = custo_fixo_mensal / margem_unitaria if margem_unitaria > 0 else float("inf")
    return {
        "custo_fixo_mensal": round(custo_fixo_mensal, 2),
        "margem_media_pct": margem_media_pct,
        "preco_medio": preco_medio,
        "margem_unitaria": round(margem_unitaria, 2),
        "unidades_breakeven": round(unidades_breakeven),
        "vendas_dia_necessarias": round(unidades_breakeven / 22),
    }

def ranking_margem() -> list:
    """SKUs ordenados por margem percentual."""
    return sorted(margem_por_sku(), key=lambda s: s["margem_pct"], reverse=True)

def relatorio_profitability() -> str:
    skus = margem_por_sku()
    be = calcular_breakeven(35000.00, 47.0)
    lines = [
        f"💰 RENTABILIDADE POR SKU",
        f"Break-even: {be['unidades_breakeven']} vendas/mês ({be['vendas_dia_necessarias']}/dia)",
        f"Custo fixo: R$ {be['custo_fixo_mensal']:,.2f} | Margem média: {be['margem_media_pct']}%",
        "", "Ranking:",
    ]
    for i, s in enumerate(ranking_margem(), 1):
        status = "✅" if s["status"] == "saudavel" else "⚠️"
        lines.append(f"  {i}. {status} {s['produto']}: {s['margem_pct']}% (R$ {s['margem']:.2f})")
    return "\n".join(lines)

if __name__ == "__main__":
    print(relatorio_profitability())
