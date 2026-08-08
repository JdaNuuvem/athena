from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao, requer_acesso_loja, usuario_atual_da_request
from core.rbac_lojas import lojas_permitidas

financeiro_relatorios_bp = Blueprint("financeiro_relatorios", __name__, url_prefix="/api/financeiro/relatorios")


def _periodo_da_request():
    hoje_str = __import__("datetime").date.today().isoformat()
    de = request.args.get("de") or hoje_str[:8] + "01"
    ate = request.args.get("ate") or hoje_str
    return de, ate


@financeiro_relatorios_bp.route("/vendas-por-loja", methods=["GET"])
def vendas_por_loja_route():
    @requer_permissao("financeiro.ver")
    def _go():
        from core.relatorios import vendas_por_loja
        de, ate = _periodo_da_request()
        resultado = vendas_por_loja(de, ate)
        usuario = usuario_atual_da_request()
        if not usuario["is_master"] and usuario["user_id"]:
            permitidas = lojas_permitidas(usuario["user_id"])
            if permitidas is not None:
                resultado["lojas"] = [l for l in resultado["lojas"] if l["id"] in permitidas]
                permitidas_set = set(permitidas)
                for dia in resultado["dias"]:
                    dia["valores_por_loja"] = {k: v for k, v in dia["valores_por_loja"].items() if k in permitidas_set}
                resultado["totais_por_loja"] = {k: v for k, v in resultado["totais_por_loja"].items() if k in permitidas_set}
        return jsonify(resultado)
    return _go()


@financeiro_relatorios_bp.route("/movimento-diario", methods=["GET"])
def movimento_diario_route():
    loja_id = request.args.get("loja_id", type=int)
    if not loja_id:
        return jsonify({"error": "loja_id obrigatorio"}), 400

    @requer_permissao("financeiro.ver")
    @requer_acesso_loja
    def _go():
        from core.relatorios import movimento_diario_por_loja
        de, ate = _periodo_da_request()
        return jsonify(movimento_diario_por_loja(de, ate, loja_id))
    return _go()
