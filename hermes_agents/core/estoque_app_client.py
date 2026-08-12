"""Client HTTP para o app proprio de bipagem/atualizacao de estoque (fonte
real dos dados fisicos das lojas — mesmo catalogo que a i9Logic serve, ja
com a contagem fisica da bipagem mesclada por produto/filial).

/api/external/produtos-existentes exige autenticacao via header X-API-Key
(ESTOQUE_APP_API_KEY) - diferente do endpoint de cache antigo, publico. A
chave nunca fica hardcoded aqui: so' env var (ou core.config como fallback,
mesmo padrao das outras integracoes)."""
import os
import requests

AGENT = "Estoque App Client"

BASE_URL = (os.environ.get("ESTOQUE_APP_BASE_URL")
            or "http://ipu9fzz363muaape6dklfnpb.177.7.45.242.sslip.io").rstrip("/")

TIMEOUT_SEGUNDOS = 60


def _api_key() -> str:
    if os.environ.get("ESTOQUE_APP_API_KEY"):
        return os.environ["ESTOQUE_APP_API_KEY"]
    from core.config import get_config
    return get_config("estoque_app", "api_key") or ""


class EstoqueAppError(Exception):
    def __init__(self, entidade: str, causa):
        self.entidade = entidade
        self.causa = causa
        super().__init__(f"falha ao buscar '{entidade}' do app de estoque: {causa}")


def fetch_produtos_existentes(filial_id: int = None) -> list:
    """Produtos ja bipados (catalogo + contagem fisica mesclada de todas as
    sessoes da loja, nao so' hoje). filial_id=None traz de todas as lojas
    que ja tem alguma sessao de bipagem registrada. qtdContada vem None pro
    produto que so' foi escaneado mas ainda nao teve quantidade digitada -
    quem consome isso NAO pode tratar None como zero."""
    api_key = _api_key()
    if not api_key:
        raise EstoqueAppError("produtos-existentes", "ESTOQUE_APP_API_KEY nao configurada")
    params = {"filialId": filial_id} if filial_id is not None else {}
    try:
        resp = requests.get(
            f"{BASE_URL}/api/external/produtos-existentes",
            headers={"X-API-Key": api_key}, params=params, timeout=TIMEOUT_SEGUNDOS)
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:
        raise EstoqueAppError("produtos-existentes", e)
    if not body.get("ok"):
        raise EstoqueAppError("produtos-existentes", body.get("error", "resposta sem ok=true"))
    return body.get("produtos", [])
