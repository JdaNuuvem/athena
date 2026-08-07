from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao

cadastros_bp = Blueprint("cadastros", __name__, url_prefix="/api/cadastros")


@cadastros_bp.route("/<tabela>", methods=["GET"])
def cad_list(tabela):
    from core.cadastros import list as cad_list_fn, list_paginado, listar_clientes_filtrado, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    # ponytail: faltava @requer_permissao aqui — qualquer usuario com token
    # valido (mesmo sem nenhuma permissao atribuida) conseguia listar
    # /api/cadastros/empresas, /api/cadastros/usuarios etc. O CRM (crm.py) ja
    # exige crm.ver pro mesmo tipo de rota; Cadastros ficou pra tras.
    @requer_permissao("cadastros.ver")
    def _go():
        # ?pagina= opcional — sem ele mantem o comportamento antigo (ate 100
        # registros, sem total) para nao quebrar telas que ja consomem esta
        # rota sem paginacao (ClientesTab e as demais abas de Cadastros).
        pagina = request.args.get("pagina", type=int)
        if pagina is not None:
            por_pagina = request.args.get("por_pagina", default=50, type=int)
            busca = request.args.get("busca", default=None, type=str)
            if tabela == "clientes":
                sort = request.args.get("sort", default="id", type=str)
                order = request.args.get("order", default="desc", type=str)
                status = request.args.get("status", default=None, type=str)
                tag = request.args.get("tag", default=None, type=str)
                whatsapp_raw = request.args.get("whatsapp", default=None, type=str)
                whatsapp = {"true": True, "false": False}.get((whatsapp_raw or "").lower())
                sem_comprar_dias = request.args.get("sem_comprar_dias", default=None, type=int)
                return jsonify(listar_clientes_filtrado(
                    pagina, por_pagina, busca, sort, order, status, tag, whatsapp, sem_comprar_dias))
            return jsonify(list_paginado(tabela, pagina, por_pagina, busca))
        return jsonify({"data": cad_list_fn(tabela)})
    return _go()


@cadastros_bp.route("/<tabela>", methods=["POST"])
def cad_create(tabela):
    from core.cadastros import create as cad_create_fn, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    if not data:
        return jsonify({"error": "Dados obrigatorios"}), 400

    @requer_permissao("cadastros.criar")
    def _go():
        return jsonify(cad_create_fn(tabela, data))
    return _go()


@cadastros_bp.route("/<tabela>/<int:id>", methods=["GET"])
def cad_get(tabela, id):
    from core.cadastros import get as cad_get_fn, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("cadastros.ver")
    def _go():
        return jsonify(cad_get_fn(tabela, id))
    return _go()


@cadastros_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def cad_update(tabela, id):
    from core.cadastros import update as cad_update_fn, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}

    @requer_permissao("cadastros.editar")
    def _go():
        return jsonify(cad_update_fn(tabela, id, data))
    return _go()


@cadastros_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def cad_delete(tabela, id):
    from core.cadastros import get as cad_get_fn, delete as cad_delete_fn, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("cadastros.excluir")
    def _go():
        from core.seguranca import auditar_exclusao
        dados_antes = cad_get_fn(tabela, id)
        resultado = cad_delete_fn(tabela, id)
        if not resultado.get("error"):
            auditar_exclusao("cadastros", tabela, id, dados_antes if not dados_antes.get("error") else None)
        return jsonify(resultado)
    return _go()


@cadastros_bp.route("/permissoes/perfil", methods=["GET"])
def cad_permissoes_perfil():
    from core.cadastros import permissoes_por_perfil

    @requer_permissao("cadastros.ver")
    def _go():
        return jsonify({"data": permissoes_por_perfil()})
    return _go()


@cadastros_bp.route("/vendedores/comissao", methods=["GET"])
def cad_vendedor_comissao():
    from core.cadastros import vendedor_comissao_resumo

    @requer_permissao("cadastros.ver")
    def _go():
        return jsonify({"data": vendedor_comissao_resumo()})
    return _go()


@cadastros_bp.route("/vendedores/metas", methods=["GET"], defaults={"mes": None})
@cadastros_bp.route("/vendedores/metas/<mes>", methods=["GET"])
def cad_vendedor_metas(mes):
    from core.cadastros import vendedor_metas

    @requer_permissao("cadastros.ver")
    def _go():
        return jsonify({"data": vendedor_metas(mes)})
    return _go()


@cadastros_bp.route("/fornecedores/resumo", methods=["GET"])
def cad_fornecedor_resumo():
    from core.cadastros import fornecedor_resumo

    @requer_permissao("cadastros.ver")
    def _go():
        return jsonify({"data": fornecedor_resumo()})
    return _go()


@cadastros_bp.route("/clientes/tags-disponiveis", methods=["GET"])
def cad_clientes_tags_disponiveis():
    from core.cadastros import tags_disponiveis

    @requer_permissao("cadastros.ver")
    def _go():
        return jsonify({"data": tags_disponiveis()})
    return _go()
