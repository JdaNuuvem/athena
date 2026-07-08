"""
AG-04: Planejador de Produção
Analisa pedidos, estoque, capacidade das máquinas e monta
automaticamente a melhor sequência de produção.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log, hoje, FactoryConfig

AGENT = "AG-04 | Planejador de Produção"

def obter_pedidos_pendentes() -> list:
    """Lista pedidos pendentes de produção ordenados por prioridade."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT id, sku, quantidade, prazo, prioridade, status
            FROM pedidos_producao WHERE status IN ('pendente','em_andamento')
            ORDER BY prazo ASC, prioridade DESC
        """)
        return [dict(r) for r in rows]
    return run_async(_go())

def obter_estoque() -> list:
    """Estoque atual de matéria-prima."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT nome, estoque_atual_kg, estoque_minimo_kg,
                   (estoque_atual_kg - estoque_minimo_kg) AS folga
            FROM materias_primas ORDER BY nome
        """)
        return [dict(r) for r in rows]
    return run_async(_go())

def calcular_score_producao(sku: str, prazo_dias: int, margem_pct: float, cliente_tipo: str, tempo_setup_min: int) -> int:
    """Calcula score de prioridade de produção (0-100)."""
    urgencia = max(0, 100 - prazo_dias * 10)
    margem_score = min(margem_pct * 2, 50)
    cliente_score = 30 if cliente_tipo == "atacado" else 15
    setup_score = max(0, 20 - tempo_setup_min)
    return int(urgencia * 0.4 + margem_score * 0.3 + cliente_score * 0.2 + setup_score * 0.1)

def verificar_estoque_disponivel(sku: str, quantidade: int) -> bool:
    """Verifica se há estoque suficiente para produção."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            SELECT SUM(mp.estoque_atual_kg) AS total_estoque
            FROM materias_primas mp
            WHERE mp.estoque_atual_kg > mp.estoque_minimo_kg
        """)
        if not row:
            return False
        
        # Estimativa simples: 1kg = 10 unidades
        capacidade = int(row['total_estoque'] * 10) if row['total_estoque'] else 0
        return capacidade >= quantidade
    return run_async(_go())

def adicionar_pedido_producao(sku: str, quantidade: int, prazo, prioridade: int = 0, cliente_id: int = None) -> dict:
    """Adiciona novo pedido de produção."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            INSERT INTO pedidos_producao (sku, quantidade, prazo, prioridade, cliente_id)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """, sku, quantidade, prazo, prioridade, cliente_id)
        return dict(row)
    return run_async(_go())

def gerar_plano_diario(data: str = None) -> list:
    """Gera o plano de produção otimizado para hoje."""
    from datetime import date, timedelta
    
    data_alvo = data or date.today()
    log(AGENT, f"Gerando plano de produção para {data_alvo}...")
    
    pedidos = obter_pedidos_pendentes()
    estoque = obter_estoque()
    
    plano = []
    for p in pedidos:
        # Verificar estoque disponível
        if not verificar_estoque_disponivel(p['sku'], p['quantidade']):
            log(AGENT, f"⚠️ Estoque insuficiente para {p['sku']}")
            continue
        
        # Obter margem do AG-02
        margem_pct = 30.0  # Default
        async def _get_margem():
            db = await get_db()
            row = await db.fetchrow("""
                SELECT margem_pct FROM margens_diarias
                WHERE sku = $1 AND data = CURRENT_DATE
            """, p['sku'])
            return float(row['margem_pct']) if row else 30.0
        
        # Calcular dias até prazo
        prazo_date = p['prazo'] if hasattr(p['prazo'], 'date') else data_alvo + timedelta(days=5)
        dias_ate_prazo = (prazo_date - data_alvo).days if hasattr(prazo_date, '__sub__') else 5
        
        score = calcular_score_producao(
            sku=p["sku"],
            prazo_dias=max(0, dias_ate_prazo),
            margem_pct=margem_pct,
            cliente_tipo="atacado" if p.get('cliente_id') else "varejo",
            tempo_setup_min=15,
        )
        
        plano.append({**p, "score": score})
    
    plano.sort(key=lambda x: x["score"], reverse=True)
    
    # Salvar plano no DB
    async def _save_plano():
        db = await get_db()
        await db.execute("""
            INSERT INTO plano_producao_diario (data, pedidos_sequenciados, capacidade_utilizada_pct)
            VALUES ($1, $2, $3)
        """, data_alvo, plano, min(len(plano) * 10, 100))
    
    try:
        run_async(_save_plano())
    except Exception as e:
        log(AGENT, f"⚠️ Erro ao salvar plano: {e}")
    
    log(AGENT, f"Plano gerado: {len(plano)} pedidos sequenciados")
    return plano

