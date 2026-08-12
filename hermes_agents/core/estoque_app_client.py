"""Client HTTP para o app proprio de bipagem/atualizacao de estoque (fonte
real dos dados fisicos das lojas — o mesmo catalogo que a i9Logic serve, ja
paginado e cacheado por aquele app). Os endpoints /api/cache/* la sao
publicos (sem autenticacao), entao aqui so' fazemos GET direto — nao ha'
login/token envolvido.

Usado no lugar da paginacao direta contra a API i9Logic (core/i9logic.py):
aquela paginacao respeita rate limit (2.5s/pagina) e pra 22k+ produtos leva
minutos, sujeito a timeout do proxy. O app de bipagem ja mantem esse mesmo
catalogo sincronizado e serve tudo numa unica chamada."""
import os
import requests

AGENT = "Estoque App Client"

BASE_URL = (os.environ.get("ESTOQUE_APP_BASE_URL")
            or "http://ipu9fzz363muaape6dklfnpb.177.7.45.242.sslip.io").rstrip("/")

TIMEOUT_SEGUNDOS = 60


class EstoqueAppError(Exception):
    def __init__(self, entidade: str, causa):
        self.entidade = entidade
        self.causa = causa
        super().__init__(f"falha ao buscar '{entidade}' do app de estoque: {causa}")


def _fetch_cache(entidade: str) -> list:
    try:
        resp = requests.get(f"{BASE_URL}/api/cache/{entidade}", timeout=TIMEOUT_SEGUNDOS)
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:
        raise EstoqueAppError(entidade, e)
    if not body.get("ok"):
        raise EstoqueAppError(entidade, body.get("error", "resposta sem ok=true"))
    return body.get("data", [])


def status() -> dict:
    """Contadores do cache remoto (ready/loading/counts) — usado pra checar
    se vale a pena puxar antes de disparar uma importacao pesada."""
    resp = requests.get(f"{BASE_URL}/api/cache/status", timeout=TIMEOUT_SEGUNDOS)
    resp.raise_for_status()
    return resp.json()


def fetch_produtos() -> list:
    return _fetch_cache("produtos")


def fetch_estoques() -> list:
    return _fetch_cache("estoques")


def fetch_filiais() -> list:
    return _fetch_cache("filiais")
