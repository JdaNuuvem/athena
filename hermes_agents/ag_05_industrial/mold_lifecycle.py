"""
AG-05: Lifecycle de Moldes
Tracking completo do ciclo de vida de moldes: design → fabricação → instalação → manutenção.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log, hoje
from datetime import date
import json

AGENT = "AG-05 | Lifecycle de Moldes"

# ===========================================================================
# Eventos de Lifecycle
# ===========================================================================

def registrar_evento_molde(molde_id: int, tipo: str, descricao: str = "", 
                            dados: dict = None, usuario: str = "Sistema") -> int:
    """Registra evento no lifecycle do molde."""
    async def _go():
        db = await get_db()
        
        row = await db.fetchrow("""
            INSERT INTO moldes_eventos (molde_id, tipo, descricao, dados, usuario)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """, molde_id, tipo, descricao, json.dumps(dados or {}), usuario)
        
        # Atualizar status do molde baseado no tipo de evento
        status_map = {
            'designed': 'designed',
            'fabrication_started': 'em_fabricacao',
            'fabrication_completed': 'fabricado',
            'installed': 'instalado',
            'removed': 'ativo',  # Volta para ativo se não foi descartado
            'maintenance': 'manutencao',
            'retired': 'inativo',
        }
        
        novo_status = status_map.get(tipo)
        if novo_status:
            await db.execute("""
                UPDATE moldes
                SET status_atual = $1, updated_at = NOW()
                WHERE id = $2
            """, novo_status, molde_id)
            
            # Atualizar campos específicos
            if tipo == 'designed':
                await db.execute("""
                    UPDATE moldes SET data_design = CURRENT_DATE WHERE id = $1
                """, molde_id)
            elif tipo == 'fabrication_started':
                await db.execute("""
                    UPDATE moldes SET data_fabricacao_inicio = CURRENT_DATE WHERE id = $1
                """, molde_id)
            elif tipo == 'fabrication_completed':
                await db.execute("""
                    UPDATE moldes SET data_fabricacao_fim = CURRENT_DATE WHERE id = $1
                """, molde_id)
            elif tipo == 'installed':
                maquina_id = dados.get('maquina_id', '') if dados else ''
                await db.execute("""
                    UPDATE moldes SET data_instalacao = CURRENT_DATE, maquina_id = $1 WHERE id = $2
                """, maquina_id, molde_id)
            elif tipo == 'maintenance':
                await db.execute("""
                    UPDATE moldes SET ultima_manutencao = CURRENT_DATE WHERE id = $1
                """, molde_id)
        
        log(AGENT, f"Evento registrado: {tipo} para molde {molde_id}")
        return row['id']
    return run_async(_go())

def avancar_status_molde(molde_id: int, novo_status: str, dados: dict = None) -> bool:
    """Avança o status do molde e registra evento."""
    # Verificar se status é válido
    status_validos = ['designed', 'em_fabricacao', 'fabricado', 'instalado', 'manutencao', 'inativo']
    if novo_status not in status_validos:
        return False
    
    # Mapear status para tipo de evento
    tipo_map = {
        'designed': 'designed',
        'em_fabricacao': 'fabrication_started',
        'fabricado': 'fabrication_completed',
        'instalado': 'installed',
        'manutencao': 'maintenance',
        'inativo': 'retired',
    }
    
    tipo = tipo_map.get(novo_status)
    if not tipo:
        return False
    
    registrar_evento_molde(molde_id, tipo, dados.get('descricao', ''), dados)
    return True

def obter_historico_molde(molde_id: int) -> list:
    """Obtém histórico completo de eventos do molde."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT me.*, m.codigo, m.produto
            FROM moldes_eventos me
            JOIN moldes m ON m.id = me.molde_id
            WHERE me.molde_id = $1
            ORDER BY me.created_at DESC
        """, molde_id)
        return [dict(r) for r in rows]
    return run_async(_go()

def obter_status_atual_molde(molde_id: int) -> dict:
    """Obtém status atual e informações do molde."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            SELECT m.*,
                   COALESCE(m.ciclos_acumulados, 0) as ciclos_totais,
                   CASE 
                       WHEN m.ciclos_previstos > 0 
                       THEN ROUND(m.ciclos_acumulados::numeric / m.ciclos_previstos * 100, 1)
                       ELSE 0
                   END as utilizacao_pct
            FROM moldes m
            WHERE m.id = $1
        """, molde_id)
        
        if not row:
            return {"error": "Molde não encontrado"}
        
        molde = dict(row)
        
        # Obter último evento
        ultimo_evento = await db.fetchrow("""
            SELECT * FROM moldes_eventos
            WHERE molde_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """, molde_id)
        
        molde['ultimo_evento'] = dict(ultimo_evento) if ultimo_evento else None
        
        # Obter próxima manutenção prevista
        if molde.get('proxima_manutencao'):
            ciclos_restantes = molde['proxima_manutencao'] - molde['ciclos_acumulados']
            molde['ciclos_ate_manutencao'] = ciclos_restantes
        else:
            molde['ciclos_ate_manutencao'] = None
        
        return molde
    return run_async(_go()

# ===========================================================================
# Jobs CNC
# ===========================================================================

def criar_cnc_job(molde_id: int, maquina_id: str, dados_job: dict) -> str:
    """Cria job de usinagem CNC para fabricação de molde."""
    import uuid
    
    async def _go():
        db = await get_db()
        
        job_id = f"CNC-{hoje().replace('-', '')}-{uuid.uuid4().hex[:6]}"
        
        row = await db.fetchrow("""
            INSERT INTO cnc_jobs 
            (job_id, molde_id, maquina_id, operador, status, data_inicio,
             horas_planejadas, material_tipo, observacoes)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
        """, job_id, molde_id, maquina_id, dados_job.get('operador', ''),
            'scheduled', dados_job.get('data_inicio'), 
            dados_job.get('horas_planejadas'), 
            dados_job.get('material_tipo', ''),
            dados_job.get('observacoes', '')
        )
        
        # Registrar evento no molde
        registrar_evento_molde(molde_id, 'fabrication_started', 
                              f"Job CNC iniciado: {job_id}", 
                              {"job_id": job_id, "maquina": maquina_id})
        
        return job_id
    return run_async(_go()

def iniciar_cnc_job(job_id: str, operador: str = "") -> dict:
    """Inicia execução de job CNC."""
    async def _go():
        db = await get_db()
        
        await db.execute("""
            UPDATE cnc_jobs
            SET status = 'running', data_inicio = CURRENT_DATE, operador = $1, updated_at = NOW()
            WHERE job_id = $2
        """, operador, job_id)
        
        return {"success": True, "job_id": job_id}
    return run_async(_go()

def concluir_cnc_job(job_id: str, dados_conclusao: dict) -> dict:
    """Conclui job CNC."""
    async def _go():
        db = await get_db()
        
        # Obter job para pegar molde_id
        job = await db.fetchrow("SELECT * FROM cnc_jobs WHERE job_id = $1", job_id)
        if not job:
            return {"error": "Job não encontrado"}
        
        await db.execute("""
            UPDATE cnc_jobs
            SET status = 'completed', 
                data_fim = CURRENT_DATE,
                horas_reais = $1,
                material_usado_kg = $2,
                observacoes = COALESCE(observacoes, '') || ' - ' || $3,
                updated_at = NOW()
            WHERE job_id = $4
        """, dados_conclusao.get('horas_reais'),
            dados_conclusao.get('material_usado_kg'),
            dados_conclusao.get('observacoes', ''),
            job_id,
        )
        
        # Registrar evento de fabricação concluída
        registrar_evento_molde(job['molde_id'], 'fabrication_completed',
                              f"Job CNC concluído: {job_id}",
                              {"job_id": job_id, "horas": dados_conclusao.get('horas_reais')})
        
        return {"success": True, "job_id": job_id, "molde_id": job['molde_id']}
    return run_async(_go()

def obter_cnc_jobs_molde(molde_id: int) -> list:
    """Obtém todos os jobs CNC de um molde."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT * FROM cnc_jobs
            WHERE molde_id = $1
            ORDER BY data_inicio DESC NULLS LAST, created_at DESC
        """, molde_id)
        return [dict(r) for r in rows]
    return run_async(_go()

# ===========================================================================
# Dashboard de Moldes
# ===========================================================================

def dashboard_moldes() -> dict:
    """Dashboard com status geral de todos os moldes."""
    async def _go():
        db = await get_db()
        
        # Totais por status
        por_status = await db.fetch("""
            SELECT status_atual, COUNT(*) as quantidade
            FROM moldes
            GROUP BY status_atual
        """)
        
        # Moldes críticos (próximos da vida útil)
        criticos = await db.fetch("""
            SELECT codigo, produto, ciclos_previstos, ciclos_acumulados,
                   ROUND(ciclos_acumulados::numeric / ciclos_previstos * 100, 1) as utilizacao_pct
            FROM moldes
            WHERE ciclos_acumulados >= ciclos_previstos * 0.8
            ORDER BY utilizacao_pct DESC
        """)
        
        # Jobs CNC ativos
        jobs_ativos = await db.fetch("""
            SELECT * FROM cnc_jobs
            WHERE status IN ('scheduled', 'running')
            ORDER BY data_inicio
        """)
        
        # Eventos recentes
        eventos_recentes = await db.fetch("""
            SELECT me.*, m.codigo as molde_codigo
            FROM moldes_eventos me
            JOIN moldes m ON m.id = me.molde_id
            ORDER BY me.created_at DESC
            LIMIT 10
        """)
        
        return {
            "data": hoje(),
            "totais_por_status": {r['status_atual']: r['quantidade'] for r in por_status},
            "moldes_criticos": len(criticos),
            "moldes_criticos_detalhe": [dict(r) for r in criticos],
            "jobs_cnc_ativos": len(jobs_ativos),
            "jobs_cnc_detalhe": [dict(r) for r in jobs_ativos],
            "eventos_recentes": [dict(r) for r in eventos_recentes],
        }
    return run_async(_go()

# ===========================================================================
# Auto-teste
# ===========================================================================

if __name__ == "__main__":
    log(AGENT, "Auto-teste")
    
    # Dashboard
    dashboard = dashboard_moldes()
    print(f"Totais por status: {dashboard['totais_por_status']}")
    print(f"Moldes críticos: {dashboard['moldes_criticos']}")
    print(f"Jobs CNC ativos: {dashboard['jobs_cnc_ativos']}")