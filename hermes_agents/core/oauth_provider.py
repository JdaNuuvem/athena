"""OAuth2 provider — o Hermes atua como Identity Provider para clientes
externos (Rocket.Chat). Mesmo padrao de core/rbac.py: JWT assinado com
pyjwt, sem framework OAuth novo.

`code` e `access_token` sao os dois JWTs curtos do fluxo Authorization
Code — cada um carrega um claim `typ` (`oauth_code` / `oauth_access`) para
que um nao possa ser usado no lugar do outro mesmo sendo ambos JWTs
assinados com o mesmo secret."""
from datetime import datetime, timedelta, timezone
import jwt as _jwt
from core.rbac import _jwt_secret, JWT_ALGORITHM

AGENT = "OAuth Provider"

CODE_EXPIRACAO_SEGUNDOS = 60
ACCESS_TOKEN_EXPIRACAO_SEGUNDOS = 3600


def gerar_authorization_code(user_id: int, client_id: str, redirect_uri: str) -> str:
    payload = {
        "typ": "oauth_code",
        "user_id": user_id,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=CODE_EXPIRACAO_SEGUNDOS),
        "iat": datetime.now(timezone.utc),
    }
    return _jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def validar_authorization_code(code: str, client_id: str, redirect_uri: str) -> "int | None":
    if not code:
        return None
    try:
        payload = _jwt.decode(code, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except Exception:
        return None
    if payload.get("typ") != "oauth_code":
        return None
    if payload.get("client_id") != client_id or payload.get("redirect_uri") != redirect_uri:
        return None
    return payload.get("user_id")


def gerar_access_token(user_id: int) -> str:
    payload = {
        "typ": "oauth_access",
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=ACCESS_TOKEN_EXPIRACAO_SEGUNDOS),
        "iat": datetime.now(timezone.utc),
    }
    return _jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def validar_access_token(token: str) -> "int | None":
    if not token:
        return None
    try:
        payload = _jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except Exception:
        return None
    if payload.get("typ") != "oauth_access":
        return None
    return payload.get("user_id")
