"""
AG-201: Cash Flow Agent
Monitora saldo bancário, projeta fluxo de caixa futuro,
alerta sobre baixa liquidez e risco de insolvência.
Frequência: diário + alertas em tempo real.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

AGENT = "AG-201 | Cash Flow Agent"

def obter_saldo_atual() -> float:
    """Saldo atual consolidado de todas as contas."""
    # ponytail: placeholder, integrar com API bancária via MCP quando disponível
    return 28450.75

def obter_fluxo_caixa_30d() -> dict:
    """Projeta entradas e saídas dos próximos 30 dias."""
    return {
        "saldo_atual": obter_saldo_atual(),
        "entradas_previstas": 45200.00,
        "saidas_previstas": 38750.00,
        "saldo_projetado": obter_saldo_atual() + 45200.00 - 38750.00,
        "dias_cobertura": 22,
        "dias_criticos": [],  # dias com saldo projetado < 5000
        "status": "saudavel",  # saudavel | atencao | critico
    }

def verificar_liquidez() -> dict:
    """Verifica se há risco de liquidez."""
    cf = obter_fluxo_caixa_30d()
    status = "saudavel"
    if cf["saldo_projetado"] < 5000: status = "critico"
    elif cf["saldo_projetado"] < 15000: status = "atencao"

    alertas = []
    if status != "saudavel":
        alertas.append(f"⚠️ Liquidez {status}: saldo projetado R${cf['saldo_projetado']:.2f} em 30 dias")

    return {"status": status, "saldo_projetado": cf["saldo_projetado"], "alertas": alertas}

def relatorio_cashflow() -> str:
    cf = obter_fluxo_caixa_30d()
    liq = verificar_liquidez()
    return f"""💰 CASH FLOW 30 DIAS
Saldo atual: R$ {cf['saldo_atual']:,.2f}
Entradas previstas: R$ {cf['entradas_previstas']:,.2f}
Saídas previstas: R$ {cf['saidas_previstas']:,.2f}
Saldo projetado: R$ {cf['saldo_projetado']:,.2f}
Cobertura: {cf['dias_cobertura']} dias
Status: {liq['status'].upper()}
"""

if __name__ == "__main__":
    print(relatorio_cashflow())
