import os
import hmac
import secrets
import functools
from datetime import datetime, timedelta, timezone

import jwt
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint("auth", __name__)

API_TOKEN = os.environ.get("ATHENA_TOKEN", "")
if not API_TOKEN:
    API_TOKEN = secrets.token_hex(16)

JWT_SECRET = os.environ.get("ATHENA_JWT_SECRET", "")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)


# ponytail: users from env vars ATHENA_USERS="admin:hash:role:nome,joao:hash:role:nome"
# hash gerado com werkzeug.security.generate_password_hash
raw = os.environ.get("ATHENA_USERS", "")
USUARIOS = {}
if raw:
    for entry in raw.split(","):
        parts = entry.strip().split(":")
        if len(parts) >= 4:
            USUARIOS[parts[0]] = {"hash": parts[1], "role": parts[2], "name": parts[3]}

if "admin" not in USUARIOS:
    _senha_temporaria = secrets.token_urlsafe(12)
    USUARIOS["admin"] = {
        "hash": generate_password_hash(_senha_temporaria),
        "role": "admin",
        "name": "Admin",
    }
    print(f"[auth] ATHENA_USERS não configurada — senha temporária do admin gerada: {_senha_temporaria}")


ROLE_PERMISSIONS = {
    "admin": [
        "ver_produtos", "ver_estoque", "ver_lojas", "ver_vendas", "ver_financeiro",
        "ver_tributario", "ver_perdas", "ver_marketplaces", "ver_integracoes",
        "exportar", "gerenciar_usuarios",
    ],
    "financeiro": ["ver_financeiro", "ver_tributario", "ver_perdas", "ver_vendas", "exportar"],
    "operador_loja": ["ver_lojas", "ver_estoque", "ver_vendas", "ver_perdas", "ver_produtos"],
}


def _issue_token(username: str, role: str, name: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "name": name,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _decode_token(auth_header: str):
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def require_role(*roles: str):
    """Decorator Flask: exige JWT válido; se `roles` não vazio, exige que o papel do token esteja nele."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            payload = _decode_token(request.headers.get("Authorization", ""))
            if payload is None:
                return jsonify({"error": "Unauthorized"}), 401
            if roles and payload.get("role") not in roles:
                return jsonify({"error": "Forbidden"}), 403
            request.user = payload
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@auth_bp.route("/api/auth/login", methods=["POST"])
def simple_login():
    data = request.json or {}
    username = data.get("username", "").lower()
    password = data.get("password", "")
    api_key = data.get("api_key", "")

    user = USUARIOS.get(username, {})
    if user and check_password_hash(user.get("hash", ""), password):
        token = _issue_token(username, user["role"], user["name"])
        return jsonify({"token": token, "role": user["role"], "name": user["name"]})
    if api_key and hmac.compare_digest(api_key, API_TOKEN):
        token = _issue_token("admin", "admin", "Admin")
        return jsonify({"token": token, "role": "admin", "name": "Admin"})
    return jsonify({"error": "Invalid credentials"}), 401


@auth_bp.route("/api/me", methods=["GET"])
def current_user():
    payload = _decode_token(request.headers.get("Authorization", ""))
    if payload is None:
        return jsonify({"error": "Unauthorized"}), 401
    role = payload.get("role", "")
    return jsonify({
        "name": payload.get("name", ""),
        "role": role,
        "permissoes": ROLE_PERMISSIONS.get(role, []),
    })
