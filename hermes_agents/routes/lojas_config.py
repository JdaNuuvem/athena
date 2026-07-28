"""Rotas de configuracao por secao da loja (operacional/comercial/fiscal/
financeiro/estoque/virtual/delivery) — cada secao e' um PUT dedicado que
delega pro core/lojas_*.py correspondente."""
from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao
from core.seguranca import auditar_alteracao
from core.lojas import obter

lojas_config_bp = Blueprint("lojas_config", __name__, url_prefix="/api/lojas/manage")


def _registrar_secao(nome_secao: str, atualizar_fn, whitelist: set, mascarar=None):
    """Fabrica e registra a view PUT /manage/<id>/<nome_secao>."""
    def view(id):
        data = request.json or {}
        campos = {k: v for k, v in data.items() if k in whitelist}

        @requer_permissao("configuracoes.editar")
        def _go():
            dados_antes = obter(id)
            if dados_antes is None:
                return jsonify({"error": "Loja nao encontrada"}), 404
            ok = atualizar_fn(id, campos)
            if not ok:
                return jsonify({"error": "Falha ao atualizar"}), 500
            log_campos = mascarar(campos) if mascarar else campos
            auditar_alteracao("editar", "lojas", nome_secao, id, dados_antes=dados_antes, dados_depois=log_campos)
            return jsonify({"success": True})
        return _go()

    view.__name__ = f"atualizar_loja_{nome_secao}"
    lojas_config_bp.add_url_rule(f"/<int:id>/{nome_secao}", view_func=view, methods=["PUT"])


from core.lojas_operacional import atualizar_operacional, atualizar_comercial, CAMPOS_OPERACIONAL, CAMPOS_COMERCIAL
from core.lojas_fiscal_financeiro import (
    atualizar_fiscal, atualizar_financeiro, atualizar_estoque_config,
    CAMPOS_FISCAL, CAMPOS_FINANCEIRO, CAMPOS_ESTOQUE_CONFIG, mascarar_para_auditoria,
)
from core.lojas_virtual import atualizar_virtual, atualizar_delivery, CAMPOS_VIRTUAL, CAMPOS_DELIVERY

_registrar_secao("operacional", atualizar_operacional, CAMPOS_OPERACIONAL)
_registrar_secao("comercial", atualizar_comercial, CAMPOS_COMERCIAL)
_registrar_secao("fiscal", atualizar_fiscal, CAMPOS_FISCAL, mascarar=mascarar_para_auditoria)
_registrar_secao("financeiro", atualizar_financeiro, CAMPOS_FINANCEIRO, mascarar=mascarar_para_auditoria)
_registrar_secao("estoque-config", atualizar_estoque_config, CAMPOS_ESTOQUE_CONFIG)
_registrar_secao("virtual", atualizar_virtual, CAMPOS_VIRTUAL)
_registrar_secao("delivery", atualizar_delivery, CAMPOS_DELIVERY)
