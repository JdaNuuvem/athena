"""
Shopee Stores — list connected stores.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core import log, run_async, get_db

AGENT = "AG-03 | Shopee Stores"


def listar_todas_lojas_shopee() -> list:
    """Retorna lista de lojas com token Shopee valido."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT id, nome, shopee_shop_id, shopee_access_token, shopee_shop_name, ativa, COALESCE(shopee_markup_pct, 100) as shopee_markup_pct FROM lojas WHERE shopee_access_token IS NOT NULL AND ativa = TRUE ORDER BY nome")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except: return []
