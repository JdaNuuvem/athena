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
# ── Token storage (env var > cache) ──
_TOKEN = {"access": "", "refresh": ""}

def get_access_token() -> str:
    return os.environ.get("BLING_ACCESS_TOKEN", "") or _TOKEN["access"]

def set_access_token(token: str):
    _TOKEN["access"] = token

def get_refresh_token() -> str:
    return os.environ.get("BLING_REFRESH_TOKEN", "") or _TOKEN["refresh"]

def set_refresh_token(token: str):
    _TOKEN["refresh"] = token

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

def listar_contas_receber(pagina: int = 1, limite: int = 100) -> dict:
    return _request("contas/receber", {"pagina": pagina, "limite": limite})

def listar_notas_fiscais(pagina: int = 1, limite: int = 100) -> dict:
    return _request("nfe", {"pagina": pagina, "limite": limite})

def get_nfe_detail(id_nota: int) -> dict:
    """Retorna detalhes completos de uma NF-e incluindo link do XML e DANFE."""
    return _request(f"nfe/{id_nota}")

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

def sincronizar_produtos() -> dict:
    async def _go():
        db = await get_db()
        r = listar_produtos()
        dados = r.get("data", [])
        if not dados:
            return {"erro": r.get("error", "sem dados"), "total": 0}
        total = 0
        for p in dados:
            try:
                sku = p.get("codigo", "") or str(p["id"])
                nome = p.get("descricao", "")
                preco = float(p.get("preco", 0)) if p.get("preco") else 0
                await db.execute("""
                    INSERT INTO fichas_tecnicas (sku, descricao) VALUES ($1, $2)
                    ON CONFLICT (sku) DO NOTHING
                """, sku, nome)
                await db.execute("""
                    INSERT INTO anuncios (sku, marketplace, preco, status)
                    VALUES ($1, 'bling', $2, 'ativo')
                    ON CONFLICT (sku, marketplace) WHERE anuncio_id IS NULL
                    DO UPDATE SET preco = $2
                """, sku, preco)
                total += 1
            except Exception as e:
                log(AGENT, f"Erro produto {p.get('codigo')}: {e}")
        return {"sincronizados": total}
    return run_async(_go())

def sincronizar_pedidos() -> dict:
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
                        INSERT INTO vendas (data, sku, marketplace, quantidade, preco_venda, receita_bruta, taxa_marketplace_pct, taxa_marketplace_valor, frete, impostos)
                        VALUES ($1, $2, 'bling', $3, $4, $5, 0, 0, 0, 0)
                    """, data, sku, qtd, preco, receita)
                    total += 1
            except Exception as e:
                log(AGENT, f"Erro pedido: {e}")
        return {"sincronizados": total}
    return run_async(_go())

def status() -> dict:
    token = get_access_token()
    return {
        "client_id_setado": bool(_client_id()),
        "autenticado": bool(token),
        "auth_url": get_auth_url() if not token else "",
    }

def webhook_bling_pedido(payload: dict) -> dict:
    """Processa webhook de pedido recebido do Bling."""
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
                "INSERT INTO vendas (data, sku, marketplace, quantidade, preco_venda, receita_bruta) VALUES ($1,$2,'bling',$3,$4,$5)",
                date.today(), sku, qtd, preco, preco * qtd)
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
            await db.execute("""
                INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (sku, loja) DO UPDATE SET quantidade = $3, data_atualizacao = NOW()
            """, sku, str(id_deposito), saldo)

        return {"processed": True, "evento": evento, "resource": resource}

    try:
        return run_async(_go())
    except Exception as e:
        return {"error": str(e), "evento": evento}


if __name__ == "__main__":
    log(AGENT, f"Configurado: {bool(_client_id())}")
    if _client_id():
        log(AGENT, f"Auth URL: {get_auth_url()}")
