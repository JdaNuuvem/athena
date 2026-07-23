import psycopg2
import psycopg2.extras
import time

from flask import Blueprint, request, jsonify, redirect
from core import run_async, get_db, FactoryConfig, hoje

shopee_bp = Blueprint("shopee", __name__, url_prefix="/api/shopee")
shopee_ads_bp = Blueprint("shopee_ads", __name__, url_prefix="/api/shopee-ads")


# ===========================================================================
# Shopee Ads (chamado pelo ShopeeAdsIntegration.tsx)
# ===========================================================================

@shopee_ads_bp.route('/campaigns', methods=['GET'])
def shopee_ads_campaigns():
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM shopee_ads_campaigns ORDER BY id DESC")
        return [dict(r) for r in rows]
    return jsonify(run_async(_go()))

@shopee_ads_bp.route('/campaigns', methods=['POST'])
def shopee_ads_create_campaign():
    data = request.json or {}
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            INSERT INTO shopee_ads_campaigns (campaign_id, shop_id, nome, tipo, status, daily_budget, start_date)
            VALUES ($1, $2, $3, $4, 'active', $5, $6::date) RETURNING *
        """, f"camp_{int(time.time())}", data.get("shopId", ""),
            data.get("name", "Campanha"), "search",
            data.get("dailyBudget", 100), data.get("startDate", hoje()))
        return dict(row)
    return jsonify(run_async(_go()))

@shopee_ads_bp.route('/performance', methods=['GET'])
def shopee_ads_performance():
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM shopee_ads_performance ORDER BY data DESC LIMIT 90")
        return [dict(r) for r in rows]
    return jsonify(run_async(_go()))

@shopee_ads_bp.route('/insights', methods=['GET'])
def shopee_ads_insights():
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM shopee_ads_insights ORDER BY created_at DESC LIMIT 50")
        return [dict(r) for r in rows]
    return jsonify(run_async(_go()))

@shopee_ads_bp.route('/insights/<int:insight_id>/resolve', methods=['POST'])
def shopee_ads_resolve_insight(insight_id):
    async def _go():
        db = await get_db()
        await db.execute("UPDATE shopee_ads_insights SET action_taken = true WHERE id = $1", insight_id)
    run_async(_go())
    return jsonify({"success": True})

@shopee_ads_bp.route('/abtests', methods=['GET'])
def shopee_ads_abtests():
    return jsonify([])

@shopee_ads_bp.route('/campaigns/<campaign_id>/analyze', methods=['GET'])
def shopee_ads_analyze(campaign_id):
    days = request.args.get("days", 30, type=int)
    return jsonify({
        "campaign_id": campaign_id, "periodo_dias": days,
        "impressions": 0, "clicks": 0, "cost": 0, "orders": 0, "revenue": 0,
        "roas": 0, "ctr": 0, "cpc": 0, "conversion_rate": 0,
        "recomendacao": "Sincronize campanhas primeiro via sync Shopee",
    })

@shopee_ads_bp.route('/campaigns/<campaign_id>/adjust-bids', methods=['POST'])
def shopee_ads_adjust_bids(campaign_id):
    data = request.json or {}
    target_roas = data.get("targetRoas", 3.0)
    return jsonify({
        "campaign_id": campaign_id, "target_roas": target_roas,
        "ajustes": [], "status": "ok",
        "mensagem": f"Bids ajustados para ROAS {target_roas} (simulado)",
    })

@shopee_ads_bp.route('/campaigns/<campaign_id>/predict', methods=['GET'])
def shopee_ads_predict(campaign_id):
    days = request.args.get("days", 30, type=int)
    return jsonify({
        "campaign_id": campaign_id, "previsao_dias": days,
        "impressions_estimado": 0, "clicks_estimado": 0,
        "cost_estimado": 0, "revenue_estimado": 0,
        "roas_estimado": 0,
        "confianca": "baixa — precisa de dados historicos",
    })

@shopee_ads_bp.route('/campaigns/<campaign_id>/suggest-budget', methods=['GET'])
def shopee_ads_suggest_budget(campaign_id):
    target_roas = request.args.get("targetRoas", 3.0, type=float)
    return jsonify({
        "campaign_id": campaign_id, "target_roas": target_roas,
        "budget_atual": 0,
        "budget_sugerido": 100.00,
        "motivo": "Orcamento sugerido baseado em media de mercado",
    })


# ===========================================================================
# Helpers
# ===========================================================================

def _db_sync():
    cfg = FactoryConfig.load()
    conn = psycopg2.connect(host=cfg.db_host, port=cfg.db_port, dbname=cfg.db_name,
                            user=cfg.db_user, password=cfg.db_password, connect_timeout=5)
    conn.set_session(autocommit=True)
    return conn

def _url_publica_segura(url: str) -> bool:
    import socket, ipaddress
    from urllib.parse import urlparse
    try:
        host = urlparse(url).hostname
        if not host:
            return False
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except Exception:
        return False


# ===========================================================================
# Shopee endpoints estendidos (port do ATHENA shopee-adapter.ts)
# ===========================================================================

@shopee_bp.route('/callback', methods=['GET'])
@shopee_bp.route('/oauth2callback', methods=['GET'])
def shopee_oauth_callback():
    from urllib.parse import urlencode
    code = request.args.get("code", "")
    shop_id = request.args.get("shop_id", "")
    loja_id = request.args.get("loja_id", type=int)
    if not code:
        return redirect("/integracoes/shopee?" + urlencode({"shopee_auth": "erro", "shopee_msg": "Parametro code ausente"}))
    from shopee import exchange_shopee_code
    result = exchange_shopee_code(code, shop_id, loja_id=loja_id)
    if result.get("success"):
        loja = result.get("loja") or {}
        params = {
            "shopee_auth": "ok",
            "shopee_shop_id": result.get("shop_id", ""),
            "shopee_loja_nome": loja.get("nome", ""),
            "shopee_expire_in": result.get("expire_in", ""),
        }
        if loja.get("error"):
            params["shopee_msg"] = f"Autorizado, mas nao foi possivel vincular a loja: {loja['error']}"
        return redirect("/integracoes/shopee?" + urlencode(params))
    return redirect("/integracoes/shopee?" + urlencode({"shopee_auth": "erro", "shopee_msg": result.get("error", "Falha na autenticacao")}))

@shopee_bp.route('/auth-url', methods=['GET'])
def shopee_auth_url():
    from shopee import get_auth_url
    sandbox = request.args.get("sandbox", "").lower() == "true"
    loja_id = request.args.get("loja_id", type=int)
    url = get_auth_url(sandbox=sandbox, loja_id=loja_id)
    if not url:
        return jsonify({"error": "Partner ID nao configurado"}), 400
    return jsonify({"url": url})

@shopee_bp.route('/lojas', methods=['GET'])
def shopee_listar_lojas():
    from core.lojas import listar_lojas_shopee
    return jsonify({"lojas": listar_lojas_shopee()})

@shopee_bp.route('/lojas/<int:loja_id>/conectar', methods=['POST'])
def shopee_conectar_loja(loja_id):
    from shopee import get_auth_url
    sandbox = (request.json or {}).get("sandbox", False) if request.is_json else False
    url = get_auth_url(sandbox=sandbox, loja_id=loja_id)
    if not url:
        return jsonify({"error": "Partner ID nao configurado"}), 400
    return jsonify({"url": url})

@shopee_bp.route('/lojas/<int:loja_id>/renovar-token', methods=['POST'])
def shopee_renovar_token(loja_id):
    from shopee import refresh_shopee_token
    try:
        return jsonify(refresh_shopee_token(loja_id=loja_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@shopee_bp.route('/lojas/<int:loja_id>', methods=['DELETE'])
def shopee_desconectar_loja(loja_id):
    from core.lojas import desconectar_shopee
    return jsonify(desconectar_shopee(loja_id))

@shopee_bp.route('/sync-log', methods=['GET'])
def shopee_sync_log():
    from shopee_sync import status_ultimo_sync
    return jsonify({"log": status_ultimo_sync()})

@shopee_bp.route('/pedidos', methods=['GET'])
def shopee_listar_pedidos():
    from shopee import listar_pedidos_shopee_detalhado
    loja_id = request.args.get("loja_id", type=int)
    dias = request.args.get("dias", 7, type=int)
    status = request.args.get("status") or None
    try:
        return jsonify(listar_pedidos_shopee_detalhado(dias, loja_id=loja_id, status=status))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@shopee_bp.route('/dashboard', methods=['GET'])
def shopee_dashboard_consolidado():
    from core.lojas import listar_lojas_shopee
    dias = request.args.get("dias", 30, type=int)
    lojas = listar_lojas_shopee()
    try:
        conn = _db_sync(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        resultado = []
        for l in lojas:
            shop_id = l.get("shopee_shop_id") or ""
            cur.execute("""
                SELECT COALESCE(SUM(receita_bruta),0) AS receita, COALESCE(SUM(quantidade),0) AS unidades,
                       COUNT(DISTINCT sku) AS skus_vendidos
                FROM vendas WHERE marketplace = 'shopee' AND loja_id = %s AND data >= CURRENT_DATE - %s
            """, (l["id"], dias))
            vendas_row = cur.fetchone() or {}
            cur.execute("""
                SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE status = 'ativo') AS ativos
                FROM anuncios WHERE marketplace = 'shopee' AND shop_id = %s
            """, (shop_id,))
            anuncios_row = cur.fetchone() or {}
            cur.execute("""
                SELECT COUNT(DISTINCT a.sku) AS total FROM anuncios a
                JOIN catalogo_produtos c ON c.sku = a.sku
                LEFT JOIN estoque_lojas e ON e.sku = a.sku
                WHERE a.marketplace = 'shopee' AND a.shop_id = %s
                  AND c.estoque_minimo IS NOT NULL
                GROUP BY a.sku HAVING COALESCE(SUM(e.quantidade), 0) <= MAX(c.estoque_minimo)
            """, (shop_id,))
            estoque_baixo = len(cur.fetchall() or [])
            resultado.append({
                "loja_id": l["id"], "nome": l["nome"], "shop_id": shop_id,
                "tem_token": l.get("tem_token", False),
                "receita": float(vendas_row.get("receita") or 0),
                "unidades_vendidas": int(vendas_row.get("unidades") or 0),
                "skus_vendidos": int(vendas_row.get("skus_vendidos") or 0),
                "anuncios_total": int(anuncios_row.get("total") or 0),
                "anuncios_ativos": int(anuncios_row.get("ativos") or 0),
                "produtos_estoque_baixo": estoque_baixo,
            })
        cur.close(); conn.close()
        return jsonify({"lojas": resultado, "dias": dias})
    except Exception as e:
        return jsonify({"error": str(e), "lojas": []})

@shopee_bp.route('/lojas/<int:destino_id>/replicar-de/<int:origem_id>', methods=['POST'])
def shopee_replicar_produtos(destino_id, origem_id):
    from shopee import transferir_produtos_para_loja
    max_produtos = (request.json or {}).get("max_produtos")
    try:
        return jsonify(transferir_produtos_para_loja(origem_id, destino_id, max_produtos=max_produtos))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@shopee_bp.route('/estoque/sincronizar-todas', methods=['POST'])
def shopee_sincronizar_estoque_todas():
    from shopee import sincronizar_estoque_todas_lojas_automatico
    data = request.json or {}
    sku = data.get("sku", "")
    qtd = int(data.get("quantidade", 0))
    if not sku:
        return jsonify({"error": "SKU obrigatorio"}), 400
    try:
        return jsonify(sincronizar_estoque_todas_lojas_automatico(sku, qtd))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@shopee_bp.route('/margem', methods=['GET'])
def shopee_verificar_margem():
    from shopee import calcular_margem_produto
    sku = request.args.get("sku", "")
    preco = float(request.args.get("preco", 0))
    loja_id = request.args.get("loja_id", type=int)
    if not sku or not preco:
        return jsonify({"error": "SKU e preco obrigatorios"}), 400
    try:
        return jsonify(calcular_margem_produto(sku, preco, loja_id=loja_id))
    except Exception as e:
        return jsonify({"error": str(e)})

@shopee_bp.route('/concorrencia', methods=['GET'])
def shopee_concorrencia():
    from shopee import analisar_concorrencia
    sku = request.args.get("sku", "")
    preco = float(request.args.get("preco", 0))
    if not sku:
        return jsonify({"error": "SKU obrigatorio"}), 400
    return jsonify(analisar_concorrencia(sku, preco))

@shopee_bp.route('/sugestao-kits', methods=['GET'])
def shopee_sugestao_kits():
    from shopee import sugerir_kits
    dias = request.args.get("dias", 90, type=int)
    min_oc = request.args.get("min", 3, type=int)
    return jsonify({"data": sugerir_kits(dias, min_oc)})

@shopee_bp.route('/produtos/<int:item_id>/preco', methods=['POST'])
def shopee_atualizar_preco(item_id):
    from shopee import update_price
    data = request.json or {}
    loja_id = data.get("loja_id")
    preco = data.get("price")
    if preco is None:
        return jsonify({"error": "price e obrigatorio"}), 400
    try:
        return jsonify(update_price(item_id, float(preco), loja_id=loja_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@shopee_bp.route('/produtos/<int:item_id>/variacoes', methods=['GET'])
def shopee_variacoes_produto(item_id):
    from shopee import get_model_list
    loja_id = request.args.get("loja_id", type=int)
    try:
        return jsonify(get_model_list(item_id, loja_id=loja_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@shopee_bp.route('/produtos/<sku>/estoque', methods=['PUT'])
def shopee_atualizar_estoque_produto(sku):
    from shopee import sincronizar_estoque_shopee
    data = request.json or {}
    loja_id = data.get("loja_id")
    quantidade = data.get("quantidade")
    if loja_id is None or quantidade is None:
        return jsonify({"error": "loja_id e quantidade sao obrigatorios"}), 400
    try:
        return jsonify(sincronizar_estoque_shopee(sku, int(quantidade), loja_id=int(loja_id)))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@shopee_bp.route('/estoque/todas-lojas', methods=['POST'])
def shopee_estoque_todas_lojas():
    from shopee import sincronizar_estoque_todas_lojas
    data = request.json or {}
    sku = data.get("sku")
    quantidade = data.get("quantidade")
    if not sku or quantidade is None:
        return jsonify({"error": "sku e quantidade sao obrigatorios"}), 400
    try:
        return jsonify(sincronizar_estoque_todas_lojas(sku, int(quantidade)))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@shopee_bp.route('/categorias', methods=['GET'])
def shopee_categorias():
    from shopee import listar_categorias_cache
    busca = request.args.get("busca", "")
    parent_id = request.args.get("parent_id", type=int)
    apenas_folhas = request.args.get("apenas_folhas", "").lower() == "true"
    return jsonify({"categorias": listar_categorias_cache(busca, parent_id, apenas_folhas)})

@shopee_bp.route('/categorias/sincronizar', methods=['POST'])
def shopee_categorias_sincronizar():
    from shopee import sincronizar_categorias
    data = request.json or {}
    return jsonify(sincronizar_categorias(data.get("loja_id")))

@shopee_bp.route('/categorias/<int:category_id>/atributos', methods=['GET'])
def shopee_categoria_atributos(category_id):
    from shopee import get_attribute_tree
    loja_id = request.args.get("loja_id", type=int)
    r = get_attribute_tree(category_id, loja_id=loja_id)
    lista = r.get("response", {}).get("list", [])
    brutos = lista[0].get("attribute_tree", []) if lista else []
    atributos = [{
        "attribute_id": a.get("attribute_id"),
        "original_attribute_name": a.get("name", ""),
        "is_mandatory": bool(a.get("mandatory", False)),
        "attribute_value_list": [
            {"value_id": v.get("value_id"), "original_value_name": v.get("name", "")}
            for v in (a.get("attribute_value_list") or [])
        ],
    } for a in brutos]
    return jsonify({"atributos": atributos, "erro": r.get("error") or None})

@shopee_bp.route('/categorias/<int:category_id>/marcas', methods=['GET'])
def shopee_categoria_marcas(category_id):
    from shopee import get_brand_list
    loja_id = request.args.get("loja_id", type=int)
    r = get_brand_list(category_id, loja_id=loja_id)
    resp = r.get("response", {})
    return jsonify({"marcas": resp.get("brand_list", []), "obrigatorio": resp.get("is_mandatory", False), "erro": r.get("error") or None})

@shopee_bp.route('/logistica/canais', methods=['GET'])
def shopee_logistica_canais():
    from shopee import get_logistics_channel_list
    loja_id = request.args.get("loja_id", type=int)
    r = get_logistics_channel_list(loja_id=loja_id)
    canais_brutos = r.get("response", {}).get("logistics_channel_list", [])
    canais = [{
        "logistic_id": c.get("logistics_channel_id"),
        "logistic_name": c.get("logistics_channel_name", ""),
        "enabled": bool(c.get("enabled", False)),
    } for c in canais_brutos]
    return jsonify({"canais": canais, "erro": r.get("error") or None})

@shopee_bp.route('/upload-imagem', methods=['POST'])
def shopee_upload_imagem():
    from shopee import upload_image
    import requests as req_lib
    loja_id = request.form.get("loja_id", type=int)
    if "file" in request.files:
        file = request.files["file"]
        image_bytes = file.read()
        filename = file.filename or "imagem.jpg"
    else:
        image_url = request.form.get("image_url", "")
        if not image_url.startswith(("http://", "https://")):
            return jsonify({"error": "Envie um arquivo ou informe uma image_url http(s) valida"}), 400
        if not _url_publica_segura(image_url):
            return jsonify({"error": "image_url nao permitida"}), 400
        try:
            resp = req_lib.get(image_url, timeout=20, allow_redirects=False)
            resp.raise_for_status()
            image_bytes = resp.content
            filename = image_url.rsplit("/", 1)[-1].split("?")[0] or "imagem.jpg"
        except Exception as e:
            from core import log
            log("Shopee Upload", f"Falha ao baixar {image_url}: {e}")
            return jsonify({"error": "Falha ao baixar imagem"}), 400
    r = upload_image(image_bytes, filename, loja_id=loja_id)
    resp = r.get("response", {})
    image_info = resp.get("image_info", {})
    return jsonify({"image_id": image_info.get("image_id"), "image_url": (image_info.get("image_url_list") or [{}])[0].get("image_url", ""), "erro": r.get("error") or None})

@shopee_bp.route('/produtos', methods=['POST'])
def shopee_criar_produto():
    from shopee import add_item, calcular_margem_produto
    data = request.json or {}
    loja_id = data.pop("loja_id", None)
    if loja_id is None:
        return jsonify({"error": "loja_id e obrigatorio"}), 400
    forcar = bool(data.pop("forcar_publicacao", False))
    sku = data.get("item_sku", "")
    preco = data.get("original_price", 0)
    if sku and preco and not forcar:
        margem = calcular_margem_produto(sku, float(preco), loja_id=int(loja_id))
        if not margem.get("ok"):
            return jsonify({"error": margem["mensagem"], "margem": margem, "bloqueado_por_margem": True}), 400
    return jsonify(add_item(data, loja_id=int(loja_id)))

@shopee_bp.route('/produtos/<int:item_id>', methods=['GET'])
def shopee_detalhe_produto(item_id):
    from shopee import get_item_base_info
    loja_id = request.args.get("loja_id", type=int)
    try:
        r = get_item_base_info([item_id], loja_id=loja_id)
        itens = (r.get("response", {}) or {}).get("item_list", [])
        if not itens:
            return jsonify({"error": "Item nao encontrado"}), 404
        return jsonify({"item": itens[0]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@shopee_bp.route('/produtos/<int:item_id>', methods=['PUT'])
def shopee_editar_produto(item_id):
    from shopee import update_item
    data = request.json or {}
    loja_id = data.pop("loja_id", None)
    if loja_id is None:
        return jsonify({"error": "loja_id e obrigatorio"}), 400
    return jsonify(update_item(item_id, data, loja_id=int(loja_id)))

@shopee_bp.route('/produtos/<int:item_id>', methods=['DELETE'])
def shopee_deletar_produto(item_id):
    from shopee import delete_item_shopee
    loja_id = request.args.get("loja_id", type=int)
    return jsonify(delete_item_shopee(item_id, loja_id=loja_id))

@shopee_bp.route('/produtos/<int:item_id>/unlist', methods=['POST'])
def shopee_unlist_produto(item_id):
    from shopee import unlist_item
    data = request.json or {}
    loja_id = data.get("loja_id")
    unlist = data.get("unlist", True)
    return jsonify(unlist_item([item_id], unlist=unlist, loja_id=loja_id))
