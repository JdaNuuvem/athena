"""Rotas REST da Reconciliacao i9Logic — /api/integrations/i9logic/*"""
from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao, usuario_atual_da_request
from core.i9logic import (
    criar_mapeamento, listar_mapeamentos, executar_matching_automatico,
    executar_coleta_todas_filiais, listar_itens_para_revisao, marcar_revisado,
    aplicar_ajuste_divergencia, comparar_com_athena, seed_inicial,
)

i9logic_bp = Blueprint("i9logic", __name__, url_prefix="/api/integrations/i9logic")


@i9logic_bp.route("/depara", methods=["GET"])
def i9logic_listar_depara():
    @requer_permissao("estoque.ver")
    def _go():
        return jsonify({"data": listar_mapeamentos(request.args.get("tipo"))})
    return _go()


@i9logic_bp.route("/depara", methods=["POST"])
def i9logic_criar_depara():
    @requer_permissao("estoque.editar")
    def _go():
        dados = request.json or {}
        return jsonify(criar_mapeamento(
            dados.get("tipo", ""), dados.get("id_i9logic", ""), dados.get("codigo_athena", "")))
    return _go()


@i9logic_bp.route("/depara/matching", methods=["POST"])
def i9logic_matching_automatico():
    @requer_permissao("estoque.editar")
    def _go():
        dados = request.json or {}
        return jsonify(executar_matching_automatico(
            dados.get("tipo", ""), dados.get("pares", [])))
    return _go()


@i9logic_bp.route("/coletar", methods=["POST"])
def i9logic_coletar():
    @requer_permissao("estoque.editar")
    def _go():
        return jsonify(executar_coleta_todas_filiais())
    return _go()


@i9logic_bp.route("/divergencias", methods=["GET"])
def i9logic_listar_divergencias():
    @requer_permissao("estoque.ver")
    def _go():
        return jsonify({"data": listar_itens_para_revisao()})
    return _go()


@i9logic_bp.route("/divergencias/<int:snapshot_id>/resolver", methods=["POST"])
def i9logic_resolver_divergencia(snapshot_id):
    """Aceita a divergencia como conhecida — so' marca revisado, nunca ajusta saldo."""
    @requer_permissao("estoque.editar")
    def _go():
        return jsonify(marcar_revisado(snapshot_id))
    return _go()


@i9logic_bp.route("/divergencias/<int:snapshot_id>/ajustar", methods=["POST"])
def i9logic_ajustar_divergencia(snapshot_id):
    """Ajusta o saldo Athena pro fisico coletado, via ledger formal (Fase 1)."""
    @requer_permissao("estoque.editar")
    def _go():
        usuario = usuario_atual_da_request()
        resultado = aplicar_ajuste_divergencia(snapshot_id, usuario.get("user_id"), usuario.get("nome", ""))
        if resultado.get("erro"):
            erro = resultado["erro"]
            eh_nao_encontrado = "nao encontrado" in erro or "sem snapshot" in erro
            return jsonify(resultado), (404 if eh_nao_encontrado else 400)
        return jsonify(resultado)
    return _go()


@i9logic_bp.route("/comparar", methods=["GET"])
def i9logic_comparar():
    @requer_permissao("estoque.ver")
    def _go():
        return jsonify(comparar_com_athena(request.args.get("sku", ""), request.args.get("loja", "")))
    return _go()


@i9logic_bp.route("/seed", methods=["POST"])
def i9logic_seed():
    @requer_permissao("estoque.editar")
    def _go():
        dados = request.json or {}
        usuario = usuario_atual_da_request()
        resultado = seed_inicial(
            dados.get("sku", ""), dados.get("loja", ""),
            usuario.get("user_id"), usuario.get("nome", ""))
        if resultado.get("erro"):
            erro = resultado["erro"]
            eh_nao_encontrado = "nao encontrado" in erro or "sem snapshot" in erro
            return jsonify(resultado), (404 if eh_nao_encontrado else 400)
        return jsonify(resultado)
    return _go()
