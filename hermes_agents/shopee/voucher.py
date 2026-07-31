"""
Shopee Voucher — cupom de loja ou de produto.

Regras de estado confirmadas na doc oficial (via error_list): ongoing so' aceita editar
voucher_name/usage_quantity/end_time/display_channel_list/item_id_list — nunca preco/
percentual/min_basket. usage_quantity so' pode AUMENTAR, end_time so' pode ENCURTAR.
`end_voucher` e' TERMINAL: depois de encerrado vira "expired" pra sempre, sem update/delete.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from .auth import _request

AGENT = "AG-03 | Shopee Voucher"


def add_voucher(voucher_name: str, voucher_code: str, start_time: int, end_time: int,
                 voucher_type: int, reward_type: int, usage_quantity: int, min_basket_price: float,
                 loja_id: int = None, discount_amount: float = None, percentage: int = None,
                 max_price: float = None, display_channel_list: list = None,
                 item_id_list: list = None, display_start_time: int = None) -> dict:
    """voucher_type: 1=cupom de loja, 2=cupom de produto (exige item_id_list).
    reward_type: 1=valor fixo (discount_amount), 2=percentual (percentage, +max_price opcional
    como teto de desconto), 3=coin cashback (percentage). end_time <=3 meses de vigencia."""
    params = {
        "voucher_name": voucher_name, "voucher_code": voucher_code,
        "start_time": start_time, "end_time": end_time,
        "voucher_type": voucher_type, "reward_type": reward_type,
        "usage_quantity": usage_quantity, "min_basket_price": min_basket_price,
    }
    if discount_amount is not None: params["discount_amount"] = discount_amount
    if percentage is not None: params["percentage"] = percentage
    if max_price is not None: params["max_price"] = max_price
    if display_channel_list: params["display_channel_list"] = display_channel_list
    if item_id_list: params["item_id_list"] = item_id_list
    if display_start_time is not None: params["display_start_time"] = display_start_time
    return _request("voucher/add_voucher", params, method="POST", loja_id=loja_id)


def update_voucher(voucher_id: int, loja_id: int = None, voucher_name: str = None,
                    start_time: int = None, end_time: int = None, usage_quantity: int = None,
                    min_basket_price: float = None, discount_amount: float = None,
                    percentage: int = None, max_price: float = None,
                    display_channel_list: list = None, item_id_list: list = None,
                    display_start_time: int = None) -> dict:
    """Se o voucher estiver ongoing, a Shopee rejeita qualquer campo alem de voucher_name/
    usage_quantity(so' aumentar)/end_time(so' encurtar)/display_channel_list/item_id_list."""
    params = {"voucher_id": voucher_id}
    for k, v in {
        "voucher_name": voucher_name, "start_time": start_time, "end_time": end_time,
        "usage_quantity": usage_quantity, "min_basket_price": min_basket_price,
        "discount_amount": discount_amount, "percentage": percentage, "max_price": max_price,
        "display_channel_list": display_channel_list, "item_id_list": item_id_list,
        "display_start_time": display_start_time,
    }.items():
        if v is not None:
            params[k] = v
    return _request("voucher/update_voucher", params, method="POST", loja_id=loja_id)


def get_voucher(voucher_id: int, loja_id: int = None) -> dict:
    return _request("voucher/get_voucher", {"voucher_id": voucher_id}, loja_id=loja_id)


def get_voucher_list(status: str = "all", page_no: int = 1, page_size: int = 20, loja_id: int = None) -> dict:
    """status: upcoming | ongoing | expired | all."""
    return _request("voucher/get_voucher_list", {
        "status": status, "page_no": page_no, "page_size": page_size,
    }, loja_id=loja_id)


def end_voucher(voucher_id: int, loja_id: int = None) -> dict:
    """Encerra AGORA um voucher ongoing. TERMINAL/IRREVERSIVEL — vira 'expired' pra sempre.
    Exigir confirmacao explicita antes de chamar."""
    return _request("voucher/end_voucher", {"voucher_id": voucher_id}, method="POST", loja_id=loja_id)


def delete_voucher(voucher_id: int, loja_id: int = None) -> dict:
    """So' funciona em voucher upcoming (ainda nao comecou). Irreversivel — sem restore."""
    return _request("voucher/delete_voucher", {"voucher_id": voucher_id}, method="POST", loja_id=loja_id)
