"""
Integração Bling ERP v3 — OAuth2 + Webhooks
"""
import os, json, time, requests
from urllib.parse import urlencode

from core import log, run_async, get_db
from core.config import get_config, set_config

AGENT = "Bling ERP v3"

def _client_id():
    return os.environ.get("BLING_CLIENT_ID") or get_config("bling", "client_id") or ""

def _client_secret():
    return os.environ.get("BLING_CLIENT_SECRET") or get_config("bling", "client_secret") or ""

BLING_DOMAIN = os.environ.get("BLING_DOMAIN", "athena.zoikom.site")
REDIRECT_URI = f"https://{BLING_DOMAIN}/api/bling/oauth/callback"
BASE_URL = "https://www.bling.com.br/Api/v3"

# ── Token management (persistido no DB) ──
# ponytail: env var > DB config > cache. Sobrevive a restarts.

_TOKEN = {"access": "", "refresh": ""}

def get_access_token() -> str:
    t = os.environ.get("BLING_ACCESS_TOKEN", "")
    if t: return t
    t = _TOKEN["access"]
    if t: return t
    try:
        t = get_config("bling", "access_token") or ""
        if t: _TOKEN["access"] = t
    except: pass
    return t

def set_access_token(token: str):
    _TOKEN["access"] = token
    try: set_config("bling", "access_token", token)
    except: pass

def get_refresh_token() -> str:
    t = os.environ.get("BLING_REFRESH_TOKEN", "")
    if t: return t
    t = _TOKEN["refresh"]
    if t: return t
    try:
        t = get_config("bling", "refresh_token") or ""
        if t: _TOKEN["refresh"] = t
    except: pass
    return t

def set_refresh_token(token: str):
    _TOKEN["refresh"] = token
    try: set_config("bling", "refresh_token", token)
    except: pass

def get_auth_url() -> str:
    params = urlencode({
        "response_type": "code",
        "client_id": _client_id(),
        "redirect_uri": REDIRECT_URI,
        "state": os.urandom(16).hex(),
    })
    return f"{BASE_URL}/oauth/authorize?{params}"

def exchange_code(code: str) -> dict:
    try:
        cid = _client_id()
        csecret = _client_secret()
        auth = requests.auth._basic_auth_str(cid, csecret)
        r = requests.post(f"{BASE_URL}/oauth/token", json={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        }, headers={"Authorization": auth}, timeout=30)
        data = r.json()
        if "access_token" in data:
            set_access_token(data["access_token"])
            set_refresh_token(data.get("refresh_token", ""))
            return {"success": True, "expires_in": data.get("expires_in", 3600)}
        return {"error": data.get("error", "unknown"), "detail": data}
    except Exception as e:
        return {"error": str(e)}

def refresh_access_token() -> dict:
    rt = get_refresh_token()
    if not rt:
        return {"error": "No refresh token"}
    try:
        cid = _client_id()
        csecret = _client_secret()
        auth = requests.auth._basic_auth_str(cid, csecret)
        r = requests.post(f"{BASE_URL}/oauth/token", json={
            "grant_type": "refresh_token",
            "refresh_token": rt,
        }, headers={"Authorization": auth}, timeout=30)
        data = r.json()
        if "access_token" in data:
            set_access_token(data["access_token"])
            set_refresh_token(data.get("refresh_token", rt))
            return {"success": True}
        return {"error": data}
    except Exception as e:
        return {"error": str(e)}

def _request(endpoint: str, params: dict = None, method: str = "GET") -> dict:
    token = get_access_token()
    if not token:
        return {"error": "Bling não autenticado. Visite /api/bling/auth para autorizar."}
    url = f"{BASE_URL}/{endpoint}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}
    try:
        r = requests.request(method, url, headers=headers, json=params if method == "POST" else None,
                             params=params if method == "GET" else None, timeout=30)
        if r.status_code == 401:
            refresh_access_token()
            token = get_access_token()
            headers["Authorization"] = f"Bearer {token}"
            r = requests.request(method, url, headers=headers, json=params if method == "POST" else None,
                                 params=params if method == "GET" else None, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e), "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None}

def listar_produtos(pagina: int = 1, limite: int = 100) -> dict:
    return _request("produtos", {"pagina": pagina, "limite": limite})

def listar_pedidos(pagina: int = 1, limite: int = 100) -> dict:
    return _request("pedidos/vendas", {"pagina": pagina, "limite": limite})

def listar_contatos(pagina: int = 1, limite: int = 100) -> dict:
    return _request("contatos", {"pagina": pagina, "limite": limite})

def listar_categorias(pagina: int = 1, limite: int = 100) -> dict:
    return _request("categorias/produtos", {"pagina": pagina, "limite": limite})

