from flask import Blueprint, request, jsonify

cadastros_bp = Blueprint("cadastros", __name__, url_prefix="/api/cadastros")


@cadastros_bp.route("/<tabela>", methods=["GET"])
def cad_list(tabela):
    from core.cadastros import list as cad_list_fn, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify({"data": cad_list_fn(tabela)})


@cadastros_bp.route("/<tabela>", methods=["POST"])
def cad_create(tabela):
    from core.cadastros import create as cad_create_fn, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    if not data:
        return jsonify({"error": "Dados obrigatorios"}), 400
    return jsonify(cad_create_fn(tabela, data))


@cadastros_bp.route("/<tabela>/<int:id>", methods=["GET"])
def cad_get(tabela, id):
    from core.cadastros import get as cad_get_fn, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(cad_get_fn(tabela, id))


@cadastros_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def cad_update(tabela, id):
    from core.cadastros import update as cad_update_fn, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    return jsonify(cad_update_fn(tabela, id, data))


@cadastros_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def cad_delete(tabela, id):
    from core.cadastros import delete as cad_delete_fn, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(cad_delete_fn(tabela, id))


@cadastros_bp.route("/permissoes/perfil", methods=["GET"])
def cad_permissoes_perfil():
    from core.cadastros import permissoes_por_perfil
    return jsonify({"data": permissoes_por_perfil()})


@cadastros_bp.route("/vendedores/comissao", methods=["GET"])
def cad_vendedor_comissao():
    from core.cadastros import vendedor_comissao_resumo
    return jsonify(vendedor_comissao_resumo())


@cadastros_bp.route("/vendedores/metas", methods=["GET"], defaults={"mes": None})
@cadastros_bp.route("/vendedores/metas/<mes>", methods=["GET"])
def cad_vendedor_metas(mes):
    from core.cadastros import vendedor_metas
    return jsonify({"data": vendedor_metas(mes)})


@cadastros_bp.route("/fornecedores/resumo", methods=["GET"])
def cad_fornecedor_resumo():
    from core.cadastros import fornecedor_resumo
    return jsonify({"data": fornecedor_resumo()})
