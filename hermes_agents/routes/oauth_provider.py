"""Rotas do OAuth2 provider (Authorization Code flow) que fazem o Hermes
atuar como Identity Provider para clientes externos — hoje so' o
Rocket.Chat. Ver hermes_agents/core/oauth_provider.py para a geracao/
validacao de code e access_token."""
import os
import hmac
from urllib.parse import quote
from flask import Blueprint, request, jsonify, redirect
from core import get_db, run_async
from core.rbac import verificar_token_sessao
from core.oauth_provider import (
    gerar_authorization_code, validar_authorization_code,
    gerar_access_token, validar_access_token,
    ACCESS_TOKEN_EXPIRACAO_SEGUNDOS,
)

oauth_provider_bp = Blueprint("oauth_provider", __name__, url_prefix="/oauth")


def _client_id() -> str:
    return os.environ.get("ROCKETCHAT_OAUTH_CLIENT_ID", "")


def _client_secret() -> str:
    return os.environ.get("ROCKETCHAT_OAUTH_CLIENT_SECRET", "")


def _redirect_uri_esperado() -> str:
    return os.environ.get("ROCKETCHAT_OAUTH_REDIRECT_URI", "")


def _hermes_login_url() -> str:
    return os.environ.get("HERMES_LOGIN_URL", "/login")


def _token_da_request() -> str:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):]
    return request.cookies.get("auth_token", "")


@oauth_provider_bp.route("/authorize", methods=["GET"])
def authorize():
    if request.args.get("response_type") != "code":
        return jsonify({"error": "unsupported_response_type"}), 400

    client_id = request.args.get("client_id", "")
    redirect_uri = request.args.get("redirect_uri", "")
    if not _client_id() or client_id != _client_id():
        return jsonify({"error": "invalid_client"}), 400
    if not _redirect_uri_esperado() or redirect_uri != _redirect_uri_esperado():
        return jsonify({"error": "invalid_redirect_uri"}), 400

    payload = verificar_token_sessao(_token_da_request())
    if not payload or not payload.get("user_id"):
        return redirect(_hermes_login_url())

    code = gerar_authorization_code(payload["user_id"], client_id, redirect_uri)
    state = request.args.get("state", "")
    separador = "&" if "?" in redirect_uri else "?"
    destino = f"{redirect_uri}{separador}code={quote(code)}"
    if state:
        destino += f"&state={quote(state)}"
    return redirect(destino)


@oauth_provider_bp.route("/token", methods=["POST"])
def token():
    if request.form.get("grant_type") != "authorization_code":
        return jsonify({"error": "unsupported_grant_type"}), 400

    client_id = request.form.get("client_id", "")
    client_secret = request.form.get("client_secret", "")
    code = request.form.get("code", "")
    redirect_uri = request.form.get("redirect_uri", "")

    if (not _client_id() or not _client_secret() or client_id != _client_id()
            or not hmac.compare_digest(client_secret, _client_secret())):
        return jsonify({"error": "invalid_client"}), 401

    user_id = validar_authorization_code(code, client_id, redirect_uri)
    if not user_id:
        return jsonify({"error": "invalid_grant"}), 400

    access_token = gerar_access_token(user_id)
    return jsonify({
        "access_token": access_token, "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_EXPIRACAO_SEGUNDOS,
    })


async def _buscar_usuario(user_id: int):
    db = await get_db()
    row = await db.fetchrow(
        "SELECT id, nome, email FROM rbac_usuarios WHERE id = $1 AND ativo = TRUE", user_id
    )
    return dict(row) if row else None


@oauth_provider_bp.route("/userinfo", methods=["GET"])
def userinfo():
    user_id = validar_access_token(_token_da_request())
    if not user_id:
        return jsonify({"error": "invalid_token"}), 401

    usuario = run_async(_buscar_usuario(user_id))
    if not usuario:
        return jsonify({"error": "invalid_token"}), 401

    email = usuario.get("email", "")
    username = email.split("@")[0] if email else f"usuario{usuario['id']}"
    return jsonify({
        "id": usuario["id"],
        "username": username,
        "email": email,
        "name": usuario.get("nome") or username,
    })
