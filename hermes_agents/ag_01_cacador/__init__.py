"""
AG-01: Caçador de Produtos
Pesquisa diariamente marketplaces em busca de produtos em alta,
com baixa concorrência, que a fábrica consegue produzir.
"""
import sys, json, os
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Optional
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log, hoje, pct

AGENT = "AG-01 | Caçador de Produtos"

# ---------------------------------------------------------------------------
# Config de fontes
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
MARKETPLACES = ["shopee", "mercado_livre", "amazon", "temu", "tiktok_shop"]
FONTES_TENDENCIAS = ["google_trends", "pinterest"]

# Fonte de dados: "simulada" (JSON config) ou "api" (APIs reais)
FONTE_DADOS = os.getenv("CACADOR_FONTE", "simulada")

def _carregar_produtos() -> dict:
    """Carrega catálogo simulado do JSON de configuração."""
    path = CONFIG_DIR / "produtos.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}

PRODUTOS_CONFIG = _carregar_produtos()

# ---------------------------------------------------------------------------
# Coleta de produtos
# ---------------------------------------------------------------------------

def pesquisar_marketplace(marketplace: str, categoria: str = "casa_e_decoracao") -> list:
    """
    Coleta produtos do marketplace.
    Modo 'simulada': carrega do JSON de config.
    Modo 'api': usa APIs reais (requer tokens configurados).
    """
    log(AGENT, f"Pesquisando {marketplace} > {categoria}...")

    if FONTE_DADOS == "simulada":
        return PRODUTOS_CONFIG.get(marketplace, [])
    # ponytail: placeholder para modo api, integrar com APIs reais quando tokens configurados
    log(AGENT, f"⚠ Modo API ainda não implementado para {marketplace}, usando dados simulados")
    return PRODUTOS_CONFIG.get(marketplace, [])

# ---------------------------------------------------------------------------
# Coleta de tendências
# ---------------------------------------------------------------------------

def coletar_tendencias() -> list:
    """Coleta tendências do Google Trends e Pinterest."""
    log(AGENT, "Coletando tendências...")

    if FONTE_DADOS == "simulada":
        path = CONFIG_DIR / "tendencias.json"
        tendencias = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    else:
        # ponytail: placeholder, trocar por pytrends / pinterest API
        log(AGENT, "⚠ Modo API ainda não implementado para tendências, usando dados simulados")
        path = CONFIG_DIR / "tendencias.json"
        tendencias = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    async def _save():
        db = await get_db()
        for t in tendencias:
            await db.execute("""
                INSERT INTO tendencias (termo, plataforma, volume_buscas, crescimento_pct, data_coleta, categoria, relevancia)
                VALUES ($1, 'google_trends', $2, $3, CURRENT_DATE, $4, $5)
                ON CONFLICT DO NOTHING
            """, t["termo"], t["volume"], t["crescimento"], t["categoria"], min(int(t["crescimento"]), 100))
    run_async(_save())
    return tendencias

# ---------------------------------------------------------------------------
# Análise de viabilidade
# ---------------------------------------------------------------------------

