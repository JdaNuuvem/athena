import os
from flask import Blueprint, request, jsonify
from core import get_db, run_async

integrations_bp = Blueprint("integrations", __name__)


# --- Integration listing ---

@integrations_bp.route("/api/integrations", methods=["GET"])
def list_integrations():
    from core.config import get_config
    bling_ok = bool(get_config("bling", "access_token")) or bool(get_config("bling", "client_id"))
    shopee_ok = bool(get_config("shopee", "api_key")) or bool(os.environ.get("SHOPEE_PARTNER_ID"))
    telegram_ok = bool(get_config("telegram", "token")) or bool(os.environ.get("TELEGRAM_BOT_TOKEN"))
    whatsapp_ok = bool(get_config("whatsapp", "api_key")) or bool(os.environ.get("EVOLUTION_API_KEY"))
    return jsonify([
        {"id": "bling", "name": "Bling ERP", "category": "erp", "status": "connected" if bling_ok else "disconnected"},
        {"id": "shopee", "name": "Shopee", "category": "ecommerce", "status": "connected" if shopee_ok else "disconnected"},
        {"id": "shopee-ads", "name": "Shopee Ads (AG-ADS)", "category": "ai", "status": "disconnected"},
        {"id": "mercadolivre", "name": "Mercado Livre", "category": "ecommerce", "status": "disconnected"},
        {"id": "nuvemshop", "name": "Nuvemshop", "category": "ecommerce", "status": "disconnected"},
        {"id": "shopify", "name": "Shopify", "category": "ecommerce", "status": "disconnected"},
        {"id": "pagseguro", "name": "PagSeguro", "category": "payment", "status": "disconnected"},
        {"id": "mercado_pago", "name": "Mercado Pago", "category": "payment", "status": "disconnected"},
        {"id": "correios", "name": "Correios", "category": "logistics", "status": "disconnected"},
        {"id": "jadlog", "name": "Jadlog", "category": "logistics", "status": "disconnected"},
        {"id": "whatsapp", "name": "WhatsApp Business", "category": "communication", "status": "connected" if whatsapp_ok else "disconnected"},
        {"id": "google_analytics", "name": "Google Analytics", "category": "analytics", "status": "disconnected"},
        {"id": "meta", "name": "Meta (Facebook/Instagram)", "category": "ecommerce", "status": "disconnected"},
        {"id": "hermes", "name": "Hermes Agents", "category": "ai", "status": "connected"},
    ])


@integrations_bp.route("/api/integrations/<integ_id>/connect", methods=["POST"])
def connect_integration(integ_id):
    urls = {"shopee": "/shopee", "bling": "/bling", "whatsapp": "/integrations"}
    msgs = {
        "shopee": "Configure as chaves da Shopee na página de integração",
        "bling": "Configure a API key do Bling na página de integração",
        "whatsapp": "Configure a Evolution API key nas variáveis de ambiente",
    }
    return jsonify({
        "success": True,
        "authUrl": urls.get(integ_id, ""),
        "message": msgs.get(integ_id, f"Integração {integ_id} conectada (simulado)"),
    })


@integrations_bp.route("/api/integrations/<integ_id>/disconnect", methods=["POST"])
def disconnect_integration(integ_id):
    return jsonify({"success": True, "message": f"Integração {integ_id} desconectada"})


# --- Shopee endpoints ---

@integrations_bp.route("/api/shopee/produtos/detalhes", methods=["POST"])
def shopee_detalhes_produtos():
    from shopee import get_item_base_info
    return jsonify(get_item_base_info(request.json.get("item_ids", [])))


@integrations_bp.route("/api/shopee/produtos/<int:item_id>/estoque", methods=["GET"])
def shopee_estoque_item(item_id):
    from shopee import check_stock
    return jsonify(check_stock(item_id))


@integrations_bp.route("/api/shopee/produtos/<int:item_id>/preco", methods=["POST"])
def shopee_atualizar_preco(item_id):
    from shopee import update_price
    return jsonify(update_price(item_id, request.json.get("price", 0)))


@integrations_bp.route("/api/shopee/produtos/sincronizar", methods=["POST"])
def shopee_sync():
    from shopee import sync_all_items
    itens = sync_all_items()
    return jsonify({"total": len(itens), "itens": itens})


