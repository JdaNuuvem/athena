"""
Shopee Integration — Marketplace API v2
Adaptado do ATHENA OS shopee-adapter.ts com HMAC-SHA256 correto.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from .auth import (
    get_shopee_config, _is_sandbox, _base_url, configurado, _sign, _request,
    get_auth_url, exchange_shopee_code, refresh_shopee_token,
    BASE_URL_LIVE, BASE_URL_BRAZIL, BASE_URL_SANDBOX, SHOPEE_SANDBOX, SHOPEE_REGION, AGENT,
)
from .pricing import calcular_margem_produto
from .products import (
    get_items, get_item_base_info, get_model_list, check_stock,
    update_price, update_stock, add_item, update_item, delete_item_shopee,
    unlist_item, listar_produtos_shopee, sync_all_items,
)
from .images import upload_image
from .categories import (
    get_category, get_attribute_tree, get_brand_list, _ensure_categorias_table,
    sincronizar_categorias, listar_categorias_cache,
)
from .orders import (
    get_orders, get_order_detail, get_orders_by_time_range,
    obter_pedidos_shopee, listar_pedidos_shopee_detalhado,
    webhook_shopee_pedido, get_logistics_channel_list,
)
from .replication import transferir_produtos_para_loja
from .stock import (
    sincronizar_estoque_shopee, sincronizar_estoque_todas_lojas,
    sincronizar_estoque_todas_lojas_automatico,
)
from .stores import listar_todas_lojas_shopee
from .kits import sugerir_kits
from .concorrencia import analisar_concorrencia

MENSAGENS_SHOPEE = {
    "produtos": "📦 Produtos sincronizados com Shopee.",
    "estoque": "📊 Estoque sincronizado com Shopee em tempo real.",
    "pedidos": "🛒 Pedidos da Shopee integrados ao planejamento de produção.",
}

if __name__ == "__main__":
    from core import log
    log(AGENT, "Auto-teste")
    log(AGENT, f"Configurado: {configurado()}")
    log(AGENT, f"Base URL: {_base_url()}")
