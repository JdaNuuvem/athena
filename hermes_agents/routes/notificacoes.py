from flask import Blueprint, jsonify
from core.rbac import usuario_atual_da_request

notificacoes_bp = Blueprint("notificacoes", __name__, url_prefix="/api/notificacoes")


@notificacoes_bp.route("", methods=["GET"])
def notif_listar():
    usuario = usuario_atual_da_request()
    # ponytail: user_id da conta master (login ATHENA_ADMIN_EMAIL) e' 0 —
    # "if not usuario.get('user_id')" tratava 0 como falsy e barrava a conta
    # master de TODA pagina (NotificationBell monta em todo layout, o 401
    # dispara handleUnauthorized() e redireciona pro login). 0 e' um user_id
    # valido, so' a ausencia de token (None) que deve virar 401. Mesmo padrao
    # ja corrigido em routes/chat.py e core/chat_ws.py.
    if usuario.get("user_id") is None:
        return jsonify({"error": "Nao autenticado"}), 401
    from core.notificacoes import listar_notificacoes
    return jsonify({"data": listar_notificacoes(int(usuario["user_id"]))})


@notificacoes_bp.route("/<int:id>/lida", methods=["POST"])
def notif_marcar_lida(id):
    usuario = usuario_atual_da_request()
    if usuario.get("user_id") is None:
        return jsonify({"error": "Nao autenticado"}), 401
    from core.notificacoes import marcar_lida
    return jsonify(marcar_lida(id, int(usuario["user_id"])))


@notificacoes_bp.route("/marcar-todas-lidas", methods=["POST"])
def notif_marcar_todas_lidas():
    usuario = usuario_atual_da_request()
    if usuario.get("user_id") is None:
        return jsonify({"error": "Nao autenticado"}), 401
    from core.notificacoes import marcar_todas_lidas
    return jsonify(marcar_todas_lidas(int(usuario["user_id"])))
