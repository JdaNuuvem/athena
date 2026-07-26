from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao, usuario_atual_da_request, usuario_tem_permissao

financeiro_bp = Blueprint("financeiro", __name__, url_prefix="/api/financeiro")


@financeiro_bp.route("/<tabela>", methods=["GET"])
def fin_list(tabela):
    from core.financeiro import list as fin_list_fn, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify({"data": fin_list_fn(tabela)})


@financeiro_bp.route("/<tabela>", methods=["POST"])
def fin_create(tabela):
    from core.financeiro import criar_pagamento, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    if not data:
        return jsonify({"error": "Dados obrigatorios"}), 400

    @requer_permissao("financeiro.criar")
    def _go():
        usuario = usuario_atual_da_request()
        tem_aprovar = usuario_tem_permissao("financeiro.aprovar")
        return jsonify(criar_pagamento(tabela, data, usuario["user_id"], usuario["nome"], tem_aprovar))
    return _go()


@financeiro_bp.route("/<tabela>/<int:id>", methods=["GET"])
def fin_get(tabela, id):
    from core.financeiro import get as fin_get_fn, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(fin_get_fn(tabela, id))


@financeiro_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def fin_update(tabela, id):
    from core.financeiro import atualizar_pagamento, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}

    @requer_permissao("financeiro.editar")
    def _go():
        usuario = usuario_atual_da_request()
        tem_aprovar = usuario_tem_permissao("financeiro.aprovar")
        return jsonify(atualizar_pagamento(tabela, id, data, usuario["user_id"], usuario["nome"], tem_aprovar))
    return _go()


@financeiro_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def fin_delete(tabela, id):
    from core.financeiro import get as fin_get_fn, delete as fin_delete_fn, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("financeiro.excluir")
    def _go():
        from core.seguranca import auditar_exclusao
        dados_antes = fin_get_fn(tabela, id)
        resultado = fin_delete_fn(tabela, id)
        if not resultado.get("error"):
            auditar_exclusao("financeiro", tabela, id, dados_antes if not dados_antes.get("error") else None)
        return jsonify(resultado)
    return _go()


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
