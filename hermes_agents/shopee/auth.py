"""
Shopee Auth — config, signing, OAuth2 flow.
"""
import sys, os, json, time, hmac, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import requests
from core import log, run_async, get_db, hoje
from core.config import get_config, set_config

AGENT = "AG-03 | Shopee Auth"

BASE_URL_LIVE = "https://partner.shopeemobile.com/api/v2"
BASE_URL_BRAZIL = "https://openplatform.shopee.com.br/api/v2"
BASE_URL_SANDBOX = "https://openplatform.sandbox.test-stable.shopee.sg/api/v2"
SHOPEE_SANDBOX = os.environ.get("SHOPEE_SANDBOX", "false").lower() == "true" or get_config("shopee", "sandbox") == "true"
SHOPEE_REGION = os.environ.get("SHOPEE_REGION", "br") or get_config("shopee", "region", "br")


def get_shopee_config(loja_id: int = None) -> dict:
    """Config de uma loja Shopee especifica (multiloja) ou, se loja_id for None,
    a config global legada (unica loja, mantida por compatibilidade)."""
    partner_id = os.environ.get("SHOPEE_PARTNER_ID") or get_config("shopee", "partner_id") or ""
    api_key = os.environ.get("SHOPEE_PARTNER_KEY") or get_config("shopee", "api_key") or ""
    if loja_id is not None:
        from core.lojas import obter_credenciais_shopee
        cred = obter_credenciais_shopee(loja_id)
        return {
            "partner_id": partner_id,
            "shop_id": cred.get("shopee_shop_id") or "",
            "api_key": api_key,
            "access_token": cred.get("shopee_access_token") or "",
        }
    return {
        "partner_id": partner_id,
        "shop_id": os.environ.get("SHOPEE_SHOP_ID") or get_config("shopee", "shop_id") or "",
        "api_key": api_key,
        "access_token": os.environ.get("SHOPEE_ACCESS_TOKEN") or get_config("shopee", "access_token") or "",
    }
    # ponytail: access_token is the OAuth token from Shopee, separate from partner key


def _is_sandbox() -> bool:
    try:
        return os.environ.get("SHOPEE_SANDBOX","false").lower()=="true" or str(get_config("shopee","sandbox") or "").lower()=="true"
    except:
        return os.environ.get("SHOPEE_SANDBOX","false").lower()=="true"


def _base_url() -> str:
    """ponytail: a doc oficial (Authorization and Authentication.md, secoes GetAccessToken/
    RefreshAccessToken) so documenta partner.shopeemobile.com para chamadas de API em producao,
    para qualquer regiao — openplatform.shopee.com.br so aparece pra tela de login (browser),
    nao para as chamadas assinadas de API. BASE_URL_BRAZIL fica so como fallback documentado."""
    if _is_sandbox():
        return BASE_URL_SANDBOX
    return BASE_URL_LIVE


def configurado(loja_id: int = None) -> bool:
    c = get_shopee_config(loja_id)
    return bool(c["partner_id"] and c["shop_id"] and c["api_key"] and c["access_token"])


