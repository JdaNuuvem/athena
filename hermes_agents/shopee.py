"""
Integração Shopee - API Marketplace v2
Adaptado do ATHENA OS shopee-adapter.ts com HMAC-SHA256 correto.
"""
import sys, os, json, time, hmac, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from core import log, run_async, get_db, hoje
from core.__init__ import FactoryConfig
from core.config import get_config, set_config

AGENT = "AG-03 | Shopee Integration"

BASE_URL_LIVE = "https://partner.shopeemobile.com/api/v2"
BASE_URL_BRAZIL = "https://openplatform.shopee.com.br/api/v2"
BASE_URL_SANDBOX = "https://openplatform.sandbox.test-stable.shopee.sg/api/v2"
SHOPEE_SANDBOX = os.environ.get("SHOPEE_SANDBOX", "false").lower() == "true" or get_config("shopee", "sandbox") == "true"
SHOPEE_REGION = os.environ.get("SHOPEE_REGION", "br") or get_config("shopee", "region", "br")

def get_shopee_config(loja_id: int = None) -> dict:
    """Config de uma loja Shopee especifica (multiloja) ou, se loja_id for None,
    a config global legada (unica loja, mantida por compatibilidade)."""
    partner_id = os.environ.get("SHOPEE_PARTNER_ID") or get_config("shopee", "partner_id") or ""
    api_key = os.environ.get("SHOPEE_PARTNER_KEY") or get_config("shopee", "api_key") or ""
    if loja_id is not None:
        from core.lojas import obter_credenciais_shopee
        cred = obter_credenciais_shopee(loja_id)
        return {
            "partner_id": partner_id,
            "shop_id": cred.get("shopee_shop_id") or "",
            "api_key": api_key,
            "access_token": cred.get("shopee_access_token") or "",
        }
    return {
        "partner_id": partner_id,
        "shop_id": os.environ.get("SHOPEE_SHOP_ID") or get_config("shopee", "shop_id") or "",
        "api_key": api_key,
        "access_token": os.environ.get("SHOPEE_ACCESS_TOKEN") or get_config("shopee", "access_token") or "",
    }
    # ponytail: access_token is the OAuth token from Shopee, separate from partner key

def _is_sandbox() -> bool:
    try:
        return os.environ.get("SHOPEE_SANDBOX","false").lower()=="true" or str(get_config("shopee","sandbox") or "").lower()=="true"
    except:
        return os.environ.get("SHOPEE_SANDBOX","false").lower()=="true"

def _base_url() -> str:
    """ponytail: a doc oficial (Authorization and Authentication.md, secoes GetAccessToken/
    RefreshAccessToken) so documenta partner.shopeemobile.com para chamadas de API em producao,
    para qualquer regiao — openplatform.shopee.com.br so aparece pra tela de login (browser),
    nao para as chamadas assinadas de API. BASE_URL_BRAZIL fica so como fallback documentado."""
    if _is_sandbox():
        return BASE_URL_SANDBOX
    return BASE_URL_LIVE

def configurado(loja_id: int = None) -> bool:
    c = get_shopee_config(loja_id)
    return bool(c["partner_id"] and c["shop_id"] and c["api_key"] and c["access_token"])

