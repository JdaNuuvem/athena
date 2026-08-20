import os
import threading
from flask import Blueprint, request, jsonify
from core import get_db, run_async, log
from core.rbac import requer_permissao

integrations_bp = Blueprint("integrations", __name__)

AGENT = "Shopee Sync HTTP"

# Sync completa (produtos + pedidos) pode levar minutos num catalogo grande
# (paginacao da API Shopee) — muito acima do timeout de proxy do Cloudflare
# (~100s, HTTP 524). Roda em background por loja_id e devolve na hora; o
# frontend acompanha via GET /api/shopee/sync-log (shopee_sync_log ja
# registra 'executando'/'concluido'/'erro' por corrida, ver shopee_sync.py).
_sync_em_andamento = set()  # loja_id (int) ou "global" (None) -> sync rodando agora
_sync_lock = threading.Lock()


def _shopee_sync_worker(loja_id):
    from shopee_sync import sync_produtos, sync_pedidos
    chave = loja_id if loja_id is not None else "global"
    try:
        run_async(sync_produtos(loja_id=loja_id))
        run_async(sync_pedidos(loja_id=loja_id))
    except Exception as e:
        log(AGENT, f"Erro na sincronizacao em background (loja_id={loja_id}): {e}")
    finally:
        with _sync_lock:
            _sync_em_andamento.discard(chave)


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
    # Sincroniza produtos/anuncios E pedidos numa tacada so' — antes so'
    # chamava sync_produtos(), entao vendas/receita da Shopee nunca eram
    # gravadas em `vendas` e o Painel Consolidado (dashboard) ficava sempre
    # zerado, mesmo com anuncios sincronizados normalmente.
    #
    # Roda em background (ver _shopee_sync_worker acima): rodar sincrono
    # aqui estourava o timeout de proxy do Cloudflare (HTTP 524) em
    # catalogos grandes — a paginacao da API Shopee sozinha ja passa dos
    # ~100s permitidos. O frontend acompanha o progresso via
    # GET /api/shopee/sync-log.
    loja_id = (request.get_json(silent=True) or {}).get("loja_id")
    chave = loja_id if loja_id is not None else "global"
    with _sync_lock:
        ja_rodando = chave in _sync_em_andamento
        if not ja_rodando:
            _sync_em_andamento.add(chave)
    if not ja_rodando:
        threading.Thread(target=_shopee_sync_worker, args=(loja_id,), daemon=True).start()
    return jsonify({"status": "ja_processando" if ja_rodando else "processando", "loja_id": loja_id})


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


# --- Entidades SSOT: Vincular Clientes / Migrar Fornecedores ---

@integrations_bp.route("/api/integracoes/vincular-clientes", methods=["POST"])
def vincular_clientes():
    """Varre vendas_pedidos e fiscal_notas_fiscais e vincula contatos ao cad_clientes pelo documento."""
    from core.entidades import vincular_cliente_por_documento, migrar_fornecedores_compras
    r_vendas = vincular_cliente_por_documento("vendas_pedidos", 0)
    r_fiscal = vincular_cliente_por_documento("fiscal_notas_fiscais", 0)
    v = r_vendas.get("vinculados", 0) if isinstance(r_vendas, dict) else 0
    f = r_fiscal.get("vinculados", 0) if isinstance(r_fiscal, dict) else 0
    return jsonify({"vinculados": v + f})


