"""Rotas de responsaveis da loja (proprietario/gerentes/etc) — vinculo
informativo, nao controla acesso (ver core/lojas_responsaveis.py)."""
from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao
from core.seguranca import auditar_alteracao, auditar_exclusao

lojas_responsaveis_bp = Blueprint("lojas_responsaveis", __name__, url_prefix="/api/lojas/manage")


@lojas_responsaveis_bp.route("/<int:id>/responsaveis", methods=["GET"])
def listar_responsaveis(id):
    @requer_permissao("configuracoes.editar")
    def _go():
        from core.lojas_responsaveis import listar
        return jsonify({"responsaveis": listar(id)})
    return _go()


@lojas_responsaveis_bp.route("/<int:id>/responsaveis", methods=["POST"])
def vincular_responsavel(id):
    data = request.json or {}
    usuario_id = data.get("usuario_id")
    cargo = data.get("cargo", "")
    if not usuario_id:
        return jsonify({"error": "usuario_id e obrigatorio"}), 400

    @requer_permissao("configuracoes.editar")
    def _go():
        from core.lojas_responsaveis import vincular
        result = vincular(id, usuario_id, cargo, permissoes=data.get("permissoes"),
                           data_inicio=data.get("data_inicio"), data_fim=data.get("data_fim"))
        if result.get("error"):
            return jsonify(result), 400
        auditar_alteracao("criar", "lojas", "responsaveis", id, dados_depois=result)
        return jsonify({"responsavel": result})
    return _go()


@lojas_responsaveis_bp.route("/<int:id>/responsaveis/<int:vinculo_id>", methods=["PUT"])
def atualizar_responsavel(id, vinculo_id):
    data = request.json or {}

    @requer_permissao("configuracoes.editar")
    def _go():
        from core.lojas_responsaveis import atualizar, encerrar
        if "data_fim" in data:
            ok = encerrar(vinculo_id, data_fim=data.get("data_fim"))
        else:
            ok = atualizar(vinculo_id, cargo=data.get("cargo"), permissoes=data.get("permissoes"))
        if not ok:
            return jsonify({"error": "Vinculo nao encontrado ou dados invalidos"}), 404
        auditar_alteracao("editar", "lojas", "responsaveis", id, dados_depois={"vinculo_id": vinculo_id, **data})
        return jsonify({"success": True})
    return _go()


@lojas_responsaveis_bp.route("/<int:id>/responsaveis/<int:vinculo_id>", methods=["DELETE"])
def remover_responsavel(id, vinculo_id):
    @requer_permissao("configuracoes.excluir")
    def _go():
        from core.lojas_responsaveis import remover
        ok = remover(vinculo_id)
        if not ok:
            return jsonify({"error": "Vinculo nao encontrado"}), 404
        auditar_exclusao("lojas", "responsaveis", id, {"vinculo_id": vinculo_id})
        return jsonify({"success": True})
    return _go()