def calcular_margem_produto(sku: str, preco: float, loja_id: int = None) -> dict:
    """Calcula margem real de um produto na Shopee: preco - comissao - custo.
    Retorna { margem_valor, margem_pct, custo, comissao_pct, comissao_valor, ok, mensagem }"""
    # buscar custo do catalogo
    async def _go():
        db = await get_db()
        custo_row = await db.fetchrow("SELECT preco_custo FROM catalogo_produtos WHERE sku = $1 LIMIT 1", sku)
        custo = float(custo_row["preco_custo"] or 0) if custo_row else 0
        return custo
    try: custo = run_async(_go())
    except: custo = 0

    # comissao Shopee (configuravel por loja ou global, default 12%)
    comissao_pct = float(os.environ.get("SHOPEE_COMISSAO_PCT") or get_config("shopee", "comissao_pct") or 12)
    comissao_valor = round(preco * comissao_pct / 100, 2)
    margem_valor = round(preco - comissao_valor - custo, 2)
    margem_pct = round((margem_valor / preco * 100) if preco > 0 else 0, 1)

    if custo <= 0:
        return {"margem_valor": margem_valor, "margem_pct": margem_pct, "custo": custo,
                "comissao_pct": comissao_pct, "comissao_valor": comissao_valor,
                "ok": True, "mensagem": "Custo nao cadastrado — margem nao verificada"}

    if margem_valor < 0:
        return {"margem_valor": margem_valor, "margem_pct": margem_pct, "custo": custo,
                "comissao_pct": comissao_pct, "comissao_valor": comissao_valor,
                "ok": False, "mensagem": f"PREJUIZO: margem de R$ {margem_valor:.2f} ({margem_pct}%). "
                f"Custo R$ {custo:.2f} + comissao {comissao_pct}% (R$ {comissao_valor:.2f}) > preco R$ {preco:.2f}"}

    cfg = FactoryConfig.load()
    if margem_pct < cfg.margem_minima_pct:
        return {"margem_valor": margem_valor, "margem_pct": margem_pct, "custo": custo,
                "comissao_pct": comissao_pct, "comissao_valor": comissao_valor,
                "ok": True, "alerta": True,
                "mensagem": f"Margem baixa: {margem_pct}% (minimo configurado: {cfg.margem_minima_pct}%). "
                f"Preco R$ {preco:.2f} - comissao R$ {comissao_valor:.2f} - custo R$ {custo:.2f} = R$ {margem_valor:.2f}"}

    return {"margem_valor": margem_valor, "margem_pct": margem_pct, "custo": custo,
            "comissao_pct": comissao_pct, "comissao_valor": comissao_valor,
            "ok": True, "mensagem": f"Margem: {margem_pct}% (R$ {margem_valor:.2f})"}