@integrations_bp.route("/api/shopee/pedidos/<order_sn>", methods=["GET"])
def shopee_detalhe_pedido(order_sn):
    from shopee import get_order_detail
    return jsonify(get_order_detail(order_sn))


@integrations_bp.route("/api/shopee/config", methods=["GET"])
def shopee_config_get():
    from core.config import get_config
    return jsonify({
        "partner_id": get_config("shopee", "partner_id") or os.environ.get("SHOPEE_PARTNER_ID", ""),
        "partner_key": "",
        "shop_id": get_config("shopee", "shop_id") or os.environ.get("SHOPEE_SHOP_ID", ""),
        "region": get_config("shopee", "region") or os.environ.get("SHOPEE_REGION", "br"),
        "sandbox": (get_config("shopee", "sandbox") or os.environ.get("SHOPEE_SANDBOX", "false")).lower() == "true",
    })


@integrations_bp.route("/api/shopee/config", methods=["PUT"])
def shopee_config_put():
    from core.config import set_config
    data = request.json or {}
    for campo in ("partner_id", "shop_id", "api_key", "access_token", "region"):
        if campo in data:
            set_config("shopee", campo, str(data[campo]))
    if "partner_key" in data and data["partner_key"]:
        set_config("shopee", "api_key", data["partner_key"])
    if "sandbox" in data:
        set_config("shopee", "sandbox", "true" if data["sandbox"] else "false")
    return jsonify({"success": True})


@integrations_bp.route("/api/shopee/products", methods=["GET"])
def shopee_products():
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT anuncio_id, sku, titulo, status, preco, ultima_atualizacao
            FROM anuncios
            WHERE marketplace = 'shopee'
            ORDER BY ultima_atualizacao DESC
            LIMIT 200
        """)
        return [dict(r) for r in rows]
    try:
        rows = run_async(_go())
        return jsonify([{
            "item_id": int(r.get("anuncio_id") or 0),
            "item_sku": r.get("sku", ""),
            "item_name": r.get("titulo", ""),
            "item_status": (r.get("status") or "normal").upper(),
            "stock": 0,
            "reserved_stock": 0,
            "has_model": False,
            "price": float(r.get("preco") or 0),
            "last_synced_at": r["ultima_atualizacao"].isoformat() if r.get("ultima_atualizacao") else "",
        } for r in rows])
    except Exception as e:
        return jsonify([])


@integrations_bp.route("/api/shopee/orders", methods=["GET"])
def shopee_orders():
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT data, sku, quantidade, preco_venda, receita_bruta
            FROM vendas
            WHERE marketplace = 'shopee'
            ORDER BY data DESC
            LIMIT 100
        """)
        return [dict(r) for r in rows]
    try:
        rows = run_async(_go())
        return jsonify([{
            "order_sn": r.get("sku", ""),
            "order_status": "COMPLETED",
            "buyer": "",
            "total_amount": float(r.get("receita_bruta") or 0),
            "items": [{"item_name": r.get("sku", ""), "quantity": int(r.get("quantidade") or 1)}],
            "ordered_at": r["data"].isoformat() if r.get("data") else "",
            "synced_to_athena": True,
        } for r in rows])
    except Exception:
        return jsonify([])


@integrations_bp.route("/api/shopee/test", methods=["POST"])
def shopee_test():
    from shopee import configurado, get_items
    if not configurado():
        return jsonify({"success": False, "message": "Shopee não configurada. Preencha Partner ID, Shop ID e Partner Key."})
    try:
        r = get_items("NORMAL", 0)
        if r.get("error"):
            return jsonify({"success": False, "message": f"Erro Shopee: {r['error']}"})
        return jsonify({"success": True, "message": "Conexão com Shopee estabelecida com sucesso!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Falha na conexão: {str(e)}"})


@integrations_bp.route("/api/shopee/sync", methods=["POST"])
def shopee_sync_products():
    from shopee_sync import sync_produtos
    try:
        result = run_async(sync_produtos())
        return jsonify({"count": result.get("total", 0), "errors": result.get("detalhes_erros", [])})
    except Exception as e:
        return jsonify({"count": 0, "errors": [str(e)]})


@integrations_bp.route("/api/shopee/sync-orders", methods=["POST"])
def shopee_sync_orders():
    from shopee_sync import sync_pedidos
    try:
        result = run_async(sync_pedidos())
        return jsonify({"count": result.get("total", 0), "errors": result.get("detalhes_erros", [])})
    except Exception as e:
        return jsonify({"count": 0, "errors": [str(e)]})