@integrations_bp.route("/api/integracoes/migrar-fornecedores", methods=["POST"])
def migrar_fornecedores():
    """Puxa contatos Bling tipo=F e insere em cad_fornecedores, depois migra compras locais."""
    from bling_erp import listar_contatos, get_access_token
    from core import get_db, run_async
    token = get_access_token()
    if not token:
        return jsonify({"error": "Bling não autenticado", "migrados": 0})
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS cad_fornecedores (
            id SERIAL PRIMARY KEY, nome VARCHAR(200), tipo VARCHAR(2) DEFAULT 'PJ',
            documento VARCHAR(30), status VARCHAR(20) DEFAULT 'ativo',
            created_at TIMESTAMP DEFAULT NOW())""")
        total = 0
        for pagina in range(1, 20):
            try:
                r = listar_contatos(pagina=pagina, limite=100, tipo="F")
                dados = r.get("data", [])
                if not dados or r.get("error"):
                    break
                for c in dados:
                    nome = c.get("nome", "")
                    doc = (c.get("numeroDocumento") or "").replace(".","").replace("/","").replace("-","").strip()
                    if not nome:
                        continue
                    try:
                        await db.execute("""INSERT INTO cad_fornecedores (nome, tipo, documento, status)
                            VALUES ($1, 'PJ', $2, 'ativo')
                            ON CONFLICT DO NOTHING""", nome, doc)
                        total += 1
                    except Exception:
                        pass
                if len(dados) < 100:
                    break
            except Exception:
                break
        return total
    try:
        from core import run_async
        bling_count = run_async(_go())
    except Exception:
        bling_count = 0
    # Tambem migra compras locais
    from core.entidades import migrar_fornecedores_compras
    r_local = migrar_fornecedores_compras()
    local_count = r_local.get("migrados", 0) if isinstance(r_local, dict) else 0
    return jsonify({"migrados": bling_count + local_count})


# --- Contas Financeiras SSOT ---

@integrations_bp.route("/api/integracoes/migrar-contas", methods=["POST"])
def migrar_contas():
    """Migra contas a receber e a pagar do Bling → fin_contas_receber / fin_contas_pagar."""
    from core.fiscal import sincronizar_contas_receber_bling, sincronizar_contas_pagar_bling
    cr = sincronizar_contas_receber_bling()
    cp = sincronizar_contas_pagar_bling()
    return jsonify({
        "receber": cr.get("sync", 0),
        "pagar": cp.get("sync", 0),
        "migrados": (cr.get("sync", 0) or 0) + (cp.get("sync", 0) or 0),
    })


@integrations_bp.route("/api/integracoes/backfill-fluxo-caixa", methods=["POST"])
def backfill_fluxo_caixa():
    """Gera fluxo de caixa retroativo pra pedidos Shopee/i9Logic ja
    sincronizados como 'concluido' antes de core.entidades.ao_concluir_venda_avista
    existir — rodar uma vez manualmente apos o deploy que introduziu o hook,
    nao e' um job periodico. Idempotente, seguro rodar mais de uma vez."""
    @requer_permissao("financeiro.criar")
    def _go():
        from core.entidades import backfill_fluxo_caixa_vendas
        return jsonify(backfill_fluxo_caixa_vendas())
    return _go()


@integrations_bp.route("/api/eventos/compra/<int:id_compra>/receber", methods=["POST"])
def receber_compra(id_compra):
    """Registra recebimento de compra no Bling e atualiza estoque local."""
    from bling_erp import _request
    r = _request(f"pedidos/compras/{id_compra}/receber", {}, method="POST")
    return jsonify(r)


@integrations_bp.route("/api/eventos/venda/<int:id_pedido>/cancelar", methods=["POST"])
def cancelar_venda(id_pedido):
    from bling_erp import _request
    r = _request(f"pedidos/vendas/{id_pedido}/cancelar", {}, method="POST")
    return jsonify(r)


@integrations_bp.route("/api/eventos/venda/<int:id_pedido>/estornar", methods=["POST"])
def estornar_venda(id_pedido):
    from bling_erp import _request
    r = _request(f"pedidos/vendas/{id_pedido}/estornar", {}, method="POST")
    return jsonify(r)


@integrations_bp.route("/api/eventos/venda/<int:id_pedido>/rastreio", methods=["POST"])
def enviar_rastreio(id_pedido):
    from bling_erp import _request
    dados = request.get_json(silent=True) or {}
    r = _request(f"pedidos/vendas/{id_pedido}/rastrear", {"codigoRastreamento": dados.get("codigo", "")}, method="POST")
    return jsonify(r)


@integrations_bp.route("/api/eventos/conta/<int:id_conta>/baixar", methods=["POST"])
def baixar_conta(id_conta):
    from bling_erp import _request
    r = _request(f"contas/receber/{id_conta}/baixar", {}, method="POST")
    return jsonify(r)


@integrations_bp.route("/api/eventos/producao/<int:id_op>/finalizar", methods=["POST"])
def finalizar_producao(id_op):
    """Finaliza OP e atualiza estoque."""
    try:
        from ag_04_planejador import registrar_producao_concluida
        r = registrar_producao_concluida(id_op)
        if isinstance(r, dict) and r.get("error"):
            return jsonify(r), 404
        return jsonify(r)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/api/eventos/pdv/<int:id_caixa>/fechar-caixa", methods=["POST"])