def analisar_viabilidade(produto: dict) -> dict:
    """Analisa se um produto é viável para fabricação própria."""
    # Critérios de fabricabilidade
    materiais_compativeis = ["plastico", "silicone", "pp", "abs", "pead", "pvc", "acrilico"]
    nome_lower = produto["nome"].lower()

    # Verifica se usa material que temos
    fabricavel = any(m in nome_lower for m in materiais_compativeis)

    # Estima complexidade do molde
    palavras_complexas = ["dobravel", "articulado", "mola", "encaixe", "rosca", "eletronico"]
    complexidade = sum(1 for p in palavras_complexas if p in nome_lower)
    complexidade = min(complexidade + 3, 10)

    # Estima margem
    preco = produto["preco"]
    custo_molde_estimado = complexidade * 5000  # R$5000 por ponto de complexidade
    custo_producao_unitario = preco * 0.18  # ~18% do preço de venda

    # Taxas marketplace (~18% em média)
    taxa = preco * 0.18
    lucro = preco - custo_producao_unitario - taxa
    margem = round((lucro / preco) * 100, 1) if preco else 0

    # Score final
    concorrencia = produto.get("concorrentes", 100)
    score = 0
    if fabricavel: score += 40
    if concorrencia < 30: score += 30
    elif concorrencia < 80: score += 15
    if margem > 40: score += 30
    elif margem > 25: score += 15

    nivel_concorrencia = "baixa" if concorrencia < 30 else ("media" if concorrencia < 100 else "alta")

    return {
        "nome": produto["nome"],
        "marketplace_origem": produto.get("marketplace", "desconhecido"),
        "url": produto.get("url", ""),
        "preco_medio": preco,
        "volume_vendas_estimado": produto.get("vendas_mes", 0),
        "concorrentes_diretos": concorrencia,
        "nivel_concorrencia": nivel_concorrencia,
        "fabricavel": fabricavel,
        "complexidade_molde": complexidade,
        "custo_molde_estimado": custo_molde_estimado,
        "custo_producao_unitario": round(custo_producao_unitario, 2),
        "margem_estimada": margem,
        "tempo_lancamento_dias": complexidade * 7 + 15,
        "tendencia": "estavel",
        "score_final": min(score, 100),
        "status": "analisar",
    }

# ---------------------------------------------------------------------------
# Pipeline principal: coleta + análise + salva
# ---------------------------------------------------------------------------

def executar_cacada(categoria: str = "casa_e_decoracao") -> list:
    """
    Executa a caçada completa:
    1. Coleta de todos os marketplaces
    2. Análise de viabilidade
    3. Ranking por score
    4. Salva no banco
    """
    log(AGENT, f"Iniciando caçada diária em {len(MARKETPLACES)} marketplaces...")
    todos_produtos = []

    for mp in MARKETPLACES:
        produtos = pesquisar_marketplace(mp, categoria)
        for p in produtos:
            p["marketplace"] = mp
            analise = analisar_viabilidade(p)
            todos_produtos.append(analise)

    # Ordena por score
    todos_produtos.sort(key=lambda x: x["score_final"], reverse=True)

    # Salva no banco
    async def _save():
        db = await get_db()
        for p in todos_produtos:
            await db.execute("""
                INSERT INTO produtos_descobertos
                    (nome, marketplace_origem, url, data_descoberta, preco_medio,
                     volume_vendas_estimado, concorrentes_diretos, nivel_concorrencia,
                     fabricavel, complexidade_molde, custo_molde_estimado,
                     custo_producao_unitario, margem_estimada_pct,
                     tempo_lancamento_dias, tendencia, score_final, status)
                VALUES ($1,$2,$3,CURRENT_DATE,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,'analisar')
                ON CONFLICT DO NOTHING
            """, p["nome"], p["marketplace_origem"], p["url"], p["preco_medio"],
                p["volume_vendas_estimado"], p["concorrentes_diretos"], p["nivel_concorrencia"],
                p["fabricavel"], p["complexidade_molde"], p["custo_molde_estimado"],
                p["custo_producao_unitario"], p["margem_estimada"],
                p["tempo_lancamento_dias"], p["tendencia"], p["score_final"])
    run_async(_save())

    log(AGENT, f"Caçada concluída: {len(todos_produtos)} produtos encontrados")
    return todos_produtos

def top_oportunidades(n: int = 10) -> list:
    """Retorna as top N oportunidades do dia."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT * FROM produtos_descobertos
            WHERE data_descoberta = CURRENT_DATE AND status = 'analisar'
            ORDER BY score_final DESC
            LIMIT $1
        """, n)
        return [dict(r) for r in rows]
    return run_async(_go())

# ---------------------------------------------------------------------------
# Auto-teste
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log(AGENT, "=== Auto-teste ===")
    resultados = executar_cacada()
    print(f"\nTop 5 oportunidades:")
    for i, p in enumerate(resultados[:5], 1):
        print(f"  {i}. [{p['score_final']}/100] {p['nome']}")
        print(f"     R${p['preco_medio']:.2f} | Margem: {p['margem_estimada']}% | Concorrência: {p['nivel_concorrencia']} | Fabricável: {p['fabricavel']}")
