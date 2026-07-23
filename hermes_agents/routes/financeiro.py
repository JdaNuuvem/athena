from flask import Blueprint, request, jsonify

financeiro_bp = Blueprint("financeiro", __name__, url_prefix="/api/financeiro")


@financeiro_bp.route("/<tabela>", methods=["GET"])
def fin_list(tabela):
    from core.financeiro import list as fin_list_fn, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify({"data": fin_list_fn(tabela)})


@financeiro_bp.route("/<tabela>", methods=["POST"])
def fin_create(tabela):
    from core.financeiro import create as fin_create_fn, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    if not data:
        return jsonify({"error": "Dados obrigatorios"}), 400
    return jsonify(fin_create_fn(tabela, data))


@financeiro_bp.route("/<tabela>/<int:id>", methods=["GET"])
def fin_get(tabela, id):
    from core.financeiro import get as fin_get_fn, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(fin_get_fn(tabela, id))


@financeiro_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def fin_update(tabela, id):
    from core.financeiro import update as fin_update_fn, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    return jsonify(fin_update_fn(tabela, id, data))


@financeiro_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def fin_delete(tabela, id):
    from core.financeiro import delete as fin_delete_fn, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(fin_delete_fn(tabela, id))


@financeiro_bp.route("/fluxo_caixa/resumo", methods=["GET"])
def fin_fluxo_caixa_resumo():
    from core.financeiro import fluxo_caixa_resumo
    dias = request.args.get("dias", 30, type=int)
    return jsonify(fluxo_caixa_resumo(dias))


@financeiro_bp.route("/dre/resumo", methods=["GET"], defaults={"mes": None})
@financeiro_bp.route("/dre/resumo/<mes>", methods=["GET"])
def fin_dre_resumo(mes):
    from core.financeiro import dre_resumo
    mes = mes or request.args.get("mes")
    return jsonify(dre_resumo(mes))
