"""
AG-12: Gestor de Manutenção
Gerencia manutenção preventiva e corretiva de máquinas e moldes.
Agendamento, histórico, previsão, alertas.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log, hoje
from datetime import date, timedelta
import uuid

AGENT = "AG-12 | Gestor de Manutenção"

# ===========================================================================
# Manutenções
# ===========================================================================

def agendar_manutencao(equipamento_tipo: str, equipamento_id: str, tipo: str, 
                       data_agendada: date, descricao: str, prioridade: int = 3,
                       tecnico: str = "", observacoes: str = "") -> str:
    """Agenda manutenção de equipamento."""
    async def _go():
        db = await get_db()
        
        # Gerar número da manutenção
        numero = f"MAN-{hoje().replace('-', '')}-{uuid.uuid4().hex[:6]}"
        
        row = await db.fetchrow("""
            INSERT INTO manutencoes 
            (numero, equipamento_tipo, equipamento_id, tipo, prioridade,
             descricao, data_agendada, tecnico, observacoes)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
        """, numero, equipamento_tipo, equipamento_id, tipo, prioridade,
            descricao, data_agendada, tecnico, observacoes)
        
        # Registrar histórico
        await db.execute("""
            INSERT INTO manutencoes_historico (manutencao_id, descricao, usuario, acao)
            VALUES ($1, $2, $3, $4)
        """, row['id'], f"Manutenção agendada para {data_agendada}", "Sistema", "criada")
        
        return numero
    return run_async(_go())

def iniciar_manutencao(manutencao_id: int, tecnico: str = "") -> dict:
    """Inicia execução de manutenção."""
    async def _go():
        db = await get_db()
        
        await db.execute("""
            UPDATE manutencoes
            SET status = 'em_andamento',
                data_inicio = CURRENT_DATE,
                tecnico = COALESCE($1, tecnico),
                updated_at = NOW()
            WHERE id = $2
        """, tecnico, manutencao_id)
        
        # Registrar histórico
        await db.execute("""
            INSERT INTO manutencoes_historico (manutencao_id, descricao, usuario, acao)
            VALUES ($1, $2, $3, $4)
        """, manutencao_id, "Manutenção iniciada", tecnico or "Sistema", "iniciada")
        
        return {"success": True, "manutencao_id": manutencao_id}
    return run_async(_go())

def concluir_manutencao(manutencao_id: int, dados_conclusao: dict) -> dict:
    """Registra manutenção realizada."""
    async def _go():
        db = await get_db()
        
        duracao = None
        if dados_conclusao.get('data_inicio'):
            data_fim = date.today()
            duracao = (data_fim - dados_conclusao['data_inicio']).days * 8  # Aprox 8h/dia
        
        custo_total = (dados_conclusao.get('custo_pecas', 0) + 
                       dados_conclusao.get('custo_mao_obra', 0))
        
        await db.execute("""
            UPDATE manutencoes
            SET status = 'concluida',
                data_fim = CURRENT_DATE,
                duracao_horas = $1,
                pecas_substituidas = $2,
                custo_pecas = $3,
                custo_mao_obra = $4,
                custo_total = $5,
                observacoes = COALESCE(observacoes, '') || ' - ' || $6,
                updated_at = NOW()
            WHERE id = $7
        """, duracao or dados_conclusao.get('duracao_horas'),
            json.dumps(dados_conclusao.get('pecas_substituidas', [])),
            dados_conclusao.get('custo_pecas', 0),
            dados_conclusao.get('custo_mao_obra', 0),
            custo_total,
            dados_conclusao.get('observacoes', ''),
            manutencao_id,
        )
        
        # Registrar histórico
        await db.execute("""
            INSERT INTO manutencoes_historico (manutencao_id, descricao, usuario, acao)
            VALUES ($1, $2, $3, $4)
        """, manutencao_id, f"Manutenção concluída - Custo: R$ {custo_total}", 
            dados_conclusao.get('tecnico', 'Sistema'), "concluida")
        
        # Atualizar molde se for manutenção de molde
        manutencao = await db.fetchrow("SELECT * FROM manutencoes WHERE id = $1", manutencao_id)
        if manutencao['equipamento_tipo'] == 'molde':
            # Atualizar última manutenção e prever próxima
            ciclos_molde = await db.fetchval("SELECT ciclos_atuais FROM moldes WHERE codigo = $1", 
                                            manutencao['equipamento_id'])
            proxima_manutencao = ciclos_molde + 10000 if ciclos_molde else None
            
            await db.execute("""
                UPDATE moldes
                SET ultima_manutencao = CURRENT_DATE,
                    proxima_manutencao = $1,
                    status = CASE 
                        WHEN $2 = 'corretiva' THEN 'ativo'
                        ELSE status
                    END
                WHERE codigo = $2
            """, proxima_manutencao, manutencao['equipamento_id'])
        
        return {"success": True, "manutencao_id": manutencao_id, "custo_total": custo_total}
    return run_async(_go())

def obter_manutencoes_pendentes() -> list:
    """Lista manutenções pendentes ordenadas por prioridade."""
    async def _go():
        db = await get_db()
        
        rows = await db.fetch("""
            SELECT m.*, 
                   CASE 
                       WHEN m.data_agendada < CURRENT_DATE THEN 1  -- Atrasada
                       WHEN m.data_agendada = CURRENT_DATE THEN 2  -- Hoje
                       WHEN m.data_agendada <= CURRENT_DATE + INTERVAL '3 days' THEN 3  -- 3 dias
                       ELSE 4  -- Futura
                   END as urgencia
            FROM manutencoes m
            WHERE m.status IN ('agendada', 'em_andamento')
            ORDER BY urgencia, m.data_agendada, m.prioridade
        """)
        
        manutencoes = []
        for row in rows:
            r = dict(row)
            r['dias_agendamento'] = (r['data_agendada'] - date.today()).days
            manutencoes.append(r)
        
        return manutencoes
    return run_async(_go())

def obter_historico_equipamento(equipamento_tipo: str, equipamento_id: str, 
                                 limite: int = 20) -> list:
    """Obtém histórico de manutenções de um equipamento."""
    async def _go():
        db = await get_db()
        
        rows = await db.fetch("""
            SELECT * FROM manutencoes
            WHERE equipamento_tipo = $1 AND equipamento_id = $2
            ORDER BY data_fim DESC NULLS LAST, data_agendada DESC
            LIMIT $3
        """, equipamento_tipo, equipamento_id, limite)
        
        return [dict(r) for r in rows]
    return run_async(_go>()

# ===========================================================================
# Previsão e Alertas
# ===========================================================================

def prever_proxima_manutencao(equipamento_tipo: str, equipamento_id: str) -> dict:
    """Preve próxima manutenção baseado em histórico."""
    async def _go():
        db = await get_db()
        
        # Obter histórico
        historico = await db.fetch("""
            SELECT data_inicio, data_fim, duracao_horas, tipo
            FROM manutencoes
            WHERE equipamento_tipo = $1 AND equipamento_id = $2 
              AND status = 'concluida'
            ORDER BY data_fim DESC
            LIMIT 10
        """, equipamento_tipo, equipamento_id)
        
        if not historico:
            return {
                "equipamento": f"{equipamento_tipo}:{equipamento_id}",
                "proxima_manutencao": None,
                "motivo": "Sem histórico de manutenções"
            }
        
        # Calcular intervalo médio entre manutenções
        historico_lista = list(historico)
        if len(historico_lista) >= 2:
            intervalos = []
            for i in range(len(historico_lista) - 1):
                if historico_lista[i]['data_fim'] and historico_lista[i + 1]['data_fim']:
                    dias = (historico_lista[i]['data_fim'] - historico_lista[i + 1]['data_fim']).days
                    intervalos.append(dias)
            
            intervalo_medio = sum(intervalos) // len(intervalos) if intervalos else 30
            
            # Próxima manutenção baseada na última
            ultima = historico_lista[0]['data_fim']
            proxima = ultima + timedelta(days=intervalo_medio) if ultima else None
            
            dias_ate_proxima = (proxima - date.today()).days if proxima else None
            
            return {
                "equipamento": f"{equipamento_tipo}:{equipamento_id}",
                "ultima_manutencao": str(ultima),
                "proxima_manutencao": str(proxima) if proxima else None,
                "dias_ate_proxima": dias_ate_proxima,
                "intervalo_medio_dias": intervalo_medio,
                "total_manutencoes": len(historico_lista)
            }
        
        # Se só tem uma manutenção, usar padrão de 30 dias
        ultima = historico_lista[0]['data_fim']
        proxima = ultima + timedelta(days=30) if ultima else None
        
        return {
            "equipamento": f"{equipamento_tipo}:{equipamento_id}",
            "ultima_manutencao": str(ultima),
            "proxima_manutencao": str(proxima) if proxima else None,
            "dias_ate_proxima": (proxima - date.today()).days if proxima else None,
            "intervalo_medio_dias": 30,
            "total_manutencoes": 1
        }
    return run_async(_go())

def verificar_alertas_manutencao() -> list:
    """Verifica equipamentos que precisam de manutenção."""
    async def _go():
        db = await get_db()
        
        alertas = []
        
        # Manutenções atrasadas
        atrasadas = await db.fetch("""
            SELECT * FROM manutencoes
            WHERE data_agendada < CURRENT_DATE AND status = 'agendada'
            ORDER BY data_agendada
        """)
        
        for m in atrasadas:
            alertas.append({
                "tipo": "manutencao_atrasada",
                "gravidade": "alta",
                "equipamento": f"{m['equipamento_tipo']}:{m['equipamento_id']}",
                "dias_atraso": (date.today() - m['data_agendada']).days,
                "mensagem": f"Manutenção {m['numero']} atrasada há {(date.today() - m['data_agendada']).days} dias"
            })
        
        # Moldes próximos da vida útil (80% de ciclos)
        moles_criticos = await db.fetch("""
            SELECT codigo, produto, ciclos_previstos, ciclos_atuais,
                   ROUND(ciclos_atuais::numeric / ciclos_previstos * 100, 1) as utilizacao_pct
            FROM moldes
            WHERE ciclos_atuais >= ciclos_previstos * 0.8 AND status = 'ativo'
        """)
        
        for m in molles_criticos:
            pct = m['utilizacao_pct']
            if pct >= 90:
                gravidade = "critica"
            elif pct >= 85:
                gravidade = "alta"
            else:
                gravidade = "media"
            
            alertas.append({
                "tipo": "molde_proximo_vida",
                "gravidade": gravidade,
                "equipamento": f"molde:{m['codigo']}",
                "utilizaco_pct": pct,
                "mensagem": f"Molde {m['codigo']} com {pct}% da vida útil utilizada"
            })
        
        # Próximas 7 dias
        proximas = await db.fetch("""
            SELECT * FROM manutencoes
            WHERE data_agendada BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
              AND status = 'agendada'
            ORDER BY data_agendada
        """)
        
        for m in proximas:
            dias = (m['data_agendada'] - date.today()).days
            alertas.append({
                "tipo": "manutencao_proxima",
                "gravidade": "media" if dias > 3 else "alta",
                "equipamento": f"{m['equipamento_tipo']}:{m['equipamento_id']}",
                "dias_restantes": dias,
                "mensagem": f"Manutenção {m['numero']} agendada para {dias} dias"
            })
        
        # Ordenar por gravidade
        gravidade_ordem = {"critica": 1, "alta": 2, "media": 3, "baixa": 4}
        alertas.sort(key=lambda x: gravidade_ordem.get(x['gravidade'], 5))
        
        return alertas
    return run_async(_go()

# ===========================================================================
# Estatísticas
# ===========================================================================

def calcular_mtbtf(equipamento_tipo: str, equipamento_id: str) -> dict:
    """Calcula MTBF (Mean Time Between Failures)."""
    async def _go():
        db = await get_db()
        
        # Obter manutenções corretivas
        corretivas = await db.fetch("""
            SELECT data_inicio, data_fim, duracao_horas
            FROM manutencoes
            WHERE equipamento_tipo = $1 AND equipamento_id = $2 
              AND tipo = 'corretiva' AND status = 'concluida'
            ORDER BY data_inicio
        """, equipamento_tipo, equipamento_id)
        
        if len(corretivas) < 2:
            return {
                "equipamento": f"{equipamento_tipo}:{equipamento_id}",
                "mtbf_horas": None,
                "total_falhas": len(corretivas),
                "motivo": "Menos de 2 falhas registradas"
            }
        
        # Calcular tempo entre falhas
        tempos = []
        for i in range(len(corretivas) - 1):
            if corretivas[i]['data_inicio'] and corretivas[i + 1]['data_inicio']:
                dias = (corretivas[i + 1]['data_inicio'] - corretivas[i]['data_inicio']).days
                horas = dias * 24
                tempos.append(horas)
        
        if tempos:
            mtbf = sum(tempos) / len(tempos)
            return {
                "equipamento": f"{equipamento_tipo}:{equipamento_id}",
                "mtbf_horas": round(mtbf, 1),
                "total_falhas": len(corretivas),
                "periodo_analisado_dias": sum(t // 24 for t in tempos) // len(tempos),
                "menor_tempo_horas": min(tempos),
                "maior_tempo_horas": max(tempos)
            }
        
        return {
            "equipamento": f"{equipamento_tipo}:{equipamento_id}",
            "mtbf_horas": None,
            "total_falhas": len(corretivas),
            "motivo": "Dados insuficientes"
        }
    return run_async(_go())

def obter_kpi_manutencao(periodo_dias: int = 30) -> dict:
    """Obtém KPIs de manutenção."""
    async def _go():
        db = await get_db()
        
        # Totais
        totais = await db.fetchrow("""
            SELECT 
                COUNT(*) FILTER (WHERE tipo = 'preventiva') as preventivas,
                COUNT(*) FILTER (WHERE tipo = 'corretiva') as corretivas,
                COUNT(*) FILTER (WHERE tipo = 'preditiva') as preditivas,
                SUM(COALESCE(custo_total, 0)) as custo_total
            FROM manutencoes
            WHERE data_fim >= CURRENT_DATE - make_interval(days => $1)
        """, periodo_dias)
        
        # Por status
        por_status = await db.fetch("""
            SELECT status, COUNT(*) as quantidade
            FROM manutencoes
            WHERE data_agendada >= CURRENT_DATE - make_interval(days => $1)
            GROUP BY status
        """, periodo_dias)
        
        # Top equipamentos (mais manutenções)
        top_equipamentos = await db.fetch("""
            SELECT 
                equipamento_tipo || ':' || equipamento_id as equipamento,
                COUNT(*) as total_manutencoes,
                SUM(COALESCE(custo_total, 0)) as custo_total
            FROM manutencoes
            WHERE data_fim >= CURRENT_DATE - make_interval(days => $1)
            GROUP BY equipamento_tipo, equipamento_id
            ORDER BY total_manutencoes DESC
            LIMIT 5
        """, periodo_dias)
        
        return {
            "periodo_dias": periodo_dias,
            "totais": dict(totais) if totais else {},
            "por_status": {r['status']: r['quantidade'] for r in por_status},
            "top_equipamentos": [dict(r) for r in top_equipamentos],
        }
    return run_async(_go())

# ===========================================================================
# Auto-teste
# ===========================================================================

if __name__ == "__main__":
    log(AGENT, "Auto-teste")
    
    # Manutenções pendentes
    pendentes = obter_manutencoes_pendentes()
    print(f"Manutenções pendentes: {len(pendentes)}")
    
    # Alertas
    alertas = verificar_alertas_manutencao()
    print(f"Alertas de manutenção: {len(alertas)}")
    
    # Previsão
    previsao = prever_proxima_manutencao('molde', 'M-001')
    print(f"Próxima manutenção M-001: {previsao.get('proxima_manutencao')}")
    
    # KPIs
    kpis = obter_kpi_manutencao(30)
    print(f"KPIs (30 dias): {kpis['totais']}")