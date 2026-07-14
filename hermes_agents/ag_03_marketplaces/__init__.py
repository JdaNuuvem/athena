"""
AG-03: Gerente de Marketplaces
Monitora posição de anúncios, preços dos concorrentes, avaliações,
e gera sugestões de otimização (títulos, SEO, preços, kits).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log, hoje

# ── Integração com Memória ──
try:
    from core.memory import store as memory_store
except ImportError:
    def memory_store(*a, **kw): pass

AGENT = "AG-03 | Gerente de Marketplaces"

# ===========================================================================
# Monitoramento de posição
# ===========================================================================

def verificar_posicoes() -> list:
    """Verifica posição de todos os anúncios ativos nos marketplaces."""
    log(AGENT, "Verificando posições dos anúncios...")
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT sku, marketplace, titulo, posicao_busca, avaliacao_media, total_avaliacoes
            FROM anuncios
            WHERE status = 'ativo'
            ORDER BY marketplace, posicao_busca
        """)
        return [dict(r) for r in rows]
    resultado = run_async(_go())

    memory_store(
        query="Verificação de posições dos anúncios",
        response=f"{len(resultado)} anúncios ativos",
        agent_id="ag_03", category="marketing",
        metadata={"total_anuncios": len(resultado)}
    )

    return resultado

def anuncios_caindo() -> list:
    """Anúncios que caíram de posição (fora do top 10)."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT * FROM anuncios
            WHERE status = 'ativo' AND posicao_busca > 10
            ORDER BY posicao_busca ASC
        """)
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Preços dos concorrentes
# ===========================================================================

def comparar_precos_concorrentes(sku: str = "") -> list:
    """Compara preço nosso vs concorrência para um SKU ou todos."""
    log(AGENT, f"Comparando preços {'para ' + sku if sku else 'todos SKUs'}...")
    async def _go():
        db = await get_db()
        query = """
            SELECT a.sku, a.marketplace, a.preco AS nosso_preco,
                   c.nome AS concorrente, c.preco AS preco_concorrente,
                   ROUND((a.preco - c.preco) / c.preco * 100, 1) AS diff_pct
            FROM anuncios a
            JOIN concorrentes c ON c.marketplace = a.marketplace
                AND c.produto_similar ILIKE '%' || a.sku || '%'
            WHERE a.status = 'ativo' AND c.data_coleta = CURRENT_DATE
        """
        if sku:
            query += " AND a.sku = $1"
            rows = await db.fetch(query, sku)
        else:
            rows = await db.fetch(query)
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Sugestões de otimização
# ===========================================================================

def gerar_sugestao_titulo(sku: str, palavras_chave: list, marketplace: str) -> dict:
    """Gera sugestão de título otimizado para SEO."""
    kws = " ".join(palavras_chave[:5])
    titulo_atual = f"Produto {sku}"

    async def _go():
        db = await get_db()
        a = await db.fetchrow("SELECT titulo FROM anuncios WHERE sku = $1 AND marketplace = $2", sku, marketplace)
        if a:
            titulo_atual = a["titulo"]

    run_async(_go())

    # Heurística simples de otimização
    novo_titulo = f"{sku} | {kws} — Entrega Rápida | Frete Grátis"
    return {
        "sku": sku,
        "marketplace": marketplace,
        "tipo": "titulo",
        "titulo_atual": titulo_atual,
        "sugestao": novo_titulo,
        "palavras_chave": palavras_chave,
        "impacto_estimado": "medio",
    }

def sugerir_kit(sku_a: str, sku_b: str, marketplace: str) -> dict:
    """Sugere criação de kit combinando dois produtos complementares."""
    async def _go():
        db = await get_db()
        a = await db.fetchrow("SELECT titulo, preco FROM anuncios WHERE sku = $1 AND marketplace = $2", sku_a, marketplace)
        b = await db.fetchrow("SELECT titulo, preco FROM anuncios WHERE sku = $1 AND marketplace = $2", sku_b, marketplace)
        if not a or not b:
            return {"erro": "SKU não encontrado"}
        preco_kit = round((float(a["preco"]) + float(b["preco"])) * 0.85, 2)
        return {
            "tipo": "kit",
            "sku_a": sku_a,
            "sku_b": sku_b,
            "nome_kit": f"Combo {a['titulo']} + {b['titulo']}",
            "preco_individual": round(float(a["preco"]) + float(b["preco"]), 2),
            "preco_kit": preco_kit,
            "desconto_pct": 15,
            "impacto_estimado": "alto",
        }
    return run_async(_go())

