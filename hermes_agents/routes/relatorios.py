from flask import Blueprint, request, jsonify

relatorios_bp = Blueprint("relatorios", __name__, url_prefix="/api/relatorios")


@relatorios_bp.route("/vendas", methods=["GET"])
def rel_vendas():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from core.relatorios import vendas
        dias = request.args.get("dias", 30, type=int)
        loja_id = request.args.get("loja_id", type=int) or request.args.get("loja", type=int)
        return jsonify(vendas(dias, loja_id))
    return _handler()


@relatorios_bp.route("/lucro", methods=["GET"])
def rel_lucro():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from core.relatorios import lucro_margem
        dias = request.args.get("dias", 30, type=int)
        loja_id = request.args.get("loja_id", type=int) or request.args.get("loja", type=int)
        return jsonify(lucro_margem(dias, loja_id))
    return _handler()


@relatorios_bp.route("/estoque", methods=["GET"])
def rel_estoque():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from core.relatorios import estoque
        loja_id = request.args.get("loja_id", type=int) or request.args.get("loja", type=int)
        return jsonify(estoque(loja_id))
    return _handler()


@relatorios_bp.route("/clientes", methods=["GET"])
def rel_clientes():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from core.relatorios import clientes
        dias = request.args.get("dias", 90, type=int)
        loja_id = request.args.get("loja_id", type=int) or request.args.get("loja", type=int)
        return jsonify(clientes(dias, loja_id))
    return _handler()


@relatorios_bp.route("/fornecedores", methods=["GET"])
def rel_fornecedores():
    from core.relatorios import fornecedores
    return jsonify(fornecedores())


@relatorios_bp.route("/aging", methods=["GET"])
def rel_aging():
    from core.relatorios import aging_financeiro
    return jsonify(aging_financeiro())


@relatorios_bp.route("/fluxo-caixa", methods=["GET"])
def rel_fluxo():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from core.relatorios import fluxo_caixa
        dias = request.args.get("dias", 30, type=int)
        loja_id = request.args.get("loja_id", type=int) or request.args.get("loja", type=int)
        return jsonify(fluxo_caixa(dias, loja_id))
    return _handler()


@relatorios_bp.route("/ticket-medio", methods=["GET"])
def rel_ticket():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from core.relatorios import ticket_medio
        dias = request.args.get("dias", 30, type=int)
        loja_id = request.args.get("loja_id", type=int) or request.args.get("loja", type=int)
        return jsonify(ticket_medio(dias, loja_id))
    return _handler()


@relatorios_bp.route("/dre", methods=["GET"])
def rel_dre():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from core.relatorios import dre
        dias = request.args.get("dias", 30, type=int)
        loja_id = request.args.get("loja_id", type=int) or request.args.get("loja", type=int)
        return jsonify(dre(dias, loja_id))
    return _handler()


@relatorios_bp.route("/previsao", methods=["GET"])
def rel_previsao():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from core.relatorios import previsao
        dias = request.args.get("dias", 30, type=int)
        loja_id = request.args.get("loja_id", type=int) or request.args.get("loja", type=int)
        return jsonify(previsao(dias, loja_id))
    return _handler()


@relatorios_bp.route("/compras", methods=["GET"])
def rel_compras():
    from core.relatorios import compras
    dias = request.args.get("dias", 30, type=int)
    return jsonify(compras(dias))


@relatorios_bp.route("/impostos", methods=["GET"])
def rel_impostos():
    from core.relatorios import impostos
    dias = request.args.get("dias", 30, type=int)
    return jsonify(impostos(dias))


@relatorios_bp.route("/comissao", methods=["GET"])
def rel_comissao():
    from core.relatorios import comissao
    dias = request.args.get("dias", 30, type=int)
    return jsonify(comissao(dias))


@relatorios_bp.route("/marketplaces", methods=["GET"])
def rel_marketplaces():
    from core.relatorios import marketplaces
    dias = request.args.get("dias", 30, type=int)
    return jsonify(marketplaces(dias))