# --- Bling ERP v3 ---

@integrations_bp.route("/api/bling/auth", methods=["GET"])
def bling_auth_url():
    from bling_erp import get_auth_url, status
    return jsonify({"auth_url": get_auth_url(), **status()})


@integrations_bp.route("/api/bling/oauth/callback", methods=["GET"])
def bling_oauth_callback():
    from bling_erp import exchange_code
    code = request.args.get("code", "")
    if not code:
        return jsonify({"error": "No code provided"}), 400
    resultado = exchange_code(code)
    if resultado.get("success"):
        return '<html><body><h2>✅ Bling conectado!</h2><p>Pode fechar esta janela e voltar ao dashboard.</p><script>setTimeout(()=>{window.close()},2000)</script></body></html>'
    return jsonify({"error": "Falha na autenticação", "detalhe": resultado}), 400


@integrations_bp.route("/api/bling/status", methods=["GET"])
def bling_status():
    from bling_erp import status
    return jsonify(status())


@integrations_bp.route("/api/bling/sync", methods=["POST"])
def bling_sync():
    from bling_erp import sincronizar_produtos, sincronizar_pedidos
    produtos = sincronizar_produtos()
    pedidos = sincronizar_pedidos()
    return jsonify({"produtos": produtos, "pedidos": pedidos})


@integrations_bp.route("/api/bling/webhook/registrar", methods=["POST"])
def bling_webhook_registrar():
    from bling_erp import registrar_webhook
    data = request.json or {}
    return jsonify(registrar_webhook(data.get("tipo", "pedido"), data.get("url")))


@integrations_bp.route("/api/bling/config", methods=["GET"])
def bling_config_get():
    from bling_erp import status
    s = status()
    return jsonify({
        "api_key": s.get("autenticado", False) and "configurado" or "",
        "sandbox": False, "auto_sync": False, "sync_interval_minutes": 30,
        "sync_products": True, "sync_orders": True, "sync_invoices": False,
        "sync_receivables": False, "sync_stock": False,
        "auth_url": s.get("auth_url", ""), "autenticado": s.get("autenticado", False),
    })


@integrations_bp.route("/api/bling/config", methods=["PUT"])
def bling_config_put():
    from core.config import set_config
    data = request.json or {}
    if data.get("api_key"):
        set_config("bling", "api_key", data["api_key"])
    return jsonify({"success": True})


@integrations_bp.route("/api/bling/test", methods=["POST"])
def bling_test():
    from bling_erp import status
    s = status()
    return jsonify({
        "success": s.get("autenticado", False),
        "message": "Conectado" if s.get("autenticado") else "Não autenticado",
    })


@integrations_bp.route("/api/bling/products", methods=["GET"])
def bling_products():
    from bling_erp import listar_produtos
    r = listar_produtos()
    dados = r.get("data", [])
    return jsonify([{
        "id": p.get("id", 0), "codigo": p.get("codigo", ""),
        "descricao": p.get("descricao", ""),
        "preco": float(p.get("preco", 0) or 0),
        "estoque_atual": int(p.get("estoqueAtual", 0) or 0),
        "estoque_minimo": int(p.get("estoqueMinimo", 0) or 0),
        "situacao": p.get("situacao", "Ativo"),
    } for p in dados])


@integrations_bp.route("/api/bling/orders", methods=["GET"])
def bling_orders():
    from bling_erp import listar_pedidos
    r = listar_pedidos()
    dados = r.get("data", [])
    return jsonify([{
        "id": p.get("id", 0), "numero": str(p.get("numero", "")),
        "data": p.get("dataEmissao", ""),
        "total_venda": float(p.get("totalVenda", 0) or 0),
        "situacao": p.get("situacao", ""),
        "contato_nome": p.get("contato", {}).get("nome", ""),
        "imported_at": "",
    } for p in dados])


@integrations_bp.route("/api/bling/sync/products", methods=["POST"])
def bling_sync_products():
    from bling_erp import sincronizar_produtos
    r = sincronizar_produtos()
    return jsonify({"count": r.get("sincronizados", 0), "errors": [r["erro"]] if r.get("erro") else []})