def _sign(path: str, loja_id: int = None) -> dict:
    """HMAC-SHA256 sign per Shopee spec: HMAC(partner_id + path + timestamp + access_token + shop_id, key=partner_key).
    ponytail: o partner_key e' so' a CHAVE do HMAC — nao entra na mensagem. Validado ao vivo contra o
    sandbox real (erro "Wrong sign" ate' remover o partner_key duplicado do fim da string)."""
    c = get_shopee_config(loja_id)
    timestamp = int(time.time())
    sign_str = f"{c['partner_id']}{path}{timestamp}{c['access_token']}{c['shop_id']}"
    signature = hmac.new(c["api_key"].encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    return {
        "partner_id": c["partner_id"], "timestamp": timestamp,
        "access_token": c["access_token"], "shop_id": c["shop_id"], "sign": signature,
    }


def _request(endpoint: str, params: dict = None, method: str = "GET", loja_id: int = None) -> dict:
    """Request autenticado à API Shopee. loja_id identifica QUAL loja Shopee (multiloja);
    quando omitido, usa a config global legada (unica loja)."""
    if not configurado(loja_id):
        return {"error": "Shopee não configurado"}
    path = f"/api/v2/{endpoint}"
    sig = _sign(path, loja_id)
    url = f"{_base_url()}/{endpoint}"
    default_params = {
        "partner_id": sig["partner_id"], "timestamp": sig["timestamp"],
        "access_token": sig["access_token"], "shop_id": sig["shop_id"], "sign": sig["sign"],
    }
    try:
        if method == "GET":
            p = {**default_params, **(params or {})}
            r = requests.get(url, params=p, timeout=30)
        else:
            body = {**default_params, **(params or {})}
            r = requests.post(url, json=body, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(AGENT, f"Erro {method} {endpoint}: {e}")
        return {"error": str(e)}


# ── OAuth2 Authorization Flow ──

def get_auth_url(redirect_uri: str = "", sandbox: bool = None, loja_id: int = None) -> str:
    """Gera URL de autorizacao Shopee. Usuario clica para autorizar o app.
    loja_id (opcional): quando informado, e' propagado no redirect_uri para que o callback
    saiba a qual loja vincular esta autorizacao (suporte a multiplas contas Shopee)."""
    cfg = get_shopee_config()
    if not cfg["partner_id"]:
        return ""
    if sandbox is None:
        sandbox = _is_sandbox()
    # ponytail: a doc oficial so documenta partner.shopeemobile.com pro endpoint assinado
    # /api/v2/shop/auth_partner (BR so tem host proprio pra tela de login open.shopee.com.br/auth)
    base = (BASE_URL_SANDBOX if sandbox else BASE_URL_LIVE).replace("/api/v2", "") + "/api/v2/shop/auth_partner"
    if not redirect_uri:
        # ponytail: /api/shopee/callback fica sem explicacao caindo no fallback do frontend em
        # producao (nao e' cache); /oauth2callback e' um alias novo que contorna isso.
        domain = os.environ.get("SHOPEE_REDIRECT_URL", "https://athena.zoikom.site/api/shopee/oauth2callback")
        redirect_uri = domain
    if loja_id is not None:
        sep = "&" if "?" in redirect_uri else "?"
        redirect_uri = f"{redirect_uri}{sep}loja_id={loja_id}"
    params = {
        "partner_id": int(cfg["partner_id"]),
        "redirect": redirect_uri,
        "timestamp": int(time.time()),
    }
    sign_str = f"{cfg['partner_id']}{'/api/v2/shop/auth_partner'}{params['timestamp']}"
    signature = hmac.new(cfg["api_key"].encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    params["sign"] = signature
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base}?{qs}"


def exchange_shopee_code(code: str, shop_id: str = "", loja_id: int = None) -> dict:
    """Troca o codigo de autorizacao por access_token e refresh_token.
    Vincula o resultado a uma loja (multiloja): usa loja_id quando informado,
    reaproveita a loja existente com o mesmo shop_id, ou cria uma nova loja."""
    cfg = get_shopee_config()
    if not cfg["partner_id"] or not code:
        return {"error": "partner_id ou code ausente"}
    base = _base_url().replace("/api/v2", "") + "/api/v2/auth/token/get"
    timestamp = int(time.time())
    body = {"code": code, "partner_id": int(cfg["partner_id"])}
    if shop_id:
        body["shop_id"] = int(shop_id)
    sign_str = f"{cfg['partner_id']}{'/api/v2/auth/token/get'}{timestamp}"
    signature = hmac.new(cfg["api_key"].encode(), sign_str.encode(), hashlib.sha256).hexdigest()

    try:
        r = requests.post(base, json=body, params={
            "partner_id": cfg["partner_id"], "timestamp": timestamp, "sign": signature,
        }, timeout=30)
        data = r.json()
        if not data.get("access_token"):
            return {"error": data.get("message", data.get("error", "unknown"))}

        access_token = data["access_token"]
        refresh_token = data.get("refresh_token", "")
        resolved_shop_id = str(body.get("shop_id") or data.get("shop_id") or "")
        expire_in = data.get("expire_in", 0)
        from datetime import datetime, timedelta
        expira_em = datetime.now() + timedelta(seconds=expire_in) if expire_in else None

        # Legado: mantem a config global funcionando (compatibilidade com a loja unica ja configurada)
        set_config("shopee", "access_token", access_token)
        set_config("shopee", "refresh_token", refresh_token)
        if resolved_shop_id:
            set_config("shopee", "shop_id", resolved_shop_id)

        # Multiloja: vincula (ou cria) a loja correspondente na tabela lojas
        loja_resultado = None
        if resolved_shop_id:
            from core.lojas import vincular_shopee, criar_loja_shopee, listar_lojas_shopee
            if loja_id:
                loja_resultado = vincular_shopee(loja_id, resolved_shop_id, access_token, refresh_token, expira_em=expira_em)
            else:
                existente = next((l for l in listar_lojas_shopee() if l.get("shopee_shop_id") == resolved_shop_id), None)
                if existente:
                    loja_resultado = vincular_shopee(existente["id"], resolved_shop_id, access_token, refresh_token, expira_em=expira_em)
                else:
                    loja_resultado = criar_loja_shopee(resolved_shop_id, access_token, refresh_token, expira_em=expira_em)

        return {"success": True, "expire_in": expire_in, "shop_id": resolved_shop_id, "loja": loja_resultado}
    except Exception as e:
        return {"error": str(e)}


def refresh_shopee_token(loja_id: int = None) -> dict:
    """Renova o access_token usando o refresh_token."""
    cfg = get_shopee_config(loja_id)
    refresh = get_config("shopee", "refresh_token") or ""
    if loja_id is not None:
        from core.lojas import obter_credenciais_shopee
        refresh = obter_credenciais_shopee(loja_id).get("shopee_refresh_token") or refresh
    if not refresh:
        return {"error": "refresh_token ausente"}
    base = _base_url().replace("/api/v2", "") + "/api/v2/auth/access_token/get"
    timestamp = int(time.time())
    body = {"refresh_token": refresh, "partner_id": int(cfg["partner_id"]), "shop_id": int(cfg["shop_id"])} if cfg.get("shop_id") else {"refresh_token": refresh, "partner_id": int(cfg["partner_id"])}
    sign_str = f"{cfg['partner_id']}{'/api/v2/auth/access_token/get'}{timestamp}"
    signature = hmac.new(cfg["api_key"].encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    try:
        r = requests.post(base, json=body, params={
            "partner_id": cfg["partner_id"], "timestamp": timestamp, "sign": signature,
        }, timeout=30)
        data = r.json()
        if data.get("access_token"):
            from datetime import datetime, timedelta
            expire_in = data.get("expire_in", 0)
            expira_em = datetime.now() + timedelta(seconds=expire_in) if expire_in else None
            if loja_id is not None:
                from core.lojas import vincular_shopee
                vincular_shopee(loja_id, cfg["shop_id"], data["access_token"], data.get("refresh_token", refresh), expira_em=expira_em)
                return {"success": True, "expire_in": expire_in}
            set_config("shopee", "access_token", data["access_token"])
            set_config("shopee", "refresh_token", data.get("refresh_token", ""))
            return {"success": True, "expire_in": expire_in}
        return {"error": data.get("message", "unknown")}
    except Exception as e:
        return {"error": str(e)}
