from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao, requer_acesso_loja, usuario_atual_da_request

vendas_bp = Blueprint("vendas", __name__, url_prefix="/api/vendas")


@vendas_bp.route("/dashboard", methods=["GET"])
def vendas_dashboard():
    from core.vendas import dashboard
    dias = request.args.get("dias", 30, type=int)
    return jsonify(dashboard(dias))


@vendas_bp.route("/<tabela>", methods=["GET"])
def vendas_list(tabela):
    from core.vendas import list as vl, listar_filtrado, listar_pedidos_por_loja, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data_inicio = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")
    dias = request.args.get("dias", 0, type=int)
    status = request.args.get("status", "")
    if data_inicio or data_fim or dias or status:
        return jsonify(listar_filtrado(tabela, data_inicio, data_fim, dias, status))
    if tabela == "pedidos":
        # Fase 4 (RBAC por loja, piloto vendas) — modo suave: sem vinculo em
        # loja_responsaveis, ve tudo (comportamento de sempre).
        from core.rbac_lojas import lojas_permitidas
        permitidas = lojas_permitidas(usuario_atual_da_request().get("user_id"))
        if permitidas is not None:
            return jsonify({"data": listar_pedidos_por_loja(permitidas)})
    return jsonify({"data": vl(tabela)})


@vendas_bp.route("/<tabela>", methods=["POST"])
def vendas_create(tabela):
    from core.vendas import create as vc, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}

    @requer_permissao("vendas.criar")
    def _go():
        return jsonify(vc(tabela, data))
    return _go()


@vendas_bp.route("/<tabela>/<int:id>", methods=["GET"])
def vendas_get(tabela, id):
    from core.vendas import get as vg, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(vg(tabela, id))


@vendas_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def vendas_update(tabela, id):
    from core.vendas import update as vu, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}

    @requer_permissao("vendas.editar")
    def _go():
        return jsonify(vu(tabela, id, data))
    return _go()


@vendas_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def vendas_delete(tabela, id):
    from core.vendas import get as vg, delete as vd, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("vendas.excluir")
    def _go():
        from core.seguranca import auditar_exclusao
        dados_antes = vg(tabela, id)
        resultado = vd(tabela, id)
        if not resultado.get("error"):
            auditar_exclusao("vendas", tabela, id, dados_antes if not dados_antes.get("error") else None)
        return jsonify(resultado)
    return _go()


@vendas_bp.route("/pedido", methods=["POST"])
def vendas_criar_pedido():
    data = request.json or {}

    @requer_acesso_loja
    @requer_permissao("vendas.criar")
    def _go():
        from core.vendas import criar_pedido
        return jsonify(criar_pedido(
            cliente=data.get("cliente", ""),
            itens=data.get("itens", []),
            pagamentos=data.get("pagamentos", []),
            desconto=float(data.get("desconto", 0)),
            frete=float(data.get("frete", 0)),
            vendedor=data.get("vendedor", ""),
            marketplace=data.get("marketplace", "manual"),
            loja_id=data.get("loja_id"),
            observacoes=data.get("observacoes", ""),
        ))
    return _go()


@vendas_bp.route("/pedido/<int:id>", methods=["GET"])
def vendas_detalhe_pedido(id):
    from core.vendas import detalhe_pedido
    return jsonify(detalhe_pedido(id))


@vendas_bp.route("/pedido/<int:id>/status", methods=["PUT"])
def vendas_atualizar_status(id):
    data = request.json or {}

    @requer_permissao("vendas.editar")
    def _go():
        from core.vendas import atualizar_status
        usuario = usuario_atual_da_request()
        return jsonify(atualizar_status(id, data.get("status", ""), usuario["nome"]))
    return _go()


@vendas_bp.route("/sync/bling", methods=["POST"])
def vendas_sync_bling():
    from core.vendas import sincronizar_pedidos_bling
    data = request.json or {}
    return jsonify(sincronizar_pedidos_bling(
        pagina=data.get("pagina", 1), limite=data.get("limite", 100)))


@vendas_bp.route("/sync/shopee", methods=["POST"])
def vendas_sync_shopee():
    @requer_acesso_loja
    def _handler():
        from core.vendas import sincronizar_pedidos_shopee
        data = request.json or {}
        return jsonify(sincronizar_pedidos_shopee(
            dias=data.get("dias", 30), loja_id=data.get("loja_id")))
    return _handler()
