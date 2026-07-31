"""
Shopee Logistics — etiqueta de envio e rastreio.

Fluxo real (confirmado na doc oficial v2, modulo Logistics):
  get_shipping_parameter -> mass_ship_order -> get_tracking_number
  -> (get_shipping_document_parameter) -> create_shipping_document
  -> get_shipping_document_result (poll ate' READY) -> download_shipping_document
  -> get_tracking_info (continuo)

mass_ship_order e' usado no lugar do "ship_order" singular mesmo para 1 pacote —
a doc do ship_order singular nao renderizou os parametros (so' os codigos de erro),
enquanto mass_ship_order esta' 100% documentado e aceita lote de 1 a 50 pacotes.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from .auth import _request, _request_binary

AGENT = "AG-03 | Shopee Logistics"


def get_shipping_parameter(order_sn: str, loja_id: int = None, package_number: str = None) -> dict:
    """Parametros disponiveis (pickup/dropoff/non_integrated) pra despachar este pedido.
    So' chamar quando o pedido estiver em LOGISTICS_READY/LOGISTICS_PICKUP_RETRY."""
    params = {"order_sn": order_sn}
    if package_number:
        params["package_number"] = package_number
    return _request("logistics/get_shipping_parameter", params, loja_id=loja_id)


def mass_ship_order(package_list: list, loja_id: int = None,
                     logistics_channel_id: int = None, product_location_id: str = None) -> dict:
    """Aciona o despacho real (coleta/dropoff/postagem) — IRREVERSIVEL. package_list: lista de
    dicts {"package_number": str, "pickup"|"dropoff"|"non_integrated": {...}} conforme retornado
    por get_shipping_parameter. Todos os pacotes do lote precisam ser do mesmo
    logistics_channel_id + product_location_id."""
    params = {"package_list": package_list}
    if logistics_channel_id is not None:
        params["logistics_channel_id"] = logistics_channel_id
    if product_location_id:
        params["product_location_id"] = product_location_id
    return _request("logistics/mass_ship_order", params, method="POST", loja_id=loja_id)


def get_tracking_number(order_sn: str, loja_id: int = None, package_number: str = None,
                         response_optional_fields: list = None) -> dict:
    """Numero de rastreio apos o despacho. Pode voltar vazio nos primeiros minutos —
    fazer polling a cada 5min ate' vir preenchido."""
    params = {"order_sn": order_sn}
    if package_number:
        params["package_number"] = package_number
    if response_optional_fields:
        params["response_optional_fields"] = ",".join(response_optional_fields)
    return _request("logistics/get_tracking_number", params, loja_id=loja_id)


def get_shipping_document_parameter(order_list: list, loja_id: int = None) -> dict:
    """Descobre o(s) shipping_document_type valido(s) pra cada pedido antes de gerar a etiqueta.
    order_list: lista de dicts {"order_sn": str, "package_number": str (opcional)}."""
    return _request("logistics/get_shipping_document_parameter", {"order_list": order_list}, method="POST", loja_id=loja_id)


def create_shipping_document(order_list: list, loja_id: int = None, shipping_document_type: str = None) -> dict:
    """Enfileira a geracao da etiqueta (tarefa assincrona — precisa fazer poll em
    get_shipping_document_result ate' status=READY antes de baixar)."""
    items = []
    for o in order_list:
        item = dict(o)
        if shipping_document_type and "shipping_document_type" not in item:
            item["shipping_document_type"] = shipping_document_type
        items.append(item)
    return _request("logistics/create_shipping_document", {"order_list": items}, method="POST", loja_id=loja_id)


def get_shipping_document_result(order_list: list, loja_id: int = None) -> dict:
    """Status da tarefa de geracao de etiqueta: READY | FAILED | PROCESSING."""
    return _request("logistics/get_shipping_document_result", {"order_list": order_list}, method="POST", loja_id=loja_id)


def download_shipping_document(order_list: list, loja_id: int = None) -> dict:
    """Baixa o PDF da etiqueta (so' funciona apos status=READY). Retorna
    {"content": bytes, "content_type": str} em sucesso, {"error": ...} caso contrario."""
    return _request_binary("logistics/download_shipping_document", {"order_list": order_list}, loja_id=loja_id)


def get_tracking_info(order_sn: str, loja_id: int = None, package_number: str = None) -> dict:
    """Historico de rastreio (status + eventos) do pedido."""
    params = {"order_sn": order_sn}
    if package_number:
        params["package_number"] = package_number
    return _request("logistics/get_tracking_info", params, loja_id=loja_id)
