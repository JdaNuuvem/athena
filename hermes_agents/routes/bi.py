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
