"""
Shopee Competition — price analysis vs competitors.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core import log, run_async, get_db

AGENT = "AG-03 | Shopee Competition"


def analisar_concorrencia(sku: str, preco: float, marketplace: str = "shopee") -> dict:
    """Compara o preco do produto com a media dos concorrentes na tabela anuncios.
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
            "mensagem": f"Seu preco esta {acima_pct}% {'acima' if acima_pct >= 0 else 'abaixo'} da media (R$ {media:.2f}). {n} anuncios analisados." if alerta else f"Preco competitivo: {abs(acima_pct)}% {'acima' if acima_pct >= 0 else 'abaixo'} da media."
        }
    try:
        result = run_async(_go())
        if result: return result
        return {"sku": sku, "preco_nosso": preco, "total_anuncios": 0, "mensagem": "Nenhum concorrente encontrado para este SKU."}
    except Exception as e:
        return {"sku": sku, "erro": str(e)}
