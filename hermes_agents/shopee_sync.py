"""
Sync Shopee → Hermes DB (portado do ATHENA shopee-stock-sync.ts)
Busca todos os produtos e pedidos da Shopee via API e insere no PostgreSQL
para os agentes AG-02 (lucratividade) e AG-03 (marketplaces) consumirem.
"""
import sys, os, json, time
from pathlib import Path
from datetime import date, datetime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import log, run_async, get_db, hoje
from shopee import (
    configurado, get_items, get_item_base_info, get_model_list,
    get_orders_by_time_range, get_order_detail, get_shopee_config,
)

AGENT = "Shopee Sync"

async def _init_tables():
    db = await get_db()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS shopee_sync_log (
            id SERIAL PRIMARY KEY, tipo VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL, itens_processados INT DEFAULT 0,
            erro TEXT, iniciado_em TIMESTAMP DEFAULT NOW(), concluido_em TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS shopee_ads_campaigns (
            id SERIAL PRIMARY KEY, campaign_id VARCHAR(100) UNIQUE,
            shop_id VARCHAR(50), nome VARCHAR(300), tipo VARCHAR(50),
            status VARCHAR(20), daily_budget NUMERIC(12,2),
            start_date DATE, end_date DATE, created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS shopee_ads_performance (
            id SERIAL PRIMARY KEY, campaign_id VARCHAR(100) REFERENCES shopee_ads_campaigns(campaign_id),
            data DATE NOT NULL, impressions INT DEFAULT 0, clicks INT DEFAULT 0,
            cost NUMERIC(12,2) DEFAULT 0, orders INT DEFAULT 0, revenue NUMERIC(12,2) DEFAULT 0,
            ctr NUMERIC(6,2) DEFAULT 0, cpc NUMERIC(10,4) DEFAULT 0,
            conversion_rate NUMERIC(6,2) DEFAULT 0, roas NUMERIC(8,2) DEFAULT 0,
            UNIQUE(campaign_id, data)
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS shopee_ads_insights (
            id SERIAL PRIMARY KEY, campaign_id VARCHAR(100), insight_type VARCHAR(50),
            message TEXT, severity VARCHAR(20), confidence NUMERIC(5,2),
            action_taken BOOLEAN DEFAULT false, created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS hermes_execucoes (
            id SERIAL PRIMARY KEY, agente_id VARCHAR(20) NOT NULL,
            action VARCHAR(100), params JSONB, status VARCHAR(20) DEFAULT 'em_execucao',
            resultado JSONB, erro TEXT, inicio_execucao TIMESTAMP DEFAULT NOW(),
            fim_execucao TIMESTAMP, duracao_segundos INT
        )
    """)
    # sync_pedidos rodava puro INSERT sem chave de dedup — cada chamada repetida
    # (clique duplo, retry, chamada manual do endpoint) duplicava a receita da
    # Shopee na tabela 'vendas' (lida pelo Dashboard/KPI e pelo AG-02).
    try:
        await db.execute("ALTER TABLE vendas ADD COLUMN IF NOT EXISTS shopee_order_sn VARCHAR(50)")
    except Exception:
        pass
    try:
        await db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_vendas_shopee_order_sn_sku
            ON vendas (shopee_order_sn, sku) WHERE shopee_order_sn IS NOT NULL""")
    except Exception:
        pass
    # Pedidos sincronizados (nivel de pedido, nao so' item) para a aba Shopee >
    # Pedidos — distinta de 'vendas' (usada pelo AG-02/lucratividade, so' linhas
    # de item sem endereco/pagamento/observacao). Cobre todos os 8 status da
    # Shopee, nao so' os 2 que a busca em tempo real antiga usava por default.
    await db.execute("""
        CREATE TABLE IF NOT EXISTS shopee_pedidos_sincronizados (
            id SERIAL PRIMARY KEY, order_sn VARCHAR(50) NOT NULL, shop_id VARCHAR(50) NOT NULL,
            status VARCHAR(30), create_time TIMESTAMP, update_time TIMESTAMP,
            total_amount NUMERIC(12,2) DEFAULT 0,
            buyer_username VARCHAR(100), recipient_nome VARCHAR(200), recipient_telefone VARCHAR(30),
            recipient_endereco TEXT, recipient_cidade VARCHAR(100), recipient_estado VARCHAR(100), recipient_cep VARCHAR(20),
            forma_pagamento VARCHAR(50), observacao TEXT, prazo_envio TIMESTAMP,
            ultima_sincronizacao TIMESTAMP DEFAULT NOW(),
            UNIQUE(order_sn, shop_id)
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS shopee_pedidos_itens (
            id SERIAL PRIMARY KEY, pedido_id INT REFERENCES shopee_pedidos_sincronizados(id) ON DELETE CASCADE,
            sku VARCHAR(50), nome VARCHAR(200), quantidade INT DEFAULT 0, preco NUMERIC(12,2) DEFAULT 0
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_shopee_pedidos_itens_pedido ON shopee_pedidos_itens (pedido_id)")
    # Fulfillment (emissao de NF-e via Bling + despacho/etiqueta via Shopee) —
    # ver core/shopee_fulfillment.py. package_number pode diferir de order_sn
    # (a Shopee gera 1 por pacote; a maioria dos pedidos tem so' 1 pacote).
    await db.execute("ALTER TABLE shopee_pedidos_sincronizados ADD COLUMN IF NOT EXISTS bling_pedido_id INT")
    await db.execute("ALTER TABLE shopee_pedidos_sincronizados ADD COLUMN IF NOT EXISTS bling_nota_fiscal_id INT")
    await db.execute("ALTER TABLE shopee_pedidos_sincronizados ADD COLUMN IF NOT EXISTS package_number VARCHAR(50)")
    await db.execute("ALTER TABLE shopee_pedidos_sincronizados ADD COLUMN IF NOT EXISTS despachado_em TIMESTAMP")
    # estimated_shipping_fee do get_order_detail — usado pelo sync pra
    # vendas_pedidos (core/vendas.py::sincronizar_pedidos_shopee), que precisa
    # do frete real pro DRE por Loja (sem isso, todo pedido Shopee entrava com
    # frete=0, subestimando custo/superestimando lucro).
    await db.execute("ALTER TABLE shopee_pedidos_sincronizados ADD COLUMN IF NOT EXISTS frete NUMERIC(12,2) DEFAULT 0")

async def _upsert_anuncio(db, shop_id: str, sku: str, anuncio_id: str, titulo: str,
                           preco: float, estoque: int, status: str, agora: datetime,
                           imagem_url: str = None) -> None:
    """Upsert de 1 linha em anuncios (produto simples OU 1 variacao de um produto
    com modelos) + garante a linha correspondente em fichas_tecnicas.

    fichas_tecnicas precisa ser gravado ANTES de anuncios — anuncios.sku tem
    FK pra fichas_tecnicas(sku) (ver sql/schema.sql), e SKU sincronizado pela
    primeira vez ainda nao existe la'."""
    await db.execute("""
        INSERT INTO fichas_tecnicas (sku, descricao) VALUES ($1, $2)
        ON CONFLICT (sku) DO NOTHING
    """, sku, titulo)
    await db.execute("""
        INSERT INTO anuncios (sku, marketplace, shop_id, anuncio_id, titulo, preco, estoque, status, ultima_atualizacao, imagem_url)
        VALUES ($1, 'shopee', $2, $3::text, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (sku, marketplace, shop_id)
        DO UPDATE SET anuncio_id = $3, titulo = $4, preco = $5, estoque = $6, status = $7, ultima_atualizacao = $8, imagem_url = $9
    """, sku, shop_id, anuncio_id, titulo, preco, estoque, status, agora, imagem_url)


async def sync_produtos(loja_id: int = None) -> dict:
    """Sincroniza produtos da Shopee para o catalogo local. loja_id identifica qual conta
    Shopee usar (multiloja); quando omitido, usa a config global legada (loja unica)."""
    await _init_tables()
    db = await get_db()
    shop_id = get_shopee_config(loja_id).get("shop_id") or ""
    log_id = await db.fetchval("INSERT INTO shopee_sync_log (tipo, status) VALUES ('produtos', 'executando') RETURNING id")
    total = 0
    erros = []
    offset = 0
    for pagina in range(50):
        r = get_items("NORMAL", offset, loja_id=loja_id)
        resp = r.get("response", {})
        items = resp.get("item", [])
        if not items:
            break
        ids = [i["item_id"] for i in items]
        # get_item_base_info aceita no maximo 50 IDs por chamada ("value must
        # contain between 1 and 50 items, inclusive") — get_items traz ate 100
        # por pagina, entao precisa fatiar em lotes de 50.
        detalhes = []
        for lote_inicio in range(0, len(ids), 50):
            details = get_item_base_info(ids[lote_inicio:lote_inicio + 50], loja_id=loja_id)
            if details.get("error"):
                erros.append(f"get_item_base_info (lote {lote_inicio}): {details.get('message', details['error'])}")
                continue
            detalhes.extend(details.get("response", {}).get("item_list", []))
        for d in detalhes:
            item_id = d["item_id"]
            item_name = d.get("item_name", "")
            status = d.get("item_status", "NORMAL").lower()
            agora = datetime.now()
            # Shopee guarda a foto no nivel do item pai, nao por variacao — get_model_list
            # nao traz imagem propria do modelo, entao toda variacao usa essa mesma foto.
            imagem_url = ((d.get("image") or {}).get("image_url_list") or [None])[0]
            if d.get("has_model"):
                # Produto com variacao: preco/estoque nao existem no nivel do item
                # (fica 0 em price_info/stock_info_v2) — precisa buscar cada
                # modelo (variacao) via get_model_list, 1 linha em anuncios por SKU.
                # Remove eventual linha orfa do item pai (anuncio_id = item_id puro)
                # gravada por uma sincronizacao anterior a esse suporte a variacao.
                await db.execute(
                    "DELETE FROM anuncios WHERE marketplace='shopee' AND shop_id=$1 AND anuncio_id=$2",
                    shop_id, str(item_id))
                modelos = get_model_list(item_id, loja_id=loja_id)
                if modelos.get("error"):
                    erros.append(f"get_model_list item {item_id}: {modelos.get('message', modelos['error'])}")
                    continue
                for m in modelos.get("response", {}).get("model", []):
                    try:
                        sku = m.get("model_sku") or f"{d.get('item_sku', item_id)}-{m['model_id']}"
                        s = m.get("stock_info_v2", {}).get("summary_info", {}) or {}
                        price_info = (m.get("price_info") or [{}])[0] or {}
                        nome_variacao = m.get("model_name", "")
                        titulo = f"{item_name} - {nome_variacao}" if nome_variacao else item_name
                        await _upsert_anuncio(db, shop_id, sku, f"{item_id}_{m['model_id']}", titulo,
                                               price_info.get("current_price", 0),
                                               s.get("total_available_stock", 0), status, agora, imagem_url)
                        total += 1
                    except Exception as e:
                        erros.append(f"item {item_id} modelo {m.get('model_id')}: {e}")
                continue
            try:
                sku = d.get("item_sku", str(item_id))
                s = d.get("stock_info_v2", {}).get("summary_info", {}) or {}
                price_info = (d.get("price_info") or [{}])[0] or {}
                await _upsert_anuncio(db, shop_id, sku, str(item_id), item_name,
                                       price_info.get("current_price", 0),
                                       s.get("total_available_stock", 0), status, agora, imagem_url)
                total += 1
            except Exception as e:
                erros.append(f"item {item_id}: {e}")
        offset = resp.get("next_offset", 0)
        if not resp.get("has_next_page"):
            break
    await db.execute("UPDATE shopee_sync_log SET status='concluido', itens_processados=$1, erro=$2, concluido_em=NOW() WHERE id=$3",
                     total, json.dumps(erros[:20]) if erros else None, log_id)
    return {"total": total, "erros": len(erros), "detalhes_erros": erros[:5]}

async def sync_pedidos(dias: int = 30, loja_id: int = None) -> dict:
    """order/get_order_list (usado para descobrir quais pedidos existem no
    periodo) so' devolve order_sn/status/create_time — NUNCA item_list nem
    total_amount. O codigo anterior lia o.get("items")/o.get("total_amount")
    direto dessa resposta resumida, que nao tem esses campos: o loop de itens
    nunca rodava e nenhuma linha ia pra `vendas`, mesmo com pedidos reais
    encontrados. Precisa de uma segunda chamada, get_order_detail, pro
    detalhe de fato — mesmo padrao ja usado (e testado) em
    listar_pedidos_shopee_detalhado (shopee/orders.py)."""
    await _init_tables()
    db = await get_db()
    log_id = await db.fetchval("INSERT INTO shopee_sync_log (tipo, status) VALUES ('pedidos', 'executando') RETURNING id")
    total = 0
    erros = []
    now = int(time.time())

    loja_param = loja_id
    if loja_param is None:
        shop_id_cfg = get_shopee_config(loja_id).get("shop_id") or ""
        if shop_id_cfg:
            row = await db.fetchval("SELECT id FROM lojas WHERE shopee_shop_id = $1 LIMIT 1", shop_id_cfg)
            loja_param = row if row else None

    r = get_orders_by_time_range(now - dias * 86400, now,
                                  ["READY_TO_SHIP", "PROCESSED", "SHIPPED", "COMPLETED"], 100, loja_id=loja_id)
    if r.get("error"):
        await db.execute("UPDATE shopee_sync_log SET status='erro', erro=$1, concluido_em=NOW() WHERE id=$2", r["error"], log_id)
        return {"total": 0, "erros": 1, "detalhes_erros": [r["error"]]}
    resumo = (r.get("response", {}) or {}).get("order_list", [])

    for i in range(0, len(resumo), 50):
        lote = resumo[i:i + 50]
        order_sns = [o.get("order_sn") for o in lote if o.get("order_sn")]
        if not order_sns:
            continue
        d = get_order_detail(",".join(order_sns), loja_id=loja_id)
        if d.get("error"):
            erros.append(f"lote {i // 50}: {d['error']}")
            continue
        for o in (d.get("response", {}) or {}).get("order_list", []):
            try:
                order_sn = str(o.get("order_sn", ""))
                data_criacao = datetime.fromtimestamp(o.get("create_time", now))
                # Inserir em vendas (tabela do AG-02) — ON CONFLICT protege contra
                # duplicacao quando o mesmo pedido e' sincronizado mais de uma vez
                # (o range de 'dias' se sobrepoe entre chamadas consecutivas).
                for idx, item in enumerate(o.get("item_list", [])):
                    qtd = item.get("model_quantity_purchased", 1)
                    preco_item = float(item.get("model_discounted_price") or item.get("model_original_price") or 0)
                    item_sku = item.get("item_sku", "") or f"{order_sn}-{idx}"
                    await db.execute("""
                        INSERT INTO vendas (data, sku, marketplace, loja_id, quantidade, preco_venda, receita_bruta,
                            taxa_marketplace_pct, taxa_marketplace_valor, frete, impostos, shopee_order_sn)
                        VALUES ($1, $2, 'shopee', $3, $4, $5, $6, 12.0, $7, 0, 0, $8)
                        ON CONFLICT (shopee_order_sn, sku) WHERE shopee_order_sn IS NOT NULL DO NOTHING
                    """, data_criacao.date(), item_sku,
                        loja_param, qtd, preco_item, preco_item * qtd, preco_item * qtd * 0.12, order_sn)
                total += 1
            except Exception as e:
                erros.append(f"pedido {o.get('order_sn')}: {e}")
    await db.execute("UPDATE shopee_sync_log SET status='concluido', itens_processados=$1, erro=$2, concluido_em=NOW() WHERE id=$3",
                     total, json.dumps(erros[:20]) if erros else None, log_id)
    return {"total": total, "erros": len(erros), "detalhes_erros": erros[:5]}

def sync_all(dias: int = 30, loja_id: int = None) -> dict:
    produtos = run_async(sync_produtos(loja_id))
    pedidos = run_async(sync_pedidos(dias, loja_id))
    return {"produtos": produtos, "pedidos": pedidos}

# Todos os 8 status oficiais da Shopee — a busca em tempo real antiga (usada
# pela aba Pedidos antes desta sincronizacao) so' cobria READY_TO_SHIP e
# PROCESSED por default, escondendo concluidos/cancelados/aguardando pagamento.
STATUS_PEDIDOS = ["UNPAID", "READY_TO_SHIP", "PROCESSED", "SHIPPED", "COMPLETED", "CANCELLED", "IN_CANCEL", "TO_RETURN"]

async def _upsert_pedido(db, shop_id: str, det: dict) -> None:
    """Upsert de 1 pedido completo (cabecalho + itens). det e' 1 entrada do
    response de get_order_detail. Endereco/pagamento/observacao sao best-effort
    contra a documentacao oficial da Shopee v2 — sem endpoint de raw-debug pra
    pedido pra validar ao vivo (diferente do que foi feito pra imagem de
    produto); campo ausente fica vazio/NULL sem quebrar o sync."""
    endereco = det.get("recipient_address") or {}
    order_sn = str(det.get("order_sn", ""))
    row = await db.fetchrow("""
        INSERT INTO shopee_pedidos_sincronizados (
            order_sn, shop_id, status, create_time, update_time, total_amount,
            buyer_username, recipient_nome, recipient_telefone, recipient_endereco,
            recipient_cidade, recipient_estado, recipient_cep, forma_pagamento,
            observacao, prazo_envio, frete, ultima_sincronizacao
        ) VALUES ($1,$2,$3,to_timestamp($4::bigint),to_timestamp($5::bigint),$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,to_timestamp($16::bigint),$17,NOW())
        ON CONFLICT (order_sn, shop_id) DO UPDATE SET
            status=$3, update_time=to_timestamp($5::bigint), total_amount=$6, buyer_username=$7,
            recipient_nome=$8, recipient_telefone=$9, recipient_endereco=$10,
            recipient_cidade=$11, recipient_estado=$12, recipient_cep=$13,
            forma_pagamento=$14, observacao=$15, prazo_envio=to_timestamp($16::bigint), frete=$17,
            ultima_sincronizacao=NOW()
        RETURNING id
    """, order_sn, shop_id, det.get("order_status", ""), det.get("create_time") or None,
        det.get("update_time") or None, float(det.get("total_amount", 0) or 0),
        det.get("buyer_username", ""), endereco.get("name", ""), endereco.get("phone", ""),
        endereco.get("full_address", ""), endereco.get("city", ""), endereco.get("state", ""),
        endereco.get("zipcode", ""), det.get("payment_method", ""), det.get("note", ""),
        det.get("ship_by_date") or None, float(det.get("estimated_shipping_fee", 0) or 0))
    pedido_id = row["id"]
    await db.execute("DELETE FROM shopee_pedidos_itens WHERE pedido_id = $1", pedido_id)
    for item in det.get("item_list", []):
        await db.execute("""
            INSERT INTO shopee_pedidos_itens (pedido_id, sku, nome, quantidade, preco)
            VALUES ($1, $2, $3, $4, $5)
        """, pedido_id, item.get("item_sku", ""), item.get("item_name", ""),
            item.get("model_quantity_purchased", 0),
            float(item.get("model_discounted_price") or item.get("model_original_price") or 0))

def sync_pedidos_shopee(dias: int = 30, loja_id: int = None) -> dict:
    """Sincroniza pedidos com detalhe completo (endereco, pagamento, itens) pra
    tabela local — cobre os 8 status da Shopee, usado pela aba Pedidos em vez
    de bater na API a cada carregamento de tela (mesmo padrao de sync_produtos)."""
    async def _go():
        await _init_tables()
        db = await get_db()
        shop_id = get_shopee_config(loja_id).get("shop_id") or ""
        log_id = await db.fetchval("INSERT INTO shopee_sync_log (tipo, status) VALUES ('pedidos_detalhado', 'executando') RETURNING id")
        total = 0
        erros = []
        now = int(time.time())
        r = get_orders_by_time_range(now - dias * 86400, now, STATUS_PEDIDOS, 100, loja_id=loja_id)
        if r.get("error"):
            erros.append(f"get_orders_by_time_range: {r.get('message', r['error'])}")
        resumo = (r.get("response", {}) or {}).get("order_list", [])
        order_sns = [o.get("order_sn") for o in resumo if o.get("order_sn")]
        for i in range(0, len(order_sns), 50):
            lote = order_sns[i:i + 50]
            d = get_order_detail(",".join(lote), loja_id=loja_id)
            if d.get("error"):
                erros.append(f"get_order_detail lote {i}: {d.get('message', d['error'])}")
                continue
            for det in (d.get("response", {}) or {}).get("order_list", []):
                try:
                    await _upsert_pedido(db, shop_id, det)
                    total += 1
                except Exception as e:
                    erros.append(f"pedido {det.get('order_sn')}: {e}")
        await db.execute("UPDATE shopee_sync_log SET status='concluido', itens_processados=$1, erro=$2, concluido_em=NOW() WHERE id=$3",
                          total, json.dumps(erros[:20]) if erros else None, log_id)
        return {"total": total, "erros": len(erros), "detalhes_erros": erros[:5]}
    try:
        return run_async(_go())
    except Exception as e:
        return {"total": 0, "erros": 1, "detalhes_erros": [str(e)]}

def listar_pedidos_sincronizados(loja_id: int, status: str = None, busca: str = None,
                                  pagina: int = 1, por_pagina: int = 30) -> dict:
    """Pedidos ja sincronizados (tabela shopee_pedidos_sincronizados) pra aba
    Pedidos — filtro/busca/paginacao em SQL local, sem bater na API a cada
    interacao do usuario. busca casa order_sn, nome do destinatario ou SKU/nome
    de algum item do pedido."""
    async def _go():
        db = await get_db()
        shop_id = get_shopee_config(loja_id).get("shop_id") or ""
        if not shop_id:
            return {"pedidos": [], "total": 0, "valor_total": 0, "atrasados": 0}
        where = ["p.shop_id = $1"]
        params = [shop_id]
        if status:
            params.append(status)
            where.append(f"p.status = ${len(params)}")
        if busca:
            params.append(f"%{busca}%")
            idx = len(params)
            where.append(f"""(p.order_sn ILIKE ${idx} OR p.recipient_nome ILIKE ${idx}
                OR EXISTS (SELECT 1 FROM shopee_pedidos_itens i WHERE i.pedido_id = p.id
                           AND (i.sku ILIKE ${idx} OR i.nome ILIKE ${idx})))""")
        where_sql = " AND ".join(where)
        total = await db.fetchval(f"SELECT COUNT(*) FROM shopee_pedidos_sincronizados p WHERE {where_sql}", *params)
        agregado = await db.fetchrow(f"""
            SELECT COALESCE(SUM(total_amount), 0) AS valor_total,
                   COUNT(*) FILTER (WHERE status = 'READY_TO_SHIP' AND prazo_envio IS NOT NULL AND prazo_envio < NOW()) AS atrasados
            FROM shopee_pedidos_sincronizados p WHERE {where_sql}
        """, *params)
        params_pagina = params + [por_pagina, (pagina - 1) * por_pagina]
        rows = await db.fetch(f"""
            SELECT p.* FROM shopee_pedidos_sincronizados p WHERE {where_sql}
            ORDER BY p.create_time DESC LIMIT ${len(params_pagina) - 1} OFFSET ${len(params_pagina)}
        """, *params_pagina)
        pedidos = [dict(r) for r in rows]
        if pedidos:
            ids = [p["id"] for p in pedidos]
            itens_rows = await db.fetch("SELECT * FROM shopee_pedidos_itens WHERE pedido_id = ANY($1::int[])", ids)
            itens_por_pedido = {}
            for it in itens_rows:
                itens_por_pedido.setdefault(it["pedido_id"], []).append(dict(it))
            for p in pedidos:
                p["itens"] = itens_por_pedido.get(p["id"], [])
        return {
            "pedidos": pedidos, "total": total or 0,
            "valor_total": float(agregado["valor_total"]) if agregado else 0,
            "atrasados": agregado["atrasados"] if agregado else 0,
        }
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro listar_pedidos_sincronizados: {e}")
        return {"pedidos": [], "total": 0, "valor_total": 0, "atrasados": 0}

_ESTATISTICAS_VAZIAS = {"por_estado": [], "serie_diaria": [], "por_status": [], "clientes_recorrentes": [], "tempo_medio_despacho_horas": None, "enderecos_mascarados": False}

# A Shopee mascara campos de endereco/nome do destinatario como "****" (protecao
# de dados do comprador via API — nao e' algo que o Hermes decida ou controle);
# buyer_username nao e' mascarado. "~ '^\*+$'" filtra qualquer sequencia de so'
# asteriscos, nao so' o caso exato de 4.
_NAO_MASCARADO = "!~ '^\\*+$'"

def estatisticas_pedidos_sincronizados(loja_id: int, dias: int = 90) -> dict:
    """Agregados pra pagina Pedidos: distribuicao por UF (mapa), serie diaria de
    volume, distribuicao por status, clientes recorrentes (por buyer_username,
    unico campo de identificacao do comprador que a Shopee nao mascara) e tempo
    medio de despacho. Mesma tabela de listar_pedidos_sincronizados acima."""
    async def _go():
        db = await get_db()
        shop_id = get_shopee_config(loja_id).get("shop_id") or ""
        if not shop_id:
            return _ESTATISTICAS_VAZIAS
        por_estado = await db.fetch(f"""
            SELECT UPPER(TRIM(recipient_estado)) AS estado, COUNT(*) AS total, COALESCE(SUM(total_amount),0) AS valor
            FROM shopee_pedidos_sincronizados
            WHERE shop_id = $1 AND create_time >= NOW() - (INTERVAL '1 day' * $2)
              AND recipient_estado IS NOT NULL AND recipient_estado != '' AND recipient_estado {_NAO_MASCARADO}
            GROUP BY UPPER(TRIM(recipient_estado)) ORDER BY total DESC
        """, shop_id, dias)
        total_periodo = await db.fetchval("""
            SELECT COUNT(*) FROM shopee_pedidos_sincronizados
            WHERE shop_id = $1 AND create_time >= NOW() - (INTERVAL '1 day' * $2)
        """, shop_id, dias)
        enderecos_mascarados = total_periodo > 0 and not por_estado
        serie_diaria = await db.fetch("""
            SELECT DATE(create_time) AS dia, COUNT(*) AS total
            FROM shopee_pedidos_sincronizados
            WHERE shop_id = $1 AND create_time >= NOW() - (INTERVAL '1 day' * $2)
            GROUP BY DATE(create_time) ORDER BY dia
        """, shop_id, dias)
        por_status = await db.fetch("""
            SELECT status, COUNT(*) AS total
            FROM shopee_pedidos_sincronizados
            WHERE shop_id = $1 AND create_time >= NOW() - (INTERVAL '1 day' * $2)
            GROUP BY status ORDER BY total DESC
        """, shop_id, dias)
        clientes_recorrentes = await db.fetch(f"""
            SELECT buyer_username AS cliente, COUNT(*) AS total, COALESCE(SUM(total_amount),0) AS valor
            FROM shopee_pedidos_sincronizados
            WHERE shop_id = $1 AND create_time >= NOW() - (INTERVAL '1 day' * $2)
              AND buyer_username IS NOT NULL AND buyer_username != '' AND buyer_username {_NAO_MASCARADO}
            GROUP BY buyer_username HAVING COUNT(*) > 1 ORDER BY total DESC LIMIT 10
        """, shop_id, dias)
        tempo_row = await db.fetchrow("""
            SELECT AVG(EXTRACT(EPOCH FROM (despachado_em - create_time)) / 3600.0) AS horas
            FROM shopee_pedidos_sincronizados
            WHERE shop_id = $1 AND create_time >= NOW() - (INTERVAL '1 day' * $2) AND despachado_em IS NOT NULL
        """, shop_id, dias)
        return {
            "por_estado": [{"estado": r["estado"], "total": r["total"], "valor": float(r["valor"] or 0)} for r in (por_estado or [])],
            "serie_diaria": [{"dia": r["dia"].isoformat(), "total": r["total"]} for r in (serie_diaria or [])],
            "por_status": [{"status": r["status"], "total": r["total"]} for r in (por_status or [])],
            "clientes_recorrentes": [{"cliente": r["cliente"], "total": r["total"], "valor": float(r["valor"] or 0)} for r in (clientes_recorrentes or [])],
            "tempo_medio_despacho_horas": float(tempo_row["horas"]) if tempo_row and tempo_row["horas"] is not None else None,
            "enderecos_mascarados": enderecos_mascarados,
        }
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro estatisticas_pedidos_sincronizados: {e}")
        return _ESTATISTICAS_VAZIAS

def obter_pedido_sincronizado(order_sn: str, shop_id: str) -> dict:
    """1 pedido (com itens) pelo par order_sn/shop_id — usado pelo fulfillment
    (core/shopee_fulfillment.py) pra ler o estado atual (vinculo Bling, nota,
    despacho) antes de cada acao."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "SELECT * FROM shopee_pedidos_sincronizados WHERE order_sn = $1 AND shop_id = $2",
            order_sn, shop_id)
        if not row:
            return None
        pedido = dict(row)
        itens = await db.fetch("SELECT * FROM shopee_pedidos_itens WHERE pedido_id = $1", pedido["id"])
        pedido["itens"] = [dict(i) for i in itens]
        return pedido
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro obter_pedido_sincronizado: {e}")
        return None

_CAMPOS_VINCULO_VALIDOS = {"bling_pedido_id", "bling_nota_fiscal_id", "package_number", "despachado_em"}

def atualizar_vinculo_pedido(order_sn: str, shop_id: str, **campos) -> dict:
    """Grava campos de fulfillment (vinculo Bling, nota emitida, package_number,
    despacho) no pedido ja sincronizado. Whitelist propria (_CAMPOS_VINCULO_VALIDOS)
    porque quem chama isso e' sempre codigo interno (core.shopee_fulfillment),
    nunca dado bruto de request — ainda assim nao concatena chave nao validada."""
    invalidos = set(campos) - _CAMPOS_VINCULO_VALIDOS
    if invalidos:
        return {"erro": f"campos invalidos: {', '.join(sorted(invalidos))}"}
    if not campos:
        return {"erro": "nenhum campo informado"}
    async def _go():
        db = await get_db()
        sets = ", ".join(f"{k} = ${i + 3}" for i, k in enumerate(campos.keys()))
        row = await db.fetchrow(
            f"UPDATE shopee_pedidos_sincronizados SET {sets} WHERE order_sn = $1 AND shop_id = $2 RETURNING *",
            order_sn, shop_id, *campos.values())
        return dict(row) if row else None
    try:
        r = run_async(_go())
        return {"ok": True, "pedido": r} if r else {"erro": "pedido nao encontrado"}
    except Exception as e:
        return {"erro": str(e)}

def listar_produtos_sincronizados(loja_id: int, dias: int = 90) -> list:
    """Produtos ja sincronizados (tabela anuncios) para uma loja Shopee especifica —
    usado pela aba Produtos, sem bater na API da Shopee a cada carregamento de tela.
    `qtd_vendida` soma vendas_itens dessa loja nos ultimos `dias` dias — usado pro
    filtro "mais vendidos" da aba Anuncios em /estoque."""
    async def _go():
        db = await get_db()
        shop_id = get_shopee_config(loja_id).get("shop_id") or ""
        if not shop_id:
            return []
        rows = await db.fetch("""
            SELECT a.sku, a.titulo, a.preco, a.estoque, a.status, a.anuncio_id, a.ultima_atualizacao,
                   COALESCE(a.imagem_url, c.imagem_url) AS imagem_url,
                   COALESCE(vendas.qtd_vendida, 0) AS qtd_vendida
            FROM anuncios a
            LEFT JOIN catalogo_produtos c ON c.sku = a.sku
            LEFT JOIN LATERAL (
                SELECT SUM(vi.quantidade) AS qtd_vendida
                FROM vendas_itens vi
                JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
                WHERE vi.sku = a.sku AND vp.loja_id = $2 AND vp.status != 'cancelado'
                  AND vp.data >= CURRENT_DATE - $3::int
            ) vendas ON TRUE
            WHERE a.marketplace = 'shopee' AND a.shop_id = $1
            ORDER BY a.titulo
        """, shop_id, loja_id, dias)
        return [dict(r) for r in rows]
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro listar_produtos_sincronizados: {e}")
        return []

def status_ultimo_sync() -> dict:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM shopee_sync_log ORDER BY id DESC LIMIT 10")
        return [dict(r) for r in rows]
    return run_async(_go())

if __name__ == "__main__":
    log(AGENT, f"Configurado: {configurado()}")
    if configurado():
        log(AGENT, "Iniciando sync...")
        print(sync_all())
