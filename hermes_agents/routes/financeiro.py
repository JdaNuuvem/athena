from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao, usuario_atual_da_request, usuario_tem_permissao
from core.api_utils import status_for_resultado as _status_for

financeiro_bp = Blueprint("financeiro", __name__, url_prefix="/api/financeiro")


def _resolver_aprovador(data: dict, usuario: dict) -> tuple:
    """Quem grava como aprovador de um pagamento acima do limite: o proprio
    usuario logado (se ja tem financeiro.aprovar) ou, senao, um gerente
    identificado por PIN/cracha que tenha essa permissao — mesmo padrao de
    autorizacao gerencial ja usado no PDV, aplicado ao financeiro."""
    aprovador_id, aprovador_nome = usuario["user_id"], usuario["nome"]
    tem_aprovar = usuario_tem_permissao("financeiro.aprovar")
    if not tem_aprovar and (data.get("usuario_pin_id") or data.get("codigo_barras")):
        from core.rbac import autorizar_com_permissao
        auth = autorizar_com_permissao(
            "financeiro.aprovar", data.get("usuario_pin_id"),
            str(data.get("pin", "")), str(data.get("codigo_barras", "")),
        )
        if not auth.get("error"):
            tem_aprovar = True
            aprovador_id, aprovador_nome = auth["id"], auth["nome"]
    return aprovador_id, aprovador_nome, tem_aprovar


@financeiro_bp.route("/<tabela>", methods=["GET"])
def fin_list(tabela):
    from core.financeiro import list as fin_list_fn, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("financeiro.ver")
    def _go():
        return jsonify({"data": fin_list_fn(tabela)})
    return _go()


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
        aprovador_id, aprovador_nome, tem_aprovar = _resolver_aprovador(data, usuario)
        resultado = criar_pagamento(tabela, data, aprovador_id, aprovador_nome, tem_aprovar)
        return jsonify(resultado), _status_for(resultado)
    return _go()


@financeiro_bp.route("/<tabela>/<int:id>", methods=["GET"])
def fin_get(tabela, id):
    from core.financeiro import get as fin_get_fn, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("financeiro.ver")
    def _go():
        resultado = fin_get_fn(tabela, id)
        return jsonify(resultado), _status_for(resultado)
    return _go()


@financeiro_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def fin_update(tabela, id):
    from core.financeiro import atualizar_pagamento, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}

    @requer_permissao("financeiro.editar")
    def _go():
        usuario = usuario_atual_da_request()
        aprovador_id, aprovador_nome, tem_aprovar = _resolver_aprovador(data, usuario)
        resultado = atualizar_pagamento(tabela, id, data, aprovador_id, aprovador_nome, tem_aprovar)
        return jsonify(resultado), _status_for(resultado)
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
        return jsonify(resultado), _status_for(resultado)
    return _go()


@financeiro_bp.route("/fluxo_caixa/resumo", methods=["GET"])
def fin_fluxo_caixa_resumo():
    @requer_permissao("financeiro.ver")
    def _go():
        from core.financeiro import fluxo_caixa_resumo
        dias = request.args.get("dias", 30, type=int)
        return jsonify(fluxo_caixa_resumo(dias))
    return _go()


@financeiro_bp.route("/dre/resumo", methods=["GET"], defaults={"mes": None})
@financeiro_bp.route("/dre/resumo/<mes>", methods=["GET"])
def fin_dre_resumo(mes):
    @requer_permissao("financeiro.ver")
    def _go():
        from core.financeiro import dre_resumo
        mes_final = mes or request.args.get("mes")
        return jsonify(dre_resumo(mes_final))
    return _go()
