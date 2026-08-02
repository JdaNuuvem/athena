from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao
from core.api_utils import status_for_resultado as _status_for

atendimento_bp = Blueprint("atendimento", __name__, url_prefix="/api/atendimento")


@atendimento_bp.route("/dashboard", methods=["GET"])
def atend_dashboard():
    from core.atendimento import dashboard as ad
    return jsonify(ad())


@atendimento_bp.route("/tickets/criar", methods=["POST"])
def atend_criar_ticket():
    data = request.json or {}

    @requer_permissao("atendimento.criar")
    def _go():
        from core.atendimento import criar_ticket
        return jsonify(criar_ticket(data.get("cliente", ""), data.get("assunto", ""),
                                    data.get("canal", "whatsapp"), data.get("prioridade", "normal")))
    return _go()


@atendimento_bp.route("/tickets/<int:id>/mensagem", methods=["POST"])
def atend_mensagem(id):
    data = request.json or {}

    @requer_permissao("atendimento.criar")
    def _go():
        from core.atendimento import adicionar_mensagem
        return jsonify(adicionar_mensagem(id, data.get("remetente", ""), data.get("conteudo", ""),
                                          data.get("tipo", "texto")))
    return _go()


@atendimento_bp.route("/tickets/<int:id>/fechar", methods=["POST"])
def atend_fechar(id):
    @requer_permissao("atendimento.editar")
    def _go():
        from core.atendimento import fechar_ticket
        return jsonify(fechar_ticket(id))
    return _go()


@atendimento_bp.route("/tickets/<int:id>/reabrir", methods=["POST"])
def atend_reabrir(id):
    @requer_permissao("atendimento.editar")
    def _go():
        from core.atendimento import reabrir_ticket
        return jsonify(reabrir_ticket(id))
    return _go()


@atendimento_bp.route("/tickets/<int:id>/status", methods=["PUT"])
def atend_mudar_status(id):
    data = request.json or {}

    @requer_permissao("atendimento.editar")
    def _go():
        from core.atendimento import mudar_status_ticket
        resultado = mudar_status_ticket(id, data.get("status", ""))
        return jsonify(resultado), (400 if resultado.get("error") else 200)
    return _go()


@atendimento_bp.route("/tickets/<int:id>/atribuir", methods=["PUT"])
def atend_atribuir(id):
    data = request.json or {}

    @requer_permissao("atendimento.editar")
    def _go():
        atendente_id = data.get("atendente_id")
        if not atendente_id:
            return jsonify({"error": "atendente_id obrigatorio"}), 400
        from core.atendimento import atribuir_ticket
        resultado = atribuir_ticket(id, int(atendente_id))
        return jsonify(resultado), (400 if resultado.get("error") else 200)
    return _go()


@atendimento_bp.route("/tickets", methods=["GET"])
def atend_listar_tickets():
    @requer_permissao("atendimento.ver")
    def _go():
        from core.atendimento import listar_tickets_filtrado
        atendente_id_raw = request.args.get("atendente_id")
        atendente_id = None
        if atendente_id_raw:
            try:
                atendente_id = int(atendente_id_raw)
            except ValueError:
                return jsonify({"error": "atendente_id invalido"}), 400
        return jsonify({"data": listar_tickets_filtrado(
            status=request.args.get("status") or None,
            prioridade=request.args.get("prioridade") or None,
            canal=request.args.get("canal") or None,
            atendente_id=atendente_id,
            q=request.args.get("q") or None,
            de=request.args.get("de") or None,
            ate=request.args.get("ate") or None,
        )})
    return _go()


@atendimento_bp.route("/atendentes", methods=["GET"])
def atend_listar_atendentes():
    @requer_permissao("atendimento.ver")
    def _go():
        from core.atendimento import listar_atendentes
        return jsonify({"data": listar_atendentes()})
    return _go()


@atendimento_bp.route("/kb_artigos/<int:id>/visualizar", methods=["POST"])
def atend_kb_visualizar(id):
    @requer_permissao("atendimento.ver")
    def _go():
        from core.atendimento import visualizar_artigo_kb
        resultado = visualizar_artigo_kb(id)
        return jsonify(resultado), _status_for(resultado)
    return _go()


@atendimento_bp.route("/kb_artigos/<int:id>/votar", methods=["POST"])
def atend_kb_votar(id):
    data = request.json or {}

    @requer_permissao("atendimento.ver")
    def _go():
        from core.atendimento import votar_artigo_kb
        resultado = votar_artigo_kb(id, bool(data.get("util")))
        return jsonify(resultado), _status_for(resultado)
    return _go()


@atendimento_bp.route("/<tabela>", methods=["GET"])
def atend_list(tabela):
    from core.atendimento import list as al, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("atendimento.ver")
    def _go():
        return jsonify({"data": al(tabela)})
    return _go()


@atendimento_bp.route("/<tabela>", methods=["POST"])
def atend_create(tabela):
    from core.atendimento import create as ac, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}

    @requer_permissao("atendimento.criar")
    def _go():
        resultado = ac(tabela, data)
        return jsonify(resultado), _status_for(resultado)
    return _go()


@atendimento_bp.route("/<tabela>/<int:id>", methods=["GET"])
def atend_get(tabela, id):
    from core.atendimento import get as ag, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("atendimento.ver")
    def _go():
        resultado = ag(tabela, id)
        return jsonify(resultado), _status_for(resultado)
    return _go()


@atendimento_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def atend_update(tabela, id):
    from core.atendimento import update as au, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}

    @requer_permissao("atendimento.editar")
    def _go():
        resultado = au(tabela, id, data)
        return jsonify(resultado), _status_for(resultado)
    return _go()


@atendimento_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def atend_delete(tabela, id):
    from core.atendimento import get as ag, delete as ad, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("atendimento.excluir")
    def _go():
        from core.seguranca import auditar_exclusao
        dados_antes = ag(tabela, id)
        resultado = ad(tabela, id)
        if not resultado.get("error"):
            auditar_exclusao("atendimento", tabela, id, dados_antes if not dados_antes.get("error") else None)
        return jsonify(resultado), _status_for(resultado)
    return _go()
