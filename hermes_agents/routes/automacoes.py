from flask import Blueprint, request, jsonify

automacoes_bp = Blueprint("automacoes", __name__, url_prefix="/api/automacoes")


@automacoes_bp.route("/dashboard", methods=["GET"])
def auto_dashboard():
    from core.automacoes import dashboard as ad
    return jsonify(ad())


@automacoes_bp.route("/disparar", methods=["POST"])
def auto_disparar_webhooks():
    from core.automacoes import disparar_webhooks
    data = request.json or {}
    evento = data.get("evento", "")
    dados = data.get("dados", {})
    if not evento:
        return jsonify({"error": "evento obrigatorio"}), 400
    return jsonify(disparar_webhooks(evento, dados))


@automacoes_bp.route("/<tabela>", methods=["GET"])
def auto_list(tabela):
    from core.automacoes import list as al, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify({"data": al(tabela)})


@automacoes_bp.route("/<tabela>", methods=["POST"])
def auto_create(tabela):
    from core.automacoes import create as ac, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(ac(tabela, request.json or {}))


@automacoes_bp.route("/<tabela>/<int:id>", methods=["GET"])
def auto_get(tabela, id):
    from core.automacoes import get as ag, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(ag(tabela, id))


@automacoes_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def auto_update(tabela, id):
    from core.automacoes import update as au, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(au(tabela, id, request.json or {}))


@automacoes_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def auto_delete(tabela, id):
    from core.automacoes import delete as ad, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(ad(tabela, id))
