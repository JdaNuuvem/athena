from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao

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

    @requer_permissao("compras.criar")
    def _go():
        return jsonify(cc(tabela, data))
    return _go()


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
    data = request.json or {}

    @requer_permissao("compras.editar")
    def _go():
        return jsonify(cu(tabela, id, data))
    return _go()


@compras_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def compras_delete(tabela, id):
    from core.compras import get as cg, delete as cd, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("compras.excluir")
    def _go():
        from core.seguranca import auditar_exclusao
        dados_antes = cg(tabela, id)
        resultado = cd(tabela, id)
        if not resultado.get("error"):
            auditar_exclusao("compras", tabela, id, dados_antes if not dados_antes.get("error") else None)
        return jsonify(resultado)
    return _go()


@compras_bp.route("/solicitacoes/<int:id>/aprovar", methods=["POST"])
def compras_aprovar(id):
    from core.compras import aprovar_solicitacao
    from core.rbac import usuario_atual_da_request

    @requer_permissao("compras.aprovar")
    def _go():
        usuario = usuario_atual_da_request()
        return jsonify(aprovar_solicitacao(id, usuario["user_id"], usuario["nome"]))
    return _go()