@relatorios_bp.route("/devolucoes", methods=["GET"])
def rel_devolucoes():
    from core.relatorios import devolucoes
    dias = request.args.get("dias", 30, type=int)
    return jsonify(devolucoes(dias))


@relatorios_bp.route("/rupturas", methods=["GET"])
def rel_rupturas():
    from core.relatorios import rupturas
    return jsonify(rupturas())


@relatorios_bp.route("/curvas", methods=["GET"])
def rel_curvas():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from core.relatorios import curvas
        dias = request.args.get("dias", 90, type=int)
        loja_id = request.args.get("loja_id", type=int)
        return jsonify(curvas(dias, loja_id))
    return _handler()


@relatorios_bp.route("/produtos", methods=["GET"])
def rel_produtos():
    from core.relatorios import produtos
    dias = request.args.get("dias", 30, type=int)
    return jsonify(produtos(dias))


@relatorios_bp.route("/ranking-produtos", methods=["GET"])
def rel_ranking_produtos():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from core.relatorios import ranking_produtos
        dias = request.args.get("dias", 30, type=int)
        loja_id = request.args.get("loja_id", type=int)
        return jsonify({"itens": ranking_produtos(dias, loja_id), "periodo_dias": dias})
    return _handler()


@relatorios_bp.route("/estoque-parado", methods=["GET"])
def rel_estoque_parado():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from core.bi import estoque_parado
        dias = request.args.get("dias", 60, type=int)
        limite = request.args.get("limite", 15, type=int)
        loja_id = request.args.get("loja_id", type=int)
        return jsonify(estoque_parado(dias, limite, loja_id))
    return _handler()


@relatorios_bp.route("/produtos-tendencia", methods=["GET"])
def rel_produtos_tendencia():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from core.relatorios import produtos_tendencia
        dias = request.args.get("dias", 30, type=int)
        loja_id = request.args.get("loja_id", type=int)
        return jsonify(produtos_tendencia(dias, loja_id))
    return _handler()


@relatorios_bp.route("/risco-ruptura", methods=["GET"])
def rel_risco_ruptura():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        from core.relatorios import risco_ruptura
        dias = request.args.get("dias", 30, type=int)
        loja_id = request.args.get("loja_id", type=int)
        return jsonify(risco_ruptura(dias, loja_id))
    return _handler()


@relatorios_bp.route("/financeiro", methods=["GET"])
def rel_financeiro():
    from core.relatorios import financeiro
    dias = request.args.get("dias", 30, type=int)
    return jsonify(financeiro(dias))


@relatorios_bp.route("/dre-por-loja", methods=["GET"])
def rel_dre_por_loja():
    from core.rbac import requer_acesso_loja, usuario_atual_da_request
    @requer_acesso_loja
    def _handler():
        from core.relatorios import dre_por_loja
        dias = max(1, min(request.args.get("dias", 30, type=int), 365))
        loja_id = request.args.get("loja_id", type=int)
        resultado = dre_por_loja(dias)
        if loja_id:
            resultado = [r for r in resultado if r["loja_id"] == loja_id]
        else:
            # Sem loja_id explicito na request, requer_acesso_loja nao filtra
            # nada (rota nao-escopada, por design) — sem esse filtro aqui, um
            # usuario restrito a lojas especificas via usuario_lojas via essa
            # rota especifica conseguia ver receita/lucro/margem de TODAS as
            # lojas, quebrando o isolamento que as rotas irmas (/vendas,
            # /lucro, /estoque...) ja respeitam.
            from core.rbac_lojas import lojas_permitidas
            permitidas = lojas_permitidas(usuario_atual_da_request().get("user_id"))
            if permitidas is not None:
                resultado = [r for r in resultado if r["loja_id"] in permitidas]
        return jsonify({"data": resultado})
    return _handler()
