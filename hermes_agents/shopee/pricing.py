"""
Shopee Pricing — margin calculation.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core import log, run_async, get_db
from core.__init__ import FactoryConfig
from core.config import get_config

AGENT = "AG-03 | Shopee Pricing"


def calcular_margem_produto(sku: str, preco: float, loja_id: int = None) -> dict:
    """Calcula margem real de um produto na Shopee: preco - comissao - frete medio - custo.
    Retorna { margem_valor, margem_pct, custo, frete, comissao_pct, comissao_valor, ok, mensagem }"""
    # buscar custo do catalogo
    async def _go():
        db = await get_db()
        custo_row = await db.fetchrow("SELECT preco_custo FROM catalogo_produtos WHERE sku = $1 LIMIT 1", sku)
        custo = float(custo_row["preco_custo"] or 0) if custo_row else 0
        return custo
    try: custo = run_async(_go())
    except: custo = 0

    # comissao Shopee (configuravel por loja ou global, default 12%)
    comissao_pct = float(os.environ.get("SHOPEE_COMISSAO_PCT") or get_config("shopee", "comissao_pct") or 12)
    comissao_valor = round(preco * comissao_pct / 100, 2)
    cfg = FactoryConfig.load()
    frete = float(get_config("shopee", "frete_medio") or cfg.frete_medio_shopee)
    margem_valor = round(preco - comissao_valor - frete - custo, 2)
    margem_pct = round((margem_valor / preco * 100) if preco > 0 else 0, 1)

    if custo <= 0:
        return {"margem_valor": margem_valor, "margem_pct": margem_pct, "custo": custo, "frete": frete,
                "comissao_pct": comissao_pct, "comissao_valor": comissao_valor,
                "ok": True, "mensagem": "Custo nao cadastrado — margem nao verificada"}

    if margem_valor < 0:
        return {"margem_valor": margem_valor, "margem_pct": margem_pct, "custo": custo, "frete": frete,
                "comissao_pct": comissao_pct, "comissao_valor": comissao_valor,
                "ok": False, "mensagem": f"PREJUIZO: margem de R$ {margem_valor:.2f} ({margem_pct}%). "
                f"Custo R$ {custo:.2f} + comissao {comissao_pct}% (R$ {comissao_valor:.2f}) + frete R$ {frete:.2f} > preco R$ {preco:.2f}"}

    if margem_pct < cfg.margem_minima_pct:
        return {"margem_valor": margem_valor, "margem_pct": margem_pct, "custo": custo, "frete": frete,
                "comissao_pct": comissao_pct, "comissao_valor": comissao_valor,
                "ok": True, "alerta": True,
                "mensagem": f"Margem baixa: {margem_pct}% (minimo configurado: {cfg.margem_minima_pct}%). "
                f"Preco R$ {preco:.2f} - comissao R$ {comissao_valor:.2f} - frete R$ {frete:.2f} - custo R$ {custo:.2f} = R$ {margem_valor:.2f}"}

    return {"margem_valor": margem_valor, "margem_pct": margem_pct, "custo": custo, "frete": frete,
            "comissao_pct": comissao_pct, "comissao_valor": comissao_valor,
            "ok": True, "mensagem": f"Margem: {margem_pct}% (R$ {margem_valor:.2f})"}
