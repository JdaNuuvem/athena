from flask import Blueprint, request, jsonify
from core import log

hermes_bp = Blueprint("hermes", __name__, url_prefix="/api/hermes")
memory_bp = Blueprint("memory", __name__, url_prefix="/api/memory")


# -- Executor de agente com memoria --

def _executar_agente(agente_id: str, mensagem: str, user_id: str,
                     nome: str, contexto: str = "") -> str:
    """Executa o agente apropriado com contexto da memoria."""
    prefix = f"[Memoria]: {contexto}\n\n" if contexto else ""

    try:
        if "ag_01" in agente_id:
            from ag_01_cacador import executar_cacada, top_oportunidades
            if "oportunidade" in mensagem.lower() or "produto" in mensagem.lower():
                ops = top_oportunidades(5)
                return f"{prefix}Top 5 oportunidades: {ops}" if ops else f"{prefix}Nenhuma oportunidade nova encontrada."
            r = executar_cacada()
            return f"{prefix}{r}"

        elif "ag_02" in agente_id:
            from ag_02_lucratividade import analisar_sku, relatorio_diario, verificar_alertas
            if "alerta" in mensagem.lower():
                a = verificar_alertas()
                return f"{prefix}Alertas: {a}"
            r = relatorio_diario()
            return f"{prefix}{r}"

        elif "ag_03" in agente_id:
            from ag_03_marketplaces import comparar_precos_concorrentes, verificar_posicoes
            if "preco" in mensagem.lower() or "concorrente" in mensagem.lower():
                c = comparar_precos_concorrentes()
                return f"{prefix}Comparacao de precos: {c}"
            p = verificar_posicoes()
            return f"{prefix}Posicoes dos anuncios: {p}"

        elif "ag_04" in agente_id:
            from ag_04_planejador import gerar_plano_diario
            plano = gerar_plano_diario()
            return f"{prefix}Plano diario: {plano}"

        elif "ag_07" in agente_id:
            from ag_07_laboratorio import pipeline_lancamentos
            return f"{prefix}Pipeline de lancamentos: {pipeline_lancamentos()}"

        elif "ag_09" in agente_id:
            from ag_09_memoria import buscar_similar, stats
            if "parecido" in mensagem.lower() or "similar" in mensagem.lower():
                s = buscar_similar(mensagem)
                return f"{prefix}Produtos similares: {s}"
            s = stats()
            return f"{prefix}Stats da memoria corporativa: {s}"

        else:
            return f"{prefix}Agente {agente_id} consultado. Pergunta: '{mensagem[:100]}'. Use /detalhe para aprofundar."

    except Exception as e:
        log(None, f"Erro agente {agente_id}: {e}")
        return f"{prefix}Erro ao processar com {agente_id}: {str(e)[:200]}"


# ===========================================================================
# Chat com agente (chamado pelo Chat.tsx do frontend)
# ===========================================================================

@hermes_bp.route('/chat', methods=['POST'])
def hermes_chat():
    data = request.json
    mensagem = data.get("mensagem", "")
    user_id = data.get("user_id", "anon")
    nome = data.get("nome", "Visitante")

    from core.memory import recall, context, store
    from ag_10_diretor import processar_pergunta

    memoria_contexto = context(mensagem)
    memorias = recall(mensagem, limit=3)

    rota = processar_pergunta(mensagem)
    agente = rota.get("agentes", ["ag_10"])[0] if rota.get("agentes") else "ag_10"

    resposta_texto = _executar_agente(agente, mensagem, user_id, nome, memoria_contexto)

    store(mensagem, resposta_texto, agent_id=agente,
          category=rota.get("categoria", "geral"),
          metadata={"user_id": user_id, "nome": nome})

    return jsonify({
        "resposta": resposta_texto,
        "agente": agente,
        "intencao": rota.get("acao", "geral"),
        "memorias": len(memorias),
    })


# -- Memory API --

@memory_bp.route('/stats', methods=['GET'])
def memory_stats():
    from core.memory import stats as memory_stats_fn
    s = memory_stats_fn()
    return jsonify(s)


@memory_bp.route('/history', methods=['GET'])
def memory_history():
    from core.memory import history as memory_history
    agent = request.args.get("agente", "")
    cat = request.args.get("categoria", "")
    h = memory_history(agent_id=agent or None, category=cat or None, limit=20)
    return jsonify({"history": h, "total": len(h)})


@memory_bp.route('/recall', methods=['POST'])
def memory_recall():
    from core.memory import recall as memory_recall
    data = request.json or {}
    query = data.get("query", "")
    agent = data.get("agente", "")
    results = memory_recall(query, agent_id=agent or None, limit=5)
    return jsonify({"results": results, "total": len(results)})
