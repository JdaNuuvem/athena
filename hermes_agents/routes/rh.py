from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao

rh_bp = Blueprint("rh", __name__, url_prefix="/api/rh")


@rh_bp.route("/vale", methods=["GET"])
def rh_vale_list():
    @requer_permissao("rh.ver")
    def _go():
        from core.rh import list_vale as lv
        return jsonify({"data": lv()})
    return _go()


@rh_bp.route("/vale", methods=["POST"])
def rh_vale_create():
    data = request.json or {}

    @requer_permissao("rh.criar")
    def _go():
        from core.rh import criar_vale
        return jsonify(criar_vale(
            int(data.get("funcionario_id", 0)),
            data.get("nome", ""),
            float(data.get("valor", 0)),
            data.get("motivo", "")
        ))
    return _go()


@rh_bp.route("/vale/<int:id>", methods=["PUT"])
def rh_vale_update(id):
    data = request.json or {}

    @requer_permissao("rh.editar")
    def _go():
        from core.rh import atualizar_vale
        return jsonify(atualizar_vale(id, data.get("status", "")))
    return _go()


@rh_bp.route("/comissoes", methods=["GET"])
def rh_comissoes_list():
    @requer_permissao("rh.ver")
    def _go():
        from core.rh import list_comissoes
        return jsonify({"data": list_comissoes()})
    return _go()


@rh_bp.route("/comissoes", methods=["POST"])
def rh_comissoes_create():
    data = request.json or {}

    @requer_permissao("rh.criar")
    def _go():
        from core.rh import criar_comissao
        return jsonify(criar_comissao(
            int(data.get("vendedor_id", 0)),
            data.get("nome", ""),
            data.get("mes", ""),
            float(data.get("total_vendas", 0)),
            float(data.get("comissao_pct", 0)),
            float(data.get("total_comissoes", 0))
        ))
    return _go()


@rh_bp.route("/comissoes/<int:id>", methods=["PUT"])
def rh_comissoes_update(id):
    data = request.json or {}

    @requer_permissao("rh.editar")
    def _go():
        from core.rh import atualizar_comissao
        return jsonify(atualizar_comissao(id, data.get("status", "")))
    return _go()


@rh_bp.route("/dashboard", methods=["GET"])
def rh_dashboard():
    @requer_permissao("rh.ver")
    def _go():
        from core.rh import dashboard
        return jsonify(dashboard())
    return _go()


@rh_bp.route("/<tabela>", methods=["GET"])
def rh_list(tabela):
    from core.rh import list as rh_list_fn, listar_filtrado, list_paginado, RH_TABLES
    if tabela not in RH_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("rh.ver")
    def _go():
        pagina = request.args.get("pagina", type=int)
        if pagina is not None:
            por_pagina = request.args.get("por_pagina", default=50, type=int)
            busca = request.args.get("busca", default=None, type=str)
            return jsonify(list_paginado(tabela, pagina, por_pagina, busca))
        data_inicio = request.args.get("data_inicio", "")
        data_fim = request.args.get("data_fim", "")
        status = request.args.get("status", "")
        if data_inicio or data_fim or status:
            return jsonify(listar_filtrado(tabela, data_inicio, data_fim, status))
        return jsonify({"data": rh_list_fn(tabela)})
    return _go()


@rh_bp.route("/<tabela>", methods=["POST"])
def rh_create(tabela):
    from core.rh import create as rh_create_fn, RH_TABLES
    if tabela not in RH_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    if not data:
        return jsonify({"error": "Dados obrigatorios"}), 400

    @requer_permissao("rh.criar")
    def _go():
        return jsonify(rh_create_fn(tabela, data))
    return _go()


@rh_bp.route("/<tabela>/<int:id>", methods=["GET"])
def rh_get(tabela, id):
    from core.rh import get as rh_get_fn, RH_TABLES
    if tabela not in RH_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("rh.ver")
    def _go():
        return jsonify(rh_get_fn(tabela, id))
    return _go()


@rh_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def rh_update(tabela, id):
    from core.rh import update as rh_update_fn, RH_TABLES
    if tabela not in RH_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}

    @requer_permissao("rh.editar")
    def _go():
        return jsonify(rh_update_fn(tabela, id, data))
    return _go()


@rh_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def rh_delete(tabela, id):
    from core.rh import get as rh_get_fn, delete as rh_delete_fn, RH_TABLES
    if tabela not in RH_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("rh.excluir")
    def _go():
        from core.seguranca import auditar_exclusao
        dados_antes = rh_get_fn(tabela, id)
        resultado = rh_delete_fn(tabela, id)
        if not resultado.get("error"):
            auditar_exclusao("rh", tabela, id, dados_antes if not dados_antes.get("error") else None)
        return jsonify(resultado)
    return _go()


@rh_bp.route("/ponto/data/<data>", methods=["GET"])
def rh_ponto_data(data):
    @requer_permissao("rh.ver")
    def _go():
        from core.rh import ponto_por_data
        return jsonify({"data": ponto_por_data(data)})
    return _go()


@rh_bp.route("/folha/resumo/<mes>", methods=["GET"])
def rh_folha_resumo(mes):
    @requer_permissao("rh.ver")
    def _go():
        from core.rh import folha_resumo
        return jsonify(folha_resumo(mes))
    return _go()


@rh_bp.route("/beneficios/resumo", methods=["GET"])
def rh_beneficios_resumo():
    @requer_permissao("rh.ver")
    def _go():
        from core.rh import beneficios_resumo
        return jsonify(beneficios_resumo())
    return _go()


@rh_bp.route("/funcionario/<int:id>", methods=["GET"])
def rh_funcionario_detalhe(id):
    @requer_permissao("rh.ver")
    def _go():
        from core.rh import funcionario_detalhe
        return jsonify(funcionario_detalhe(id))
    return _go()


@rh_bp.route("/avaliacoes/<int:id>/detalhe", methods=["GET"])
def rh_avaliacao_detalhe(id):
    @requer_permissao("rh.ver")
    def _go():
        from core.rh import avaliacao_detalhe
        return jsonify(avaliacao_detalhe(id))
    return _go()


@rh_bp.route("/avaliacoes/relatorio", methods=["GET"])
def rh_relatorio_desempenho():
    @requer_permissao("rh.ver")
    def _go():
        from core.rh import relatorio_desempenho
        funcionario_id = request.args.get("funcionario_id", type=int)
        periodo = request.args.get("periodo", type=str)
        return jsonify(relatorio_desempenho(funcionario_id, periodo))
    return _go()


@rh_bp.route("/treinamentos/<int:id>/detalhe", methods=["GET"])
def rh_treinamento_detalhe(id):
    @requer_permissao("rh.ver")
    def _go():
        from core.rh import treinamento_detalhe
        return jsonify(treinamento_detalhe(id))
    return _go()


@rh_bp.route("/treinamentos/relatorio", methods=["GET"])
def rh_relatorio_treinamentos():
    @requer_permissao("rh.ver")
    def _go():
        from core.rh import relatorio_treinamentos
        funcionario_id = request.args.get("funcionario_id", type=int)
        return jsonify(relatorio_treinamentos(funcionario_id))
    return _go()
