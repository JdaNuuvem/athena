from flask import Blueprint, request, jsonify

crm_bp = Blueprint("crm", __name__, url_prefix="/api/crm")


@crm_bp.route("/funil", methods=["GET"])
def crm_funil():
    from core.crm import funil as crm_funil_fn
    return jsonify(crm_funil_fn())


@crm_bp.route("/importar-bling", methods=["POST"])
def crm_importar_bling():
    from core.crm import importar_contatos_bling
    return jsonify(importar_contatos_bling())


@crm_bp.route("/<tabela>", methods=["GET"])
def crm_list(tabela):
    from core.crm import list as crm_list_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify({"data": crm_list_fn(tabela)})


@crm_bp.route("/<tabela>", methods=["POST"])
def crm_create(tabela):
    from core.crm import create as crm_create_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    if not data:
        return jsonify({"error": "Dados obrigatorios"}), 400
    return jsonify(crm_create_fn(tabela, data))


@crm_bp.route("/<tabela>/<int:id>", methods=["GET"])
def crm_get(tabela, id):
    from core.crm import get as crm_get_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(crm_get_fn(tabela, id))


@crm_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def crm_update(tabela, id):
    from core.crm import update as crm_update_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    return jsonify(crm_update_fn(tabela, id, data))


@crm_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def crm_delete(tabela, id):
    from core.crm import delete as crm_delete_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(crm_delete_fn(tabela, id))
