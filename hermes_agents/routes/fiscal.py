from flask import Blueprint, request, jsonify
from core import run_async, get_db

fiscal_bp = Blueprint("fiscal", __name__, url_prefix="/api/fiscal")


@fiscal_bp.route("/dashboard", methods=["GET"])
def fiscal_dashboard():
    from core.fiscal import dashboard
    return jsonify(dashboard())


@fiscal_bp.route("/tabelas/cfop", methods=["GET"])
def fiscal_tabelas_cfop():
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT DISTINCT cfop as codigo, natureza_operacao as descricao, tipo FROM fiscal_notas_fiscais WHERE cfop IS NOT NULL AND cfop != '' ORDER BY cfop LIMIT 50")
        return [dict(r) for r in (rows or [])]
    try:
        return jsonify(run_async(_go()))
    except Exception:
        return jsonify([])


@fiscal_bp.route("/tabelas/ncm", methods=["GET"])
def fiscal_tabelas_ncm():
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT DISTINCT ncm as codigo, '' as descricao FROM fiscal_nfe_itens WHERE ncm IS NOT NULL AND ncm != '' ORDER BY ncm LIMIT 50")
        return [dict(r) for r in (rows or [])]
    try:
        return jsonify(run_async(_go()))
    except Exception:
        return jsonify([])


@fiscal_bp.route("/tabelas/cest", methods=["GET"])
def fiscal_tabelas_cest():
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT DISTINCT cest as codigo, '' as descricao FROM fiscal_nfe_itens WHERE cest IS NOT NULL AND cest != '' ORDER BY cest LIMIT 50")
        return [dict(r) for r in (rows or [])]
    try:
        return jsonify(run_async(_go()))
    except Exception:
        return jsonify([])


@fiscal_bp.route("/<tabela>", methods=["GET"])
def fiscal_list(tabela):
    from core.fiscal import list as fl, listar_filtrado, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data_inicio = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")
    dias = request.args.get("dias", 0, type=int)
    if data_inicio or data_fim or dias:
        return jsonify(listar_filtrado(tabela, data_inicio, data_fim, dias))
    return jsonify({"data": fl(tabela)})


@fiscal_bp.route("/<tabela>", methods=["POST"])
def fiscal_create(tabela):
    from core.fiscal import create as fc, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(fc(tabela, request.json or {}))


@fiscal_bp.route("/<tabela>/<int:id>", methods=["GET"])
def fiscal_get(tabela, id):
    from core.fiscal import get as fg, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(fg(tabela, id))


@fiscal_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def fiscal_update(tabela, id):
    from core.fiscal import update as fu, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(fu(tabela, id, request.json or {}))


@fiscal_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def fiscal_delete(tabela, id):
    from core.fiscal import delete as fd, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(fd(tabela, id))


@fiscal_bp.route("/tributos/calcular/<int:nota_id>", methods=["GET"])
def fiscal_calcular_tributos(nota_id):
    from core.fiscal import calcular_tributos_nota
    return jsonify(calcular_tributos_nota(nota_id))


@fiscal_bp.route("/obrigacoes/proximas", methods=["GET"])
def fiscal_obrigacoes_proximas():
    from core.fiscal import obrigacoes_proximas
    dias = request.args.get("dias", 30, type=int)
    return jsonify({"data": obrigacoes_proximas(dias)})


@fiscal_bp.route("/obrigacoes/atrasadas", methods=["GET"])
def fiscal_obrigacoes_atrasadas():
    from core.fiscal import obrigacoes_atrasadas
    return jsonify({"data": obrigacoes_atrasadas()})


@fiscal_bp.route("/obrigacoes/<int:id>/baixar", methods=["POST"])
def fiscal_baixar_obrigacao(id):
    from core.fiscal import baixar_obrigacao
    return jsonify(baixar_obrigacao(id))


@fiscal_bp.route("/sync/notas-fiscais", methods=["POST"])
def fiscal_sync_nf():
    from core.fiscal import sincronizar_notas_fiscais_bling
    data = request.json or {}
    return jsonify(sincronizar_notas_fiscais_bling(
        pagina=data.get("pagina", 1), limite=data.get("limite", 100)))


@fiscal_bp.route("/sync/contas-receber", methods=["POST"])
def fiscal_sync_cr():
    from core.fiscal import sincronizar_contas_receber_bling
    data = request.json or {}
    return jsonify(sincronizar_contas_receber_bling(
        pagina=data.get("pagina", 1), limite=data.get("limite", 100)))


@fiscal_bp.route("/sync/contas-pagar", methods=["POST"])
def fiscal_sync_cp():
    from core.fiscal import sincronizar_contas_pagar_bling
    data = request.json or {}
    return jsonify(sincronizar_contas_pagar_bling(
        pagina=data.get("pagina", 1), limite=data.get("limite", 100)))


@fiscal_bp.route("/sync/tudo", methods=["POST"])
def fiscal_sync_tudo():
    from core.fiscal import sincronizar_tudo_bling
    return jsonify(sincronizar_tudo_bling())


@fiscal_bp.route("/notas-fiscais/<int:id>/itens", methods=["GET"])
def fiscal_nf_itens(id):
    from core.fiscal import _list
    return jsonify({"data": _list("fiscal_nfe_itens", cols="*", order="numero_item")})


@fiscal_bp.route("/notas-fiscais/<int:id>/impostos", methods=["GET"])
def fiscal_nf_impostos(id):
    from core.fiscal import _list
    return jsonify({"data": _list("fiscal_impostos_nota", cols="*", order="id")})


@fiscal_bp.route("/apuracao", methods=["GET"])
def fiscal_apuracao():
    from core.fiscal import apuracao_impostos
    ano = request.args.get("ano", type=int)
    mes = request.args.get("mes", type=int)
    dias = request.args.get("dias", 365, type=int)
    return jsonify(apuracao_impostos(ano, mes, dias))


@fiscal_bp.route("/obrigacoes/alertas", methods=["GET"])
def fiscal_alertas():
    from core.entidades import gerar_alertas_obrigacoes
    return jsonify(gerar_alertas_obrigacoes())