@integrations_bp.route("/api/bling/sync/orders", methods=["POST"])
def bling_sync_orders():
    from bling_erp import sincronizar_pedidos
    r = sincronizar_pedidos()
    return jsonify({"count": r.get("sincronizados", 0), "errors": [r["erro"]] if r.get("erro") else []})


@integrations_bp.route("/api/bling/invoices", methods=["GET"])
def bling_invoices():
    from bling_erp import listar_notas_fiscais
    r = listar_notas_fiscais()
    dados = r.get("data", [])
    return jsonify([{
        "id": nf.get("id", 0),
        "numero": str(nf.get("numero", "")),
        "serie": str(nf.get("serie", "")),
        "data_emissao": nf.get("dataEmissao", ""),
        "valor_nota": float(nf.get("valorNota", 0) or 0),
        "situacao": nf.get("situacao", ""),
        "cliente_nome": (nf.get("contato") or {}).get("nome", ""),
        "imported_at": nf.get("dataEmissao", ""),
    } for nf in dados])


@integrations_bp.route("/api/bling/receivables", methods=["GET"])
def bling_receivables():
    from bling_erp import listar_contas_receber
    r = listar_contas_receber()
    dados = r.get("data", [])
    return jsonify([{
        "id": cr.get("id", 0),
        "descricao": cr.get("descricao", ""),
        "valor": float(cr.get("valor", 0) or 0),
        "data_vencimento": cr.get("dataVencimento", ""),
        "situacao": cr.get("situacao", ""),
    } for cr in dados])


@integrations_bp.route("/api/bling/sync/invoices", methods=["POST"])
def bling_sync_invoices():
    from bling_erp import listar_notas_fiscais
    r = listar_notas_fiscais()
    dados = r.get("data", [])
    if r.get("error"):
        return jsonify({"count": 0, "errors": [r["error"]]})
    return jsonify({"count": len(dados), "errors": []})


@integrations_bp.route("/api/bling/sync/receivables", methods=["POST"])
def bling_sync_receivables():
    from bling_erp import listar_contas_receber
    r = listar_contas_receber()
    dados = r.get("data", [])
    if r.get("error"):
        return jsonify({"count": 0, "errors": [r["error"]]})
    return jsonify({"count": len(dados), "errors": []})


@integrations_bp.route("/api/bling/sync/contacts", methods=["POST"])
def bling_sync_contacts():
    from core.entidades import sincronizar_contatos_bling
    r = sincronizar_contatos_bling()
    if r.get("error"): return jsonify({"count": 0, "errors": [r["error"]]})
    return jsonify({"count": r.get("sync", 0), "errors": []})


@integrations_bp.route("/api/bling/contacts", methods=["GET"])
def bling_contacts():
    import json
    async def _go():
        from core import get_db
        db = await get_db()
        rows = await db.fetch("SELECT id, nome, tipo, documento, email, telefone, status FROM cad_clientes ORDER BY id DESC LIMIT 200")
        return [dict(r) for r in rows]
    try:
        from core import run_async
        data = run_async(_go())
        return jsonify(data)
    except: return jsonify([])


@integrations_bp.route("/api/bling/sync/categories", methods=["POST"])
def bling_sync_categories():
    from bling_erp import listar_categorias, get_access_token, get_auth_url
    token = get_access_token()
    if not token: return jsonify({"count": 0, "errors": ["Bling nao autenticado"]})
    r = listar_categorias()
    if r.get("error"): return jsonify({"count": 0, "errors": [r["error"]]})
    dados = r.get("data", [])
    async def _go():
        from core import get_db
        db = await get_db()
        total = 0
        for cat in dados:
            try:
                cid = cat.get("id")
                nome = cat.get("descricao", "")
                if cid and nome:
                    await db.execute("""INSERT INTO bling_categorias (bling_id, nome)
                        VALUES ($1,$2) ON CONFLICT (bling_id) DO UPDATE SET nome=$2""", cid, nome)
                    total += 1
            except: pass
        return total
    try:
        from core import run_async
        count = run_async(_go())
        return jsonify({"count": count, "errors": []})
    except: return jsonify({"count": len(dados), "errors": []})


