"""Rotas de slots de integracao por loja (ver core/lojas_integracoes.py —
so' Bling/Shopee sao funcionais de verdade hoje; o resto e' configuracao
pronta pra plugar depois)."""
from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao
from core.seguranca import auditar_alteracao

lojas_integracoes_bp = Blueprint("lojas_integracoes", __name__, url_prefix="/api/lojas/manage")


@lojas_integracoes_bp.route("/<int:id>/integracoes", methods=["GET"])
def listar_integracoes(id):
    @requer_permissao("configuracoes.editar")
    def _go():
        from core.lojas_integracoes import listar
        integracoes = [
            {"integracao": i["integracao"], "status": i["status"], "configurado": bool(i.get("credenciais"))}
            for i in listar(id)
        ]
        return jsonify({"integracoes": integracoes})
    return _go()


@lojas_integracoes_bp.route("/<int:id>/integracoes/<string:chave>", methods=["PUT"])
def atualizar_integracao(id, chave):
    data = request.json or {}
    status = data.get("status", "")

    @requer_permissao("configuracoes.editar")
    def _go():
        from core.lojas_integracoes import atualizar_status
        result = atualizar_status(id, chave, status, credenciais=data.get("credenciais"))
        if result.get("error"):
            return jsonify(result), 400
        # credenciais nunca vao pro log de auditoria em texto puro.
        auditar_alteracao("editar", "lojas", "integracoes", id,
                           dados_depois={"integracao": chave, "status": status})
        return jsonify({"integracao": result})
    return _go()
