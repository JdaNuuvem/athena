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
    configurado, get_items, get_item_base_info,
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
        details = get_item_base_info(ids, loja_id=loja_id)
        for d in details.get("response", {}).get("item_list", []):
            try:
                s = d.get("stock_info_v2", {}).get("summary_info", {}) or {}
                price_info = (d.get("price_info") or [{}])[0] or {}
                agora = datetime.now()
                # Upsert em anuncios (tabela do AG-03) — shop_id permite o mesmo SKU em varias lojas Shopee
                await db.execute("""
                    INSERT INTO anuncios (sku, marketplace, shop_id, anuncio_id, titulo, preco, status, ultima_atualizacao)
                    VALUES ($1, 'shopee', $2, $3::text, $4, $5, $6, $7)
                    ON CONFLICT (sku, marketplace, shop_id)
                    DO UPDATE SET anuncio_id = $3, titulo = $4, preco = $5, status = $6, ultima_atualizacao = $7
                """, d.get("item_sku", str(d["item_id"])), shop_id, str(d["item_id"]),
                    d.get("item_name", ""), price_info.get("current_price", 0),
                    d.get("item_status", "NORMAL").lower(), agora)
                # Inserir/atualizar em fichas_tecnicas
                await db.execute("""
                    INSERT INTO fichas_tecnicas (sku, descricao) VALUES ($1, $2)
                    ON CONFLICT (sku) DO NOTHING
                """, d.get("item_sku", str(d["item_id"])), d.get("item_name", ""))
                total += 1
            except Exception as e:
                erros.append(f"item {d.get('item_id')}: {e}")
        offset = resp.get("next_offset", 0)
        if not resp.get("has_next_page"):
            break
    await db.execute("UPDATE shopee_sync_log SET status='concluido', itens_processados=$1, erro=$2, concluido_em=NOW() WHERE id=$3",
                     total, json.dumps(erros[:20]) if erros else None, log_id)
    return {"total": total, "erros": len(erros), "detalhes_erros": erros[:5]}

async def sync_pedidos(dias: int = 30, loja_id: int = None) -> dict:
    await _init_tables()
    db = await get_db()
    log_id = await db.fetchval("INSERT INTO shopee_sync_log (tipo, status) VALUES ('pedidos', 'executando') RETURNING id")
    total = 0
    erros = []
    now = int(time.time())
    for status in ["READY_TO_SHIP", "PROCESSED", "SHIPPED", "COMPLETED"]:
        r = get_orders_by_time_range(now - dias * 86400, now, [status], 100, loja_id=loja_id)
        orders = r.get("response", {}).get("order_list", [])
        for o in orders:
            try:
                items = o.get("items", [])
                receita = float(o.get("total_amount", 0))
                data_criacao = datetime.fromtimestamp(o.get("create_time", now))
                sku = (items[0] or {}).get("item_sku", "") if items else ""
                marketplace_fee = receita * 0.12
                # Inserir em vendas (tabela do AG-02)
                for item in items:
                    qtd = item.get("model_quantity_purchased", 1)
                    preco_item = float(item.get("model_original_price", 0) or 0)
                    loja_param = loja_id if loja_id else None
                    if loja_param is None:
                        shop_id_cfg = get_shopee_config(loja_id).get("shop_id") or ""
                        if shop_id_cfg:
                            row = await db.fetchval("SELECT id FROM lojas WHERE shopee_shop_id = $1 LIMIT 1", shop_id_cfg)
                            loja_param = row if row else None
                    await db.execute("""
                        INSERT INTO vendas (data, sku, marketplace, loja_id, quantidade, preco_venda, receita_bruta,
                            taxa_marketplace_pct, taxa_marketplace_valor, frete, impostos)
                        VALUES ($1, $2, 'shopee', $3, $4, $5, $6, 12.0, $7, 0, 0)
                    """, data_criacao.date(), sku or str(o.get("order_sn", "")),
                        loja_param, qtd, preco_item, preco_item * qtd, preco_item * qtd * 0.12)
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
