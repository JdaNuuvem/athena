"""
AG-07: Laboratório de Produtos
Para cada ideia de produto calcula: investimento, custo do molde,
tempo de desenvolvimento, potencial de vendas, margem, risco.
Cria pipeline priorizado de lançamentos.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log, hoje

AGENT = "AG-07 | Laboratório de Produtos"

def analisar_novo_produto(nome: str, descricao: str, complexidade_molde: int,
                          preco_estimado: float, volume_projetado: int,
                          custo_molde: float = None, categoria: str = "") -> dict:
    """Analisa viabilidade completa de um novo produto."""
    if custo_molde is None:
        custo_molde = complexidade_molde * 5000

    # Calibrar preço com mercado
    preco_calibrado = calibrar_preco_com_mercado(categoria, preco_estimado) if categoria else preco_estimado
    
    # Ajustar volume por tendência
    volume_calibrado = ajustar_volume_por_tendencia(categoria, volume_projetado) if categoria else volume_projetado

    custo_unitario = preco_calibrado * 0.18
    taxa_marketplace = preco_calibrado * 0.18
    lucro_unitario = preco_calibrado - custo_unitario - taxa_marketplace
    margem = round(lucro_unitario / preco_calibrado * 100, 1) if preco_calibrado else 0
    faturamento_mes = preco_calibrado * volume_calibrado
    lucro_mes = lucro_unitario * volume_calibrado
    payback_meses = round(custo_molde / lucro_mes, 1) if lucro_mes > 0 else 99

    score = 0
    score += min(margem * 1.5, 30)
    score += min(volume_calibrado / 100, 20)
    score += max(0, 20 - payback_meses)
    score += max(0, 15 - complexidade_molde)
    score += min(lucro_mes / 1000, 15)

    risco = 1
    if complexidade_molde > 7: risco += 3
    if payback_meses > 6: risco += 2
    if margem < 25: risco += 2
    if volume_calibrado < 100: risco += 1

    return {
        "nome": nome,
        "descricao": descricao,
        "categoria": categoria,
        "investimento_total": round(custo_molde + 2000, 2),
        "custo_molde": round(custo_molde, 2),
        "tempo_desenvolvimento_dias": complexidade_molde * 7 + 15,
        "custo_producao_unitario": round(custo_unitario, 2),
        "preco_venda_sugerido": round(preco_calibrado, 2),
        "preco_original": round(preco_estimado, 2),
        "margem_estimada": margem,
        "volume_vendas_projetado_mes": volume_calibrado,
        "volume_original": volume_projetado,
        "faturamento_mensal": round(faturamento_mes, 2),
        "lucro_mensal": round(lucro_mes, 2),
        "payback_meses": payback_meses,
        "risco": min(risco, 10),
        "score_final": round(min(score, 100), 1),
        "status": "em_analise",
    }

def pipeline_lancamentos() -> list:
    """Pipeline priorizado de lançamentos."""
    log(AGENT, "Gerando pipeline de lançamentos...")
    ideias = [
        ("Organizador de Gaveta Modular", "Gaveta modular plástica empilhável", 4, 29.90, 500),
        ("Porta Tempero Giratório Premium", "Giratório 3 andares com tampa", 5, 49.90, 300),
        ("Suporte Dobrável para Notebook", "Alumínio + silicone ajustável", 7, 79.90, 200),
        ("Ventilador USB Clip Silencioso", "Ventilador clip mesa com regulagem", 8, 55.00, 400),
        ("Capa Impermeável para Sofá", "Tecido impermeável 3 lugares", 3, 119.90, 150),
    ]
    analises = [analisar_novo_produto(*i) for i in ideias]
    analises.sort(key=lambda x: x["score_final"], reverse=True)

    # Classifica por estágio
    pipeline = {"em_analise": [], "aprovado": [], "prototipagem": [], "pre_lancamento": []}
    for i, a in enumerate(analises):
        if i < 1: a["status"] = "aprovado"
        elif i < 2: a["status"] = "prototipagem"
        elif i < 3: a["status"] = "pre_lancamento"
        pipeline[a["status"]].append(a)

    return pipeline

def comparar_cenarios(produtos: list) -> list:
    """Compara múltiplos cenários de lançamento."""
    return sorted(
        [analisar_novo_produto(**p) if isinstance(p, dict) else analisar_novo_produto(*p) for p in produtos],
        key=lambda x: x["score_final"], reverse=True
    )

def obter_margens_medias_por_categoria() -> dict:
    """Busca margens médias de produtos similares para calibrar projeções."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT p.categoria, AVG(m.margem_pct) AS margem_media
            FROM produtos p
            LEFT JOIN margens_diarias m ON m.sku = p.sku
            WHERE m.data = CURRENT_DATE
            GROUP BY p.categoria
        """)
        return {r['categoria']: float(r['margem_media']) for r in rows if r['margem_media']}
    return run_async(_go())

def calibrar_preco_com_mercado(categoria: str, preco_inicial: float) -> float:
    """Ajusta preço baseado em margem média da categoria."""
    margens = obter_margens_medias_por_categoria()
    margem_media = margens.get(categoria, 30.0)
    
    custo = preco_inicial * 0.82
    margem_necessaria = (preco_inicial - custo) / preco_inicial * 100
    
    if margem_necessaria < margem_media * 0.8:
        preco_ajustado = custo / (1 - margem_media / 100)
        return round(preco_ajustado, 2)
    
    return preco_inicial

def obter_tendencias_mercado() -> list:
    """Busca tendências do AG-01 para calibrar volume projetado."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT categoria, tendencia, volume_estimado, concorrentes
            FROM produtos_descobertos
            WHERE status = 'aprovado'
            ORDER BY score_final DESC
            LIMIT 10
        """)
        return [dict(r) for r in rows]
    return run_async(_go())

def ajustar_volume_por_tendencia(categoria: str, volume_inicial: int) -> int:
    """Ajusta volume projetado baseado em tendência de mercado."""
    tendencias = obter_tendencias_mercado()
    for t in tendencias:
        if t.get('categoria') == categoria:
            if t['tendencia'] == 'subindo':
                return int(volume_inicial * 1.5)
            elif t['tendencia'] == 'estavel':
                return volume_inicial
            elif t['tendencia'] == 'caindo':
                return int(volume_inicial * 0.7)
    return volume_inicial

def salvar_pipeline(produto: dict) -> int:
    """Salva análise no banco de dados."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            INSERT INTO pipeline_lancamentos
            (nome_produto, descricao, complexidade_molde, custo_molde_estimado,
             tempo_desenvolvimento_dias, custo_producao_unitario, preco_venda_sugerido,
             margem_estimada, volume_vendas_projetado_mes, payback_meses, risco, score_final)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
        """, produto['nome'], produto['descricao'], produto.get('complexidade_molde', 4),
            produto.get('custo_molde', 0), produto.get('tempo_desenvolvimento_dias', 0),
            produto.get('custo_producao_unitario', 0), produto.get('preco_venda_sugerido', 0),
            produto.get('margem_estimada', 0), produto.get('volume_vendas_projetado_mes', 0),
            produto.get('payback_meses', 0), produto.get('risco', 0), produto.get('score_final', 0))
        return row['id']
    return run_async(_go())

def obter_pipeline_por_status(status: str) -> list:
    """Lista produtos no pipeline por status."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT * FROM pipeline_lancamentos
            WHERE status = $1
            ORDER BY score_final DESC
        """, status)
        return [dict(r) for r in rows]
    return run_async(_go())

def avancar_status(pipeline_id: int, novo_status: str) -> bool:
    """Avança o status de um produto no pipeline."""
    status_validos = ['em_analise', 'aprovado', 'prototipagem', 'pre_lancamento', 'lancamento', 'cancelado']
    
    if novo_status not in status_validos:
        return False
    
    async def _go():
        db = await get_db()
        await db.execute("""
            UPDATE pipeline_lancamentos
            SET status = $1, updated_at = NOW()
            WHERE id = $2
        """, novo_status, pipeline_id)
    run_async(_go())
    return True

if __name__ == "__main__":
    log(AGENT, "Auto-teste")
    analise = analisar_novo_produto("Organizador Gaveta", "Gaveta modular PP", 4, 29.90, 500, categoria="organizacao")
    print(f"Score: {analise['score_final']}/100 | Payback: {analise['payback_meses']}m | Risco: {analise['risco']}/10")
    print(f"Preço calibrado: {analise['preco_venda_sugerido']} (original: {analise['preco_original']})")
    print(f"Volume ajustado: {analise['volume_vendas_projetado_mes']} (original: {analise['volume_original']})")
    
    # Testar pipeline persistente
    pipeline_id = salvar_pipeline(analise)
    print(f"Pipeline ID: {pipeline_id}")
    
    # Testar obter pipeline
    em_analise = obter_pipeline_por_status("em_analise")
    print(f"Produtos em análise: {len(em_analise)}")