def registrar_producao_concluida(lote_id: int) -> dict:
    """Registra conclusão de lote e entra no estoque."""
    async def _go():
        db = await get_db()
        
        # Obter dados do lote
        lote = await db.fetchrow("SELECT * FROM producao_lotes WHERE id = $1", lote_id)
        if not lote:
            return {"error": "Lote não encontrado"}
        
        # Atualizar status do lote
        await db.execute("""
            UPDATE producao_lotes
            SET status = 'concluido', data_fim = CURRENT_DATE, updated_at = NOW()
            WHERE id = $1
        """, lote_id)
        
        # Entrar no estoque
        await db.execute("""
            INSERT INTO estoque_produtos (sku, lote_id, quantidade, data_entrada, origem)
            VALUES ($1, $2, $3, CURRENT_DATE, 'producao')
            ON CONFLICT (sku, lote_id) DO UPDATE
            SET quantidade = estoque_produtos.quantidade + $3, updated_at = NOW()
        """, lote['sku'], lote_id, lote['quantidade_produzida'])
        
        # Atualizar ciclos do molde
        await db.execute("""
            UPDATE moldes
            SET ciclos_acumulados = COALESCE(ciclos_acumulados, 0) + $1,
                ciclos_atuais = COALESCE(ciclos_atuais, 0) + $1,
                updated_at = NOW()
            WHERE id = $2
        """, lote['ciclos_realizados'], lote['molde_id'])
        
        log(AGENT, f"✅ Lote {lote['lote_id']} concluído - {lote['quantidade_produzida']} unidades no estoque")
        
        return {
            "success": True, 
            "lote_id": lote_id, 
            "sku": lote['sku'], 
            "quantidade": lote['quantidade_produzida'],
            "lote_codigo": lote['lote_id']
        }
    return run_async(_go())

def obter_estoque_produtos(sku: str = "") -> dict:
    """Obtém estoque de produtos acabados."""
    async def _go():
        db = await get_db()
        
        if sku:
            rows = await db.fetch("""
                SELECT sku, SUM(quantidade) as total_quantidade,
                       COUNT(DISTINCT lote_id) as total_lotes
                FROM estoque_produtos
                WHERE sku = $1 AND data_saida IS NULL
                GROUP BY sku
            """, sku)
        else:
            rows = await db.fetch("""
                SELECT sku, SUM(quantidade) as total_quantidade,
                       COUNT(DISTINCT lote_id) as total_lotes
                FROM estoque_produtos
                WHERE data_saida IS NULL
                GROUP BY sku
                ORDER BY total_quantidade DESC
            """)
        
        estoque = {r['sku']: {
            "quantidade": int(r['total_quantidade']),
            "lotes": int(r['total_lotes'])
        } for r in rows}
        
        return {
            "data": hoje(),
            "total_skus": len(estoque),
            "estoque": estoque
        }
    return run_async(_go())

def sugerir_transferencia(loja_origem: int, loja_destino: int) -> list:
    """Sugere transferências entre lojas baseado em giro."""
    async def _go():
        db = await get_db()
        
        # SKUs com estoque alto na origem
        estoque_origem = await db.fetch("""
            SELECT sku, SUM(quantidade) as total
            FROM estoque_produtos
            WHERE loja_id = $1 AND data_saida IS NULL
            GROUP BY sku
            HAVING SUM(quantidade) > 50
        """, loja_origem)
        
        sugestoes = []
        for row in estoque_origem:
            sku = row['sku']
            # Verificar se destino tem estoque baixo
            estoque_destino = await db.fetchval("""
                SELECT COALESCE(SUM(quantidade), 0)
                FROM estoque_produtos
                WHERE loja_id = $1 AND sku = $2 AND data_saida IS NULL
            """, loja_destino, sku)
            
            if estoque_destino < 20:
                qtd_transferir = min(row['total'] - 30, 30)  # Deixar 30 na origem
                if qtd_transferir > 0:
                    sugestoes.append({
                        "sku": sku,
                        "loja_origem": loja_origem,
                        "loja_destino": loja_destino,
                        "quantidade": qtd_transferir,
                        "estoque_origem": row['total'],
                        "estoque_destino": estoque_destino
                    })
        
        return sugestoes
    return run_async(_go())

def maquinas_disponiveis() -> list:
    """Capacidade disponível das máquinas."""
    return [
        {"maquina": "Injetora 1", "capacidade_horas": 16, "utilizadas": 10, "ociosas": 6},
        {"maquina": "Injetora 2", "capacidade_horas": 16, "utilizadas": 13, "ociosas": 3},
        {"maquina": "Injetora 3", "capacidade_horas": 16, "utilizadas": 8, "ociosas": 8},
        {"maquina": "CNC Router", "capacidade_horas": 12, "utilizadas": 6, "ociosas": 6},
    ]

def relatorio_oee() -> dict:
    """Overall Equipment Effectiveness."""
    maquinas = maquinas_disponiveis()
    total_ocioso = sum(m["ociosas"] for m in maquinas)
    total_capacidade = sum(m["capacidade_horas"] for m in maquinas)
    return {
        "data": hoje(),
        "maquinas": len(maquinas),
        "capacidade_total_horas": total_capacidade,
        "horas_ociosas": total_ocioso,
        "utilizacao_pct": round((1 - total_ocioso / total_capacidade) * 100, 1) if total_capacidade else 0,
        "detalhes": maquinas,
    }

if __name__ == "__main__":
    log(AGENT, "Auto-teste")
    print("Plano:", gerar_plano_diario()[:3])
    print("OEE:", relatorio_oee())
