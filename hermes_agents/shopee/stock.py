"""
Shopee Stock — multi-store stock sync.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core import log, run_async, get_db
from .auth import get_shopee_config
from .products import update_stock
from .stores import listar_todas_lojas_shopee

AGENT = "AG-03 | Shopee Stock"


def sincronizar_estoque_shopee(sku: str, quantidade: int, loja_id: int = None) -> dict:
    """Sincroniza estoque local → Shopee. Resolve o item_id via a tabela anuncios
    (marketplace='shopee'), respeitando a loja/shop_id quando informada (multiloja).
    Produtos com variacao gravam anuncio_id como "item_id_model_id" (ver
    shopee_sync.sync_produtos) — nesse caso o payload precisa do model_id, senao
    a Shopee rejeita o update (item com modelos nao aceita stock no nivel do item)."""
    async def _go():
        db = await get_db()
        cfg = get_shopee_config(loja_id)
        row = await db.fetchrow(
            "SELECT anuncio_id FROM anuncios WHERE sku = $1 AND marketplace = 'shopee' AND shop_id = $2",
            sku, cfg.get("shop_id") or "")
        if not row or not row["anuncio_id"]:
            return {"error": "SKU sem anuncio_id da Shopee para esta loja — execute a sincronizacao primeiro"}
        anuncio_id = row["anuncio_id"]
        if "_" in anuncio_id:
            item_id_str, model_id_str = anuncio_id.split("_", 1)
            item_id = int(item_id_str)
            stock_list = [{"model_id": int(model_id_str), "seller_stock": [{"stock": quantidade}]}]
        else:
            item_id = int(anuncio_id)
            stock_list = [{"seller_stock": [{"stock": quantidade}]}]
        return update_stock(item_id, stock_list, loja_id=loja_id)
    return run_async(_go())


def sincronizar_estoque_todas_lojas(sku: str, quantidade: int) -> dict:
    """Envia o estoque de um SKU para TODAS as lojas Shopee conectadas de uma vez."""
    from core.lojas import listar_lojas_shopee
    lojas = listar_lojas_shopee()
    if not lojas:
        return {"total": 0, "erro": "Nenhuma loja Shopee conectada"}
    resultados = []
    for l in lojas:
        r = sincronizar_estoque_shopee(sku, quantidade, loja_id=l["id"])
        resultados.append({"loja_id": l["id"], "loja_nome": l["nome"], "resultado": r})
    sucesso = sum(1 for x in resultados if not x["resultado"].get("error"))
    return {"total": len(resultados), "sucesso": sucesso, "resultados": resultados}


def sincronizar_estoque_todas_lojas_automatico(sku: str, quantidade: int) -> dict:
    """Dispara sincronizacao de estoque para TODAS as lojas Shopee conectadas.
    Chamado automaticamente pelo sistema quando o estoque local muda."""
    lojas = listar_todas_lojas_shopee()
    if not lojas:
        return {"error": "Nenhuma loja Shopee conectada"}
    resultados = []
    for loja in lojas:
        try:
            r = sincronizar_estoque_shopee(sku, quantidade, loja["id"])
            resultados.append({"loja_id": loja["id"], "loja_nome": loja["nome"], "ok": "error" not in r})
        except Exception as e:
            resultados.append({"loja_id": loja["id"], "loja_nome": loja["nome"], "ok": False, "erro": str(e)})
    return {"sku": sku, "quantidade": quantidade, "lojas": resultados}
