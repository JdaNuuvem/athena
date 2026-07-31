"""
Shopee Account Health — saude da loja (somente leitura).
Endpoints v2.account_health.* — todos GET, sem nenhuma chamada de escrita.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from .auth import _request

AGENT = "AG-03 | Shopee Account Health"


def get_shop_performance(loja_id: int = None) -> dict:
    """Rating geral (1=Poor..4=Excellent) e metric_list (fulfillment/listing/customer_service)."""
    return _request("account_health/get_shop_performance", {}, loja_id=loja_id)


def get_metric_source_detail(metric_id: int, page_no: int = 1, page_size: int = 20, loja_id: int = None) -> dict:
    """Detalhe (drill-down por pedido/listing) de 1 metrica especifica do get_shop_performance."""
    return _request("account_health/get_metric_source_detail", {
        "metric_id": metric_id, "page_no": page_no, "page_size": page_size,
    }, loja_id=loja_id)


def get_penalty_point_history(page_no: int = 1, page_size: int = 10, violation_type: int = None, loja_id: int = None) -> dict:
    """Historico de pontos de penalidade do trimestre corrente."""
    params = {"page_no": page_no, "page_size": page_size}
    if violation_type is not None:
        params["violation_type"] = violation_type
    return _request("account_health/get_penalty_point_history", params, loja_id=loja_id)


def get_punishment_history(punishment_status: int, page_no: int = 1, page_size: int = 10, loja_id: int = None) -> dict:
    """Punicoes ativas (1) ou encerradas (2)."""
    return _request("account_health/get_punishment_history", {
        "punishment_status": punishment_status, "page_no": page_no, "page_size": page_size,
    }, loja_id=loja_id)


def get_listings_with_issues(page_no: int = 1, page_size: int = 20, loja_id: int = None) -> dict:
    """Anuncios com problema (proibido, contrafacao, spam, imagem inadequada, etc)."""
    return _request("account_health/get_listings_with_issues", {
        "page_no": page_no, "page_size": page_size,
    }, loja_id=loja_id)


def get_late_orders(page_no: int = 1, page_size: int = 20, loja_id: int = None) -> dict:
    """Pedidos atrasados para envio."""
    return _request("account_health/get_late_orders", {
        "page_no": page_no, "page_size": page_size,
    }, loja_id=loja_id)