def listar_contas_receber(pagina: int = 1, limite: int = 100) -> dict:
    return _request("contas/receber", {"pagina": pagina, "limite": limite})

def listar_contas_pagar(pagina: int = 1, limite: int = 100) -> dict:
    return _request("contas/pagar", {"pagina": pagina, "limite": limite})

def listar_notas_fiscais(pagina: int = 1, limite: int = 100) -> dict:
    return _request("nfe", {"pagina": pagina, "limite": limite})

def get_nfe_detail(id_nota: int) -> dict:
    """Retorna detalhes completos de uma NF-e incluindo link do XML e DANFE."""
    return _request(f"nfe/{id_nota}")


# ── Contatos (Clientes / Fornecedores) ──

def listar_contatos(pagina: int = 1, limite: int = 100, tipo: str = "") -> dict:
    """Lista contatos. tipo: 'C'=cliente, 'F'=fornecedor, ''=todos"""
    params = {"pagina": pagina, "limite": limite}
    if tipo: params["tipo"] = tipo
    return _request("contatos", params)

def get_contato(id_contato: int) -> dict:
    return _request(f"contatos/{id_contato}")

# ── Categorias de Produtos ──

def listar_categorias(pagina: int = 1, limite: int = 100) -> dict:
    return _request("categorias/produtos", {"pagina": pagina, "limite": limite})

def get_categoria(id_categoria: int) -> dict:
    return _request(f"categorias/produtos/{id_categoria}")

# ── Detalhe do Pedido (com itens, frete, parcelas) ──

def get_pedido_detalhe(id_pedido: int) -> dict:
    """Retorna detalhes completos: itens, parcelas, transporte, vendedor."""
    return _request(f"pedidos/vendas/{id_pedido}")

# ── NF-e Completa ──

def get_nfe_completa(id_nota: int) -> dict:
    """Retorna NF-e com itens, impostos, transportadora, volumes."""
    return _request(f"nfe/{id_nota}")

# ── Contas a Pagar ──

def listar_contas_pagar(pagina: int = 1, limite: int = 100, situacao: str = "") -> dict:
    params = {"pagina": pagina, "limite": limite}
    if situacao: params["situacao"] = situacao
    return _request("contas/pagar", params)

def get_conta_pagar(id_conta: int) -> dict:
    return _request(f"contas/pagar/{id_conta}")

# ── Formas de Pagamento ──

def listar_formas_pagamento() -> dict:
    return _request("formas-pagamento")

