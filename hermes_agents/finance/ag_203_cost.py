"""
AG-203: Cost Optimization Agent
Analisa estrutura de custos, detecta anomalias (gastos acima da média),
sugere cortes e otimizações. Frequência: diário.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

AGENT = "AG-203 | Cost Optimization Agent"

def estrutura_custos() -> list:
    """Custos por categoria no mês."""
    return [
        {"categoria": "Materia-prima", "valor": 28500.00, "media_3m": 26200.00, "variacao_pct": 8.8},
        {"categoria": "Mao de obra", "valor": 42500.00, "media_3m": 42000.00, "variacao_pct": 1.2},
        {"categoria": "Energia", "valor": 12800.00, "media_3m": 11500.00, "variacao_pct": 11.3},
        {"categoria": "Ferramentas", "valor": 5600.00, "media_3m": 4800.00, "variacao_pct": 16.7},
        {"categoria": "Embalagens", "valor": 3200.00, "media_3m": 3400.00, "variacao_pct": -5.9},
        {"categoria": "Frete", "valor": 9800.00, "media_3m": 9200.00, "variacao_pct": 6.5},
        {"categoria": "Taxas Marketplace", "valor": 15600.00, "media_3m": 14200.00, "variacao_pct": 9.9},
        {"categoria": "Manutencao", "valor": 4500.00, "media_3m": 3800.00, "variacao_pct": 18.4},
        {"categoria": "Marketing", "valor": 2200.00, "media_3m": 2000.00, "variacao_pct": 10.0},
    ]

def detectar_anomalias(limiar_pct: float = 10.0) -> list:
    """Detecta gastos com variação acima do limiar vs média 3 meses."""
    custos = estrutura_custos()
    anomalias = []
    for c in custos:
        if c["variacao_pct"] > limiar_pct:
            anomalias.append({
                "categoria": c["categoria"],
                "valor_atual": c["valor"],
                "media_3m": c["media_3m"],
                "excesso": round(c["valor"] - c["media_3m"], 2),
                "excesso_pct": c["variacao_pct"],
                "severidade": "critico" if c["variacao_pct"] > 15 else "alerta",
                "sugestao": f"Revisar {c['categoria'].lower()} — R$ {c['valor'] - c['media_3m']:.2f} acima da média",
            })
    return sorted(anomalias, key=lambda a: a["excesso_pct"], reverse=True)

def custo_total_mes() -> float:
    return sum(c["valor"] for c in estrutura_custos())

def relatorio_cost() -> str:
    anomalias = detectar_anomalias()
    total = custo_total_mes()
    lines = [f"📉 CUSTOS DO MÊS — Total: R$ {total:,.2f}"]
    if anomalias:
        lines += ["", f"⚠️ {len(anomalias)} anomalias detectadas:"]
        for a in anomalias:
            lines.append(f"  [{a['severidade'].upper()}] {a['categoria']}: +{a['excesso_pct']:.1f}% (R$ {a['excesso']:.2f} acima)")
    else:
        lines.append("✅ Nenhuma anomalia detectada.")
    return "\n".join(lines)

if __name__ == "__main__":
    print(relatorio_cost())
