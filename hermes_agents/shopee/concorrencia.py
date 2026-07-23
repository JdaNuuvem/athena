"""
Shopee Pricing Consistency — compara o preco de um SKU com o mesmo SKU
publicado em OUTRAS lojas Shopee da propria conta.

ponytail: isso NAO e' comparacao com concorrentes reais no marketplace —
a API v2 da Shopee (a que o vendedor usa) e' escopada a propria conta
(partner_id + shop_id do vendedor autenticado) e nao expoe precos de
OUTROS vendedores. Nao existe endpoint de busca publica de produtos
nessa API. Renomeado de "analisar_concorrencia" para refletir o que a
funcao realmente faz: apontar quando voce mesmo esta com o mesmo SKU
anunciado por precos diferentes nas suas proprias lojas.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core import log, run_async, get_db

AGENT = "AG-03 | Shopee Pricing Consistency"


def analisar_consistencia_precos(sku: str, preco: float, marketplace: str = "shopee") -> dict:
    """Compara o preco do produto com o mesmo SKU em OUTRAS lojas Shopee da sua conta
    (nao com concorrentes externos — a API nao da acesso a isso).
    Retorna { media, mediana, min, max, total_anuncios, preco_acima_pct, alerta, mensagem }"""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT preco FROM anuncios
            WHERE sku = $1 AND marketplace = $2 AND preco > 0
            ORDER BY preco
        """, sku, marketplace)
        precos = sorted([float(r["preco"]) for r in rows])
        if not precos:
            return None
        n = len(precos)
        media = sum(precos) / n
        mediana = precos[n // 2] if n % 2 == 1 else (precos[n // 2 - 1] + precos[n // 2]) / 2
        minimo = precos[0]
        maximo = precos[-1]
        acima_pct = round((preco - media) / media * 100, 1) if media > 0 else 0
        alerta = None
        if acima_pct > 50:
            alerta = "critico"
        elif acima_pct > 20:
            alerta = "alerta"
        return {
            "sku": sku, "preco_nosso": preco, "marketplace": marketplace,
            "total_anuncios": n, "preco_medio": round(media, 2),
            "preco_mediano": round(mediana, 2), "preco_min": minimo, "preco_max": maximo,
            "preco_acima_pct": acima_pct, "alerta": alerta,
            "mensagem": f"Este SKU esta {acima_pct}% {'acima' if acima_pct >= 0 else 'abaixo'} da media das suas outras lojas (R$ {media:.2f}). {n} anuncios proprios analisados." if alerta else f"Preco consistente entre suas lojas: {abs(acima_pct)}% {'acima' if acima_pct >= 0 else 'abaixo'} da media."
        }
    try:
        result = run_async(_go())
        if result: return result
        return {"sku": sku, "preco_nosso": preco, "total_anuncios": 0, "mensagem": "Este SKU nao esta anunciado em nenhuma outra loja sua para comparar."}
    except Exception as e:
        return {"sku": sku, "erro": str(e)}
