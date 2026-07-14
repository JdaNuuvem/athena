"""
AG-204: Financial Controller
Acompanha orçamento vs realizado, controla desvios,
garante conformidade financeira. Frequência: diário + fechamento mensal.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

AGENT = "AG-204 | Financial Controller"

def budget_vs_realizado() -> list:
    """Compara orçamento mensal com realizado."""
    return [
        {"categoria": "Materia-prima", "orcado": 26000.00, "realizado": 28500.00, "desvio_pct": 9.6, "status": "acima"},
        {"categoria": "Mao de obra", "orcado": 43000.00, "realizado": 42500.00, "desvio_pct": -1.2, "status": "dentro"},
        {"categoria": "Energia", "orcado": 11000.00, "realizado": 12800.00, "desvio_pct": 16.4, "status": "acima"},
        {"categoria": "Ferramentas", "orcado": 5000.00, "realizado": 5600.00, "desvio_pct": 12.0, "status": "acima"},
        {"categoria": "Embalagens", "orcado": 3500.00, "realizado": 3200.00, "desvio_pct": -8.6, "status": "abaixo"},
        {"categoria": "Frete", "orcado": 9500.00, "realizado": 9800.00, "desvio_pct": 3.2, "status": "dentro"},
        {"categoria": "Taxas Marketplace", "orcado": 14000.00, "realizado": 15600.00, "desvio_pct": 11.4, "status": "acima"},
        {"categoria": "Manutencao", "orcado": 4000.00, "realizado": 4500.00, "desvio_pct": 12.5, "status": "acima"},
        {"categoria": "Marketing", "orcado": 2000.00, "realizado": 2200.00, "desvio_pct": 10.0, "status": "acima"},
    ]

def resumo_budget() -> dict:
    """Resumo consolidado budget vs realizado."""
    items = budget_vs_realizado()
    total_orcado = sum(i["orcado"] for i in items)
    total_realizado = sum(i["realizado"] for i in items)
    acima = [i for i in items if i["status"] == "acima"]
    return {
        "total_orcado": round(total_orcado, 2),
        "total_realizado": round(total_realizado, 2),
        "desvio_total": round(total_realizado - total_orcado, 2),
        "desvio_total_pct": round((total_realizado - total_orcado) / total_orcado * 100, 1),
        "categorias_acima": len(acima),
        "maior_desvio": max(items, key=lambda i: abs(i["desvio_pct"])),
        "status": "alerta" if total_realizado > total_orcado * 1.05 else "dentro",
    }

def relatorio_controller() -> str:
    res = resumo_budget()
    lines = [
        f"📋 BUDGET VS REALIZADO",
        f"Orçado: R$ {res['total_orcado']:,.2f}",
        f"Realizado: R$ {res['total_realizado']:,.2f}",
        f"Desvio: R$ {res['desvio_total']:,.2f} ({res['desvio_total_pct']:+.1f}%)",
        f"Status geral: {res['status'].upper()}",
        f"Categorias acima do orçamento: {res['categorias_acima']}",
    ]
    return "\n".join(lines)

if __name__ == "__main__":
    print(relatorio_controller())
