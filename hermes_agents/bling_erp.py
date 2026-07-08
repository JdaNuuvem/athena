"""
Integração Bling ERP v3 — OAuth2 + Webhooks
"""
import sys, os, json, time, requests
from pathlib import Path
from urllib.parse import urlencode
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import log, run_async, get_db
from core.config import get_config, set_config

AGENT = "Bling ERP v3"

CLIENT_ID = os.environ.get("BLING_CLIENT_ID") or get_config("bling", "client_id") or ""
CLIENT_SECRET = os.environ.get("BLING_CLIENT_SECRET") or get_config("bling", "client_secret") or ""
BLING_DOMAIN = os.environ.get("BLING_DOMAIN", "athena.zoikom.site")
REDIRECT_URI = f"https://{BLING_DOMAIN}/api/bling/oauth/callback"
BASE_URL = "https://www.bling.com.br/Api/v3"

def get_access_token() -> str:
    return get_config("bling", "access_token") or ""

def set_access_token(token: str):
    set_config("bling", "access_token", token)

def get_refresh_token() -> str:
    return get_config("bling", "refresh_token") or ""

def set_refresh_token(token: str):
    set_config("bling", "refresh_token", token)

def get_auth_url() -> str:
    params = urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": os.urandom(16).hex(),
    })
    return f"{BASE_URL}/oauth/authorize?{params}"

def exchange_code(code: str) -> dict:
    try:
        r = requests.post(f"{BASE_URL}/oauth/token", json={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
        }, timeout=30)
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
        r = requests.post(f"{BASE_URL}/oauth/token", json={
            "grant_type": "refresh_token",
            "refresh_token": rt,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }, timeout=30)
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
    return _request("notasfiscais", {"pagina": pagina, "limite": limite})

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
        "client_id_setado": bool(CLIENT_ID),
        "autenticado": bool(token),
        "auth_url": get_auth_url() if not token else "",
    }

def registrar_webhook(tipo: str = "pedido", url: str = None) -> dict:
    webhook_url = url or f"{REDIRECT_URI.replace('/oauth/callback', '/webhook/bling/pedido')}"
    return _request("webhooks", {
        "webhook": {"url": webhook_url, "evento": tipo, "metodo": "POST", "formato": "JSON"}
    }, method="POST")

if __name__ == "__main__":
    log(AGENT, f"Configurado: {bool(CLIENT_ID)}")
    if CLIENT_ID:
        log(AGENT, f"Auth URL: {get_auth_url()}")
