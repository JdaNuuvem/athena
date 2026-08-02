"""Rotas de responsaveis da loja (proprietario/gerentes/etc) — vinculo
informativo, nao controla acesso (ver core/lojas_responsaveis.py)."""
from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao, requer_acesso_loja
from core.seguranca import auditar_alteracao, auditar_exclusao

lojas_responsaveis_bp = Blueprint("lojas_responsaveis", __name__, url_prefix="/api/lojas/manage")


@lojas_responsaveis_bp.route("/<int:id>/responsaveis", methods=["GET"])
def listar_responsaveis(id):
    @requer_acesso_loja
    @requer_permissao("configuracoes.editar")
    def _go(loja_id):
        from core.lojas_responsaveis import listar
        return jsonify({"responsaveis": listar(loja_id)})
    return _go(loja_id=id)


@lojas_responsaveis_bp.route("/<int:id>/responsaveis", methods=["POST"])
def vincular_responsavel(id):
    data = request.json or {}
    usuario_id = data.get("usuario_id")
    cargo = data.get("cargo", "")
    if not usuario_id:
        return jsonify({"error": "usuario_id e obrigatorio"}), 400

    @requer_acesso_loja
    @requer_permissao("configuracoes.editar")
    def _go(loja_id):
        from core.lojas_responsaveis import vincular
        result = vincular(loja_id, usuario_id, cargo, permissoes=data.get("permissoes"),
                           data_inicio=data.get("data_inicio"), data_fim=data.get("data_fim"))
        if result.get("error"):
            return jsonify(result), 400
        auditar_alteracao("criar", "lojas", "responsaveis", loja_id, dados_depois=result)
        return jsonify({"responsavel": result})
    return _go(loja_id=id)


@lojas_responsaveis_bp.route("/<int:id>/responsaveis/<int:vinculo_id>", methods=["PUT"])
def atualizar_responsavel(id, vinculo_id):
    data = request.json or {}

    @requer_acesso_loja
    @requer_permissao("configuracoes.editar")
    def _go(loja_id):
        from core.lojas_responsaveis import atualizar, encerrar
        if "data_fim" in data:
            ok = encerrar(vinculo_id, data_fim=data.get("data_fim"), loja_id=loja_id)
        else:
            ok = atualizar(vinculo_id, cargo=data.get("cargo"), permissoes=data.get("permissoes"), loja_id=loja_id)
        if not ok:
            return jsonify({"error": "Vinculo nao encontrado ou dados invalidos"}), 404
        auditar_alteracao("editar", "lojas", "responsaveis", loja_id, dados_depois={"vinculo_id": vinculo_id, **data})
        return jsonify({"success": True})
    return _go(loja_id=id)


@lojas_responsaveis_bp.route("/<int:id>/responsaveis/<int:vinculo_id>", methods=["DELETE"])
def remover_responsavel(id, vinculo_id):
    @requer_acesso_loja
    @requer_permissao("configuracoes.excluir")
    def _go(loja_id):
        from core.lojas_responsaveis import remover
        ok = remover(vinculo_id, loja_id=loja_id)
        if not ok:
            return jsonify({"error": "Vinculo nao encontrado"}), 404
        auditar_exclusao("lojas", "responsaveis", loja_id, {"vinculo_id": vinculo_id})
        return jsonify({"success": True})
    return _go(loja_id=id)
