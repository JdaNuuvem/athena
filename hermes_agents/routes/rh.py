from flask import Blueprint, request, jsonify

rh_bp = Blueprint("rh", __name__, url_prefix="/api/rh")


@rh_bp.route("/vale", methods=["GET"])
def rh_vale_list():
    from core.rh import list_vale as lv
    return jsonify({"data": lv()})


@rh_bp.route("/vale", methods=["POST"])
def rh_vale_create():
    data = request.json or {}
    from core.rh import criar_vale
    return jsonify(criar_vale(
        int(data.get("funcionario_id", 0)),
        data.get("nome", ""),
        float(data.get("valor", 0)),
        data.get("motivo", "")
    ))


@rh_bp.route("/vale/<int:id>", methods=["PUT"])
def rh_vale_update(id):
    data = request.json or {}
    from core.rh import atualizar_vale
    return jsonify(atualizar_vale(id, data.get("status", "")))


@rh_bp.route("/comissoes", methods=["GET"])
def rh_comissoes_list():
    from core.rh import list_comissoes
    return jsonify({"data": list_comissoes()})


@rh_bp.route("/comissoes", methods=["POST"])
def rh_comissoes_create():
    data = request.json or {}
    from core.rh import criar_comissao
    return jsonify(criar_comissao(
        int(data.get("vendedor_id", 0)),
        data.get("nome", ""),
        data.get("mes", ""),
        float(data.get("total_vendas", 0)),
        float(data.get("comissao_pct", 0)),
        float(data.get("total_comissoes", 0))
    ))


@rh_bp.route("/comissoes/<int:id>", methods=["PUT"])
def rh_comissoes_update(id):
    data = request.json or {}
    from core.rh import atualizar_comissao
    return jsonify(atualizar_comissao(id, data.get("status", "")))


@rh_bp.route("/dashboard", methods=["GET"])
def rh_dashboard():
    from core.rh import dashboard
    return jsonify(dashboard())


@rh_bp.route("/<tabela>", methods=["GET"])
def rh_list(tabela):
    from core.rh import list as rh_list_fn, listar_filtrado, RH_TABLES
    if tabela not in RH_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data_inicio = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")
    status = request.args.get("status", "")
    if data_inicio or data_fim or status:
        return jsonify(listar_filtrado(tabela, data_inicio, data_fim, status))
    return jsonify({"data": rh_list_fn(tabela)})


@rh_bp.route("/<tabela>", methods=["POST"])
def rh_create(tabela):
    from core.rh import create as rh_create_fn, RH_TABLES
    if tabela not in RH_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    if not data:
        return jsonify({"error": "Dados obrigatorios"}), 400
    return jsonify(rh_create_fn(tabela, data))


@rh_bp.route("/<tabela>/<int:id>", methods=["GET"])
def rh_get(tabela, id):
    from core.rh import get as rh_get_fn, RH_TABLES
    if tabela not in RH_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(rh_get_fn(tabela, id))


@rh_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def rh_update(tabela, id):
    from core.rh import update as rh_update_fn, RH_TABLES
    if tabela not in RH_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    return jsonify(rh_update_fn(tabela, id, data))


@rh_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def rh_delete(tabela, id):
    from core.rh import delete as rh_delete_fn, RH_TABLES
    if tabela not in RH_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(rh_delete_fn(tabela, id))


@rh_bp.route("/ponto/data/<data>", methods=["GET"])
def rh_ponto_data(data):
    from core.rh import ponto_por_data
    return jsonify({"data": ponto_por_data(data)})


@rh_bp.route("/folha/resumo/<mes>", methods=["GET"])
def rh_folha_resumo(mes):
    from core.rh import folha_resumo
    return jsonify(folha_resumo(mes))


@rh_bp.route("/beneficios/resumo", methods=["GET"])
def rh_beneficios_resumo():
    from core.rh import beneficios_resumo
    return jsonify(beneficios_resumo())


@rh_bp.route("/funcionario/<int:id>", methods=["GET"])
def rh_funcionario_detalhe(id):
    from core.rh import funcionario_detalhe
    return jsonify(funcionario_detalhe(id))
