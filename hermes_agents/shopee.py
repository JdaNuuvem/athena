"""
Integração Shopee - API Marketplace v2
Adaptado do ATHENA OS shopee-adapter.ts com HMAC-SHA256 correto.
"""
import sys, os, json, time, hmac, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from core import log, run_async, get_db, hoje
from core.config import get_config, set_config

AGENT = "AG-03 | Shopee Integration"

BASE_URL_LIVE = "https://partner.shopeemobile.com/api/v2"
BASE_URL_BRAZIL = "https://openplatform.shopee.com.br/api/v2"
BASE_URL_SANDBOX = "https://openplatform.sandbox.test-stable.shopee.sg/api/v2"
SHOPEE_SANDBOX = os.environ.get("SHOPEE_SANDBOX", "false").lower() == "true"
SHOPEE_REGION = os.environ.get("SHOPEE_REGION", "br")

def get_shopee_config() -> dict:
    return {
        "partner_id": os.environ.get("SHOPEE_PARTNER_ID") or get_config("shopee", "partner_id") or "",
        "shop_id": os.environ.get("SHOPEE_SHOP_ID") or get_config("shopee", "shop_id") or "",
        "api_key": os.environ.get("SHOPEE_PARTNER_KEY") or get_config("shopee", "api_key") or "",
        "access_token": os.environ.get("SHOPEE_ACCESS_TOKEN") or get_config("shopee", "access_token") or "",
    }
    # ponytail: access_token is the OAuth token from Shopee, separate from partner key

def _base_url() -> str:
    if SHOPEE_SANDBOX:
        return BASE_URL_SANDBOX
    return BASE_URL_BRAZIL if SHOPEE_REGION == "br" else BASE_URL_LIVE

def configurado() -> bool:
    c = get_shopee_config()
    return bool(c["partner_id"] and c["shop_id"] and c["api_key"] and c["access_token"])

