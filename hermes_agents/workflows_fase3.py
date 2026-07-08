"""
Workflows Cross-Agent — Fase 3: Manufacturing Chain
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import log, hoje, run_async

def workflow_lote_para_estoque(lote_id: int) -> dict:
    """Lote produzido → inspeção → entrada estoque."""
    from ag_11_qualidade import registrar_inspecao, finalizar_inspecao
    from ag_04_planejador import registrar_producao_concluida
    
    log("WORKFLOW", f"Iniciando Lote→Estoque: lote_id={lote_id}")
    
    # Obter dados do lote
    async def _get_lote():
        from core import get_db
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM producao_lotes WHERE id = $1", lote_id)
        return dict(row) if row else None
    
    lote = run_async(_get_lote())
    
    if not lote:
        return {"success": False, "error": "Lote não encontrado"}
    
    # Registrar inspeção automática
    inspecao = registrar_inspecao(lote_id, {
        "tipo_inspecao": "final",
        "quantidade_amostrada": max(1, lote.get('quantidade_produzida', 0) // 10),
        "inspetor": "Sistema Automático",
    })
    
    # Simular aprovação (em produção real, seria inspeção física)
    resultado_inspecao = finalizar_inspecao(inspecao['id'], {
        "status_inspecao": "aprovado",
        "quantidade_aprovada": lote.get('quantidade_produzida', 0) - lote.get('quantidade_defeituosa', 0),
        "quantidade_reprovada": lote.get('quantidade_defeituosa', 0),
        "resultado": "Inspeção automática aprovada",
        "defeitos": [],
    })
    
    # Se aprovado, entrar no estoque
    if resultado_inspecao['status_inspecao'] == 'aprovado':
        estoque = registrar_producao_concluida(lote_id)
        log("WORKFLOW", f"✅ Lote {lote['lote_id']} → Estoque: {estoque.get('quantidade', 0)} unidades")
        return {"success": True, "lote_id": lote_id, "estoque": estoque}
    else:
        log("WORKFLOW", f"❌ Lote {lote['lote_id']} reprovado na qualidade")
        return {"success": False, "lote_id": lote_id, "motivo": "Reprovado na qualidade"}

def workflow_defeito_para_capa(inspecao_id: int, defeito_codigo: str) -> dict:
    """Defeito encontrado → gera CAPA automaticamente."""
    from ag_11_qualidade import listar_defeitos, gerar_capa
    
    log("WORKFLOW", f"Iniciando Defeito→CAPA: inspecao_id={inspecao_id}, defeito={defeito_codigo}")
    
    # Obter detalhes do defeito
    defeitos = listar_defeitos()
    defeito = next((d for d in defeitos if d['codigo'] == defeito_codigo), None)
    
    if not defeito:
        return {"success": False, "error": "Defeito não encontrado"}
    
    # Verificar gravidade
    if defeito['gravidade'] in ['alta', 'critica']:
        # Gerar CAPA automática
        capa = gerar_capa('defeito', inspecao_id, {
            "tipo": 'corretiva',
            "descricao_problema": f"Defeto {defeito['nome']} ({defeito['gravidade']}) detectado na inspeção",
            "causa_raiz": defeito.get('causa_raiz_sugerida', 'A ser investigada'),
            "acao_corretiva": "Revisar processo de injeção",
            "acao_preventiva": "Implementar check adicional",
            "responsavel": "Gerente de Qualidade",
            "data_prevista_conclusao": (run_async(lambda: None) or __import__('datetime').date.today() + __import__('datetime').timedelta(days=7)),
        })
        
        log("WORKFLOW", f"✅ CAPA gerada: {capa['numero']}")
        return {"success": True, "capa": capa, "defeito": defeito}
    else:
        # Defeito baixa/média, apenas log
        log("WORKFLOW", f"ℹ️ Defeito {defeito['nome']} registrado sem CAPA (gravidade: {defeito['gravidade']})")
        return {"success": True, "capa": None, "motivo": "Gravidade não requer CAPA automática"}

def workflow_manutencao_molde(molde_id: int) -> dict:
    """Manutenção realizada → revisar capacidade de produção."""
    from ag_12_manutencao import prever_proxima_manutencao
    from ag_04_planejador import gerar_plano_diario
    
    log("WORKFLOW", f"Iniciando Manutenção→Produção: molde_id={molde_id}")
    
    # Prever próxima manutenção
    async def _get_molde_codigo():
        from core import get_db
        db = await get_db()
        return await db.fetchval("SELECT codigo FROM moldes WHERE id = $1", molde_id)
    
    molde_codigo = run_async(_get_molde_codigo())
    if not molde_codigo:
        return {"success": False, "error": "Molde não encontrado"}
    
    proxima = prever_proxima_manutencao('molde', molde_codigo)
    
    # Recalcular capacidade (simplificado)
    plano = gerar_plano_diario()
    
    return {
        "success": True,
        "molde_id": molde_id,
        "molde_codigo": molde_codigo,
        "proxima_manutencao": proxima.get('proxima_manutencao'),
        "dias_ate_manutencao": proxima.get('dias_ate_proxima'),
        "plano_atualizado": len(plano),
    }

def workflow_cnc_job_concluido(job_id: str) -> dict:
    """Job CNC concluído → avança molde para fabricado."""
    from ag_05_industrial.mold_lifecycle import concluir_cnc_job
    
    log("WORKFLOW", f"Iniciando CNC Job→Molde: job_id={job_id}")
    
    # Concluir job com dados mock (em produção real, viriam da máquina CNC)
    resultado = concluir_cnc_job(job_id, {
        "horas_reais": 45.5,
        "material_usado_kg": 120.0,
        "observacoes": "Usinagem concluída com sucesso",
    })
    
    if resultado.get("success"):
        log("WORKFLOW", f"✅ Job {job_id} concluído, molde {resultado['molde_id']} em status 'fabricado'")
    
    return resultado

def workflow_alerta_manutencao_para_agenda() -> dict:
    """Verifica alertas de manutenção e agenda se necessário."""
    from ag_12_manutencao import verificar_alertas_manutencao, agendar_manutencao
    from datetime import date, timedelta
    
    log("WORKFLOW", "Iniciando Alertas→Agenda")
    
    alertas = verificar_alertas_manutencao()
    
    manutencoes_agendadas = []
    
    for alerta in alertas:
        # Se manutenção atrasada, reagendar para amanhã
        if alerta['tipo'] == 'manutencao_atrasada':
            # Extrair ID do equipamento
            partes = alerta['equipamento'].split(':')
            if len(partes) == 2:
                equipamento_tipo, equipamento_id = partes
                numero = agendar_manutencao(
                    equipamento_tipo,
                    equipamento_id,
                    'corretiva',
                    date.today() + timedelta(days=1),
                    f"Manutenção reagendada: {alerta['mensagem']}",
                    prioridade=1,
                )
                manutencoes_agendadas.append(numero)
    
    log("WORKFLOW", f"✅ {len(manutencoes_agendadas)} manutenções reagendadas")
    
    return {
        "success": True,
        "total_alertas": len(alertas),
        "manutencoes_agendadas": len(manutencoes_agendadas),
        "numeros_manutencoes": manutencoes_agendadas,
    }

if __name__ == "__main__":
    log("WORKFLOWS FASE 3", "Teste de workflows Fase 3")
    print("Workflows disponíveis:")
    print("  - workflow_lote_para_estoque(lote_id)")
    print("  - workflow_defeito_para_capa(inspecao_id, defeito_codigo)")
    print("  - workflow_manutencao_molde(molde_id)")
    print("  - workflow_cnc_job_concluido(job_id)")
    print("  - workflow_alerta_manutencao_para_agenda()")