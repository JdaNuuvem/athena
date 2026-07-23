from flask import Blueprint, request, jsonify

producao_bp = Blueprint("producao", __name__, url_prefix="/api/producao")


@producao_bp.route("/dashboard", methods=["GET"])
def prod_dashboard():
    from core.producao import dashboard as pd
    return jsonify(pd())


@producao_bp.route("/op/<int:id>/iniciar", methods=["POST"])
def prod_iniciar_op(id):
    from core.producao import iniciar_op
    return jsonify(iniciar_op(id))


@producao_bp.route("/op/<int:id>/finalizar", methods=["POST"])
def prod_finalizar_op(id):
    from core.producao import finalizar_op
    return jsonify(finalizar_op(id))


@producao_bp.route("/maquina/<int:id>/parar", methods=["POST"])
def prod_parar_maquina(id):
    data = request.json or {}
    from core.producao import parar_maquina
    return jsonify(parar_maquina(id, data.get("motivo", "")))


@producao_bp.route("/maquina/<int:id>/liberar", methods=["POST"])
def prod_liberar_maquina(id):
    from core.producao import liberar_maquina
    return jsonify(liberar_maquina(id))


@producao_bp.route("/<tabela>", methods=["GET"])
def prod_list(tabela):
    from core.producao import list as pl, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify({"data": pl(tabela)})


@producao_bp.route("/<tabela>", methods=["POST"])
def prod_create(tabela):
    from core.producao import create as pc, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(pc(tabela, request.json or {}))


@producao_bp.route("/<tabela>/<int:id>", methods=["GET"])
def prod_get(tabela, id):
    from core.producao import get as pg, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(pg(tabela, id))


@producao_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def prod_update(tabela, id):
    from core.producao import update as pu, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(pu(tabela, id, request.json or {}))


@producao_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def prod_delete(tabela, id):
    from core.producao import delete as pd, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(pd(tabela, id))
