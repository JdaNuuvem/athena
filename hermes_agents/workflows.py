"""
Cross-Agent Workflows: Integração entre agentes da Fase 2.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import log, hoje, run_async

def workflow_ag07_para_ag04(pipeline_id: int) -> dict:
    """AG-07 → AG-04: Aprovação gera pedido de produção."""
    from ag_07_laboratorio import obter_pipeline_por_status, avancar_status
    from ag_04_planejador import adicionar_pedido_producao
    from datetime import timedelta
    
    log("WORKFLOW", f"Iniciando AG-07→AG-04: pipeline_id={pipeline_id}")
    
    # Obter item do pipeline
    itens = obter_pipeline_por_status("aprovado")
    item = next((i for i in itens if i['id'] == pipeline_id), None)
    
    if not item:
        return {"success": False, "error": "Item não encontrado"}
    
    # Gerar SKU temporário
    sku_temp = f"NOVO-{pipeline_id:04d}"
    
    # Calcular quantidade inicial (30% do volume mensal)
    quantidade = int(item.get('volume_vendas_projetado_mes', 100) * 0.3)
    
    # Prazo baseado no tempo de desenvolvimento
    prazo_dias = item.get('tempo_desenvolvimento_dias', 30)
    from datetime import date
    prazo = date.today() + timedelta(days=prazo_dias)
    
    # Adicionar pedido de produção
    pedido = adicionar_pedido_producao(
        sku=sku_temp,
        quantidade=quantidade,
        prazo=prazo,
        prioridade=8,  # Alta prioridade para novos produtos
    )
    
    # Avançar status para prototipagem
    avancar_status(pipeline_id, "prototipagem")
    
    log("WORKFLOW", f"✅ Pedido de produção gerado: {pedido['id']}")
    
    return {
        "success": True,
        "pipeline_id": pipeline_id,
        "pedido_producao_id": pedido['id'],
        "sku": sku_temp,
        "quantidade": quantidade,
        "prazo": str(prazo),
    }

def workflow_ag06_para_ag04(pedido_telegram_id: str) -> dict:
    """AG-06 → AG-04: Pedido Telegram adiciona ao plano de produção."""
    from ag_06_telegram import salvar_pedido_telegram
    from ag_04_planejador import adicionar_pedido_producao
    from datetime import timedelta, date
    
    log("WORKFLOW", f"Iniciando AG-06→AG-04: pedido_telegram_id={pedido_telegram_id}")
    
    # Obter detalhes do pedido Telegram (mock - implementar query real)
    async def _get_pedido():
        from core import get_db
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM pedidos_telegram WHERE pedido_id = $1", pedido_telegram_id)
        return dict(row) if row else None
    
    pedido = run_async(_get_pedido())
    
    if not pedido:
        return {"success": False, "error": "Pedido não encontrado"}
    
    # Extrair itens do pedido
    import json
    itens = json.loads(pedido['itens']) if isinstance(pedido['itens'], str) else pedido['itens']
    
    pedidos_gerados = []
    
    # Adicionar cada item ao plano de produção
    for item in itens:
        sku = item.get('sku', f"SKU-{item.get('produto', 'DESCONHECIDO')}")
        quantidade = item.get('qtd', item.get('quantidade', 1))
        prazo = date.today() + timedelta(days=5)  # Padrão: 5 dias
        
        pedido_prod = adicionar_pedido_producao(
            sku=sku,
            quantidade=quantidade,
            prazo=prazo,
            prioridade=5,
            cliente_id=pedido.get('user_id'),
        )
        
        pedidos_gerados.append({
            "sku": sku,
            "quantidade": quantidade,
            "pedido_producao_id": pedido_prod['id'],
        })
    
    log("WORKFLOW", f"✅ {len(pedidos_gerados)} pedidos de produção gerados")
    
    return {
        "success": True,
        "pedido_telegram_id": pedido_telegram_id,
        "pedidos_producao": pedidos_gerados,
    }

def workflow_ag05_para_ag02(oee_alertas: list) -> dict:
    """AG-05 → AG-02: Alerta OEE recalcula margens."""
    from ag_05_industrial import calcular_oee
    from ag_02_lucratividade import recalcular_margens_com_ineficiencia
    import asyncio
    
    log("WORKFLOW", "Iniciando AG-05→AG-02: recalculando margens baseado em OEE")
    
    maquinas_afetadas = []
    margens_ajustadas = []
    
    for alerta in oee_alertas:
        if alerta['tipo'] == 'oee_baixo' and alerta['gravidade'] == 'alta':
            maquina_id = alerta['maquina']
            
            # Obter OEE detalhado
            oee_detalhes = asyncio.run(calcular_oee(maquina_id))
            fator_ineficiencia = oee_detalhes['oee'] / 100.0
            
            # Recalcular margens considerando ineficiência
            # Mock - implementar função real em AG-02
            resultado = {
                "maquina_id": maquina_id,
                "oee": oee_detalhes['oee'],
                "fator_ineficiencia": fator_ineficiencia,
                "margens_ajustadas": fator_ineficiencia < 0.8
            }
            
            maquinas_afetadas.append(resultado)
            
            if resultado['margens_ajustadas']:
                margens_ajustadas.append(maquina_id)
    
    log("WORKFLOW", f"✅ {len(maquinas_afetadas)} máquinas analisadas, {len(margens_ajustadas)} com margens ajustadas")
    
    return {
        "success": True,
        "maquinas_analisadas": len(maquinas_afetadas),
        "maquinas_afetadas": maquinas_afetadas,
        "margens_ajustadas": margens_ajustadas,
    }

if __name__ == "__main__":
    log("WORKFLOWS", "Teste de integração cross-agent")
    
    # Teste AG-07 → AG-04
    print("Testando AG-07 → AG-04...")
    # resultado = workflow_ag07_para_ag04(1)
    # print(resultado)
    
    # Teste AG-06 → AG-04
    print("Testando AG-06 → AG-04...")
    # resultado = workflow_ag06_para_ag04("TG-2026-07-07-123456")
    # print(resultado)
    
    # Teste AG-05 → AG-02
    print("Testando AG-05 → AG-02...")
    # alertas = [{"tipo": "oee_baixo", "maquina": "injetora_1", "gravidade": "alta"}]
    # resultado = workflow_ag05_para_ag02(alertas)
    # print(resultado)