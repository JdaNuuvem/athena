p = r"D:\JORGE CHARME E LEON\SISTEMAS\N8N AUTOMACOES\hermes_agents\bling_erp.py"
c = open(p, encoding="utf-8").read()

new_sync = '''def sincronizar_produtos() -> dict:
    """Sync completo: produtos + hierarquia pai/filho + atributos de variacao."""
    try:
        async def _go():
            db = await get_db()
            total = 0; erros = []; pagina = 1; id_to_sku = {}; filhos_pendentes = []

            # ── Passo 1: sync base + mapa de IDs ──
            while True:
                r = listar_produtos(pagina=pagina, limite=100)
                dados = r.get("data", [])
                if not dados or r.get("error"):
                    if r.get("error"): erros.append(f"pag {pagina}: {r['error']}")
                    break
                for p in dados:
                    try:
                        sku = p.get("codigo", "") or str(p["id"])
                        bid = p.get("id")
                        nome = p.get("descricao", "") or p.get("nome", "")
                        preco = float(p.get("preco", 0)) if p.get("preco") else 0
                        formato = p.get("formato", "")
                        id_pai = p.get("idProdutoPai")

                        # Registrar no mapa id->sku
                        if bid: id_to_sku[bid] = sku

                        # Upsert fichas_tecnicas
                        await db.execute("INSERT INTO fichas_tecnicas (sku, descricao) VALUES ($1, $2) ON CONFLICT (sku) DO NOTHING", sku, nome)
                        # Upsert catalogo_produtos (agora com id_bling, imagem_url, situacao)
                        imagem = p.get("imagemURL") or p.get("urlImagem") or ""
                        if not imagem and isinstance(p.get("imagem"), dict):
                            imagem = (p["imagem"] or {}).get("link") or ""
                        await db.execute(
                            "INSERT INTO catalogo_produtos (sku, descricao, id_bling, imagem_url, situacao) VALUES ($1, $2, $3, $4, 'A') ON CONFLICT (sku) DO UPDATE SET descricao = $2, id_bling = $3, imagem_url = COALESCE($4, catalogo_produtos.imagem_url)",
                            sku, nome, bid, imagem)
                        # Upsert anuncios
                        await db.execute("INSERT INTO anuncios (sku, marketplace, preco, status) VALUES ($1, 'bling', $2, 'ativo') ON CONFLICT (sku, marketplace) DO UPDATE SET preco = $2, status = 'ativo'", sku, preco)

                        # Coletar filhos para resolucao posterior
                        if id_pai:
                            filhos_pendentes.append({"sku": sku, "idPai": id_pai})
                        total += 1
                    except Exception as e:
                        log(AGENT, f"Erro produto {p.get('codigo')}: {e}")
                if len(dados) < 100:
                    break
                pagina += 1

            # ── Passo 2: resolver hierarquia pai/filho ──
            pais_resolvidos = 0
            for f in filhos_pendentes:
                pai_sku = id_to_sku.get(f["idPai"])
                if pai_sku:
                    await db.execute("UPDATE catalogo_produtos SET sku_pai = $1 WHERE sku = $2", pai_sku, f["sku"])
                    pais_resolvidos += 1

            # ── Passo 3: buscar atributos de variacao (pais com formato V) ──
            atributos_buscados = 0
            pais_formato_v = await db.fetch("SELECT DISTINCT sku_pai, sku FROM catalogo_produtos WHERE sku_pai IS NOT NULL AND sku_pai IN (SELECT sku FROM catalogo_produtos)")
            # Buscar pais unicos
            pais_set = set()
            for row in (pais_formato_v or []):
                pais_set.add(row["sku_pai"])
            
            import requests as req
            import time as t
            for pai_sku in pais_set:
                # Encontrar id_bling do pai
                pai_row = await db.fetchrow("SELECT id_bling FROM catalogo_produtos WHERE sku = $1 AND id_bling IS NOT NULL", pai_sku)
                if not pai_row: continue
                bid = pai_row["id_bling"]
                for attempt in range(3):
                    try:
                        detail = req.get(f"{BASE_URL}/produtos/{bid}", headers=_bling_headers(), timeout=20)
                        if detail.status_code == 429:
                            t.sleep(2 ** attempt)
                            continue
                        if detail.status_code != 200:
                            break
                        detail_data = detail.json().get("data", {})
                        variacoes = detail_data.get("variacoes", [])
                        for v in variacoes:
                            var_data = v.get("variacao", {}) if isinstance(v, dict) else {}
                            nome_var = var_data.get("nome", "") if isinstance(var_data, dict) else ""
                            var_prod = v.get("produto", {}) if isinstance(v, dict) else {}
                            filho_sku = var_prod.get("codigo", "") if isinstance(var_prod, dict) else ""
                            if filho_sku and nome_var:
                                await db.execute("UPDATE catalogo_produtos SET atributo = $1 WHERE sku = $2", nome_var, filho_sku)
                                atributos_buscados += 1
                        break
                    except Exception:
                        if attempt < 2:
                            t.sleep(2 ** attempt)
                        else:
                            erros.append(f"Atributos falhou para pai {pai_sku} apos 3 tentativas")

            return {"sincronizados": total, "pais_resolvidos": pais_resolvidos, "atributos_buscados": atributos_buscados, "erros": erros}

        return run_async(_go())
    except Exception as e:
        import traceback
        log(AGENT, f"FATAL sincronizar_produtos: {e}\\n{traceback.format_exc()}")
        return {"sincronizados": 0, "erro": str(e)}
'''

def _bling_headers():
    token = get_access_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Replace old function
old_start = c.index("def sincronizar_produtos() -> dict:")
old_end = c.index("def sincronizar_pedidos() -> dict:", old_start)
c = c[:old_start] + new_sync + "\n" + c[old_end:]

with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write(c)
print(f"Sync updated: {len(c)} bytes")