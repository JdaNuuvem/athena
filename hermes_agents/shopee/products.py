"""
Shopee Products — CRUD operations via API.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from .auth import _request

AGENT = "AG-03 | Shopee Products"


def get_items(status: str = "NORMAL", offset: int = 0, page_size: int = 100, loja_id: int = None) -> dict:
    """Lista itens da Shopee."""
    return _request("product/get_item_list", {
        "item_status": status, "offset": offset, "page_size": page_size,
    }, loja_id=loja_id)


def get_item_base_info(item_ids: list, loja_id: int = None) -> dict:
    """Detalhes de itens específicos. item_id_list e' string de IDs separados por
    virgula (nao array JSON) — a Shopee rejeita '[id1, id2]' com
    'strconv.ParseUint: parsing "[id1": invalid syntax'."""
    return _request("product/get_item_base_info", {
        "item_id_list": ",".join(str(i) for i in item_ids),
    }, loja_id=loja_id)


def get_model_list(item_id: int, loja_id: int = None) -> dict:
    """Modelos/variantes de um item."""
    return _request("product/get_model_list", {"item_id": item_id}, loja_id=loja_id)


def init_tier_variation(item_id: int, tier_variation: list, model_list: list, loja_id: int = None) -> dict:
    """Cria a estrutura de variacao (tiers + modelos) de um item ja publicado
    sem variacao, OU redefine a estrutura de um item que ja tem variacao
    (nesse segundo caso os model_id antigos ficam invalidos — chamar de novo
    so' quando a propria estrutura de tiers muda, nao para add/editar modelo).
    Recomendado esperar ~5s apos add_item antes de chamar isso (delay de
    propagacao documentado pela Shopee)."""
    return _request("product/init_tier_variation", {
        "item_id": item_id, "tier_variation": tier_variation, "model": model_list,
    }, method="POST", loja_id=loja_id)


def add_model(item_id: int, model_list: list, loja_id: int = None) -> dict:
    """Adiciona novo(s) modelo(s) (variacao) a um item que ja tem tier_variation
    definida — usa as mesmas opcoes de tier ja existentes (tier_index)."""
    return _request("product/add_model", {
        "item_id": item_id, "model_list": model_list,
    }, method="POST", loja_id=loja_id)


def update_tier_variation(item_id: int, tier_variation: list, model_list: list, loja_id: int = None) -> dict:
    """Adiciona/remove/reordena as OPCOES de um tier existente (ex: cores),
    preservando os model_id ja criados — model_list mapeia tier_index atual
    para o model_id correspondente. Para mudar a ESTRUTURA (ex: adicionar uma
    dimensao nova tipo tamanho), usar init_tier_variation em vez disso."""
    return _request("product/update_tier_variation", {
        "item_id": item_id, "tier_variation": tier_variation, "model_list": model_list,
    }, method="POST", loja_id=loja_id)


def delete_model(item_id: int, model_id_list: list, loja_id: int = None) -> dict:
    """Remove uma ou mais variacoes (models) de um item."""
    return _request("product/delete_model", {
        "item_id": item_id, "model_id_list": model_id_list,
    }, method="POST", loja_id=loja_id)


def check_stock(item_id: int, loja_id: int = None) -> dict:
    """Verifica estoque disponível de um item."""
    r = get_item_base_info([item_id], loja_id=loja_id)
    items = r.get("response", {}).get("item_list", [])
    if not items:
        return {"available": 0, "reserved": 0}
    s = items[0].get("stock_info_v2", {})
    info = s.get("summary_info", s)
    return {
        "available": info.get("total_available_stock", s.get("seller_stock", [{}])[0].get("stock", 0)),
        "reserved": info.get("total_reserved_stock", 0),
    }


def update_stock(item_id: int, stock_list: list, loja_id: int = None) -> dict:
    """Atualiza estoque de um item."""
    return _request("product/update_stock", {
        "item_id": item_id, "stock_list": stock_list,
    }, method="POST", loja_id=loja_id)


def update_price(item_id: int, price: float, loja_id: int = None) -> dict:
    """Atualiza preço de um item."""
    return _request("product/update_price", {"item_id": item_id, "price": price}, method="POST", loja_id=loja_id)


def add_item(dados: dict, loja_id: int = None) -> dict:
    """Cria um produto novo na Shopee. dados deve conter os campos exigidos pela
    categoria escolhida (ver get_attribute_tree/get_brand_list)."""
    return _request("product/add_item", dados, method="POST", loja_id=loja_id)


def update_item(item_id: int, dados: dict, loja_id: int = None) -> dict:
    """Atualiza um produto existente na Shopee."""
    body = {**dados, "item_id": item_id}
    return _request("product/update_item", body, method="POST", loja_id=loja_id)


def delete_item_shopee(item_id: int, loja_id: int = None) -> dict:
    """Remove definitivamente um produto da Shopee."""
    return _request("product/delete_item", {"item_id": item_id}, method="POST", loja_id=loja_id)


def unlist_item(item_ids: list, unlist: bool = True, loja_id: int = None) -> dict:
    """Tira (unlist=True) ou reativa (unlist=False) produtos do ar, sem apagar."""
    return _request("product/unlist_item", {
        "item_list": [{"item_id": i, "unlist": unlist} for i in item_ids],
    }, method="POST", loja_id=loja_id)


def listar_produtos_shopee(offset: int = 0, page_size: int = 100, loja_id: int = None) -> dict:
    return get_items("NORMAL", offset, page_size, loja_id=loja_id)


def sync_all_items(loja_id: int = None) -> list:
    """Sincroniza todos os itens da Shopee (paginado, até 5000)."""
    all_items = []
    offset = 0
    for _ in range(50):
        r = get_items("NORMAL", offset, loja_id=loja_id)
        resp = r.get("response", {})
        items = resp.get("item", [])
        if not items:
            break
        ids = [i["item_id"] for i in items]
        details = get_item_base_info(ids, loja_id=loja_id)
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