def _sign(path: str) -> dict:
    """HMAC-SHA256 sign per Shopee spec: partner_id + path + timestamp + access_token + shop_id + partner_key"""
    c = get_shopee_config()
    timestamp = int(time.time())
    sign_str = f"{c['partner_id']}{path}{timestamp}{c['access_token']}{c['shop_id']}{c['api_key']}"
    signature = hmac.new(c["api_key"].encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    return {
        "partner_id": c["partner_id"], "timestamp": timestamp,
        "access_token": c["access_token"], "shop_id": c["shop_id"], "sign": signature,
    }

def _request(endpoint: str, params: dict = None, method: str = "GET") -> dict:
    """Request autenticado à API Shopee."""
    if not configurado():
        return {"error": "Shopee não configurado"}
    path = f"/api/v2/{endpoint}"
    sig = _sign(path)
    url = f"{_base_url()}/{endpoint}"
    default_params = {
        "partner_id": sig["partner_id"], "timestamp": sig["timestamp"],
        "access_token": sig["access_token"], "shop_id": sig["shop_id"], "sign": sig["sign"],
    }
    try:
        if method == "GET":
            p = {**default_params, **(params or {})}
            r = requests.get(url, params=p, timeout=30)
        else:
            body = {**default_params, **(params or {})}
            r = requests.post(url, json=body, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(AGENT, f"Erro {method} {endpoint}: {e}")
        return {"error": str(e)}

def get_items(status: str = "NORMAL", offset: int = 0, page_size: int = 100) -> dict:
    """Lista itens da Shopee."""
    return _request("product/get_item_list", {
        "item_status": json.dumps([status]), "offset": offset, "page_size": page_size,
    })

def get_item_base_info(item_ids: list) -> dict:
    """Detalhes de itens específicos."""
    return _request("product/get_item_base_info", {
        "item_id_list": json.dumps(item_ids),
    })

def get_model_list(item_id: int) -> dict:
    """Modelos/variantes de um item."""
    return _request("product/get_model_list", {"item_id": item_id})

def check_stock(item_id: int) -> dict:
    """Verifica estoque disponível de um item."""
    r = get_item_base_info([item_id])
    items = r.get("response", {}).get("item_list", [])
    if not items:
        return {"available": 0, "reserved": 0}
    s = items[0].get("stock_info_v2", {})
    info = s.get("summary_info", s)
    return {
        "available": info.get("total_available_stock", s.get("seller_stock", [{}])[0].get("stock", 0)),
        "reserved": info.get("total_reserved_stock", 0),
    }

def update_stock(item_id: int, stock_list: list) -> dict:
    """Atualiza estoque de um item."""
    return _request("product/update_stock", {
        "item_id": item_id, "stock_list": stock_list,
    }, method="POST")

def update_price(item_id: int, price: float) -> dict:
    """Atualiza preço de um item."""
    return _request("product/update_price", {"item_id": item_id, "price": price}, method="POST")

def get_orders(status: str = "READY_TO_SHIP", limit: int = 50) -> dict:
    """Obtém pedidos da Shopee por status."""
    return _request("order/get_order_list", {
        "order_status": status, "page_size": limit,
    }, method="POST")

def get_order_detail(order_sn: str) -> dict:
    """Detalhes de um pedido específico."""
    return _request("order/get_order_detail", {"order_sn_list": [order_sn]}, method="POST")

def get_orders_by_time_range(start_time: int, end_time: int, statuses: list = None, limit: int = 50) -> dict:
    """Obtém pedidos por período."""
    if statuses is None:
        statuses = ["READY_TO_SHIP", "PROCESSED"]
    return _request("order/get_order_list", {
        "create_time_from": start_time, "create_time_to": end_time,
        "order_status": ",".join(statuses), "page_size": limit,
    }, method="POST")

def sync_all_items() -> list:
    """Sincroniza todos os itens da Shopee (paginado, até 5000)."""
    all_items = []
    offset = 0
    for _ in range(50):
        r = get_items("NORMAL", offset)
        resp = r.get("response", {})
        items = resp.get("item", [])
        if not items:
            break
        ids = [i["item_id"] for i in items]
        details = get_item_base_info(ids)
        for d in details.get("response", {}).get("item_list", []):
            s = d.get("stock_info_v2", {}).get("summary_info", {})
            price_info = d.get("price_info", [{}])
            all_items.append({
                "item_id": d["item_id"], "sku": d.get("item_sku", str(d["item_id"])),
                "name": d["item_name"], "status": d["item_status"],
                "stock": s.get("total_available_stock", 0),
                "reserved": s.get("total_reserved_stock", 0),
                "price": price_info[0].get("current_price", 0),
            })
        offset = resp.get("next_offset", 0)
        if not resp.get("has_next_page"):
            break
    return all_items

def sincronizar_estoque_shopee(sku: str, quantidade: int) -> dict:
    """Sincroniza estoque local → Shopee."""
    async def _go():
        db = await get_db()
        produto = await db.fetchrow("SELECT * FROM produtos WHERE sku = $1", sku)
        if not produto:
            return {"error": "Produto não encontrado"}
        items = await db.fetch("SELECT shopee_item_id FROM produtos WHERE sku = $1 AND shopee_item_id IS NOT NULL", sku)
        if not items:
            return {"error": "Produto sem shopee_item_id — execute sync primeiro"}
        item_id = items[0]["shopee_item_id"]
        return update_stock(item_id, [{"seller_stock": [{"stock": quantidade}]}])
    return run_async(_go())

def listar_produtos_shopee(offset: int = 0, page_size: int = 100) -> dict:
    return get_items("NORMAL", offset, page_size)

def obter_pedidos_shopee(dias: int = 7) -> dict:
    now = int(time.time())
    return get_orders_by_time_range(now - dias * 86400, now)

def webhook_shopee_pedido(pedido_shopee: dict) -> dict:
    """Processa webhook de pedido da Shopee."""
    order_sn = pedido_shopee.get("order_sn", "")
    items = pedido_shopee.get("item_list", [])
    if not items:
        return {"error": "Pedido sem itens"}
    from ag_04_planejador import adicionar_pedido_producao
    from datetime import date, timedelta
    resultados = []
    for item in items:
        sku = item.get("item_sku", "")
        quantidade = item.get("model_quantity_purchased", 0)
        if sku and quantidade:
            adicionar_pedido_producao(sku=sku, quantidade=quantidade,
                prazo=date.today() + timedelta(days=5), prioridade=7, cliente_id=f"Shopee-{order_sn}")
            resultados.append({"sku": sku, "quantidade": quantidade})
    log(AGENT, f"Pedido {order_sn} sincronizado: {len(resultados)} itens")
    return {"success": True, "itens": resultados}

MENSAGENS_SHOPEE = {
    "produtos": "📦 Produtos sincronizados com Shopee.",
    "estoque": "📊 Estoque sincronizado com Shopee em tempo real.",
    "pedidos": "🛒 Pedidos da Shopee integrados ao planejamento de produção.",
}

if __name__ == "__main__":
    log(AGENT, "Auto-teste")
    log(AGENT, f"Configurado: {configurado()}")
    log(AGENT, f"Base URL: {_base_url()}")
