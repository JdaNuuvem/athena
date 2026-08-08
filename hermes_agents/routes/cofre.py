from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao, requer_acesso_loja, usuario_atual_da_request, usuario_tem_permissao
from core.api_utils import status_for_resultado as _status_for

cofre_bp = Blueprint("cofre", __name__, url_prefix="/api/financeiro/cofre")


@cofre_bp.route("", methods=["GET"])
def cofre_extrato():
    loja_id = request.args.get("loja_id", type=int)
    if not loja_id:
        return jsonify({"error": "loja_id obrigatorio"}), 400

    @requer_permissao("financeiro.ver")
    @requer_acesso_loja
    def _go():
        from core.cofre import listar_movimentos
        dias = request.args.get("dias", 90, type=int)
        return jsonify(listar_movimentos(loja_id, dias))
    return _go()


@cofre_bp.route("/saldo-total", methods=["GET"])
def cofre_saldo_total():
    @requer_permissao("financeiro.ver")
    def _go():
        from core.cofre import saldo_total
        from core.rbac_lojas import lojas_permitidas
        usuario = usuario_atual_da_request()
        loja_ids = None
        if not usuario["is_master"] and usuario["user_id"]:
            loja_ids = lojas_permitidas(usuario["user_id"])
        return jsonify({"saldo_total": saldo_total(loja_ids)})
    return _go()


@cofre_bp.route("/movimento", methods=["POST"])
def cofre_criar_movimento():
    data = request.json or {}
    loja_id = data.get("loja_id")
    if not loja_id:
        return jsonify({"error": "loja_id obrigatorio"}), 400

    @requer_permissao("financeiro.criar")
    @requer_acesso_loja
    def _go():
        from core.cofre import criar_movimento
        tipo = data.get("tipo")
        # ajuste e' sempre sensivel (pode zerar/inflar saldo sem lastro real
        # de sangria/despesa) — exige financeiro.aprovar independente de
        # valor, diferente do limite de R$5000 dos pagamentos.
        if tipo == "ajuste" and not usuario_tem_permissao("financeiro.aprovar"):
            return jsonify({"error": "Ajuste de cofre exige permissao financeiro.aprovar"}), 403
        usuario = usuario_atual_da_request()
        resultado = criar_movimento(
            loja_id, tipo, data.get("valor"),
            categoria=data.get("categoria"), descricao=data.get("descricao"),
            caixa_id=data.get("caixa_id"),
            criado_por=usuario.get("nome"), criado_por_id=usuario.get("user_id"))
        return jsonify(resultado), _status_for(resultado)
    return _go()


@cofre_bp.route("/movimento/<int:movimento_id>", methods=["DELETE"])
def cofre_excluir_movimento(movimento_id):
    @requer_permissao("financeiro.excluir")
    def _go():
        from core.cofre import get_loja_do_movimento, excluir_movimento
        from core.rbac_lojas import lojas_permitidas
        from core.seguranca import auditar_exclusao
        # a URL so' tem movimento_id (sem loja_id), entao requer_acesso_loja
        # nao teria o que checar — resolve a loja dona do movimento primeiro
        # e aplica a mesma regra manualmente (senao um usuario restrito a
        # certas lojas conseguiria excluir movimento de cofre de qualquer
        # outra loja so' adivinhando o id).
        loja_id = get_loja_do_movimento(movimento_id)
        if loja_id is None:
            return jsonify({"error": "Movimento nao encontrado"}), 404
        usuario = usuario_atual_da_request()
        if not usuario["is_master"] and usuario["user_id"]:
            permitidas = lojas_permitidas(usuario["user_id"])
            if permitidas is not None and loja_id not in permitidas:
                return jsonify({"error": "Sem acesso a esta loja", "loja_id": loja_id}), 403
        resultado = excluir_movimento(movimento_id)
        if not resultado.get("error"):
            auditar_exclusao("financeiro", "cofre_movimentos", movimento_id, None)
        return jsonify(resultado), _status_for(resultado)
    return _go()
