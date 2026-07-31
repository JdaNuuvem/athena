"""
Shopee Discount — desconto por item/variacao com janela de tempo (ate' 180 dias).

Regras de estado confirmadas na doc oficial (via error_list): uma vez "ongoing", so'
da pra ENCURTAR o end_time (nunca prorrogar) e so' da pra editar
nome/end_time/itens — nao da pra voltar pra "upcoming". `end_discount` e' TERMINAL:
depois de encerrado o desconto vira "end" e nao aceita mais update nem delete.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from .auth import _request

AGENT = "AG-03 | Shopee Discount"


def add_discount(discount_name: str, start_time: int, end_time: int, loja_id: int = None) -> dict:
    """Cria o desconto vazio (sem item ainda). start_time >=1h no futuro; janela <180 dias."""
    return _request("discount/add_discount", {
        "discount_name": discount_name, "start_time": start_time, "end_time": end_time,
    }, method="POST", loja_id=loja_id)


def add_discount_item(discount_id: int, item_list: list, loja_id: int = None) -> dict:
    """Adiciona ate' 50 itens por chamada. Cada item: {"item_id", "purchase_limit" (0=sem limite),
    "item_promotion_price" (se sem variacao) OU "model_list": [{"model_id","model_promotion_price",
    "model_promotion_stock"?}] (se com variacao)}."""
    return _request("discount/add_discount_item", {
        "discount_id": discount_id, "item_list": item_list,
    }, method="POST", loja_id=loja_id)


def update_discount(discount_id: int, loja_id: int = None, discount_name: str = None,
                     start_time: int = None, end_time: int = None) -> dict:
    """Ongoing: so' aceita ENCURTAR end_time, nunca prorrogar. Rejeitado se status='end'."""
    params = {"discount_id": discount_id}
    if discount_name is not None: params["discount_name"] = discount_name
    if start_time is not None: params["start_time"] = start_time
    if end_time is not None: params["end_time"] = end_time
    return _request("discount/update_discount", params, method="POST", loja_id=loja_id)


def update_discount_item(discount_id: int, item_list: list, loja_id: int = None) -> dict:
    """Mesma forma do add_discount_item; todos os campos de item exceto item_id ficam opcionais."""
    return _request("discount/update_discount_item", {
        "discount_id": discount_id, "item_list": item_list,
    }, method="POST", loja_id=loja_id)


def delete_discount(discount_id: int, loja_id: int = None) -> dict:
    """So' funciona se ainda nao comecou (upcoming). Irreversivel — sem restore."""
    return _request("discount/delete_discount", {"discount_id": discount_id}, method="POST", loja_id=loja_id)


def delete_discount_item(discount_id: int, item_id: int, loja_id: int = None, model_id: int = 0) -> dict:
    """Remove 1 item por chamada (nao e' batch)."""
    return _request("discount/delete_discount_item", {
        "discount_id": discount_id, "item_id": item_id, "model_id": model_id,
    }, method="POST", loja_id=loja_id)


def end_discount(discount_id: int, loja_id: int = None) -> dict:
    """Encerra AGORA um desconto ongoing. TERMINAL/IRREVERSIVEL — a Shopee nao permite
    update nem delete depois disso (status vira 'end' pra sempre). Exigir confirmacao
    explicita antes de chamar."""
    return _request("discount/end_discount", {"discount_id": discount_id}, method="POST", loja_id=loja_id)


def get_discount(discount_id: int, page_no: int = 1, page_size: int = 50, loja_id: int = None) -> dict:
    """Detalhe do desconto, paginado pelos ITENS dentro dele (nao e' uma lista de descontos)."""
    return _request("discount/get_discount", {
        "discount_id": discount_id, "page_no": page_no, "page_size": page_size,
    }, loja_id=loja_id)


def get_discount_list(discount_status: str = "all", page_no: int = 1, page_size: int = 50, loja_id: int = None) -> dict:
    """discount_status: upcoming | ongoing | expired | all."""
    return _request("discount/get_discount_list", {
        "discount_status": discount_status, "page_no": page_no, "page_size": page_size,
    }, loja_id=loja_id)
