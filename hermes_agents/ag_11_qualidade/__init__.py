"""
AG-11: Controlador de Qualidade
Gerencia inspeções, defeitos, CAPA (Corrective and Preventive Actions),
estatísticas de qualidade, tendências de defeitos.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log, hoje
import json

AGENT = "AG-11 | Controlador de Qualidade"

# ===========================================================================
# Inspeções
# ===========================================================================

def registrar_inspecao(lote_id: int, dados_inspecao: dict) -> dict:
    """Registra inspeção de qualidade de um lote."""
    import uuid
    
    async def _go():
        db = await get_db()
        
        # Verificar se lote existe
        lote = await db.fetchrow("SELECT * FROM producao_lotes WHERE id = $1", lote_id)
        if not lote:
            return {"error": "Lote não encontrado"}
        
        # Gerar ID de inspeção
        inspecao_id = f"INSP-{hoje().replace('-', '')}-{uuid.uuid4().hex[:8]}"
        
        # Inserir inspeção
        row = await db.fetchrow("""
            INSERT INTO inspecao_qualidade 
            (inspecao_id, lote_id, data_inspecao, inspetor, tipo_inspecao,
             quantidade_amostrada, quantidade_aprovada, quantidade_reprovada,
             status_inspecao, resultado, acoes_tomadas)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
        """, 
            inspecao_id,
            lote_id,
            dados_inspecao.get('data_inspecao', hoje()),
            dados_inspecao.get('inspetor', 'Sistema'),
            dados_inspecao.get('tipo_inspecao', 'final'),
            dados_inspecao.get('quantidade_amostrada', 0),
            dados_inspecao.get('quantidade_aprovada', 0),
            dados_inspecao.get('quantidade_reprovada', 0),
            dados_inspecao.get('status_inspecao', 'em_andamento'),
            dados_inspecao.get('resultado', ''),
            dados_inspecao.get('acoes_tomadas', ''),
        )
        
        return dict(row)
    return run_async(_go())

def finalizar_inspecao(inspecao_id: str, resultado: dict) -> dict:
    """Finaliza inspeção com resultado e defeitos."""
    async def _go():
        db = await get_db()
        
        # Atualizar inspeção
        await db.execute("""
            UPDATE inspecao_qualidade
            SET status_inspecao = $1,
                quantidade_aprovada = $2,
                quantidade_reprovada = $3,
                resultado = $4,
                acoes_tomadas = $5,
                updated_at = NOW()
            WHERE inspecao_id = $6
        """, 
            resultado['status_inspecao'],
            resultado.get('quantidade_aprovada', 0),
            resultado.get('quantidade_reprovada', 0),
            resultado.get('resultado', ''),
            resultado.get('acoes_tomadas', ''),
            inspecao_id,
        )
        
        # Registrar defeitos se houver
        defeitos_registrados = []
        for defeito in resultado.get('defeitos', []):
            defeito_id = await db.fetchval("""
                INSERT INTO inspecao_defeitos 
                (inspecao_id, defeito_id, quantidade, gravidade, posicao_peca, observacoes)
                SELECT $1, id, $2, $3, $4, $5
                FROM defeitos WHERE codigo = $6
                RETURNING id
            """, 
                inspecao_id,
                defeito.get('quantidade', 1),
                defeito.get('gravidade', 'media'),
                defeito.get('posicao_peca', ''),
                defeito.get('observacoes', ''),
                defeito['codigo'],
            )
            defeitos_registrados.append(defeito_id)
        
        # Atualizar status do lote se inspeção final
        inspecao = await db.fetchrow("SELECT * FROM inspecao_qualidade WHERE inspecao_id = $1", inspecao_id)
        if inspecao['tipo_inspecao'] == 'final':
            novo_status_lote = 'concluido' if resultado['status_inspecao'] == 'aprovado' else 'em_qualidade'
            await db.execute("""
                UPDATE producao_lotes
                SET status = $1, updated_at = NOW()
                WHERE id = $2
            """, novo_status_lote, inspecao['lote_id'])
        
        return {
            "inspecao_id": inspecao_id,
            "status_inspecao": resultado['status_inspecao'],
            "defeitos_registrados": len(defeitos_registrados),
            "lote_status_atualizado": True
        }
    return run_async(_go())

def obter_inspecoes_lote(lote_id: int) -> list:
    """Obtém todas as inspeções de um lote."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT * FROM inspecao_qualidade
            WHERE lote_id = $1
            ORDER BY data_inspecao
        """, lote_id)
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Defeitos
# ===========================================================================

def listar_defeitos(categoria: str = "", gravidade: str = "") -> list:
    """Lista defeitos, opcionalmente filtrado."""
    async def _go():
        db = await get_db()
        query = "SELECT * FROM defeitos WHERE 1=1"
        params = []
        
        if categoria:
            query += " AND categoria = $" + str(len(params) + 1)
            params.append(categoria)
        
        if gravidade:
            query += " AND gravidade = $" + str(len(params) + 1)
            params.append(gravidade)
        
        query += " ORDER BY gravidade DESC, nome"
        
        rows = await db.fetch(query, *params)
        return [dict(r) for r in rows]
    return run_async(_go())

def analisar_defeitos(lote_id: int) -> dict:
    """Analisa defeitos encontrados e classifica por tipo."""
    async def _go():
        db = await get_db()
        
        # Obter defeitos do lote
        rows = await db.fetch("""
            SELECT d.*, SUM(idf.quantidade) as total_quantidade
            FROM inspecao_defeitos idf
            JOIN inspecao_qualidade iq ON iq.id = idf.inspecao_id
            JOIN defeitos d ON d.id = idf.defeito_id
            WHERE iq.lote_id = $1
            GROUP BY d.id
            ORDER BY total_quantidade DESC
        """, lote_id)
        
        defeitos = [dict(r) for r in rows]
        
        # Classificar por categoria
        por_categoria = {}
        for d in defeitos:
            cat = d['categoria']
            if cat not in por_categoria:
                por_categoria[cat] = []
            por_categoria[cat].append(d)
        
        # Calcular totais
        total_defeitos = sum(d['total_quantidade'] for d in defeitos)
        
        return {
            "lote_id": lote_id,
            "total_defeitos": total_defeitos,
            "tipos_defeitos": len(defeitos),
            "por_categoria": {cat: len(items) for cat, items in por_categoria.items()},
            "defeitos": defeitos,
        }
    return run_async(_go())

def pareto_defeitos(periodo_dias: int = 30) -> list:
    """Gera análise Pareto de defeitos (80/20)."""
    async def _go():
        db = await get_db()
        
        rows = await db.fetch("""
            SELECT d.codigo, d.nome, d.categoria, d.gravidade,
                   SUM(idf.quantidade) as total_ocorrencias,
                   COUNT(DISTINCT iq.lote_id) as lotes_afetados
            FROM inspecao_defeitos idf
            JOIN inspecao_qualidade iq ON iq.id = idf.inspecao_id
            JOIN defeitos d ON d.id = idf.defeito_id
            WHERE iq.data_inspecao >= CURRENT_DATE - make_interval(days => $1)
            GROUP BY d.id, d.codigo, d.nome, d.categoria, d.gravidade
            ORDER BY total_ocorrencias DESC
        """, periodo_dias)
        
        defeitos = [dict(r) for r in rows]
        
        # Calcular percentual acumulado (regra 80/20)
        total = sum(d['total_ocorrencias'] for d in defeitos) if defeitos else 1
        acumulado = 0
        pareto_top_20 = []
        
        for d in defeitos:
            d['pct_total'] = round(d['total_ocorrencias'] / total * 100, 1)
            acumulado += d['pct_total']
            d['pct_acumulado'] = round(acumulado, 1)
            pareto_top_20.append(d)
            if acumulado >= 80:
                break
        
        return {
            "periodo_dias": periodo_dias,
            "total_defeitos": total,
            "pareto_80_20": pareto_top_20,
            "total_tipos": len(defeitos),
        }
    return run_async(_go())

# ===========================================================================
# CAPA
# ===========================================================================

def gerar_capa(origem: str, origem_id: int, dados_capa: dict) -> dict:
    """Gera CAPA (Corrective and Preventive Action)."""
    import uuid
    
    async def _go():
        db = await get_db()
        
        # Gerar número da CAPA
        capa_numero = f"CAPA-{hoje().replace('-', '')}-{uuid.uuid4().hex[:6]}"
        
        row = await db.fetchrow("""
            INSERT INTO capa_registros 
            (numero, tipo, origem, origem_id, descricao_problema, causa_raiz,
             acao_corretiva, acao_preventiva, responsavel, data_prevista_conclusao)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
        """, 
            capa_numero,
            dados_capa.get('tipo', 'corretiva'),
            origem,
            origem_id,
            dados_capa['descricao_problema'],
            dados_capa.get('causa_raiz', ''),
            dados_capa.get('acao_corretiva', ''),
            dados_capa.get('acao_preventiva', ''),
            dados_capa.get('responsavel', ''),
            dados_capa.get('data_prevista_conclusao'),
        )
        
        return dict(row)
    return run_async(_go())

def obter_capas_abertas() -> list:
    """Lista CAPAs abertas ou em andamento."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT * FROM capa_registros
            WHERE status IN ('aberta', 'em_andamento')
            ORDER BY prioridade_vencimento DESC, data_abertura
        """)
        
        # Adicionar prioridade de vencimento
        capas = []
        for row in rows:
            r = dict(row)
            if r['data_prevista_conclusao']:
                dias_ate_vencimento = (r['data_prevista_conclusao'] - __import__('datetime').date.today()).days
                r['dias_ate_vencimento'] = dias_ate_vencimento
                if dias_ate_vencimento < 0:
                    r['prioridade_vencimento'] = 1  # Vencida
                elif dias_ate_vencimento <= 3:
                    r['prioridade_vencimento'] = 2  # Urgente
                elif dias_ate_vencimento <= 7:
                    r['prioridade_vencimento'] = 3  # Atenção
                else:
                    r['prioridade_vencimento'] = 4  # Normal
            else:
                r['dias_ate_vencimento'] = None
                r['prioridade_vencimento'] = 5  # Sem data
            capas.append(r)
        
        return sorted(capas, key=lambda x: x['prioridade_vencimento'])
    return run_async(_go())

def fechar_capa(capa_id: int, eficacia: bool, observacoes: str = "") -> dict:
    """Fecha CAPA verificando eficácia."""
    async def _go():
        db = await get_db()
        
        await db.execute("""
            UPDATE capa_registros
            SET status = 'concluida',
                data_conclusao = CURRENT_DATE,
                eficacia_verificada = $1,
                observacoes = COALESCE(observacoes, '') || ' - ' || $2,
                updated_at = NOW()
            WHERE id = $3
        """, eficacia, observacoes, capa_id)
        
        return {"success": True, "capa_id": capa_id, "eficacia": eficacia}
    return run_async(_go())

# ===========================================================================
# Estatísticas
# ===========================================================================

def calcular_taxa_defeitos(periodo_dias: int = 30) -> dict:
    """Calcula taxa de defeitos por SKU, molde, máquina."""
    async def _go():
        db = await get_db()
        
        # Taxa geral
        taxa_geral = await db.fetchrow("""
            SELECT 
                COUNT(DISTINCT iq.lote_id) as lotes_inspecionados,
                COUNT(DISTINCT CASE WHEN iq.status_inspecao = 'aprovado' THEN iq.lote_id END) as lotes_aprovados,
                ROUND(
                    COUNT(DISTINCT CASE WHEN iq.status_inspecao != 'aprovado' THEN iq.lote_id END)::numeric /
                    NULLIF(COUNT(DISTINCT iq.lote_id), 0) * 100, 
                    1
                ) as taxa_reprovacao_pct
            FROM inspecao_qualidade iq
            WHERE iq.data_inspecao >= CURRENT_DATE - make_interval(days => $1)
        """, periodo_dias)
        
        taxa_geral = dict(taxa_geral) if taxa_geral else {}
        
        # Por SKU
        por_sku = await db.fetch("""
            SELECT 
                pl.sku,
                COUNT(DISTINCT iq.id) as total_inspecoes,
                COUNT(DISTINCT CASE WHEN iq.status_inspecao = 'aprovado' THEN iq.id END) as aprovacoes,
                ROUND(
                    SUM(idf.quantidade)::numeric /
                    NULLIF(SUM(pl.quantidade_produzida), 0) * 100, 
                    2
                ) as taxa_defeitos_pct
            FROM producao_lotes pl
            LEFT JOIN inspecao_qualidade iq ON iq.lote_id = pl.id
            LEFT JOIN inspecao_defeitos idf ON idf.inspecao_id = iq.id
            WHERE pl.data_inicio >= CURRENT_DATE - make_interval(days => $1)
            GROUP BY pl.sku
            ORDER BY taxa_defeitos_pct DESC NULLS LAST
        """, periodo_dias)
        
        por_sku = [dict(r) for r in por_sku]
        
        return {
            "periodo_dias": periodo_dias,
            "lotes_inspecionados": taxa_geral.get('lotes_inspecionados', 0),
            "lotes_aprovados": taxa_geral.get('lotes_aprovados', 0),
            "taxa_reprovacao_pct": taxa_geral.get('taxa_reprovacao_pct', 0),
            "por_sku": por_sku[:10],  # Top 10
        }
    return run_async(_go())

# ===========================================================================
# Auto-teste
# ===========================================================================

if __name__ == "__main__":
    log(AGENT, "Auto-teste")
    
    # Listar defeitos
    defeitos = listar_defeitos()
    print(f"Defeitos cadastrados: {len(defeitos)}")
    
    # Pareto de defeitos
    pareto = pareto_defeitos(30)
    print(f"Pareto (últimos 30 dias): {pareto['total_defeitos']} defeitos")
    
    # Taxa de defeitos
    taxa = calcular_taxa_defeitos(30)
    print(f"Taxa de reprovação: {taxa['taxa_reprovacao_pct']}%")
    
    # CAPAs abertas
    capas = obter_capas_abertas()
    print(f"CAPAs abertas: {len(capas)}")