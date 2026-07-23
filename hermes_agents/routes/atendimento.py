from flask import Blueprint, request, jsonify

atendimento_bp = Blueprint("atendimento", __name__, url_prefix="/api/atendimento")


@atendimento_bp.route("/dashboard", methods=["GET"])
def atend_dashboard():
    from core.atendimento import dashboard as ad
    return jsonify(ad())


@atendimento_bp.route("/tickets/criar", methods=["POST"])
def atend_criar_ticket():
    data = request.json or {}
    from core.atendimento import criar_ticket
    return jsonify(criar_ticket(data.get("cliente", ""), data.get("assunto", ""),
                                data.get("canal", "whatsapp"), data.get("prioridade", "normal")))


@atendimento_bp.route("/tickets/<int:id>/mensagem", methods=["POST"])
def atend_mensagem(id):
    data = request.json or {}
    from core.atendimento import adicionar_mensagem
    return jsonify(adicionar_mensagem(id, data.get("remetente", ""), data.get("conteudo", ""),
                                      data.get("tipo", "texto")))


@atendimento_bp.route("/tickets/<int:id>/fechar", methods=["POST"])
def atend_fechar(id):
    from core.atendimento import fechar_ticket
    return jsonify(fechar_ticket(id))


@atendimento_bp.route("/tickets/<int:id>/reabrir", methods=["POST"])
def atend_reabrir(id):
    from core.atendimento import reabrir_ticket
    return jsonify(reabrir_ticket(id))


@atendimento_bp.route("/<tabela>", methods=["GET"])
def atend_list(tabela):
    from core.atendimento import list as al, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify({"data": al(tabela)})


@atendimento_bp.route("/<tabela>", methods=["POST"])
def atend_create(tabela):
    from core.atendimento import create as ac, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(ac(tabela, request.json or {}))


@atendimento_bp.route("/<tabela>/<int:id>", methods=["GET"])
def atend_get(tabela, id):
    from core.atendimento import get as ag, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(ag(tabela, id))


@atendimento_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def atend_update(tabela, id):
    from core.atendimento import update as au, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(au(tabela, id, request.json or {}))


@atendimento_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def atend_delete(tabela, id):
    from core.atendimento import delete as ad, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(ad(tabela, id))
