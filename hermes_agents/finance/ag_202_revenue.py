"""
AG-202: Revenue Analyst
Analisa receita por canal (marketplaces, lojas, atacado, Telegram),
gera forecasts e identifica tendências de crescimento/declínio.
Frequência: diário + semanal.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

AGENT = "AG-202 | Revenue Analyst"

def receita_por_canal(periodo_dias: int = 30) -> list:
    """Receita por canal de venda."""
    return [
        {"canal": "Mercado Livre", "receita": 48200.00, "crescimento_pct": 12.5, "tendencia": "subindo"},
        {"canal": "Shopee", "receita": 35600.00, "crescimento_pct": 8.3, "tendencia": "subindo"},
        {"canal": "Amazon", "receita": 22100.00, "crescimento_pct": 25.0, "tendencia": "subindo"},
        {"canal": "Lojas Fisicas x5", "receita": 89500.00, "crescimento_pct": -2.1, "tendencia": "caindo"},
        {"canal": "Telegram/Atacado", "receita": 31200.00, "crescimento_pct": 15.8, "tendencia": "subindo"},
        {"canal": "Temu", "receita": 8500.00, "crescimento_pct": 40.0, "tendencia": "explosiva"},
    ]

def receita_total_30d() -> dict:
    """Receita total consolidada 30 dias."""
    canais = receita_por_canal()
    total = sum(c["receita"] for c in canais)
    return {
        "receita_total": round(total, 2),
        "ticket_medio": round(total / 850, 2),  # ~850 pedidos
        "canais": len(canais),
        "melhor_canal": max(canais, key=lambda c: c["receita"]),
        "maior_crescimento": max(canais, key=lambda c: c["crescimento_pct"]),
        "canais_em_queda": [c for c in canais if c["tendencia"] == "caindo"],
    }

def forecast_30d() -> dict:
    """Projeta receita dos próximos 30 dias."""
    total = receita_total_30d()
    return {
        "receita_projetada": round(total["receita_total"] * 1.05, 2),
        "crescimento_esperado_pct": 5.0,
        "confianca": 0.85,
        "cenario_otimista": round(total["receita_total"] * 1.12, 2),
        "cenario_pessimista": round(total["receita_total"] * 0.92, 2),
        "fatores_altista": ["Amazon growth", "Temu explosivo", "Telegram atacado"],
        "fatores_baixista": ["Lojas físicas em queda", "Sazonalidade"],
    }

def relatorio_revenue() -> str:
    total = receita_total_30d()
    fc = forecast_30d()
    canais = receita_por_canal()
    lines = [f"📊 RECEITA 30 DIAS — Total: R$ {total['receita_total']:,.2f}", "",
             "Por canal:"]
    for c in canais:
        arrow = "▲" if c["tendencia"] == "subindo" else ("▼" if c["tendencia"] == "caindo" else "→")
        lines.append(f"  {arrow} {c['canal']}: R$ {c['receita']:,.2f} ({c['crescimento_pct']:+.1f}%)")
    lines += ["", f"Forecast 30d: R$ {fc['receita_projetada']:,.2f} (+{fc['crescimento_esperado_pct']}%)"]
    return "\n".join(lines)

if __name__ == "__main__":
    print(relatorio_revenue())
