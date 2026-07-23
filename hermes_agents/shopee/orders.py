"""
Shopee Orders — order retrieval, webhook processing, logistics.
"""
import sys, os, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from datetime import date, timedelta

from core import log
from .auth import _request, AGENT

AGENT_ORD = "AG-03 | Shopee Orders"


def get_orders(status: str = "READY_TO_SHIP", limit: int = 50, loja_id: int = None) -> dict:
    """Obtém pedidos da Shopee por status."""
    return _request("order/get_order_list", {
        "order_status": status, "page_size": limit,
    }, method="POST", loja_id=loja_id)


def get_order_detail(order_sn: str, loja_id: int = None) -> dict:
    """Detalhes de um pedido específico."""
    return _request("order/get_order_detail", {"order_sn_list": [order_sn]}, method="POST", loja_id=loja_id)


def get_orders_by_time_range(start_time: int, end_time: int, statuses: list = None, limit: int = 50, loja_id: int = None) -> dict:
    """Obtém pedidos por período."""
    if statuses is None:
        statuses = ["READY_TO_SHIP", "PROCESSED"]
    return _request("order/get_order_list", {
        "create_time_from": start_time, "create_time_to": end_time,
        "order_status": ",".join(statuses), "page_size": limit,
    }, method="POST", loja_id=loja_id)


def get_logistics_channel_list(loja_id: int = None) -> dict:
    """Canais de logistica habilitados na loja — add_item exige pelo menos 1 no logistic_info."""
    return _request("logistics/get_channel_list", {}, loja_id=loja_id)


def obter_pedidos_shopee(dias: int = 7, loja_id: int = None) -> dict:
    now = int(time.time())
    return get_orders_by_time_range(now - dias * 86400, now, loja_id=loja_id)


def listar_pedidos_shopee_detalhado(dias: int = 7, loja_id: int = None, status: str = None, max_pedidos: int = 100) -> dict:
    """Lista pedidos com detalhe (cliente, itens, valor) — get_order_list so' traz order_sn/
    status/create_time, entao busca o detalhe de cada pedido (bounded a max_pedidos para
    evitar chamadas ilimitadas)."""
    statuses = [status] if status else None
    r = obter_pedidos_shopee(dias, loja_id=loja_id) if not statuses else get_orders_by_time_range(
        int(time.time()) - dias * 86400, int(time.time()), statuses, loja_id=loja_id)
    if r.get("error"):
        return r
    resumo = (r.get("response", {}) or {}).get("order_list", [])[:max_pedidos]
    if not resumo:
        return {"pedidos": []}
    pedidos = []
    for i in range(0, len(resumo), 50):
        lote = resumo[i:i + 50]
        order_sns = [o.get("order_sn") for o in lote if o.get("order_sn")]
        if not order_sns:
            continue
        d = _request("order/get_order_detail", {"order_sn_list": order_sns}, method="POST", loja_id=loja_id)
        detalhes = {o["order_sn"]: o for o in (d.get("response", {}) or {}).get("order_list", [])}
        for o in lote:
            det = detalhes.get(o.get("order_sn"), o)
            pedidos.append({
                "order_sn": det.get("order_sn", o.get("order_sn", "")),
                "status": det.get("order_status", o.get("order_status", "")),
                "create_time": det.get("create_time", o.get("create_time", 0)),
                "update_time": det.get("update_time", o.get("update_time", 0)),
                "total_amount": det.get("total_amount", 0),
                "buyer_username": det.get("buyer_username", ""),
                "recipient_nome": (det.get("recipient_address", {}) or {}).get("name", ""),
                "itens": [{
                    "sku": item.get("item_sku", ""),
                    "nome": item.get("item_name", ""),
                    "quantidade": item.get("model_quantity_purchased", 0),
                    "preco": item.get("model_discounted_price", item.get("model_original_price", 0)),
                } for item in det.get("item_list", [])],
            })
    return {"pedidos": pedidos}


def webhook_shopee_pedido(pedido_shopee: dict) -> dict:
    """Processa webhook de pedido da Shopee."""
    order_sn = pedido_shopee.get("order_sn", "")
    items = pedido_shopee.get("item_list", [])
    if not items:
        return {"error": "Pedido sem itens"}
    from ag_04_planejador import adicionar_pedido_producao
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
