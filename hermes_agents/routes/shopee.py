import psycopg2
import psycopg2.extras
import time
import calendar
from datetime import date

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
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_auth_url
        sandbox = request.args.get("sandbox", "").lower() == "true"
        loja_id = request.args.get("loja_id", type=int)
        url = get_auth_url(sandbox=sandbox, loja_id=loja_id)
        if not url:
            return jsonify({"error": "Partner ID nao configurado"}), 400
        return jsonify({"url": url})
    return _handler()

@shopee_bp.route('/lojas', methods=['GET'])
def shopee_listar_lojas():
    from core.lojas import listar_lojas_shopee
    return jsonify({"lojas": listar_lojas_shopee()})

@shopee_bp.route('/lojas/<int:loja_id>/conectar', methods=['POST'])
def shopee_conectar_loja(loja_id):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler(loja_id):
        from shopee import get_auth_url
        sandbox = (request.json or {}).get("sandbox", False) if request.is_json else False
        url = get_auth_url(sandbox=sandbox, loja_id=loja_id)
        if not url:
            return jsonify({"error": "Partner ID nao configurado"}), 400
        return jsonify({"url": url})
    return _handler(loja_id=loja_id)

@shopee_bp.route('/lojas/<int:loja_id>/renovar-token', methods=['POST'])
def shopee_renovar_token(loja_id):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler(loja_id):
        from shopee import refresh_shopee_token
        try:
            return jsonify(refresh_shopee_token(loja_id=loja_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler(loja_id=loja_id)

@shopee_bp.route('/lojas/<int:loja_id>', methods=['DELETE'])
def shopee_desconectar_loja(loja_id):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler(loja_id):
        from core.lojas import desconectar_shopee
        return jsonify(desconectar_shopee(loja_id))
    return _handler(loja_id=loja_id)

@shopee_bp.route('/sync-log', methods=['GET'])
def shopee_sync_log():
    from shopee_sync import status_ultimo_sync
    return jsonify({"log": status_ultimo_sync()})

@shopee_bp.route('/produtos-sincronizados', methods=['GET'])
def shopee_produtos_sincronizados():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee_sync import listar_produtos_sincronizados
        loja_id = request.args.get("loja_id", type=int)
        if not loja_id:
            return jsonify({"error": "loja_id obrigatorio"}), 400
        return jsonify({"produtos": listar_produtos_sincronizados(loja_id)})
    return _handler()

@shopee_bp.route('/pedidos', methods=['GET'])
def shopee_listar_pedidos():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import listar_pedidos_shopee_detalhado
        loja_id = request.args.get("loja_id", type=int)
        dias = request.args.get("dias", 7, type=int)
        status = request.args.get("status") or None
        try:
            return jsonify(listar_pedidos_shopee_detalhado(dias, loja_id=loja_id, status=status))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/pedidos-sincronizados', methods=['GET'])
def shopee_pedidos_sincronizados():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee_sync import listar_pedidos_sincronizados
        loja_id = request.args.get("loja_id", type=int)
        if not loja_id:
            return jsonify({"error": "loja_id obrigatorio"}), 400
        status = request.args.get("status") or None
        busca = request.args.get("busca") or None
        pagina = request.args.get("pagina", 1, type=int)
        return jsonify(listar_pedidos_sincronizados(loja_id, status=status, busca=busca, pagina=pagina))
    return _handler()

@shopee_bp.route('/pedidos-sincronizados/estatisticas', methods=['GET'])
def shopee_pedidos_estatisticas():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee_sync import estatisticas_pedidos_sincronizados
        loja_id = request.args.get("loja_id", type=int)
        if not loja_id:
            return jsonify({"error": "loja_id obrigatorio"}), 400
        dias = request.args.get("dias", 90, type=int)
        return jsonify(estatisticas_pedidos_sincronizados(loja_id, dias=dias))
    return _handler()

@shopee_bp.route('/pedidos/sincronizar', methods=['POST'])
def shopee_sincronizar_pedidos_detalhado():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee_sync import sync_pedidos_shopee
        data = request.json or {}
        loja_id = data.get("loja_id")
        dias = data.get("dias", 30)
        return jsonify(sync_pedidos_shopee(dias=dias, loja_id=loja_id))
    return _handler()

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
            # shopee_sync.py grava o item_status real da Shopee em minusculo
            # ("normal", "unlist", "banned" — nunca "ativo"); o filtro errado
            # fazia "Anuncios ativos" sempre mostrar 0 mesmo com produtos sincronizados.
            cur.execute("""
                SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE status = 'normal') AS ativos,
                       COUNT(*) FILTER (WHERE status = 'unlist') AS pausados, COUNT(*) FILTER (WHERE status = 'banned') AS banidos
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
            cur.execute("""
                SELECT COALESCE(SUM(receita_bruta),0) AS receita, COALESCE(SUM(quantidade),0) AS unidades,
                       COUNT(DISTINCT COALESCE(shopee_order_sn, id::text)) AS pedidos
                FROM vendas WHERE marketplace = 'shopee' AND loja_id = %s AND data = CURRENT_DATE
            """, (l["id"],))
            hoje_row = cur.fetchone() or {}
            receita_hoje = float(hoje_row.get("receita") or 0)
            pedidos_hoje = int(hoje_row.get("pedidos") or 0)
            token_expira = l.get("shopee_token_expira_em")
            resultado.append({
                "loja_id": l["id"], "nome": l["nome"], "shop_id": shop_id,
                "tem_token": l.get("tem_token", False),
                "shopee_token_expira_em": token_expira.isoformat() if token_expira else None,
                "receita": float(vendas_row.get("receita") or 0),
                "unidades_vendidas": int(vendas_row.get("unidades") or 0),
                "skus_vendidos": int(vendas_row.get("skus_vendidos") or 0),
                "anuncios_total": int(anuncios_row.get("total") or 0),
                "anuncios_ativos": int(anuncios_row.get("ativos") or 0),
                "anuncios_pausados": int(anuncios_row.get("pausados") or 0),
                "anuncios_banidos": int(anuncios_row.get("banidos") or 0),
                "produtos_estoque_baixo": estoque_baixo,
                "receita_hoje": receita_hoje,
                "unidades_hoje": int(hoje_row.get("unidades") or 0),
                "pedidos_hoje": pedidos_hoje,
                "ticket_medio_hoje": round(receita_hoje / pedidos_hoje, 2) if pedidos_hoje else 0.0,
            })

        cur.execute("""
            SELECT data AS dia, COALESCE(SUM(receita_bruta),0) AS receita,
                   COUNT(DISTINCT COALESCE(shopee_order_sn, id::text)) AS pedidos
            FROM vendas WHERE marketplace = 'shopee' AND data >= CURRENT_DATE - %s
            GROUP BY data ORDER BY data
        """, (dias,))
        serie_diaria = [{"dia": r["dia"].isoformat(), "receita": float(r["receita"] or 0), "pedidos": int(r["pedidos"] or 0)} for r in (cur.fetchall() or [])]

        cur.execute("""
            SELECT v.sku, COALESCE(c.descricao, v.sku) AS descricao,
                   SUM(v.quantidade) AS quantidade, SUM(v.receita_bruta) AS receita
            FROM vendas v LEFT JOIN catalogo_produtos c ON c.sku = v.sku
            WHERE v.marketplace = 'shopee' AND v.data = CURRENT_DATE
            GROUP BY v.sku, c.descricao ORDER BY quantidade DESC LIMIT 8
        """)
        top_produtos_hoje = [{"sku": r["sku"], "descricao": r["descricao"], "quantidade": int(r["quantidade"] or 0), "receita": float(r["receita"] or 0)} for r in (cur.fetchall() or [])]

        cur.execute("""
            SELECT v.sku, COALESCE(c.descricao, v.sku) AS descricao, SUM(v.quantidade) AS vendidos,
                   COALESCE(e.estoque_total, 0) AS estoque_atual, c.estoque_minimo
            FROM vendas v
            JOIN catalogo_produtos c ON c.sku = v.sku
            LEFT JOIN (SELECT sku, SUM(quantidade) AS estoque_total FROM estoque_lojas GROUP BY sku) e ON e.sku = v.sku
            WHERE v.marketplace = 'shopee' AND v.data >= CURRENT_DATE - %s AND c.estoque_minimo IS NOT NULL
            GROUP BY v.sku, c.descricao, e.estoque_total, c.estoque_minimo
            HAVING COALESCE(e.estoque_total, 0) <= c.estoque_minimo
            ORDER BY SUM(v.quantidade) DESC LIMIT 10
        """, (dias,))
        def _dias_ate_ruptura(vendidos, estoque_atual, dias):
            if vendidos <= 0:
                return None
            velocidade_diaria = vendidos / dias
            return round(estoque_atual / velocidade_diaria, 1) if velocidade_diaria > 0 else None

        estoque_risco = [{
            "sku": r["sku"], "descricao": r["descricao"], "vendidos": int(r["vendidos"] or 0),
            "estoque_atual": int(r["estoque_atual"] or 0), "estoque_minimo": int(r["estoque_minimo"] or 0),
            "dias_ate_ruptura": _dias_ate_ruptura(int(r["vendidos"] or 0), int(r["estoque_atual"] or 0), dias),
        } for r in (cur.fetchall() or [])]

        shop_ids = [l.get("shopee_shop_id") for l in lojas if l.get("shopee_shop_id")]
        funil_fulfillment = {"total": 0, "sem_bling": 0, "sem_nota": 0, "nao_despachado": 0}
        if shop_ids:
            cur.execute("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE bling_pedido_id IS NULL) AS sem_bling,
                       COUNT(*) FILTER (WHERE bling_nota_fiscal_id IS NULL) AS sem_nota,
                       COUNT(*) FILTER (WHERE despachado_em IS NULL) AS nao_despachado
                FROM shopee_pedidos_sincronizados
                WHERE shop_id = ANY(%s) AND create_time >= NOW() - (INTERVAL '1 day' * %s)
            """, (shop_ids, dias))
            funil_row = cur.fetchone() or {}
            funil_fulfillment = {
                "total": int(funil_row.get("total") or 0),
                "sem_bling": int(funil_row.get("sem_bling") or 0),
                "sem_nota": int(funil_row.get("sem_nota") or 0),
                "nao_despachado": int(funil_row.get("nao_despachado") or 0),
            }

        # Mesma taxa/logica de comissao usada em core/relatorios.py::ranking_produtos
        # (SHOPEE_COMISSAO_PCT) — duplicada aqui pra nao acoplar routes/shopee.py a
        # core/relatorios.py so' por uma constante.
        SHOPEE_COMISSAO_PCT = 12

        cur.execute("""
            SELECT COALESCE(SUM(v.receita_bruta),0) AS receita,
                   COALESCE(SUM(v.quantidade * COALESCE(c.preco_custo,0)),0) AS custo
            FROM vendas v LEFT JOIN catalogo_produtos c ON c.sku = v.sku
            WHERE v.marketplace = 'shopee' AND v.data >= CURRENT_DATE - %s
        """, (dias,))
        lucro_row = cur.fetchone() or {}
        receita_periodo = float(lucro_row.get("receita") or 0)
        custo_periodo = float(lucro_row.get("custo") or 0)
        lucro_periodo = round(receita_periodo - (receita_periodo * SHOPEE_COMISSAO_PCT / 100.0) - custo_periodo, 2)

        cur.execute("""
            SELECT COALESCE(SUM(receita_bruta),0) AS receita, COALESCE(SUM(quantidade),0) AS unidades
            FROM vendas
            WHERE marketplace = 'shopee' AND data >= CURRENT_DATE - (%s * 2) AND data < CURRENT_DATE - %s
        """, (dias, dias))
        anterior_row = cur.fetchone() or {}
        periodo_anterior = {"receita": float(anterior_row.get("receita") or 0), "unidades": int(anterior_row.get("unidades") or 0)}

        cancelamentos = {"total": 0, "cancelados": 0, "devolucao": 0, "taxa_cancelamento_pct": 0.0, "taxa_devolucao_pct": 0.0}
        if shop_ids:
            cur.execute("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status IN ('CANCELLED','IN_CANCEL')) AS cancelados,
                       COUNT(*) FILTER (WHERE status = 'TO_RETURN') AS devolucao
                FROM shopee_pedidos_sincronizados
                WHERE shop_id = ANY(%s) AND create_time >= NOW() - (INTERVAL '1 day' * %s)
            """, (shop_ids, dias))
            canc_row = cur.fetchone() or {}
            total_canc = int(canc_row.get("total") or 0)
            cancelados = int(canc_row.get("cancelados") or 0)
            devolucao = int(canc_row.get("devolucao") or 0)
            cancelamentos = {
                "total": total_canc, "cancelados": cancelados, "devolucao": devolucao,
                "taxa_cancelamento_pct": round(cancelados / total_canc * 100, 1) if total_canc else 0.0,
                "taxa_devolucao_pct": round(devolucao / total_canc * 100, 1) if total_canc else 0.0,
            }

        hoje = date.today()
        dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]
        cur.execute("""
            SELECT COALESCE(SUM(receita_bruta),0) AS receita
            FROM vendas WHERE marketplace = 'shopee' AND data >= DATE_TRUNC('month', CURRENT_DATE)::date
        """)
        receita_mes = float((cur.fetchone() or {}).get("receita") or 0)
        projecao_mes = round(receita_mes / hoje.day * dias_no_mes, 2) if hoje.day > 0 else 0.0

        cur.execute("""
            SELECT v.sku, COALESCE(c.descricao, v.sku) AS descricao, SUM(v.quantidade) AS quantidade,
                   SUM(v.receita_bruta) AS receita,
                   SUM(v.receita_bruta) - SUM(v.receita_bruta * %s / 100.0) - SUM(v.quantidade * COALESCE(c.preco_custo,0)) AS lucro
            FROM vendas v LEFT JOIN catalogo_produtos c ON c.sku = v.sku
            WHERE v.marketplace = 'shopee' AND v.data >= CURRENT_DATE - %s
            GROUP BY v.sku, c.descricao ORDER BY receita DESC LIMIT 15
        """, (SHOPEE_COMISSAO_PCT, dias))
        ranking_periodo = [{
            "sku": r["sku"], "descricao": r["descricao"], "quantidade": int(r["quantidade"] or 0),
            "receita": float(r["receita"] or 0), "lucro": round(float(r["lucro"] or 0), 2),
        } for r in (cur.fetchall() or [])]

        cur.execute("""
            SELECT a.sku, a.titulo, a.preco, a.estoque
            FROM anuncios a
            WHERE a.marketplace = 'shopee' AND a.status = 'normal' AND a.estoque > 0
              AND NOT EXISTS (
                SELECT 1 FROM vendas v WHERE v.sku = a.sku AND v.marketplace = 'shopee' AND v.data >= CURRENT_DATE - %s
              )
            ORDER BY a.estoque DESC LIMIT 15
        """, (dias,))
        produtos_parados = [{"sku": r["sku"], "titulo": r["titulo"], "preco": float(r["preco"] or 0), "estoque": int(r["estoque"] or 0)} for r in (cur.fetchall() or [])]

        cur.close(); conn.close()
        return jsonify({
            "lojas": resultado, "dias": dias,
            "serie_diaria": serie_diaria,
            "top_produtos_hoje": top_produtos_hoje,
            "estoque_risco": estoque_risco,
            "lucro_periodo": lucro_periodo,
            "periodo_anterior": periodo_anterior,
            "cancelamentos": cancelamentos,
            "projecao_mes": projecao_mes,
            "ranking_periodo": ranking_periodo,
            "produtos_parados": produtos_parados,
            "funil_fulfillment": funil_fulfillment,
        })
    except Exception as e:
        return jsonify({"error": str(e), "lojas": [], "serie_diaria": [], "top_produtos_hoje": [], "estoque_risco": [],
                         "funil_fulfillment": {"total": 0, "sem_bling": 0, "sem_nota": 0, "nao_despachado": 0},
                         "lucro_periodo": 0.0, "periodo_anterior": {"receita": 0.0, "unidades": 0},
                         "cancelamentos": {"total": 0, "cancelados": 0, "devolucao": 0, "taxa_cancelamento_pct": 0.0, "taxa_devolucao_pct": 0.0},
                         "projecao_mes": 0.0, "ranking_periodo": [], "produtos_parados": []})

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
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
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
    return _handler()

@shopee_bp.route('/consistencia-precos', methods=['GET'])
def shopee_consistencia_precos():
    """Compara o preco de um SKU com o mesmo SKU em OUTRAS lojas Shopee da propria conta
    (nao com concorrentes externos — a API da Shopee nao expoe isso)."""
    from shopee import analisar_consistencia_precos
    sku = request.args.get("sku", "")
    preco = float(request.args.get("preco", 0))
    loja_id = request.args.get("loja_id", type=int)
    if not sku:
        return jsonify({"error": "SKU obrigatorio"}), 400
    return jsonify(analisar_consistencia_precos(sku, preco, loja_id=loja_id))

@shopee_bp.route('/sugestao-kits', methods=['GET'])
def shopee_sugestao_kits():
    from shopee import sugerir_kits
    dias = request.args.get("dias", 90, type=int)
    min_oc = request.args.get("min", 3, type=int)
    return jsonify({"data": sugerir_kits(dias, min_oc)})

@shopee_bp.route('/produtos/<int:item_id>/preco', methods=['POST'])
def shopee_atualizar_preco(item_id):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
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
    return _handler()

@shopee_bp.route('/produtos/<int:item_id>/variacoes', methods=['GET'])
def shopee_variacoes_produto(item_id):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_model_list
        loja_id = request.args.get("loja_id", type=int)
        try:
            return jsonify(get_model_list(item_id, loja_id=loja_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/produtos/<sku>/estoque', methods=['PUT'])
def shopee_atualizar_estoque_produto(sku):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
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
    return _handler()

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
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import sincronizar_categorias
        data = request.json or {}
        return jsonify(sincronizar_categorias(data.get("loja_id")))
    return _handler()

@shopee_bp.route('/categorias/<int:category_id>/atributos', methods=['GET'])
def shopee_categoria_atributos(category_id):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
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
    return _handler()

@shopee_bp.route('/categorias/<int:category_id>/marcas', methods=['GET'])
def shopee_categoria_marcas(category_id):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_brand_list
        loja_id = request.args.get("loja_id", type=int)
        r = get_brand_list(category_id, loja_id=loja_id)
        resp = r.get("response", {})
        return jsonify({"marcas": resp.get("brand_list", []), "obrigatorio": resp.get("is_mandatory", False), "erro": r.get("error") or None})
    return _handler()

@shopee_bp.route('/logistica/canais', methods=['GET'])
def shopee_logistica_canais():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
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
    return _handler()

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
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
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
    return _handler()

@shopee_bp.route('/produtos/<int:item_id>', methods=['GET'])
def shopee_detalhe_produto(item_id):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
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
    return _handler()

@shopee_bp.route('/produtos/<int:item_id>', methods=['PUT'])
def shopee_editar_produto(item_id):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import update_item
        data = request.json or {}
        loja_id = data.pop("loja_id", None)
        if loja_id is None:
            return jsonify({"error": "loja_id e obrigatorio"}), 400
        return jsonify(update_item(item_id, data, loja_id=int(loja_id)))
    return _handler()

@shopee_bp.route('/produtos/<int:item_id>', methods=['DELETE'])
def shopee_deletar_produto(item_id):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import delete_item_shopee
        loja_id = request.args.get("loja_id", type=int)
        return jsonify(delete_item_shopee(item_id, loja_id=loja_id))
    return _handler()

@shopee_bp.route('/produtos/<int:item_id>/unlist', methods=['POST'])
def shopee_unlist_produto(item_id):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import unlist_item
        data = request.json or {}
        loja_id = data.get("loja_id")
        unlist = data.get("unlist", True)
        return jsonify(unlist_item([item_id], unlist=unlist, loja_id=loja_id))
    return _handler()

@shopee_bp.route('/produtos/<int:item_id>/clonar-para-loja', methods=['POST'])
def shopee_clonar_produto_para_loja(item_id):
    from shopee import clonar_item_para_loja
    from core.rbac import requer_permissao

    @requer_permissao("produtos.criar")
    def _handler():
        data = request.json or {}
        origem_loja_id = data.get("origem_loja_id")
        destino_loja_id = data.get("destino_loja_id")
        if origem_loja_id is None or destino_loja_id is None:
            return jsonify({"error": "origem_loja_id e destino_loja_id sao obrigatorios"}), 400
        try:
            return jsonify(clonar_item_para_loja(item_id, int(origem_loja_id), int(destino_loja_id)))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()

@shopee_bp.route('/produtos/<sku>/duplicar', methods=['POST'])
def shopee_duplicar_produto(sku):
    from core.catalogo import duplicar
    from core.rbac import requer_permissao

    @requer_permissao("produtos.criar")
    def _handler():
        data = request.json or {}
        novo_sku = (data.get("novo_sku") or "").strip()
        if not novo_sku:
            return jsonify({"error": "novo_sku e obrigatorio"}), 400
        resultado = duplicar(sku, novo_sku)
        if resultado.get("error"):
            status = 409 if "ja existe" in resultado["error"].lower() else 400
            return jsonify(resultado), status
        try:
            from core.seguranca import auditar_alteracao
            auditar_alteracao("criar", "produtos", "catalogo_produtos", resultado.get("id"), dados_depois={"sku": novo_sku, "duplicado_de": sku})
        except Exception:
            pass
        return jsonify({"success": True, "produto": resultado}), 201

    return _handler()

# ===========================================================================
# Variacoes (tier_variation / model) — criar produto com cor/tamanho etc.
# ===========================================================================

@shopee_bp.route('/produtos/<int:item_id>/variacoes', methods=['POST'])
def shopee_criar_variacoes_produto(item_id):
    """Cria a estrutura de variacao (tiers + modelos) de um item ja publicado
    sem variacao — so' pode ser chamado 1x por item (ver init_tier_variation)."""
    from shopee import init_tier_variation
    from core.rbac import requer_permissao, requer_acesso_loja

    @requer_acesso_loja
    @requer_permissao("produtos.criar")
    def _handler():
        data = request.json or {}
        loja_id = data.get("loja_id")
        tier_variation = data.get("tier_variation")
        model_list = data.get("model_list")
        if loja_id is None:
            return jsonify({"error": "loja_id e obrigatorio"}), 400
        if not tier_variation or not model_list:
            return jsonify({"error": "tier_variation e model_list sao obrigatorios"}), 400
        try:
            return jsonify(init_tier_variation(item_id, tier_variation, model_list, loja_id=int(loja_id)))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()

@shopee_bp.route('/produtos/<int:item_id>/variacoes/adicionar', methods=['POST'])
def shopee_adicionar_variacao_produto(item_id):
    """Adiciona novo(s) modelo(s) a um item que ja tem tier_variation definida."""
    from shopee import add_model
    from core.rbac import requer_permissao, requer_acesso_loja

    @requer_acesso_loja
    @requer_permissao("produtos.criar")
    def _handler():
        data = request.json or {}
        loja_id = data.get("loja_id")
        model_list = data.get("model_list")
        if loja_id is None:
            return jsonify({"error": "loja_id e obrigatorio"}), 400
        if not model_list:
            return jsonify({"error": "model_list e obrigatorio"}), 400
        try:
            return jsonify(add_model(item_id, model_list, loja_id=int(loja_id)))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()

@shopee_bp.route('/produtos/<int:item_id>/variacoes', methods=['PUT'])
def shopee_atualizar_variacoes_produto(item_id):
    """Adiciona/remove/reordena as opcoes de um tier existente, preservando os
    model_id ja criados (model_list mapeia tier_index -> model_id)."""
    from shopee import update_tier_variation
    from core.rbac import requer_permissao, requer_acesso_loja

    @requer_acesso_loja
    @requer_permissao("produtos.editar")
    def _handler():
        data = request.json or {}
        loja_id = data.get("loja_id")
        tier_variation = data.get("tier_variation")
        model_list = data.get("model_list")
        if loja_id is None:
            return jsonify({"error": "loja_id e obrigatorio"}), 400
        if not tier_variation or not model_list:
            return jsonify({"error": "tier_variation e model_list sao obrigatorios"}), 400
        try:
            return jsonify(update_tier_variation(item_id, tier_variation, model_list, loja_id=int(loja_id)))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()

@shopee_bp.route('/produtos/<int:item_id>/variacoes', methods=['DELETE'])
def shopee_remover_variacao_produto(item_id):
    """Remove uma ou mais variacoes (models) de um item."""
    from shopee import delete_model
    from core.rbac import requer_permissao

    @requer_permissao("produtos.editar")
    def _handler():
        data = request.json or {}
        loja_id = data.get("loja_id")
        model_id_list = data.get("model_id_list")
        if loja_id is None:
            return jsonify({"error": "loja_id e obrigatorio"}), 400
        if not model_id_list:
            return jsonify({"error": "model_id_list e obrigatorio"}), 400
        try:
            # A Shopee so' aceita 1 model_id por chamada (delete_model.model_id
            # e' singular) — a rota aceita uma lista por conveniencia do
            # cliente e faz 1 chamada por model_id.
            resultados = [{"model_id": mid, **delete_model(item_id, mid, loja_id=int(loja_id))} for mid in model_id_list]
            erros = [r for r in resultados if r.get("error")]
            return jsonify({"resultados": resultados, "sucesso": len(resultados) - len(erros), "total": len(resultados)})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()


# ===========================================================================
# Account Health — saude da loja (100% leitura)
# ===========================================================================

@shopee_bp.route('/saude/performance', methods=['GET'])
def shopee_saude_performance():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_shop_performance
        loja_id = request.args.get("loja_id", type=int)
        try:
            return jsonify(get_shop_performance(loja_id=loja_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/saude/metrica/<int:metric_id>', methods=['GET'])
def shopee_saude_metrica(metric_id):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_metric_source_detail
        loja_id = request.args.get("loja_id", type=int)
        page_no = request.args.get("page_no", 1, type=int)
        page_size = request.args.get("page_size", 20, type=int)
        try:
            return jsonify(get_metric_source_detail(metric_id, page_no=page_no, page_size=page_size, loja_id=loja_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/saude/penalidades', methods=['GET'])
def shopee_saude_penalidades():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_penalty_point_history
        loja_id = request.args.get("loja_id", type=int)
        page_no = request.args.get("page_no", 1, type=int)
        page_size = request.args.get("page_size", 10, type=int)
        violation_type = request.args.get("violation_type", type=int)
        try:
            return jsonify(get_penalty_point_history(page_no=page_no, page_size=page_size, violation_type=violation_type, loja_id=loja_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/saude/punicoes', methods=['GET'])
def shopee_saude_punicoes():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_punishment_history
        loja_id = request.args.get("loja_id", type=int)
        punishment_status = request.args.get("punishment_status", 1, type=int)
        page_no = request.args.get("page_no", 1, type=int)
        page_size = request.args.get("page_size", 10, type=int)
        try:
            return jsonify(get_punishment_history(punishment_status, page_no=page_no, page_size=page_size, loja_id=loja_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/saude/anuncios-com-problema', methods=['GET'])
def shopee_saude_listagens():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_listings_with_issues
        loja_id = request.args.get("loja_id", type=int)
        page_no = request.args.get("page_no", 1, type=int)
        page_size = request.args.get("page_size", 20, type=int)
        try:
            return jsonify(get_listings_with_issues(page_no=page_no, page_size=page_size, loja_id=loja_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/saude/pedidos-atrasados', methods=['GET'])
def shopee_saude_pedidos_atrasados():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_late_orders
        loja_id = request.args.get("loja_id", type=int)
        page_no = request.args.get("page_no", 1, type=int)
        page_size = request.args.get("page_size", 20, type=int)
        try:
            return jsonify(get_late_orders(page_no=page_no, page_size=page_size, loja_id=loja_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()


# ===========================================================================
# Logistics — etiqueta de envio e rastreio
# ===========================================================================

@shopee_bp.route('/logistica/parametro-envio', methods=['GET'])
def shopee_logistica_parametro_envio():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_shipping_parameter
        loja_id = request.args.get("loja_id", type=int)
        order_sn = request.args.get("order_sn", "")
        package_number = request.args.get("package_number")
        if not order_sn:
            return jsonify({"error": "order_sn e obrigatorio"}), 400
        try:
            return jsonify(get_shipping_parameter(order_sn, loja_id=loja_id, package_number=package_number))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/logistica/despachar', methods=['POST'])
def shopee_logistica_despachar():
    """Aciona coleta/dropoff/postagem REAL — irreversivel (a Shopee rejeita
    'ja despachado' se chamado 2x pro mesmo pacote)."""
    from shopee import mass_ship_order
    from core.rbac import requer_permissao, requer_acesso_loja

    @requer_acesso_loja
    @requer_permissao("produtos.editar")
    def _handler():
        data = request.json or {}
        loja_id = data.get("loja_id")
        package_list = data.get("package_list")
        if loja_id is None:
            return jsonify({"error": "loja_id e obrigatorio"}), 400
        if not package_list:
            return jsonify({"error": "package_list e obrigatorio"}), 400
        try:
            return jsonify(mass_ship_order(
                package_list, loja_id=int(loja_id),
                logistics_channel_id=data.get("logistics_channel_id"),
                product_location_id=data.get("product_location_id"),
            ))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()

@shopee_bp.route('/logistica/numero-rastreio', methods=['GET'])
def shopee_logistica_numero_rastreio():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_tracking_number
        loja_id = request.args.get("loja_id", type=int)
        order_sn = request.args.get("order_sn", "")
        package_number = request.args.get("package_number")
        if not order_sn:
            return jsonify({"error": "order_sn e obrigatorio"}), 400
        try:
            return jsonify(get_tracking_number(order_sn, loja_id=loja_id, package_number=package_number))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/logistica/parametro-documento', methods=['POST'])
def shopee_logistica_parametro_documento():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_shipping_document_parameter
        data = request.json or {}
        loja_id = data.get("loja_id")
        order_list = data.get("order_list")
        if loja_id is None or not order_list:
            return jsonify({"error": "loja_id e order_list sao obrigatorios"}), 400
        try:
            return jsonify(get_shipping_document_parameter(order_list, loja_id=int(loja_id)))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/logistica/criar-documento', methods=['POST'])
def shopee_logistica_criar_documento():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import create_shipping_document
        data = request.json or {}
        loja_id = data.get("loja_id")
        order_list = data.get("order_list")
        if loja_id is None or not order_list:
            return jsonify({"error": "loja_id e order_list sao obrigatorios"}), 400
        try:
            return jsonify(create_shipping_document(order_list, loja_id=int(loja_id), shipping_document_type=data.get("shipping_document_type")))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/logistica/status-documento', methods=['POST'])
def shopee_logistica_status_documento():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_shipping_document_result
        data = request.json or {}
        loja_id = data.get("loja_id")
        order_list = data.get("order_list")
        if loja_id is None or not order_list:
            return jsonify({"error": "loja_id e order_list sao obrigatorios"}), 400
        try:
            return jsonify(get_shipping_document_result(order_list, loja_id=int(loja_id)))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/logistica/baixar-documento', methods=['POST'])
def shopee_logistica_baixar_documento():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import download_shipping_document
        data = request.json or {}
        loja_id = data.get("loja_id")
        order_list = data.get("order_list")
        if loja_id is None or not order_list:
            return jsonify({"error": "loja_id e order_list sao obrigatorios"}), 400
        try:
            r = download_shipping_document(order_list, loja_id=int(loja_id))
            if r.get("error"):
                return jsonify(r), 400
            from flask import Response
            return Response(r["content"], mimetype=r.get("content_type", "application/pdf"))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/logistica/rastreio', methods=['GET'])
def shopee_logistica_rastreio():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_tracking_info
        loja_id = request.args.get("loja_id", type=int)
        order_sn = request.args.get("order_sn", "")
        package_number = request.args.get("package_number")
        if not order_sn:
            return jsonify({"error": "order_sn e obrigatorio"}), 400
        try:
            return jsonify(get_tracking_info(order_sn, loja_id=loja_id, package_number=package_number))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()


# ===========================================================================
# Fulfillment — vincula pedido Shopee ao pedido/NF-e do Bling, despacho fica
# registrado apos as rotas de logistica acima confirmarem sucesso
# ===========================================================================

@shopee_bp.route('/pedidos/<order_sn>/fulfillment', methods=['GET'])
def shopee_fulfillment_status(order_sn):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from core.shopee_fulfillment import status_fulfillment
        loja_id = request.args.get("loja_id", type=int)
        if not loja_id:
            return jsonify({"erro": "loja_id e obrigatorio"}), 400
        resultado = status_fulfillment(order_sn, loja_id)
        return jsonify(resultado), (404 if "nao encontrado" in resultado.get("erro", "") else 400 if resultado.get("erro") else 200)
    return _handler()

@shopee_bp.route('/pedidos/<order_sn>/vincular-bling', methods=['POST'])
def shopee_fulfillment_vincular_bling(order_sn):
    from core.rbac import requer_permissao, requer_acesso_loja
    @requer_acesso_loja
    @requer_permissao("produtos.editar")
    def _handler():
        from core.shopee_fulfillment import vincular_pedido_bling
        data = request.json or {}
        loja_id = data.get("loja_id")
        if not loja_id:
            return jsonify({"erro": "loja_id e obrigatorio"}), 400
        id_pedido_bling = data.get("id_pedido_bling")
        resultado = vincular_pedido_bling(order_sn, int(loja_id), id_pedido_bling=int(id_pedido_bling) if id_pedido_bling else None)
        return jsonify(resultado), (400 if resultado.get("erro") else 200)
    return _handler()

@shopee_bp.route('/pedidos/<order_sn>/emitir-nota', methods=['POST'])
def shopee_fulfillment_emitir_nota(order_sn):
    """Emite a NF-e no Bling — acao fiscal, nao reversivel pelo painel."""
    from core.rbac import requer_permissao, requer_acesso_loja
    @requer_acesso_loja
    @requer_permissao("produtos.editar")
    def _handler():
        from core.shopee_fulfillment import emitir_nota_fiscal
        data = request.json or {}
        loja_id = data.get("loja_id")
        if not loja_id:
            return jsonify({"erro": "loja_id e obrigatorio"}), 400
        resultado = emitir_nota_fiscal(order_sn, int(loja_id))
        return jsonify(resultado), (400 if resultado.get("erro") else 200)
    return _handler()

@shopee_bp.route('/pedidos/<order_sn>/nota-pdf', methods=['GET'])
def shopee_fulfillment_nota_pdf(order_sn):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from core.shopee_fulfillment import baixar_nota_pdf
        loja_id = request.args.get("loja_id", type=int)
        if not loja_id:
            return jsonify({"erro": "loja_id e obrigatorio"}), 400
        conteudo, content_type = baixar_nota_pdf(order_sn, loja_id)
        if not conteudo:
            return jsonify({"erro": "PDF da nota nao disponivel — emita a nota fiscal antes"}), 404
        from flask import Response
        return Response(conteudo, mimetype=content_type or "application/pdf")
    return _handler()

@shopee_bp.route('/pedidos/<order_sn>/despachar-confirmar', methods=['POST'])
def shopee_fulfillment_despachar_confirmar(order_sn):
    """So' registra que o despacho aconteceu — chame DEPOIS que
    /logistica/despachar (mass_ship_order) confirmar sucesso."""
    from core.rbac import requer_permissao, requer_acesso_loja
    @requer_acesso_loja
    @requer_permissao("produtos.editar")
    def _handler():
        from core.shopee_fulfillment import marcar_despachado
        data = request.json or {}
        loja_id = data.get("loja_id")
        if not loja_id:
            return jsonify({"erro": "loja_id e obrigatorio"}), 400
        resultado = marcar_despachado(order_sn, int(loja_id), package_number=data.get("package_number"))
        return jsonify(resultado), (400 if resultado.get("erro") else 200)
    return _handler()


# ===========================================================================
# Discount — desconto por item com janela de tempo
# ===========================================================================

@shopee_bp.route('/descontos', methods=['GET'])
def shopee_listar_descontos():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_discount_list
        loja_id = request.args.get("loja_id", type=int)
        status = request.args.get("status", "all")
        page_no = request.args.get("page_no", 1, type=int)
        page_size = request.args.get("page_size", 50, type=int)
        try:
            return jsonify(get_discount_list(status, page_no=page_no, page_size=page_size, loja_id=loja_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/descontos/<int:discount_id>', methods=['GET'])
def shopee_detalhe_desconto(discount_id):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_discount
        loja_id = request.args.get("loja_id", type=int)
        page_no = request.args.get("page_no", 1, type=int)
        page_size = request.args.get("page_size", 50, type=int)
        try:
            return jsonify(get_discount(discount_id, page_no=page_no, page_size=page_size, loja_id=loja_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/descontos', methods=['POST'])
def shopee_criar_desconto():
    from shopee import add_discount
    from core.rbac import requer_permissao, requer_acesso_loja

    @requer_acesso_loja
    @requer_permissao("produtos.criar")
    def _handler():
        data = request.json or {}
        loja_id = data.get("loja_id")
        discount_name = data.get("discount_name", "")
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        if loja_id is None or not discount_name or not start_time or not end_time:
            return jsonify({"error": "loja_id, discount_name, start_time e end_time sao obrigatorios"}), 400
        try:
            return jsonify(add_discount(discount_name, int(start_time), int(end_time), loja_id=int(loja_id)))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()

@shopee_bp.route('/descontos/<int:discount_id>/itens', methods=['POST'])
def shopee_adicionar_item_desconto(discount_id):
    from shopee import add_discount_item
    from core.rbac import requer_permissao, requer_acesso_loja

    @requer_acesso_loja
    @requer_permissao("produtos.criar")
    def _handler():
        data = request.json or {}
        loja_id = data.get("loja_id")
        item_list = data.get("item_list")
        if loja_id is None or not item_list:
            return jsonify({"error": "loja_id e item_list sao obrigatorios"}), 400
        try:
            return jsonify(add_discount_item(discount_id, item_list, loja_id=int(loja_id)))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()

@shopee_bp.route('/descontos/<int:discount_id>', methods=['PUT'])
def shopee_atualizar_desconto(discount_id):
    from shopee import update_discount
    from core.rbac import requer_permissao, requer_acesso_loja

    @requer_acesso_loja
    @requer_permissao("produtos.editar")
    def _handler():
        data = request.json or {}
        loja_id = data.get("loja_id")
        if loja_id is None:
            return jsonify({"error": "loja_id e obrigatorio"}), 400
        try:
            return jsonify(update_discount(
                discount_id, loja_id=int(loja_id), discount_name=data.get("discount_name"),
                start_time=data.get("start_time"), end_time=data.get("end_time"),
            ))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()

@shopee_bp.route('/descontos/<int:discount_id>/itens', methods=['PUT'])
def shopee_atualizar_item_desconto(discount_id):
    from shopee import update_discount_item
    from core.rbac import requer_permissao, requer_acesso_loja

    @requer_acesso_loja
    @requer_permissao("produtos.editar")
    def _handler():
        data = request.json or {}
        loja_id = data.get("loja_id")
        item_list = data.get("item_list")
        if loja_id is None or not item_list:
            return jsonify({"error": "loja_id e item_list sao obrigatorios"}), 400
        try:
            return jsonify(update_discount_item(discount_id, item_list, loja_id=int(loja_id)))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()

@shopee_bp.route('/descontos/<int:discount_id>', methods=['DELETE'])
def shopee_deletar_desconto(discount_id):
    """So' funciona em desconto 'upcoming'. Irreversivel."""
    from shopee import delete_discount
    from core.rbac import requer_permissao, requer_acesso_loja

    @requer_acesso_loja
    @requer_permissao("produtos.editar")
    def _handler():
        loja_id = request.args.get("loja_id", type=int)
        if loja_id is None:
            return jsonify({"error": "loja_id e obrigatorio"}), 400
        try:
            return jsonify(delete_discount(discount_id, loja_id=loja_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()

@shopee_bp.route('/descontos/<int:discount_id>/itens/<int:item_id>', methods=['DELETE'])
def shopee_deletar_item_desconto(discount_id, item_id):
    from shopee import delete_discount_item
    from core.rbac import requer_permissao, requer_acesso_loja

    @requer_acesso_loja
    @requer_permissao("produtos.editar")
    def _handler():
        loja_id = request.args.get("loja_id", type=int)
        model_id = request.args.get("model_id", 0, type=int)
        if loja_id is None:
            return jsonify({"error": "loja_id e obrigatorio"}), 400
        try:
            return jsonify(delete_discount_item(discount_id, item_id, loja_id=loja_id, model_id=model_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()

@shopee_bp.route('/descontos/<int:discount_id>/encerrar', methods=['POST'])
def shopee_encerrar_desconto(discount_id):
    """TERMINAL/IRREVERSIVEL — depois de encerrado, a Shopee nao aceita mais update
    nem delete neste desconto. A UI precisa exigir confirmacao explicita antes de chamar."""
    from shopee import end_discount
    from core.rbac import requer_permissao, requer_acesso_loja

    @requer_acesso_loja
    @requer_permissao("produtos.editar")
    def _handler():
        data = request.json or {}
        loja_id = data.get("loja_id")
        if loja_id is None:
            return jsonify({"error": "loja_id e obrigatorio"}), 400
        try:
            return jsonify(end_discount(discount_id, loja_id=int(loja_id)))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()


# ===========================================================================
# Voucher — cupom de loja/produto
# ===========================================================================

@shopee_bp.route('/vouchers', methods=['GET'])
def shopee_listar_vouchers():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_voucher_list
        loja_id = request.args.get("loja_id", type=int)
        status = request.args.get("status", "all")
        page_no = request.args.get("page_no", 1, type=int)
        page_size = request.args.get("page_size", 20, type=int)
        try:
            return jsonify(get_voucher_list(status, page_no=page_no, page_size=page_size, loja_id=loja_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/vouchers/<int:voucher_id>', methods=['GET'])
def shopee_detalhe_voucher(voucher_id):
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from shopee import get_voucher
        loja_id = request.args.get("loja_id", type=int)
        try:
            return jsonify(get_voucher(voucher_id, loja_id=loja_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return _handler()

@shopee_bp.route('/vouchers', methods=['POST'])
def shopee_criar_voucher():
    from shopee import add_voucher
    from core.rbac import requer_permissao, requer_acesso_loja

    @requer_acesso_loja
    @requer_permissao("produtos.criar")
    def _handler():
        data = request.json or {}
        loja_id = data.get("loja_id")
        campos_obrigatorios = ["voucher_name", "voucher_code", "start_time", "end_time",
                                "voucher_type", "reward_type", "usage_quantity", "min_basket_price"]
        faltando = [c for c in campos_obrigatorios if data.get(c) in (None, "")]
        if loja_id is None or faltando:
            return jsonify({"error": f"loja_id e obrigatorio; campos faltando: {faltando}" if faltando else "loja_id e obrigatorio"}), 400
        try:
            return jsonify(add_voucher(
                data["voucher_name"], data["voucher_code"], int(data["start_time"]), int(data["end_time"]),
                int(data["voucher_type"]), int(data["reward_type"]), int(data["usage_quantity"]),
                float(data["min_basket_price"]), loja_id=int(loja_id),
                discount_amount=data.get("discount_amount"), percentage=data.get("percentage"),
                max_price=data.get("max_price"), display_channel_list=data.get("display_channel_list"),
                item_id_list=data.get("item_id_list"), display_start_time=data.get("display_start_time"),
            ))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()

@shopee_bp.route('/vouchers/<int:voucher_id>', methods=['PUT'])
def shopee_atualizar_voucher(voucher_id):
    from shopee import update_voucher
    from core.rbac import requer_permissao, requer_acesso_loja

    @requer_acesso_loja
    @requer_permissao("produtos.editar")
    def _handler():
        data = request.json or {}
        loja_id = data.get("loja_id")
        if loja_id is None:
            return jsonify({"error": "loja_id e obrigatorio"}), 400
        try:
            campos = {k: v for k, v in data.items() if k != "loja_id"}
            return jsonify(update_voucher(voucher_id, loja_id=int(loja_id), **campos))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()

@shopee_bp.route('/vouchers/<int:voucher_id>/encerrar', methods=['POST'])
def shopee_encerrar_voucher(voucher_id):
    """TERMINAL/IRREVERSIVEL — vira 'expired' pra sempre. A UI precisa exigir
    confirmacao explicita antes de chamar."""
    from shopee import end_voucher
    from core.rbac import requer_permissao, requer_acesso_loja

    @requer_acesso_loja
    @requer_permissao("produtos.editar")
    def _handler():
        data = request.json or {}
        loja_id = data.get("loja_id")
        if loja_id is None:
            return jsonify({"error": "loja_id e obrigatorio"}), 400
        try:
            return jsonify(end_voucher(voucher_id, loja_id=int(loja_id)))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()

@shopee_bp.route('/vouchers/<int:voucher_id>', methods=['DELETE'])
def shopee_deletar_voucher(voucher_id):
    """So' funciona em voucher 'upcoming'. Irreversivel."""
    from shopee import delete_voucher
    from core.rbac import requer_permissao, requer_acesso_loja

    @requer_acesso_loja
    @requer_permissao("produtos.editar")
    def _handler():
        loja_id = request.args.get("loja_id", type=int)
        if loja_id is None:
            return jsonify({"error": "loja_id e obrigatorio"}), 400
        try:
            return jsonify(delete_voucher(voucher_id, loja_id=loja_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()