def fechar_caixa_pdv(id_caixa):
    """Fecha caixa PDV com saldo final."""
    dados = request.get_json(silent=True) or {}
    from core.pdv import fechar_caixa
    try:
        r = fechar_caixa(
            id_caixa, float(dados.get("saldoFinal", 0) or 0),
            dados.get("operador_id"), dados.get("senha", ""),
            dados.get("gerente_pin_id"), dados.get("pin", ""), dados.get("codigo_barras", ""),
        )
        return jsonify(r)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ponytail: rota duplicada removida (havia outra "/api/eventos/crm/lead/<id>/converter"
# em athena_bridge.py, registrada como a fonte canonica via core.entidades.ao_converter_lead).
# Esta aqui, alem de duplicar a URL (uma delas ficava inalcancavel dependendo da ordem de
# registro dos blueprints), tinha 2 bugs: fazia UPDATE crm_leads SET cliente_id = $1, mas
# crm_leads nunca teve coluna cliente_id (so' empresa_id) — dava erro 500 sempre que o
# INSERT em cad_clientes de fato retornava um id; e o dedupe por ON CONFLICT DO NOTHING nao
# tinha coluna de conflito declarada, entao so' funcionava por acidente se alguma constraint
# unica generica batesse.


# --- Full Sync / Migrar Tudo ---

@integrations_bp.route("/api/eventos/venda/<int:id_pedido>/faturar", methods=["POST"])
def faturar_venda(id_pedido):
    """Gera NF-e no Bling para o pedido."""
    from bling_erp import _request
    r = _request(f"pedidos/vendas/{id_pedido}/gerar-nfe", {}, method="POST")
    return jsonify(r)


@integrations_bp.route("/api/integracoes/migrar-tudo", methods=["POST"])
def migrar_tudo():
    """Orquestra todas as migracoes Bling → SSOT em paralelo."""
    from bling_erp import sincronizar_produtos
    from core.vendas import sincronizar_pedidos_bling
    from core.entidades import vincular_cliente_por_documento, migrar_fornecedores_compras
    from core.fiscal import sincronizar_contas_receber_bling, sincronizar_contas_pagar_bling
    import concurrent.futures
    erros = []
    resultados = {}
    def seguro(fn, nome, *args):
        try:
            r = fn(*args) if args else fn()
            if isinstance(r, dict):
                if r.get("error"):
                    erros.append(f"{nome}: {r['error']}")
                    return 0
                return r.get("sincronizados") or r.get("sync") or r.get("vinculados") or r.get("migrados") or 0
            return 0
        except Exception as e:
            erros.append(f"{nome}: {e}")
            return 0
    # Produtos
    resultados["produtos"] = seguro(sincronizar_produtos, "produtos")
    # Vendas
    resultados["vendas"] = seguro(lambda: sincronizar_pedidos_bling(pagina=1, limite=100), "vendas")
    # Clientes
    r_c = seguro(vincular_cliente_por_documento, "clientes", "vendas_pedidos", 0)
    r_f = seguro(vincular_cliente_por_documento, "clientes_fiscal", "fiscal_notas_fiscais", 0)
    resultados["clientes"] = r_c + r_f
    # Fornecedores
    r_local = seguro(migrar_fornecedores_compras, "fornecedores")
    resultados["fornecedores"] = r_local
    # Contas financeiras
    cr = seguro(sincronizar_contas_receber_bling, "contas_receber")
    cp = seguro(sincronizar_contas_pagar_bling, "contas_pagar")
    resultados["contas"] = cr + cp
    resultados["total_erros"] = len(erros)
    if erros:
        resultados["erros"] = erros
    return jsonify(resultados)


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
    resumo_vendas, sincronizar_produtos,
    listar_webhooks, criar_webhook, deletar_webhook, registrar_webhook,
    listar_notificacoes, confirmar_leitura_notificacao,
)
from core.vendas import sincronizar_pedidos_bling

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
    dados = request.get_json(silent=True) or {}
    return jsonify(sincronizar_pedidos_bling(
        pagina=dados.get("pagina", 1),
        limite=dados.get("limite", 100),
    ))


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
@requer_permissao("financeiro.ver")
def api_contas_pagar():
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    situacao = request.args.get("situacao", "")
    return jsonify(listar_contas_pagar(pagina, limite, situacao))

@bling_bp.route("/formas-pagamento")
def api_formas_pagamento():
    return jsonify(listar_formas_pagamento())


@bling_bp.route("/financeiro/contas-receber")
@requer_permissao("financeiro.ver")
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
    from bling_erp import get_nfe_danfe_url
    danfe_url = get_nfe_danfe_url(id_nota)
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


@bling_bp.route("/webhook/registrar", methods=["POST"])
def api_webhook_registrar():
    """Re-registra o webhook de pedido do Bling apontando pra /webhook/bling.

    Passo operacional pós-deploy (ver plano Task 6, Step 8): usa o default
    inteligente de registrar_webhook(), que já resolve a URL certa e o
    formato JSON esperado pelo Bling, sem exigir que o chamador monte o
    payload manualmente (diferente de POST /api/bling/webhooks).
    """
    dados = request.get_json(silent=True) or {}
    return jsonify(registrar_webhook(dados.get("tipo", "pedido"), dados.get("url")))


@bling_bp.route("/notificacoes")
def api_notificacoes():
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_notificacoes(pagina, limite))


@bling_bp.route("/notificacoes/<int:id_notificacao>", methods=["PATCH"])
def api_confirmar_notificacao(id_notificacao):
    return jsonify(confirmar_leitura_notificacao(id_notificacao))