def _sign(path: str, loja_id: int = None) -> dict:
    """HMAC-SHA256 sign per Shopee spec: HMAC(partner_id + path + timestamp + access_token + shop_id, key=partner_key).
    ponytail: o partner_key e' so' a CHAVE do HMAC — nao entra na mensagem. Validado ao vivo contra o
    sandbox real (erro "Wrong sign" ate' remover o partner_key duplicado do fim da string)."""
    c = get_shopee_config(loja_id)
    timestamp = int(time.time())
    sign_str = f"{c['partner_id']}{path}{timestamp}{c['access_token']}{c['shop_id']}"
    signature = hmac.new(c["api_key"].encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    return {
        "partner_id": c["partner_id"], "timestamp": timestamp,
        "access_token": c["access_token"], "shop_id": c["shop_id"], "sign": signature,
    }

def _request(endpoint: str, params: dict = None, method: str = "GET", loja_id: int = None) -> dict:
    """Request autenticado à API Shopee. loja_id identifica QUAL loja Shopee (multiloja);
    quando omitido, usa a config global legada (unica loja)."""
    if not configurado(loja_id):
        return {"error": "Shopee não configurado"}
    path = f"/api/v2/{endpoint}"
    sig = _sign(path, loja_id)
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

def get_items(status: str = "NORMAL", offset: int = 0, page_size: int = 100, loja_id: int = None) -> dict:
    """Lista itens da Shopee."""
    return _request("product/get_item_list", {
        "item_status": json.dumps([status]), "offset": offset, "page_size": page_size,
    }, loja_id=loja_id)

def get_item_base_info(item_ids: list, loja_id: int = None) -> dict:
    """Detalhes de itens específicos."""
    return _request("product/get_item_base_info", {
        "item_id_list": json.dumps(item_ids),
    }, loja_id=loja_id)

def get_model_list(item_id: int, loja_id: int = None) -> dict:
    """Modelos/variantes de um item."""
    return _request("product/get_model_list", {"item_id": item_id}, loja_id=loja_id)

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


# ── Cadastro de produtos: categorias, atributos, marcas, imagens ──
# Necessarios para criar/editar produtos direto na Shopee (product/add_item exige
# category_id valido + atributos obrigatorios da categoria + pelo menos 1 imagem).

def get_category(loja_id: int = None) -> dict:
    """Arvore completa de categorias da Shopee (raramente muda — cacheada em shopee_categorias)."""
    return _request("product/get_category", {}, loja_id=loja_id)

def get_attribute_tree(category_id: int, loja_id: int = None) -> dict:
    """Atributos (obrigatorios e opcionais) de uma categoria especifica.
    ponytail: category_id_list e' uma string simples/CSV (ex: "400358"), NAO um array
    JSON — validado ao vivo contra o sandbox (Shopee tentava fazer parse como uint e falhava com "[400358]")."""
    return _request("product/get_attribute_tree", {
        "category_id_list": str(category_id),
    }, loja_id=loja_id)

def get_brand_list(category_id: int, offset: int = 0, page_size: int = 50, loja_id: int = None) -> dict:
    """Marcas cadastradas na Shopee para uma categoria (algumas categorias exigem marca)."""
    return _request("product/get_brand_list", {
        "category_id": category_id, "offset": offset, "page_size": page_size, "status": 1,
    }, loja_id=loja_id)

def upload_image(image_bytes: bytes, filename: str, loja_id: int = None) -> dict:
    """Envia uma imagem para a Shopee (media_space/upload_image). Retorna image_id,
    que e' usado em add_item/update_item — a Shopee nao aceita URL externa direto."""
    if not configurado(loja_id):
        return {"error": "Shopee não configurado"}
    path = "/api/v2/media_space/upload_image"
    sig = _sign(path, loja_id)
    url = f"{_base_url()}/media_space/upload_image"
    params = {
        "partner_id": sig["partner_id"], "timestamp": sig["timestamp"],
        "access_token": sig["access_token"], "shop_id": sig["shop_id"], "sign": sig["sign"],
    }
    try:
        r = requests.post(url, params=params, files={"image": (filename, image_bytes)}, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(AGENT, f"Erro upload_image: {e}")
        return {"error": str(e)}

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

def get_logistics_channel_list(loja_id: int = None) -> dict:
    """Canais de logistica habilitados na loja — add_item exige pelo menos 1 no logistic_info."""
    return _request("logistics/get_channel_list", {}, loja_id=loja_id)


# ── Categorias: cache local (a arvore tem centenas de nos, evita bater na API toda hora) ──

_categorias_table_ok = False

def _ensure_categorias_table():
    global _categorias_table_ok
    if _categorias_table_ok:
        return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shopee_categorias (
                category_id BIGINT PRIMARY KEY,
                parent_category_id BIGINT DEFAULT 0,
                nome VARCHAR(200) NOT NULL,
                tem_filhos BOOLEAN DEFAULT FALSE,
                atualizado_em TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_shopee_categorias_parent ON shopee_categorias (parent_category_id)")
        try:
            await db.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_shopee_categorias_nome_trgm ON shopee_categorias USING gin (nome gin_trgm_ops)")
        except Exception as e:
            log(AGENT, f"pg_trgm indisponivel para shopee_categorias: {e}")
    try:
        run_async(_go())
        _categorias_table_ok = True
    except Exception as e:
        log(AGENT, f"Erro tabela shopee_categorias: {e}")

def sincronizar_categorias(loja_id: int = None) -> dict:
    """Busca a arvore de categorias na Shopee e grava em cache local."""
    _ensure_categorias_table()
    r = get_category(loja_id)
    categorias = r.get("response", {}).get("category_list", [])
    if not categorias and r.get("error"):
        return {"total": 0, "erro": r["error"]}
    async def _go():
        db = await get_db()
        for c in categorias:
            await db.execute("""
                INSERT INTO shopee_categorias (category_id, parent_category_id, nome, tem_filhos, atualizado_em)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (category_id) DO UPDATE SET
                    parent_category_id = $2, nome = $3, tem_filhos = $4, atualizado_em = NOW()
            """, c.get("category_id"), c.get("parent_category_id", 0),
                c.get("display_category_name", c.get("original_category_name", "")),
                bool(c.get("has_children", False)))
        return len(categorias)
    try:
        total = run_async(_go())
        return {"total": total}
    except Exception as e:
        return {"total": 0, "erro": str(e)}

def listar_categorias_cache(busca: str = "", parent_id: int = None, apenas_folhas: bool = False) -> list:
    """Le a arvore de categorias do cache local. Sincroniza automaticamente na 1a vez."""
    _ensure_categorias_table()
    async def _go():
        db = await get_db()
        count = await db.fetchval("SELECT COUNT(*) FROM shopee_categorias")
        if count == 0:
            return None  # sinaliza que precisa sincronizar
        where = ["1=1"]
        params = []
        if busca:
            params.append(f"%{busca}%")
            where.append(f"nome ILIKE ${len(params)}")
        if parent_id is not None:
            params.append(parent_id)
            where.append(f"parent_category_id = ${len(params)}")
        if apenas_folhas:
            where.append("tem_filhos = FALSE")
        sql = f"SELECT category_id, parent_category_id, nome, tem_filhos FROM shopee_categorias WHERE {' AND '.join(where)} ORDER BY nome LIMIT 500"
        rows = await db.fetch(sql, *params)
        return [dict(r) for r in rows]
    try:
        resultado = run_async(_go())
        if resultado is None:
            sincronizar_categorias()
            return run_async(_go()) or []
        return resultado
    except Exception as e:
        log(AGENT, f"Erro listar_categorias_cache: {e}")
        return []


# ── Estoque multiloja em lote ──

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

def sincronizar_estoque_shopee(sku: str, quantidade: int, loja_id: int = None) -> dict:
    """Sincroniza estoque local → Shopee. Resolve o item_id via a tabela anuncios
    (marketplace='shopee'), respeitando a loja/shop_id quando informada (multiloja)."""
    async def _go():
        db = await get_db()
        cfg = get_shopee_config(loja_id)
        row = await db.fetchrow(
            "SELECT anuncio_id FROM anuncios WHERE sku = $1 AND marketplace = 'shopee' AND shop_id = $2",
            sku, cfg.get("shop_id") or "")
        if not row or not row["anuncio_id"]:
            return {"error": "SKU sem anuncio_id da Shopee para esta loja — execute a sincronizacao primeiro"}
        item_id = int(row["anuncio_id"])
        return update_stock(item_id, [{"seller_stock": [{"stock": quantidade}]}], loja_id=loja_id)
    return run_async(_go())

def listar_produtos_shopee(offset: int = 0, page_size: int = 100, loja_id: int = None) -> dict:
    return get_items("NORMAL", offset, page_size, loja_id=loja_id)

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


# ── OAuth2 Authorization Flow ──

def get_auth_url(redirect_uri: str = "", sandbox: bool = None, loja_id: int = None) -> str:
    """Gera URL de autorizacao Shopee. Usuario clica para autorizar o app.
    loja_id (opcional): quando informado, e' propagado no redirect_uri para que o callback
    saiba a qual loja vincular esta autorizacao (suporte a multiplas contas Shopee)."""
    cfg = get_shopee_config()
    if not cfg["partner_id"]:
        return ""
    if sandbox is None:
        sandbox = _is_sandbox()
    # ponytail: a doc oficial so documenta partner.shopeemobile.com pro endpoint assinado
    # /api/v2/shop/auth_partner (BR so tem host proprio pra tela de login open.shopee.com.br/auth)
    base = (BASE_URL_SANDBOX if sandbox else BASE_URL_LIVE).replace("/api/v2", "") + "/api/v2/shop/auth_partner"
    if not redirect_uri:
        # ponytail: /api/shopee/callback fica sem explicacao caindo no fallback do frontend em
        # producao (nao e' cache); /oauth2callback e' um alias novo que contorna isso.
        domain = os.environ.get("SHOPEE_REDIRECT_URL", "https://athena.zoikom.site/api/shopee/oauth2callback")
        redirect_uri = domain
    if loja_id is not None:
        sep = "&" if "?" in redirect_uri else "?"
        redirect_uri = f"{redirect_uri}{sep}loja_id={loja_id}"
    params = {
        "partner_id": int(cfg["partner_id"]),
        "redirect": redirect_uri,
        "timestamp": int(time.time()),
    }
    sign_str = f"{cfg['partner_id']}{'/api/v2/shop/auth_partner'}{params['timestamp']}"
    signature = hmac.new(cfg["api_key"].encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    params["sign"] = signature
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base}?{qs}"

def exchange_shopee_code(code: str, shop_id: str = "", loja_id: int = None) -> dict:
    """Troca o codigo de autorizacao por access_token e refresh_token.
    Vincula o resultado a uma loja (multiloja): usa loja_id quando informado,
    reaproveita a loja existente com o mesmo shop_id, ou cria uma nova loja."""
    cfg = get_shopee_config()
    if not cfg["partner_id"] or not code:
        return {"error": "partner_id ou code ausente"}
    base = _base_url().replace("/api/v2", "") + "/api/v2/auth/token/get"
    timestamp = int(time.time())
    body = {"code": code, "partner_id": int(cfg["partner_id"])}
    if shop_id:
        body["shop_id"] = int(shop_id)
    sign_str = f"{cfg['partner_id']}{'/api/v2/auth/token/get'}{timestamp}"
    signature = hmac.new(cfg["api_key"].encode(), sign_str.encode(), hashlib.sha256).hexdigest()

    try:
        r = requests.post(base, json=body, params={
            "partner_id": cfg["partner_id"], "timestamp": timestamp, "sign": signature,
        }, timeout=30)
        data = r.json()
        if not data.get("access_token"):
            return {"error": data.get("message", data.get("error", "unknown"))}

        access_token = data["access_token"]
        refresh_token = data.get("refresh_token", "")
        resolved_shop_id = str(body.get("shop_id") or data.get("shop_id") or "")
        expire_in = data.get("expire_in", 0)
        from datetime import datetime, timedelta
        expira_em = datetime.now() + timedelta(seconds=expire_in) if expire_in else None

        # Legado: mantem a config global funcionando (compatibilidade com a loja unica ja configurada)
        set_config("shopee", "access_token", access_token)
        set_config("shopee", "refresh_token", refresh_token)
        if resolved_shop_id:
            set_config("shopee", "shop_id", resolved_shop_id)

        # Multiloja: vincula (ou cria) a loja correspondente na tabela lojas
        loja_resultado = None
        if resolved_shop_id:
            from core.lojas import vincular_shopee, criar_loja_shopee, listar_lojas_shopee
            if loja_id:
                loja_resultado = vincular_shopee(loja_id, resolved_shop_id, access_token, refresh_token, expira_em=expira_em)
            else:
                existente = next((l for l in listar_lojas_shopee() if l.get("shopee_shop_id") == resolved_shop_id), None)
                if existente:
                    loja_resultado = vincular_shopee(existente["id"], resolved_shop_id, access_token, refresh_token, expira_em=expira_em)
                else:
                    loja_resultado = criar_loja_shopee(resolved_shop_id, access_token, refresh_token, expira_em=expira_em)

        return {"success": True, "expire_in": expire_in, "shop_id": resolved_shop_id, "loja": loja_resultado}
    except Exception as e:
        return {"error": str(e)}

def refresh_shopee_token(loja_id: int = None) -> dict:
    """Renova o access_token usando o refresh_token."""
    cfg = get_shopee_config(loja_id)
    refresh = get_config("shopee", "refresh_token") or ""
    if loja_id is not None:
        from core.lojas import obter_credenciais_shopee
        refresh = obter_credenciais_shopee(loja_id).get("shopee_refresh_token") or refresh
    if not refresh:
        return {"error": "refresh_token ausente"}
    base = _base_url().replace("/api/v2", "") + "/api/v2/auth/access_token/get"
    timestamp = int(time.time())
    body = {"refresh_token": refresh, "partner_id": int(cfg["partner_id"]), "shop_id": int(cfg["shop_id"])} if cfg.get("shop_id") else {"refresh_token": refresh, "partner_id": int(cfg["partner_id"])}
    sign_str = f"{cfg['partner_id']}{'/api/v2/auth/access_token/get'}{timestamp}"
    signature = hmac.new(cfg["api_key"].encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    try:
        r = requests.post(base, json=body, params={
            "partner_id": cfg["partner_id"], "timestamp": timestamp, "sign": signature,
        }, timeout=30)
        data = r.json()
        if data.get("access_token"):
            from datetime import datetime, timedelta
            expire_in = data.get("expire_in", 0)
            expira_em = datetime.now() + timedelta(seconds=expire_in) if expire_in else None
            if loja_id is not None:
                from core.lojas import vincular_shopee
                vincular_shopee(loja_id, cfg["shop_id"], data["access_token"], data.get("refresh_token", refresh), expira_em=expira_em)
                return {"success": True, "expire_in": expire_in}
            set_config("shopee", "access_token", data["access_token"])
            set_config("shopee", "refresh_token", data.get("refresh_token", ""))
            return {"success": True, "expire_in": expire_in}
        return {"error": data.get("message", "unknown")}
    except Exception as e:
        return {"error": str(e)}


# ── Lateralizacao: transferir produtos entre lojas + estoque automatico ──

def listar_todas_lojas_shopee() -> list:
    """Retorna lista de lojas com token Shopee valido."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT id, nome, shopee_shop_id, shopee_access_token, shopee_shop_name, ativa, COALESCE(shopee_markup_pct, 100) as shopee_markup_pct FROM lojas WHERE shopee_access_token IS NOT NULL AND ativa = TRUE ORDER BY nome")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except: return []

def transferir_produtos_para_loja(origem_loja_id: int, destino_loja_id: int, max_produtos: int = None) -> dict:
    """Replica TODOS os produtos de uma loja Shopee origem para uma loja destino.
    Baixa e reenvia imagens (image_id e vinculado ao shop_id)."""
    if not configurado(origem_loja_id) or not configurado(destino_loja_id):
        return {"error": "Origem ou destino nao configurado na Shopee"}

    resultados = {"total": 0, "sucesso": 0, "erros": [], "pulados": 0}

    # 1. Listar todos os itens da origem (paginado)
    todos_ids = []
    offset = 0
    while True:
        resp = get_items(status="NORMAL", offset=offset, page_size=100, loja_id=origem_loja_id)
        items = resp.get("response", {}).get("item_list", []) if isinstance(resp, dict) else []
        if not items:
            break
        for it in items:
            todos_ids.append(it["item_id"])
        if len(items) < 100:
            break
        offset += 100
        if max_produtos and len(todos_ids) >= max_produtos:
            break

    resultados["total"] = len(todos_ids)
    if not todos_ids:
        return {**resultados, "mensagem": "Nenhum produto encontrado na loja origem"}

    # verificar grupos de publicacao da loja destino
    async def _dg():
        db = await get_db()
        g = await db.fetchval("SELECT grupos_publicacao FROM lojas WHERE id = $1", destino_loja_id)
        return (g or "").strip()
    try: grupos_destino = set(x.strip() for x in run_async(_dg()).split(",") if x.strip())
    except: grupos_destino = set()
    filtrar_grupo = len(grupos_destino) > 0

    # 2. Processar em lotes de 20
    batch_size = 20
    for i in range(0, len(todos_ids), batch_size):
        batch = todos_ids[i:i + batch_size]
        try:
            info = get_item_base_info(batch, loja_id=origem_loja_id)
            item_list = info.get("response", {}).get("item_list", []) if isinstance(info, dict) else []
        except Exception as e:
            resultados["erros"].append(f"Falha ao buscar info do lote {batch[0]}: {e}")
            continue

        for item in item_list:
            item_id = item.get("item_id")
            try:
                # Extrair campos necessarios para add_item
                nome = item.get("item_name", "")
                sku = item.get("item_sku", "")
                # filtrar por grupo da loja destino
                if filtrar_grupo:
                    try:
                        async def _g(): db2 = await get_db(); return await db2.fetchval("SELECT grupo FROM catalogo_produtos WHERE sku = $1", sku)
                        grupo_prod = run_async(_g()) or ""
                        if grupo_prod.strip() and grupo_prod.strip() not in grupos_destino:
                            resultados["pulados"] += 1
                            continue
                    except Exception: pass
                cat_id = item.get("category_id", 0)
                desc = item.get("description", "")
                weight = item.get("weight", 0)
                preco_info = (item.get("price_info") or [{}])[0]
                preco = preco_info.get("current_price") or preco_info.get("original_price", 0)
                # aplicar markup da loja destino
                async def _mk():
                    db = await get_db()
                    mk = await db.fetchval("SELECT shopee_markup_pct FROM lojas WHERE id = $1", destino_loja_id)
                    return float(mk or 100)
                try: markup_pct = run_async(_mk())
                except: markup_pct = 100
                if markup_pct != 100:
                    preco = round(float(preco) * markup_pct / 100, 2)
                # aplicar regras de preco automaticas (sazonais, produto parado, etc.)
                try:
                    from core.automacoes import aplicar_regras_preco
                    regras = aplicar_regras_preco(sku, preco, destino_loja_id)
                    preco = regras.get("preco_final", preco)
                except Exception: pass
                dim = item.get("dimension", {})
                attr = item.get("attribute_list", [])
                brand = item.get("brand", {}) if isinstance(item.get("brand"), dict) else {}
                logistic = (item.get("logistic_info") or [{}])[0]
                # Imagens — baixar da origem e reenviar ao destino
                image_ids = []
                for img in (item.get("image", {}) or {}).get("image_id_list", []) or (item.get("images") or []):
                    img_url = img if isinstance(img, str) else img.get("image_url", "")
                    if not img_url: continue
                    try:
                        # ponytail: baixar imagem da URL da Shopee e reenviar
                        from urllib.request import urlopen
                        img_data = urlopen(img_url, timeout=30).read()
                        up = upload_image(img_data, f"{sku}.jpg", loja_id=destino_loja_id)
                        up_resp = up.get("response", up) if isinstance(up, dict) else {}
                        new_image_id = up_resp.get("image_id") or up_resp.get("image_info", {}).get("image_id", "")
                        if new_image_id:
                            image_ids.append(str(new_image_id))
                    except Exception as ie:
                        log(AGENT, f"Erro ao transferir imagem {img_url}: {ie}")
                        continue
                if not image_ids:
                    resultados["erros"].append(f"Item #{item_id} ({sku}): sem imagens")
                    continue
                if not cat_id:
                    resultados["erros"].append(f"Item #{item_id} ({sku}): sem categoria")
                    continue

                payload = {
                    "category_id": int(cat_id),
                    "item_name": str(nome)[:120],
                    "item_sku": str(sku)[:100],
                    "original_price": float(preco),
                    "description": str(desc),
                    "image": {"image_id_list": image_ids},
                    "weight": float(weight),
                    "dimension": {
                        "package_length": int(dim.get("package_length", 10) or 10),
                        "package_width": int(dim.get("package_width", 10) or 10),
                        "package_height": int(dim.get("package_height", 10) or 10),
                    },
                    "attribute_list": attr,
                    "logistic_info": [{"logistic_id": int(logistic.get("logistic_id", 0))}] if logistic else [],
                    "condition": "NEW",
                    "seller_stock": [{"stock": 0}],
                }
                if brand.get("brand_id"):
                    payload["brand"] = {"brand_id": int(brand["brand_id"]), "original_brand_name": brand.get("original_brand_name", "")}
                if isinstance(item.get("description_info"), dict) and item["description_info"].get("extended_description"):
                    payload["description_info"] = {"extended_description": {"field_list": item["description_info"]["extended_description"].get("field_list", [])}}

                resp_add = add_item(payload, loja_id=destino_loja_id)
                if resp_add.get("error"):
                    resultados["erros"].append(f"Item #{item_id} ({sku}): {resp_add['error']}")
                else:
                    resultados["sucesso"] += 1
                    # verificar concorrencia apos publicacao (background)
                    try:
                        conc = analisar_concorrencia(sku, preco)
                        if conc.get("alerta"):
                            resultados["erros"].append(f"Item #{item_id} ({sku}): {conc['mensagem']}")
                    except Exception: pass

                # verificar margem apos publicacao (so aviso, nao bloqueia)
                margem = calcular_margem_produto(sku, float(preco), loja_id=destino_loja_id)
                if not margem["ok"]:
                    resultados["erros"].append(f"Item #{item_id} ({sku}): {margem['mensagem']}")
            except Exception as e:
                resultados["erros"].append(f"Item #{item_id} ({item.get('item_sku','?')}): {e}")

    return resultados


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


# ── Concorrencia / Precificacao ──

def analisar_concorrencia(sku: str, preco: float, marketplace: str = "shopee") -> dict:
    """Compara o preco do produto com a media dos concorrentes na tabela anuncios.
    Retorna { media, mediana, min, max, total_anuncios, preco_acima_pct, alerta, mensagem }"""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT preco FROM anuncios
            WHERE sku = $1 AND marketplace = $2 AND preco > 0
            ORDER BY preco
        """, sku, marketplace)
        precos = sorted([float(r["preco"]) for r in rows])
        if not precos:
            return None
        n = len(precos)
        media = sum(precos) / n
        mediana = precos[n // 2] if n % 2 == 1 else (precos[n // 2 - 1] + precos[n // 2]) / 2
        minimo = precos[0]
        maximo = precos[-1]
        acima_pct = round((preco - media) / media * 100, 1) if media > 0 else 0
        alerta = None
        if acima_pct > 50:
            alerta = "critico"
        elif acima_pct > 20:
            alerta = "alerta"
        return {
            "sku": sku, "preco_nosso": preco, "marketplace": marketplace,
            "total_anuncios": n, "preco_medio": round(media, 2),
            "preco_mediano": round(mediana, 2), "preco_min": minimo, "preco_max": maximo,
            "preco_acima_pct": acima_pct, "alerta": alerta,
            "mensagem": f"Seu preco esta {acima_pct}% {'acima' if acima_pct >= 0 else 'abaixo'} da media (R$ {media:.2f}). {n} anuncios analisados." if alerta else f"Preco competitivo: {abs(acima_pct)}% {'acima' if acima_pct >= 0 else 'abaixo'} da media."
        }
    try:
        result = run_async(_go())
        if result: return result
        return {"sku": sku, "preco_nosso": preco, "total_anuncios": 0, "mensagem": "Nenhum concorrente encontrado para este SKU."}
    except Exception as e:
        return {"sku": sku, "erro": str(e)}


# ── Sugestao de Kits / Cross-sell ──

def sugerir_kits(dias: int = 90, min_ocorrencias: int = 3) -> list:
    """Analisa vendas e sugere kits com base em produtos comprados juntos.
    Retorna lista de { sku_a, nome_a, sku_b, nome_b, qtd_juntos, confianca_pct }"""
    async def _go():
        db = await get_db()
        # ponytail: pares de SKUs no mesmo pedido nos ultimos N dias
        rows = await db.fetch("""
            SELECT a.sku AS sku_a, b.sku AS sku_b, COUNT(DISTINCT a.pedido_id) AS juntos
            FROM vendas_itens a
            JOIN vendas_itens b ON b.pedido_id = a.pedido_id AND b.sku != a.sku
            JOIN vendas_pedidos v ON v.id = a.pedido_id
            WHERE v.data >= CURRENT_DATE - $1 AND v.status != 'cancelado'
            GROUP BY a.sku, b.sku
            HAVING COUNT(DISTINCT a.pedido_id) >= $2
            ORDER BY juntos DESC
            LIMIT 50
        """, dias, min_ocorrencias)
        resultado = []
        for r in rows:
            # buscar nomes dos produtos
            na = await db.fetchval("SELECT descricao FROM catalogo_produtos WHERE sku = $1", r["sku_a"])
            nb = await db.fetchval("SELECT descricao FROM catalogo_produtos WHERE sku = $1", r["sku_b"])
            total_a = await db.fetchval("SELECT COUNT(DISTINCT pedido_id) FROM vendas_itens WHERE sku = $1", r["sku_a"])
            confianca = round((r["juntos"] / total_a * 100) if total_a else 0, 1)
            resultado.append({
                "sku_a": r["sku_a"], "nome_a": na or r["sku_a"],
                "sku_b": r["sku_b"], "nome_b": nb or r["sku_b"],
                "qtd_juntos": r["juntos"],
                "confianca_pct": confianca,
            })
        # remover duplicatas invertidas (A,B e B,A)
        visto = set()
        unicos = []
        for r in resultado:
            par = tuple(sorted([r["sku_a"], r["sku_b"]]))
            if par not in visto:
                visto.add(par)
                unicos.append(r)
        return unicos[:30]
    try: return run_async(_go())
    except Exception as e: return []