@integrations_bp.route("/api/bling/categories", methods=["GET"])
def bling_categories():
    import json
    async def _go():
        from core import get_db
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS bling_categorias (
            id SERIAL PRIMARY KEY, bling_id BIGINT UNIQUE, nome VARCHAR(200),
            created_at TIMESTAMP DEFAULT NOW())""")
        rows = await db.fetch("SELECT id, bling_id, nome FROM bling_categorias ORDER BY nome")
        return [dict(r) for r in rows]
    try:
        from core import run_async
        data = run_async(_go())
        return jsonify(data)
    except: return jsonify([])


# --- Test endpoints ---

@integrations_bp.route("/api/test/bling", methods=["GET"])
def test_bling():
    from bling_erp import status
    return jsonify(status())


@integrations_bp.route("/api/test/shopee", methods=["GET"])
def test_shopee():
    from core.config import get_config
    config = {
        "partner_id": get_config("shopee", "partner_id"),
        "shop_id": get_config("shopee", "shop_id"),
        "api_key": get_config("shopee", "api_key"),
    }
    configurado = all(config.values())
    return jsonify({
        "configurado": configurado,
        "campos_preenchidos": sum(1 for v in config.values() if v),
        "total_campos": 3,
    })


@integrations_bp.route("/api/test/telegram", methods=["GET"])
def test_telegram():
    from core.config import get_config
    token = get_config("telegram", "token")
    webhook_url = get_config("telegram", "webhook_url")
    return jsonify({
        "configurado": bool(token),
        "webhook_url": webhook_url,
        "token_prefixo": token[:10] + "***" if token else "",
    })


@integrations_bp.route("/api/test/whatsapp", methods=["GET"])
def test_whatsapp():
    from core.config import get_config
    return jsonify({
        "configurado": bool(get_config("whatsapp", "api_key")) or bool(os.environ.get("EVOLUTION_API_KEY")),
    })


# ── Bling API v2 (new bling_bp) ──

from bling_erp import (
    status as bling_status_fn, get_auth_url, exchange_code,
    listar_produtos, listar_produtos_agrupados, criar_produto, atualizar_produto, deletar_produto,
    atualizar_situacao_produtos,
    listar_depositos, obter_saldo_deposito, atualizar_estoque_deposito,
    listar_pedidos, listar_contas_receber, listar_notas_fiscais,
    get_nfe_detail, get_nfe_xml,
    listar_contatos, get_contato, listar_categorias, get_categoria,
    get_pedido_detalhe, listar_contas_pagar, listar_formas_pagamento,
    resumo_vendas, sincronizar_produtos, sincronizar_pedidos,
    listar_webhooks, criar_webhook, deletar_webhook,
    listar_notificacoes, confirmar_leitura_notificacao,
)

bling_bp = Blueprint("bling_api", __name__, url_prefix="/api/bling")


@bling_bp.route("/status")
def api_status():
    return jsonify(bling_status_fn())


@bling_bp.route("/auth")
def api_auth():
    url = get_auth_url()
    return jsonify({"url": url})


@bling_bp.route("/oauth/callback")
def api_oauth_callback():
    code = request.args.get("code", "")
    if not code:
        return jsonify({"error": "Parâmetro 'code' ausente"}), 400
    result = exchange_code(code)
    return jsonify(result)


@bling_bp.route("/produtos")
def api_produtos():
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_produtos(pagina, limite))



@bling_bp.route("/produtos/agrupados")
def api_produtos_agrupados():
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_produtos_agrupados(pagina, limite))

@bling_bp.route("/produtos", methods=["POST"])
def api_criar_produto():
    dados = request.get_json(silent=True) or {}
    return jsonify(criar_produto(dados))


@bling_bp.route("/produtos/<int:id_produto>", methods=["PUT"])
def api_atualizar_produto(id_produto):
    dados = request.get_json(silent=True) or {}
    return jsonify(atualizar_produto(id_produto, dados))


@bling_bp.route("/produtos/<int:id_produto>", methods=["DELETE"])
def api_deletar_produto(id_produto):
    return jsonify(deletar_produto(id_produto))


@bling_bp.route("/produtos/situacoes", methods=["POST"])
def api_situacao_produtos():
    dados = request.get_json(silent=True) or {}
    ids = dados.get("ids", [])
    situacao = dados.get("situacao", "A")
    return jsonify(atualizar_situacao_produtos(ids, situacao))


@bling_bp.route("/produtos/sincronizar", methods=["POST"])
def api_sincronizar_produtos():
    return jsonify(sincronizar_produtos())


@bling_bp.route("/depositos")
def api_depositos():
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_depositos(pagina, limite))


@bling_bp.route("/estoque/<int:id_deposito>")
def api_saldo_deposito(id_deposito):
    ids = request.args.getlist("idsProdutos[]")
    return jsonify(obter_saldo_deposito(id_deposito, ids if ids else None))


@bling_bp.route("/estoque", methods=["PUT"])
def api_atualizar_estoque():
    dados = request.get_json(silent=True) or {}
    return jsonify(atualizar_estoque_deposito(dados))


@bling_bp.route("/vendas")
def api_pedidos():
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_pedidos(pagina, limite))


@bling_bp.route("/vendas/sincronizar", methods=["POST"])
def api_sincronizar_pedidos():
    return jsonify(sincronizar_pedidos())


@bling_bp.route("/vendas/resumo")
def api_resumo_vendas():
    dias = request.args.get("dias", 30, type=int)
    return jsonify(resumo_vendas(dias))



@bling_bp.route("/contatos")
def api_contatos():
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    tipo = request.args.get("tipo", "")
    return jsonify(listar_contatos(pagina, limite, tipo))

@bling_bp.route("/contatos/<int:id_contato>")
def api_contato_detalhe(id_contato):
    return jsonify(get_contato(id_contato))

@bling_bp.route("/categorias")
def api_categorias():
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_categorias(pagina, limite))

@bling_bp.route("/categorias/<int:id_categoria>")
def api_categoria_detalhe(id_categoria):
    return jsonify(get_categoria(id_categoria))

@bling_bp.route("/vendas/<int:id_pedido>")
def api_pedido_detalhe(id_pedido):
    return jsonify(get_pedido_detalhe(id_pedido))

@bling_bp.route("/financeiro/contas-pagar")
def api_contas_pagar():
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    situacao = request.args.get("situacao", "")
    return jsonify(listar_contas_pagar(pagina, limite, situacao))

@bling_bp.route("/formas-pagamento")
def api_formas_pagamento():
    return jsonify(listar_formas_pagamento())


@bling_bp.route("/financeiro/contas-receber")
def api_contas_receber():
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_contas_receber(pagina, limite))


@bling_bp.route("/financeiro/notas-fiscais")
def api_notas_fiscais():
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_notas_fiscais(pagina, limite))

@bling_bp.route("/financeiro/notas-fiscais/<int:id_nota>")
def api_nfe_detail(id_nota):
    return jsonify(get_nfe_detail(id_nota))

@bling_bp.route("/financeiro/notas-fiscais/<int:id_nota>/xml")
def api_nfe_xml(id_nota):
    xml_content, content_type = get_nfe_xml(id_nota)
    if not xml_content:
        return jsonify({"error": "XML não encontrado ou acesso negado"}), 404
    from flask import Response
    return Response(xml_content, mimetype=content_type or "application/xml",
                    headers={"Content-Disposition": f"attachment; filename=nfe-{id_nota}.xml"})

@bling_bp.route("/financeiro/notas-fiscais/<int:id_nota>/danfe")
def api_nfe_danfe(id_nota):
    """Redireciona para o DANFE no site do Bling."""
    r = get_nfe_detail(id_nota)
    data = r.get("data", {})
    danfe_url = data.get("linkDanfe", "")
    if not danfe_url:
        return jsonify({"error": "DANFE não disponível"}), 404
    from flask import redirect
    return redirect(danfe_url)


@bling_bp.route("/webhooks")
def api_webhooks():
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_webhooks(pagina, limite))


@bling_bp.route("/webhooks", methods=["POST"])
def api_criar_webhook():
    dados = request.get_json(silent=True) or {}
    evento = dados.get("evento", "")
    url = dados.get("url", "")
    if not evento or not url:
        return jsonify({"error": "evento e url são obrigatórios"}), 400
    return jsonify(criar_webhook(evento, url))


@bling_bp.route("/webhooks/<int:id_webhook>", methods=["DELETE"])
def api_deletar_webhook(id_webhook):
    return jsonify(deletar_webhook(id_webhook))


@bling_bp.route("/notificacoes")
def api_notificacoes():
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_notificacoes(pagina, limite))


@bling_bp.route("/notificacoes/<int:id_notificacao>", methods=["PATCH"])
def api_confirmar_notificacao(id_notificacao):
    return jsonify(confirmar_leitura_notificacao(id_notificacao))
