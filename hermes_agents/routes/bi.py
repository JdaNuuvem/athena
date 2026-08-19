from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao

bi_bp = Blueprint("bi", __name__, url_prefix="/api/bi")


@bi_bp.route("/dashboard", methods=["GET"])
@requer_permissao("bi.ver")
def bi_dashboard():
    from core.bi import dashboard
    return jsonify(dashboard())


@bi_bp.route("/vendas/diarias", methods=["GET"])
@requer_permissao("bi.ver")
def bi_vendas_diarias():
    from core.bi import vendas_diarias
    dias = request.args.get("dias", 30, type=int)
    return jsonify(vendas_diarias(dias))


@bi_bp.route("/vendas/categorias", methods=["GET"])
@requer_permissao("bi.ver")
def bi_vendas_categorias():
    from core.bi import vendas_categorias
    dias = request.args.get("dias", 30, type=int)
    return jsonify(vendas_categorias(dias))


@bi_bp.route("/indicadores", methods=["GET"])
@requer_permissao("bi.ver")
def bi_indicadores():
    from core.bi import indicadores
    return jsonify(indicadores())


@bi_bp.route("/forecast", methods=["GET"])
@requer_permissao("bi.ver")
def bi_forecast():
    from core.bi import forecast
    return jsonify(forecast())


@bi_bp.route("/ml/anomalias", methods=["GET"])
@requer_permissao("bi.ver")
def bi_ml_anomalias():
    from core.bi import ml_anomalias
    dias = request.args.get("dias", 30, type=int)
    return jsonify(ml_anomalias(dias))


@bi_bp.route("/ml/segmentos", methods=["GET"])
@requer_permissao("bi.ver")
def bi_ml_segmentos():
    from core.bi import ml_segmentos
    return jsonify(ml_segmentos())


@bi_bp.route("/ml/recomendacoes", methods=["GET"])
@requer_permissao("bi.ver")
def bi_ml_recomendacoes():
    from core.bi import ml_recomendacoes
    dias = request.args.get("dias", 90, type=int)
    return jsonify(ml_recomendacoes(dias))


@bi_bp.route("/acoes-mes", methods=["GET"])
@requer_permissao("bi.ver")
def bi_acoes_mes():
    from core.bi import acoes_do_mes
    return jsonify(acoes_do_mes())


@bi_bp.route("/lojas", methods=["GET"])
@requer_permissao("bi.ver")
def bi_lojas():
    from core.relatorios import dre_por_loja
    from core.rbac import usuario_atual_da_request
    from core.rbac_lojas import lojas_permitidas
    dias = request.args.get("dias", 30, type=int)
    resultado = dre_por_loja(dias)
    # Achado real (auditoria do modulo BI): essa rota so' checava a
    # permissao generica bi.ver, sem filtrar por loja — um usuario
    # restrito a lojas especificas via usuario_lojas via receita/lucro de
    # TODAS as lojas ativas aqui, mesmo bug ja corrigido antes na rota
    # irma /api/relatorios/dre-por-loja (mesma funcao core, ver
    # routes/relatorios.py::rel_dre_por_loja).
    permitidas = lojas_permitidas(usuario_atual_da_request().get("user_id"))
    if permitidas is not None:
        resultado = [r for r in resultado if r["loja_id"] in permitidas]
    return jsonify(resultado)
