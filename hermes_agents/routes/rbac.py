from flask import Blueprint, request, jsonify

rbac_bp = Blueprint("rbac", __name__, url_prefix="/api/rbac")


@rbac_bp.route("/roles", methods=["GET"])
def rbac_list_roles():
    from core.rbac import list_roles
    return jsonify({"roles": list_roles()})


@rbac_bp.route("/roles", methods=["POST"])
def rbac_create_role():
    data = request.json or {}
    from core.rbac import criar_role
    return jsonify(criar_role(data.get("nome", ""), data.get("descricao", ""), data.get("permissoes")))


@rbac_bp.route("/roles/<int:id>", methods=["PUT"])
def rbac_update_role(id):
    data = request.json or {}
    from core.rbac import atualizar_role
    return jsonify(atualizar_role(id, data.get("nome"), data.get("descricao"), data.get("permissoes")))


@rbac_bp.route("/roles/<int:id>", methods=["DELETE"])
def rbac_delete_role(id):
    from core.rbac import deletar_role
    return jsonify(deletar_role(id))


@rbac_bp.route("/permissoes", methods=["GET"])
def rbac_list_permissoes():
    from core.rbac import list_permissoes
    return jsonify({"permissoes": list_permissoes()})


@rbac_bp.route("/usuarios", methods=["GET"])
def rbac_list_usuarios():
    from core.rbac import list_usuarios
    return jsonify({"usuarios": list_usuarios()})


@rbac_bp.route("/usuarios", methods=["POST"])
def rbac_create_usuario():
    data = request.json or {}
    from core.rbac import criar_usuario
    return jsonify(criar_usuario(data.get("nome", ""), data.get("email", ""), data.get("senha", ""), data.get("role", "")))


@rbac_bp.route("/usuarios/<int:id>", methods=["PUT"])
def rbac_update_usuario(id):
    data = request.json or {}
    from core.rbac import atualizar_usuario
    return jsonify(atualizar_usuario(id, data.get("nome"), data.get("role"), data.get("ativo")))
