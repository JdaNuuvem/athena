"""
Shopee Replication — transfer products between stores.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core import log, run_async, get_db
from .auth import configurado
from .products import add_item, get_items, get_item_base_info
from .images import upload_image
from .pricing import calcular_margem_produto
from .concorrencia import analisar_consistencia_precos

AGENT = "AG-03 | Shopee Replication"


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

                # verificar margem ANTES de publicar — pula o item se sairia com prejuizo
                # (nao apenas avisa depois, ja publicado, como antes)
                margem = calcular_margem_produto(sku, float(preco), loja_id=destino_loja_id)
                if not margem["ok"]:
                    resultados["erros"].append(f"Item #{item_id} ({sku}) NAO publicado — {margem['mensagem']}")
                    resultados["pulados"] += 1
                    continue

                estoque_origem = item.get("stock_info_v2", {}).get("summary_info", {}).get("total_available_stock", 0)

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
                    "seller_stock": [{"stock": int(estoque_origem)}],
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
                    if margem.get("alerta"):
                        resultados["erros"].append(f"Item #{item_id} ({sku}): publicado, mas {margem['mensagem']}")
                    # verificar consistencia de preco com outras lojas proprias (nao e' concorrencia real)
                    try:
                        consist = analisar_consistencia_precos(sku, preco)
                        if consist.get("alerta"):
                            resultados["erros"].append(f"Item #{item_id} ({sku}): {consist['mensagem']}")
                    except Exception: pass
            except Exception as e:
                resultados["erros"].append(f"Item #{item_id} ({item.get('item_sku','?')}): {e}")

    return resultados