def get_nfe_xml(id_nota: int) -> tuple[str | None, str | None]:
    """Retorna (conteudo_xml, content_type) do XML da NF-e ou (None, None) se erro."""
    r = get_nfe_detail(id_nota)
    if r.get("error"):
        return None, None
    data = r.get("data", {})
    xml_url = data.get("xml") or data.get("linkXml") or ""
    if not xml_url:
        return None, None
    try:
        token = get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(xml_url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.text, resp.headers.get("Content-Type", "application/xml")
    except Exception:
        pass
    return None, None

def _mapear_produto_bling(p: dict) -> dict:
    """Mapeia o payload de detalhe do Bling (GET /produtos/{id}) para as colunas de catalogo_produtos.
    dados_brutos_bling guarda o JSON completo, entao nenhum campo se perde mesmo que falte um mapeamento aqui."""
    categoria = p.get("categoria") or {}
    estoque = p.get("estoque") or {}
    tributacao = p.get("tributacao") or {}
    dimensoes = p.get("dimensoes") or {}
    fornecedor = p.get("fornecedor") or {}
    fornecedor_contato = fornecedor.get("contato") or {}

    imagem = p.get("imagemURL") or p.get("urlImagem") or ""
    if not imagem and isinstance(p.get("imagem"), dict):
        imagem = (p["imagem"] or {}).get("link") or ""
    imagens_lista = p.get("imagens") or (p.get("midia") or {}).get("imagens") or []

    return {
        "sku": p.get("codigo", "") or str(p.get("id", "")),
        "descricao": p.get("descricao", "") or p.get("nome", ""),
        "id_bling": p.get("id"),
        "imagem_url": imagem,
        "situacao": p.get("situacao") or "A",
        "bling_tipo": p.get("tipo", ""),
        "formato": p.get("formato", ""),
        "codigo_barras": p.get("gtin", ""),
        "gtin_embalagem": p.get("gtinEmbalagem", ""),
        "descricao_curta": p.get("descricaoCurta", ""),
        "descricao_complementar": p.get("descricaoComplementar", ""),
        "unidade_padrao": p.get("unidade") or "UN",
        "peso_bruto": p.get("pesoBruto"),
        "peso_liquido": p.get("pesoLiquido"),
        "volumes": p.get("volumes"),
        "itens_por_caixa": p.get("itensPorCaixa"),
        "tipo_producao": p.get("tipoProducao", ""),
        "condicao": p.get("condicao"),
        "frete_gratis": bool(p.get("freteGratis", False)),
        "link_externo": p.get("linkExterno", ""),
        "observacoes": p.get("observacoes", ""),
        "marca": p.get("marca", ""),
        "categoria": categoria.get("descricao", "") if isinstance(categoria, dict) else str(categoria or ""),
        "categoria_id": categoria.get("id") if isinstance(categoria, dict) else None,
        "estoque_minimo": estoque.get("minimo"),
        "estoque_maximo": estoque.get("maximo"),
        "estoque_crossdocking": estoque.get("crossdocking"),
        "estoque_localizacao": estoque.get("localizacao", ""),
        "controlar_estoque": p.get("actionEstoque", "T") != "N",
        "largura": dimensoes.get("largura"),
        "altura": dimensoes.get("altura"),
        "profundidade": dimensoes.get("profundidade"),
        "unidade_medida_dimensao": dimensoes.get("unidadeMedida", ""),
        "ncm": tributacao.get("ncm") or p.get("ncm", ""),
        "cest": tributacao.get("cest") or p.get("cest", ""),
        "origem_fiscal": tributacao.get("origem", ""),
        "nfci": tributacao.get("nFCI", ""),
        "codigo_lista_servicos": tributacao.get("codigoListaServicos", ""),
        "cnae": tributacao.get("cnae", ""),
        "codigo_item_fiscal": tributacao.get("codigoItem", ""),
        "percentual_tributos": tributacao.get("percentualTributos"),
        "valor_base_st_retencao": tributacao.get("valorBaseStRetencao"),
        "valor_st_retencao": tributacao.get("valorStRetencao"),
        "valor_icms_st": tributacao.get("valorICMSSubstituto"),
        "fornecedor_id": fornecedor_contato.get("id"),
        "fornecedor_nome": fornecedor_contato.get("nome", ""),
        "fornecedor_codigo": fornecedor.get("codigo", ""),
        "preco_custo": fornecedor.get("precoCusto") if fornecedor.get("precoCusto") is not None else p.get("precoCusto"),
        "imagens": json.dumps(imagens_lista, ensure_ascii=False),
        "campos_customizados": json.dumps(p.get("camposCustomizados") or p.get("camposPersonalizados") or [], ensure_ascii=False),
        "estrutura": json.dumps(p.get("estrutura") or [], ensure_ascii=False),
        "variacoes_detalhe": json.dumps(p.get("variacoes") or [], ensure_ascii=False),
        "dados_brutos_bling": json.dumps(p, ensure_ascii=False),
    }


async def _upsert_produto_completo(db, campos: dict):
    """Upsert dinamico em catalogo_produtos cobrindo todas as colunas mapeadas de um produto Bling."""
    campos = {k: v for k, v in campos.items() if v is not None}
    if not campos.get("sku"):
        return
    jsonb_cols = {"imagens", "campos_customizados", "estrutura", "variacoes_detalhe", "dados_brutos_bling"}
    keys = list(campos.keys())
    vals = [campos[k] for k in keys]
    placeholders = ", ".join(f"${i+1}::jsonb" if k in jsonb_cols else f"${i+1}" for i, k in enumerate(keys))
    col_list = ", ".join(keys)
    updates = ", ".join(f"{k} = COALESCE(EXCLUDED.{k}, catalogo_produtos.{k})" for k in keys if k != "sku")
    sql = f"""INSERT INTO catalogo_produtos ({col_list}) VALUES ({placeholders})
              ON CONFLICT (sku) DO UPDATE SET {updates}, updated_at = NOW()"""
    await db.execute(sql, *vals)


def sincronizar_produtos() -> dict:
    """Sync completo: busca o detalhe de CADA produto no Bling (GET /produtos/{id}) para
    importar todos os campos oferecidos (fiscal, dimensoes, estoque min/max, fornecedor,
    imagens, variacoes, campos customizados, etc), alem da hierarquia pai/filho."""
    try:
        async def _go():
            db = await get_db()
            total = 0; erros = []; pagina = 1; produtos_resumo = []

            # ── Passo 1: listar todos os produtos (resumo) para descobrir os IDs ──
            while True:
                r = listar_produtos(pagina=pagina, limite=100)
                dados = r.get("data", [])
                if not dados or r.get("error"):
                    if r.get("error"): erros.append(f"pag {pagina}: {r['error']}")
                    break
                produtos_resumo.extend(dados)
                if len(dados) < 100:
                    break
                pagina += 1

            id_to_sku = {}
            filhos_pendentes = []

            # ── Passo 2: buscar detalhe completo de cada produto e gravar todos os campos ──
            for p_resumo in produtos_resumo:
                bid = p_resumo.get("id")
                if not bid:
                    continue
                detalhe = None
                for attempt in range(3):
                    r_detalhe = _request(f"produtos/{bid}")
                    if not r_detalhe.get("error"):
                        detalhe = r_detalhe.get("data", {})
                        break
                    if r_detalhe.get("status_code") == 429:
                        time.sleep(2 ** attempt)
                        continue
                    erros.append(f"produto {bid}: {r_detalhe['error']}")
                    break
                if not detalhe:
                    detalhe = p_resumo  # fallback: usa ao menos os campos do resumo

                try:
                    campos = _mapear_produto_bling(detalhe)
                    sku = campos["sku"]
                    id_to_sku[bid] = sku
                    id_pai = detalhe.get("idProdutoPai") or p_resumo.get("idProdutoPai")
                    if id_pai:
                        filhos_pendentes.append({"sku": sku, "idPai": id_pai})

                    await _upsert_produto_completo(db, campos)
                    await db.execute("INSERT INTO fichas_tecnicas (sku, descricao) VALUES ($1, $2) ON CONFLICT (sku) DO NOTHING", sku, campos.get("descricao", ""))
                    preco = float(detalhe.get("preco", 0) or 0)
                    await db.execute("INSERT INTO anuncios (sku, marketplace, shop_id, preco, status) VALUES ($1, 'bling', '', $2, 'ativo') ON CONFLICT (sku, marketplace, shop_id) DO UPDATE SET preco = $2, status = 'ativo'", sku, preco)

                    # Variacoes ja vem no proprio detalhe do produto pai
                    for v in detalhe.get("variacoes", []):
                        var_data = v.get("variacao", {}) if isinstance(v, dict) else {}
                        nome_var = var_data.get("nome", "") if isinstance(var_data, dict) else ""
                        var_prod = v.get("produto", {}) if isinstance(v, dict) else {}
                        filho_sku = var_prod.get("codigo", "") if isinstance(var_prod, dict) else ""
                        if filho_sku and nome_var:
                            await db.execute("UPDATE catalogo_produtos SET atributo = $1 WHERE sku = $2", nome_var, filho_sku)

                    total += 1
                except Exception as e:
                    log(AGENT, f"Erro produto {p_resumo.get('codigo')}: {e}")

            # ── Passo 3: resolver hierarquia pai/filho ──
            pais_resolvidos = 0
            for f in filhos_pendentes:
                pai_sku = id_to_sku.get(f["idPai"])
                if pai_sku:
                    await db.execute("UPDATE catalogo_produtos SET sku_pai = $1 WHERE sku = $2", pai_sku, f["sku"])
                    pais_resolvidos += 1

            return {"sincronizados": total, "pais_resolvidos": pais_resolvidos, "erros": erros}

        return run_async(_go())
    except Exception as e:
        import traceback
        log(AGENT, f"FATAL sincronizar_produtos: {e}\n{traceback.format_exc()}")
        return {"sincronizados": 0, "erro": str(e)}

def sincronizar_pedidos(loja_id: int = None) -> dict:
    try:
        async def _go():
            db = await get_db()
            r = listar_pedidos()
            dados = r.get("data", [])
            if not dados:
                return {"erro": r.get("error", "sem dados"), "total": 0}
            total = 0
            for p in dados:
                try:
                    if not p.get("dataEmissao"): continue
                    data = p["dataEmissao"][:10]
                    itens = p.get("itens", [])
                    for item in itens:
                        sku = item.get("codigo", "")
                        qtd = int(item.get("quantidade", 1))
                        preco = float(item.get("valorUnitario", 0))
                        receita = float(item.get("valorTotal", 0))
                        await db.execute("""
                            INSERT INTO vendas (data, sku, marketplace, loja_id, quantidade, preco_venda, receita_bruta, taxa_marketplace_pct, taxa_marketplace_valor, frete, impostos)
                            VALUES ($1, $2, 'bling', $3, $4, $5, $6, 0, 0, 0, 0)
                        """, data, sku, loja_id, qtd, preco, receita)
                        total += 1
                except Exception as e:
                    log(AGENT, f"Erro pedido: {e}")
            return {"sincronizados": total}
        return run_async(_go())
    except Exception as e:
        import traceback
        log(AGENT, f"FATAL sincronizar_pedidos: {e}\n{traceback.format_exc()}")
        return {"sincronizados": 0, "erro": str(e)}

def status() -> dict:
    token = get_access_token()
    return {
        "client_id_setado": bool(_client_id()),
        "autenticado": bool(token),
        "auth_url": get_auth_url() if not token else "",
    }

def webhook_bling_pedido(payload: dict, loja_id: int = None) -> dict:
    from datetime import date, timedelta
    async def _go():
        db = await get_db()
        pedido = payload.get("pedido", payload)
        itens = pedido.get("itens", [])
        for item in itens:
            sku = item.get("codigo", "")
            qtd = int(item.get("quantidade", 1))
            preco = float(item.get("valorUnitario", 0))
            await db.execute(
                "INSERT INTO vendas (data, sku, marketplace, loja_id, quantidade, preco_venda, receita_bruta) VALUES ($1,$2,'bling',$3,$4,$5,$6)",
                date.today(), sku, loja_id, qtd, preco, preco * qtd)
        try:
            from ag_04_planejador import adicionar_pedido_producao
            for item in itens:
                adicionar_pedido_producao(
                    sku=item.get("codigo", ""), quantidade=int(item.get("quantidade", 1)),
                    prazo=date.today() + timedelta(days=3), prioridade=5,
                    cliente_id=pedido.get("contato", {}).get("nome", ""))
        except Exception as e:
            log(AGENT, f"Erro ao enfileirar produção: {e}")
        return {"success": True, "itens": len(itens)}
    try:
        return run_async(_go())
    except Exception as e:
        return {"error": str(e)}


def registrar_webhook(tipo: str = "pedido", url: str = None) -> dict:
    webhook_url = url or f"https://{BLING_DOMAIN}/webhook/bling/pedido"
    return _request("webhooks", {
        "webhook": {"url": webhook_url, "evento": tipo, "metodo": "POST", "formato": "JSON"}
    }, method="POST")

# ──────────────────────────────────────────────
# Task 2: CRUD de Produtos, Depósitos, Estoque, Analytics, Webhooks, Notificações
# ──────────────────────────────────────────────

def criar_produto(dados: dict) -> dict:
    """Cria um produto no Bling via POST /produtos. dados deve conter nome, codigo, preco, etc."""
    return _request("produtos", dados, method="POST")


def atualizar_produto(id_produto: int, dados: dict) -> dict:
    """Atualiza produto existente via PUT /produtos/{id}."""
    return _request(f"produtos/{id_produto}", dados, method="PUT")


def deletar_produto(id_produto: int) -> dict:
    """Deleta produto via DELETE /produtos/{idProduto}."""
    return _request(f"produtos/{id_produto}", method="DELETE")


def atualizar_situacao_produtos(ids: list, situacao: str) -> dict:
    """Altera situacao em lote via POST /produtos/situacoes. situacao: 'A' (ativo), 'I' (inativo), 'E' (excluido)."""
    return _request("produtos/situacoes", {
        "idsProdutos": ids,
        "situacao": situacao,
    }, method="POST")


# ── Depósitos e Estoque ──


def listar_produtos_agrupados(pagina: int = 1, limite: int = 100) -> dict:
    """Lista produtos agrupados por pai/filho (variacoes)."""
    raw = listar_produtos(pagina, limite)
    produtos = raw.get("data", [])
    if not produtos:
        return {"grupos": [], "avulsos": [], "total": 0}

    # Separar pais e filhos
    pais_ids = set()
    filhos_por_pai = {}
    avulsos = []
    filhos_sem_pai = []

    for p in produtos:
        pid = p.get("idProdutoPai")
        if pid:
            if pid not in filhos_por_pai:
                filhos_por_pai[pid] = []
            filhos_por_pai[pid].append(p)
            pais_ids.add(pid)
        else:
            # Pode ser um pai real ou avulso
            avulsos.append(p)

    # Buscar dados dos pais (se nao estao na lista atual)
    grupos = []
    for pid in pais_ids:
        pai = next((a for a in avulsos if a.get("id") == pid), None)
        if not pai:
            # Buscar o pai via API
            try:
                parent_raw = _request(f"produtos/{pid}")
                pai = parent_raw.get("data", {}) if isinstance(parent_raw, dict) else {}
            except:
                pai = {"id": pid, "codigo": f"PAI-{pid}", "nome": "Produto Pai"}
        filhos = filhos_por_pai.get(pid, [])
        grupos.append({"pai": pai, "filhos": filhos})
        # Remover pais que ja estao em avulsos para nao duplicar
        avulsos = [a for a in avulsos if a.get("id") != pid]

    return {
        "grupos": grupos,
        "avulsos": avulsos,
        "total": len(grupos) + len(avulsos),
        "total_filhos": sum(len(g["filhos"]) for g in grupos),
    }

def listar_depositos(pagina: int = 1, limite: int = 100) -> dict:
    """Lista depositos/lojas internas do Bling."""
    return _request("depositos", {"pagina": pagina, "limite": limite})


def obter_saldo_deposito(id_deposito: int, ids_produtos: list = None) -> dict:
    """Obtem saldo de estoque em um deposito especifico. ids_produtos: lista opcional de IDs para filtrar."""
    params = {}
    if ids_produtos:
        params["idsProdutos[]"] = ids_produtos
    return _request(f"estoques/saldos/{id_deposito}", params)


def atualizar_estoque_deposito(dados: dict) -> dict:
    """Atualiza estoque via PUT /estoques. dados deve conter: idDeposito, idProduto, operacao ('B' balanco | 'E' entrada | 'S' saida),
    quantidade, preco (opcional)."""
    return _request("estoques", dados, method="PUT")

def sincronizar_estoque_para_bling(sku: str, loja_nome: str, quantidade: float) -> dict:
    """Two-way sync: Athena → Bling. Resolve SKU e loja para IDs Bling e envia atualizacao."""
    try:
        from core import get_db, run_async
        async def _go():
            db = await get_db()
            # Resolve Bling product ID
            prod = await db.fetchrow("SELECT id_bling FROM catalogo_produtos WHERE sku = $1", sku)
            if not prod or not prod["id_bling"]:
                return {"error": f"SKU {sku} sem id_bling no catalogo"}
            id_produto = int(prod["id_bling"])
            # Resolve Bling deposito ID
            dep = await db.fetchrow("SELECT bling_id FROM lojas WHERE nome = $1", loja_nome)
            if not dep or not dep["bling_id"]:
                return {"error": f"Loja '{loja_nome}' sem bling_id vinculado"}
            id_deposito = int(dep["bling_id"])
            # Envia para Bling
            payload = {
                "idDeposito": id_deposito,
                "idProduto": id_produto,
                "operacao": "B",  # B = balanco (seta estoque exato)
                "quantidade": quantidade,
            }
            return atualizar_estoque_deposito(payload)
        return run_async(_go())
    except Exception as e:
        return {"error": str(e)}


# ── Analytics de Vendas ──

def resumo_vendas(dias: int = 30) -> dict:
    """Retorna resumo de vendas para analytics: top SKUs, vendas diarias, totais.
    Usa listar_pedidos() e agrega localmente ja que Bling nao tem endpoint especifico."""
    from datetime import date, timedelta
    import collections

    today = date.today()
    cutoff = today - timedelta(days=dias)
    top_skus = collections.defaultdict(lambda: {"quantidade": 0, "receita": 0.0})
    vendas_por_dia = collections.defaultdict(float)
    total_receita = 0.0
    total_pedidos = 0

    pagina = 1
    while True:
        r = listar_pedidos(pagina=pagina, limite=100)
        dados = r.get("data", [])
        if not dados or r.get("error"):
            break
        for pedido_val in dados:
            data_str = (pedido_val.get("data") or pedido_val.get("dataEmissao", ""))[:10]
            if not data_str or data_str < cutoff.isoformat():
                continue
            total_pedidos += 1
            valor_pedido = float(pedido_val.get("total", 0))
            total_receita += valor_pedido
            vendas_por_dia[data_str] += valor_pedido
            # Top SKUs via itens (se disponível) ou usa total do pedido
            itens = pedido_val.get("itens") or []
            if itens:
                for item in itens:
                    sku = item.get("codigo", "")
                    qtd = int(item.get("quantidade", 1))
                    preco = float(item.get("valor", item.get("valorUnitario", 0)))
                    receita_item = qtd * preco
                    top_skus[sku]["quantidade"] += qtd
                    top_skus[sku]["receita"] += receita_item
        pagina += 1
        if len(dados) < 100:
            break

    ranked = sorted(top_skus.items(), key=lambda x: x[1]["receita"], reverse=True)

    return {
        "total_receita": round(total_receita, 2),
        "total_pedidos": total_pedidos,
        "dias_analisados": dias,
        "top_skus": [{"sku": sku, **info} for sku, info in ranked[:20]],
        "vendas_diarias": sorted(vendas_por_dia.items()),
    }


# ── Webhooks ──

def listar_webhooks(pagina: int = 1, limite: int = 100) -> dict:
    """Lista webhooks cadastrados no Bling."""
    return _request("webhooks", {"pagina": pagina, "limite": limite})


def criar_webhook(evento: str, url: str) -> dict:
    """Registra um novo webhook no Bling."""
    return _request("webhooks", {
        "webhook": {"url": url, "evento": evento, "metodo": "POST", "formato": "JSON"}
    }, method="POST")


def deletar_webhook(id_webhook: int) -> dict:
    """Remove um webhook do Bling."""
    return _request(f"webhooks/{id_webhook}", method="DELETE")


def validar_assinatura_webhook(payload: bytes, signature_header: str) -> bool:
    """Valida assinatura HMAC-SHA256 do webhook. signature_header = valor de X-Bling-Signature-256."""
    import hmac
    import hashlib

    if not signature_header:
        return False
    secret = _client_secret().encode("utf-8")
    computed = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    # Tempo de comparacao constante para evitar timing attack
    return hmac.compare_digest(f"sha256={computed}", signature_header)


# ── Notificacoes ──

def listar_notificacoes(pagina: int = 1, limite: int = 100) -> dict:
    """Lista notificacoes do Bling."""
    return _request("notificacoes", {"pagina": pagina, "limite": limite})


def confirmar_leitura_notificacao(id_notificacao: int) -> dict:
    """Marca notificacao como lida."""
    return _request(f"notificacoes/{id_notificacao}", method="PATCH")


# ── Processador de Eventos Webhook ──

def processar_evento_webhook(evento: str, payload: dict) -> dict:
    """Roteia evento de webhook para o handler adequado.
    Retorna: {"processed": True, "evento": evento} ou {"error": ...}"""
    from datetime import date, timedelta

    async def _go():
        db = await get_db()
        resource = evento.split(".")[0] if "." in evento else ""

        if resource in ("pedido", "order"):
            pedido = payload.get("pedido", payload)
            itens = pedido.get("itens", [])
            for item in itens:
                sku = item.get("codigo", "")
                qtd = int(item.get("quantidade", 1))
                preco = float(item.get("valorUnitario", 0))
                await db.execute(
                    """INSERT INTO vendas (data, sku, marketplace, quantidade, preco_venda, receita_bruta)
                       VALUES ($1, $2, 'bling', $3, $4, $5)""",
                    date.today(), sku, qtd, preco, preco * qtd,
                )

            # Enfileirar producao
            try:
                from ag_04_planejador import adicionar_pedido_producao
                for item in itens:
                    adicionar_pedido_producao(
                        sku=item.get("codigo", ""),
                        quantidade=int(item.get("quantidade", 1)),
                        prazo=date.today() + timedelta(days=3),
                        prioridade=5,
                        cliente_id=pedido.get("contato", {}).get("nome", ""),
                    )
            except Exception as e:
                log(AGENT, f"webhook erro producao: {e}")

        elif resource in ("produto", "product"):
            produto = payload.get("produto", payload)
            sku = produto.get("codigo", "") or str(produto.get("id", ""))
            nome = produto.get("descricao", "")
            preco = float(produto.get("preco", 0)) if produto.get("preco") else 0
            await db.execute("""
                INSERT INTO fichas_tecnicas (sku, descricao) VALUES ($1, $2)
                ON CONFLICT (sku) DO UPDATE SET descricao = $2
            """, sku, nome)

        elif resource == "estoque":
            estoque = payload.get("estoque", payload)
            id_deposito = estoque.get("idDeposito", 0)
            sku = estoque.get("codigo", "")
            saldo = float(estoque.get("saldo", 0))
            loja_nome = str(id_deposito)
            try:
                row = await db.fetchrow("SELECT nome FROM lojas WHERE bling_id = $1", id_deposito)
                if row: loja_nome = row["nome"]
            except: pass
            await db.execute("""
                INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao, sync_status)
                VALUES ($1, $2, $3, NOW(), 'ok')
                ON CONFLICT (sku, loja) DO UPDATE SET quantidade = $3, data_atualizacao = NOW(), sync_status = 'ok'
            """, sku, loja_nome, saldo)

        elif resource in ("conta-receber", "conta-receber"):
            cr = payload.get("contaReceber", payload)
            bling_id = cr.get("id")
            if bling_id:
                existing = await db.fetchval("SELECT id FROM fin_contas_receber WHERE bling_id = $1", bling_id)
                contato = cr.get("contato", {}) or {}
                vencimento = (cr.get("vencimento") or "")[:10] or None
                data_rec = (cr.get("dataRecebimento") or "")[:10] or None
                valor = float(cr.get("valor", 0) or 0)
                if existing:
                    await db.execute("""UPDATE fin_contas_receber SET cliente=$1, valor=$2, vencimento=$3::date,
                        data_recebimento=$4::date, status=$5, origem='bling' WHERE bling_id=$6""",
                        contato.get("nome",""), valor, vencimento, data_rec, str(cr.get("situacao","pendente")), bling_id)
                else:
                    await db.execute("""INSERT INTO fin_contas_receber (cliente, descricao, valor, vencimento,
                        data_recebimento, status, forma_pagamento, bling_id, origem)
                        VALUES ($1,$2,$3,$4::date,$5::date,$6,$7,$8,'bling')""",
                        contato.get("nome",""), cr.get("descricao",""), valor, vencimento, data_rec,
                        str(cr.get("situacao","pendente")), cr.get("formaPagamento",""), bling_id)

        elif resource in ("conta-pagar", "conta-pagar"):
            cp = payload.get("contaPagar", payload)
            bling_id = cp.get("id")
            if bling_id:
                existing = await db.fetchval("SELECT id FROM fin_contas_pagar WHERE bling_id = $1", bling_id)
                fornecedor = cp.get("fornecedor", cp.get("contato", {})) or {}
                vencimento = (cp.get("vencimento") or "")[:10] or None
                data_pgto = (cp.get("dataPagamento") or "")[:10] or None
                valor = float(cp.get("valor", 0) or 0)
                if existing:
                    await db.execute("""UPDATE fin_contas_pagar SET fornecedor=$1, valor=$2, vencimento=$3::date,
                        data_pagamento=$4::date, status=$5, origem='bling' WHERE bling_id=$6""",
                        fornecedor.get("nome",""), valor, vencimento, data_pgto, str(cp.get("situacao","pendente")), bling_id)
                else:
                    await db.execute("""INSERT INTO fin_contas_pagar (fornecedor, descricao, valor, vencimento,
                        data_pagamento, status, forma_pagamento, bling_id, origem)
                        VALUES ($1,$2,$3,$4::date,$5::date,$6,$7,$8,'bling')""",
                        fornecedor.get("nome",""), cp.get("descricao",""), valor, vencimento, data_pgto,
                        str(cp.get("situacao","pendente")), cp.get("formaPagamento",""), bling_id)

        elif resource in ("nota-fiscal", "nota_fiscal", "nfe"):
            nf = payload.get("notaFiscal", payload.get("nfe", payload))
            bling_id = nf.get("id")
            if bling_id:
                existing = await db.fetchval("SELECT id FROM fiscal_notas_fiscais WHERE bling_id = $1", bling_id)
                contato = nf.get("contato", {}) or {}
                natureza = nf.get("naturezaOperacao", {}) or {}
                data_emissao = (nf.get("dataEmissao") or "")[:10] or None
                valor_nf = float(nf.get("total", 0) or 0)
                if existing:
                    await db.execute("""UPDATE fiscal_notas_fiscais SET numero=$1, data_emissao=$2::date,
                        contato_nome=$3, contato_documento=$4, valor_nf=$5, natureza_operacao=$6,
                        status=$7, sincronizado_em=NOW() WHERE bling_id=$8""",
                        str(nf.get("numero","")), data_emissao, contato.get("nome",""),
                        contato.get("numeroDocumento",""), valor_nf, natureza.get("descricao",""),
                        {1:"emitida",2:"cancelada",3:"inutilizada",4:"denegada"}.get(nf.get("situacao",1),"emitida"), bling_id)
                else:
                    await db.execute("""INSERT INTO fiscal_notas_fiscais (numero, modelo, data_emissao,
                        natureza_operacao, contato_nome, contato_documento, valor_nf, status, bling_id, sincronizado_em)
                        VALUES ($1,$2,$3::date,$4,$5,$6,$7,$8,$9,NOW())""",
                        str(nf.get("numero","")), str(nf.get("modelo","55")), data_emissao,
                        natureza.get("descricao",""), contato.get("nome",""),
                        contato.get("numeroDocumento",""), valor_nf,
                        {1:"emitida",2:"cancelada",3:"inutilizada",4:"denegada"}.get(nf.get("situacao",1),"emitida"), bling_id)

        elif resource in ("contato", "contact"):
            contato = payload.get("contato", payload)
            doc = (contato.get("numeroDocumento") or "").replace(".","").replace("/","").replace("-","").strip()
            nome = contato.get("nome", "")
            if doc or nome:
                existing = None
                if doc:
                    existing = await db.fetchrow("SELECT id FROM cad_clientes WHERE REPLACE(REPLACE(REPLACE(documento,'.',''),'/',''),'-','') = $1 LIMIT 1", doc)
                if not existing:
                    await db.execute("""INSERT INTO cad_clientes (nome, tipo, documento, status)
                        VALUES ($1, 'PF', $2, 'ativo') ON CONFLICT DO NOTHING""",
                        nome, contato.get("numeroDocumento",""))
                    # ponytail: upsert via nome se nao tiver documento
                    if not doc:
                        try:
                            await db.execute("""INSERT INTO cad_clientes (nome, tipo, status)
                                VALUES ($1, 'PF', 'ativo') ON CONFLICT DO NOTHING""", nome)
                        except: pass

        return {"processed": True, "evento": evento, "resource": resource}

    try:
        return run_async(_go())
    except Exception as e:
        return {"error": str(e), "evento": evento}


if __name__ == "__main__":
    log(AGENT, f"Configurado: {bool(_client_id())}")
    if _client_id():
        log(AGENT, f"Auth URL: {get_auth_url()}")
