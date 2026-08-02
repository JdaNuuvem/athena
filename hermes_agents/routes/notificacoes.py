from flask import Blueprint, jsonify
from core.rbac import usuario_atual_da_request

notificacoes_bp = Blueprint("notificacoes", __name__, url_prefix="/api/notificacoes")


@notificacoes_bp.route("", methods=["GET"])
def notif_listar():
    usuario = usuario_atual_da_request()
    if not usuario.get("user_id"):
        return jsonify({"error": "Nao autenticado"}), 401
    from core.notificacoes import listar_notificacoes
    return jsonify({"data": listar_notificacoes(int(usuario["user_id"]))})


@notificacoes_bp.route("/<int:id>/lida", methods=["POST"])
def notif_marcar_lida(id):
    usuario = usuario_atual_da_request()
    if not usuario.get("user_id"):
        return jsonify({"error": "Nao autenticado"}), 401
    from core.notificacoes import marcar_lida
    return jsonify(marcar_lida(id, int(usuario["user_id"])))


@notificacoes_bp.route("/marcar-todas-lidas", methods=["POST"])
def notif_marcar_todas_lidas():
    usuario = usuario_atual_da_request()
    if not usuario.get("user_id"):
        return jsonify({"error": "Nao autenticado"}), 401
    from core.notificacoes import marcar_todas_lidas
    return jsonify(marcar_todas_lidas(int(usuario["user_id"])))