def sugerir_ajuste_preco(sku: str, marketplace: str) -> dict:
    """Sugere ajuste de preço baseado na concorrência."""
    precos = comparar_precos_concorrentes(sku)
    if not precos:
        return {"sku": sku, "mensagem": "Sem dados de concorrência"}

    nosso = precos[0]["nosso_preco"]
    concorrencia = [p["preco_concorrente"] for p in precos]
    media_concorrencia = sum(concorrencia) / len(concorrencia)
    diff_pct = round((nosso - media_concorrencia) / media_concorrencia * 100, 1)

    acao = "manter"
    novo_preco = nosso
    if diff_pct > 15:
        acao = "reduzir"
        novo_preco = round(media_concorrencia * 0.95, 2)
    elif diff_pct < -10:
        acao = "aumentar"
        novo_preco = round(media_concorrencia * 1.05, 2)

    return {
        "sku": sku,
        "marketplace": marketplace,
        "tipo": "preco",
        "nosso_preco": nosso,
        "media_concorrencia": round(media_concorrencia, 2),
        "diff_pct": diff_pct,
        "acao": acao,
        "novo_preco_sugerido": novo_preco,
        "impacto_estimado": "alto" if acao != "manter" else "baixo",
    }

# ===========================================================================
# Geração de relatório consolidado
# ===========================================================================

def relatorio_consolidado() -> dict:
    """Relatório completo do estado dos marketplaces."""
    log(AGENT, "Gerando relatório consolidado de marketplaces...")
    async def _go():
        db = await get_db()
        total_anuncios = await db.fetchval("SELECT COUNT(*) FROM anuncios WHERE status = 'ativo'")
        top10 = await db.fetchval("SELECT COUNT(*) FROM anuncios WHERE status = 'ativo' AND posicao_busca <= 10")
        sugestoes_pendentes = await db.fetchval("SELECT COUNT(*) FROM sugestoes_otimizacao WHERE status = 'pendente'")
        alertas_abertos = await db.fetchval("SELECT COUNT(*) FROM alertas WHERE resolvido = false")

        return {
            "data": hoje(),
            "total_anuncios_ativos": total_anuncios,
            "anuncios_top10": top10,
            "pct_top10": round(top10 / total_anuncios * 100, 1) if total_anuncios else 0,
            "sugestoes_pendentes": sugestoes_pendentes,
            "alertas_abertos": alertas_abertos,
        }
    return run_async(_go())

# ===========================================================================
# Execução programada (a cada 4h)
# ===========================================================================

def executar_monitoramento() -> list:
    """Roda todas as verificações e gera sugestões e alertas."""
    log(AGENT, "Executando ciclo de monitoramento...")
    resultados = []

    # 1. Anúncios caindo
    caidos = anuncios_caindo()
    for a in caidos:
        resultados.append(f"⚠️ {a['sku']} caiu para posição {a['posicao_busca']} no {a['marketplace']}")

    # 2. Comparação de preços
    for a in verificar_posicoes()[:5]:
        sugestao = sugerir_ajuste_preco(a["sku"], a["marketplace"])
        if sugestao.get("acao") != "manter":
            resultados.append(f"💰 {a['sku']}: {sugestao['acao']} preço para R${sugestao['novo_preco_sugerido']}")

    # 3. Salva alertas
    async def _salvar():
        db = await get_db()
        for r in resultados:
            await db.execute("INSERT INTO alertas (tipo, sku, mensagem, gravidade) VALUES ('posicao', 'geral', $1, 'info')", r)
    run_async(_salvar())

    log(AGENT, f"Monitoramento concluído: {len(resultados)} ocorrências")

    # ── Memory: store monitoring cycle ──
    memory_store(
        query="Monitoramento de marketplaces",
        response=f"{len(resultados)} ocorrências detectadas",
        agent_id="ag_03", category="marketing",
        metadata={"ocorrencias": len(resultados)}
    )

    return resultados

# ===========================================================================
# Auto-teste
# ===========================================================================

if __name__ == "__main__":
    log(AGENT, "=== Auto-teste ===")
    print("Relatório:", relatorio_consolidado())
    print("\nSugestão de preço:", sugerir_ajuste_preco("ORG001", "shopee"))
    print("\nMonitoramento:", executar_monitoramento())
