"""
AG-10: Diretor de Inteligência
Orquestrador central. Não faz tarefas diretamente — coordena os demais
agentes e responde perguntas estratégicas consolidando informações.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import log, hoje

AGENT = "AG-10 | Diretor de Inteligência"

def processar_pergunta(pergunta: str) -> dict:
    """
    Roteia perguntas para os agentes especialistas corretos.
    Retorna agente(s) responsável(is) e ação sugerida.
    """
    perguntas = {
        "o que devemos fabricar": {"agentes": ["ag_01", "ag_07"], "acao": "executar_cacada + pipeline_lancamentos"},
        "qual produto devo lançar": {"agentes": ["ag_07"], "acao": "pipeline_lancamentos"},
        "onde estamos perdendo dinheiro": {"agentes": ["ag_02", "ag_05"], "acao": "bottom_deficitarios + relatorio_industrial"},
        "qual marketplace está dando mais lucro": {"agentes": ["ag_02", "ag_03"], "acao": "top_lucrativos + relatorio_consolidado"},
        "qual loja está performando pior": {"agentes": ["ag_08"], "acao": "comparar_lojas"},
        "qual molde não está se pagando": {"agentes": ["ag_02", "ag_09"], "acao": "analisar_sku + verificar_moldes"},
        "melhor sequência de produção": {"agentes": ["ag_04"], "acao": "gerar_plano_diario"},
        "status das máquinas": {"agentes": ["ag_05"], "acao": "analisar_gargalos + relatorio_industrial"},
        "produtos em alta": {"agentes": ["ag_01"], "acao": "top_oportunidades"},
        "preços dos concorrentes": {"agentes": ["ag_03"], "acao": "comparar_precos_concorrentes"},
        "atender cliente": {"agentes": ["ag_06"], "acao": "processar_mensagem"},
        "já fabricamos algo parecido": {"agentes": ["ag_09"], "acao": "buscar_similar"},
    }

    pergunta_lower = pergunta.lower()
    for chave, rota in perguntas.items():
        if chave in pergunta_lower:
            return {"pergunta": pergunta, "agentes": rota["agentes"], "acao": rota["acao"]}

    return {"pergunta": pergunta, "agentes": ["ag_09", "ag_01", "ag_02"], "acao": "buscar_similar + top_oportunidades + relatorio_diario"}

def relatorio_executivo() -> str:
    """Gera relatório executivo diário consolidado."""
    log(AGENT, "Gerando relatório executivo...")
    return f"""📊 RELATÓRIO EXECUTIVO — {hoje()}
━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 FATURAMENTO
  → Consulte AG-02: relatorio_diario()

🚀 OPORTUNIDADES
  → Consulte AG-01: top_oportunidades(5)

⚠️ ALERTAS
  → Consulte AG-02: verificar_alertas()
  → Consulte AG-05: analisar_gargalos()

🏭 PRODUÇÃO
  → Consulte AG-04: gerar_plano_diario()

🏬 LOJAS
  → Consulte AG-08: comparar_lojas()

━━━━━━━━━━━━━━━━━━━━━━━━━━
Digite /detalhe [topico] para aprofundar."""

# Mapeamento de agentes
AGENTES = {
    "ag_01": {"nome": "Caçador de Produtos", "modulo": "hermes_agents.ag_01_cacador"},
    "ag_02": {"nome": "Analista de Lucratividade", "modulo": "hermes_agents.ag_02_lucratividade"},
    "ag_03": {"nome": "Gerente de Marketplaces", "modulo": "hermes_agents.ag_03_marketplaces"},
    "ag_04": {"nome": "Planejador de Produção", "modulo": "hermes_agents.ag_04_planejador"},
    "ag_05": {"nome": "Gerente Industrial", "modulo": "hermes_agents.ag_05_industrial"},
    "ag_06": {"nome": "Vendedor do Telegram", "modulo": "hermes_agents.ag_06_telegram"},
    "ag_07": {"nome": "Laboratório de Produtos", "modulo": "hermes_agents.ag_07_laboratorio"},
    "ag_08": {"nome": "Analista das Lojas Físicas", "modulo": "hermes_agents.ag_08_lojas"},
    "ag_09": {"nome": "Memória Corporativa", "modulo": "hermes_agents.ag_09_memoria"},
}

if __name__ == "__main__":
    log(AGENT, "Auto-teste")
    for q in ["o que devemos fabricar", "onde estamos perdendo dinheiro", "qual loja está performando pior"]:
        print(f"❓ {q}")
        print(f"   → {processar_pergunta(q)['agentes']}")
    print(relatorio_executivo())
