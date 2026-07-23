from flask import Blueprint, request, jsonify

compras_bp = Blueprint("compras", __name__, url_prefix="/api/compras")


@compras_bp.route("/dashboard", methods=["GET"])
def compras_dashboard():
    from core.compras import dashboard as compras_dash
    return jsonify(compras_dash())


@compras_bp.route("/<tabela>", methods=["GET"])
def compras_list(tabela):
    from core.compras import list as cl, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify({"data": cl(tabela)})


@compras_bp.route("/<tabela>", methods=["POST"])
def compras_create(tabela):
    from core.compras import create as cc, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    return jsonify(cc(tabela, data))


@compras_bp.route("/<tabela>/<int:id>", methods=["GET"])
def compras_get(tabela, id):
    from core.compras import get as cg, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(cg(tabela, id))


@compras_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def compras_update(tabela, id):
    from core.compras import update as cu, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(cu(tabela, id, request.json or {}))


@compras_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def compras_delete(tabela, id):
    from core.compras import delete as cd, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(cd(tabela, id))


@compras_bp.route("/solicitacoes/<int:id>/aprovar", methods=["POST"])
def compras_aprovar(id):
    data = request.json or {}
    aprovador = data.get("aprovador", "Admin")
    from core.compras import aprovar_solicitacao
    return jsonify(aprovar_solicitacao(id, aprovador))
