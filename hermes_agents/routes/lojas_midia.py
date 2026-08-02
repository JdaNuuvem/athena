"""Rotas de midia da loja (logo/banner/fotos/galeria/video) — ver
core/lojas_midia.py (wrapper sobre o upload generico de core/documentos.py)."""
from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao, requer_acesso_loja
from core.seguranca import auditar_alteracao, auditar_exclusao

lojas_midia_bp = Blueprint("lojas_midia", __name__, url_prefix="/api/lojas/manage")


@lojas_midia_bp.route("/<int:id>/midia", methods=["GET"])
def listar_midia(id):
    @requer_acesso_loja
    @requer_permissao("configuracoes.editar")
    def _go(loja_id):
        from core.lojas_midia import listar
        tipo = request.args.get("tipo")
        return jsonify({"midia": listar(loja_id, tipo=tipo)})
    return _go(loja_id=id)


@lojas_midia_bp.route("/<int:id>/midia", methods=["POST"])
def vincular_midia(id):
    tipo = request.form.get("tipo", "")
    arquivo = request.files.get("arquivo")
    if not arquivo:
        return jsonify({"error": "Arquivo e obrigatorio"}), 400

    @requer_acesso_loja
    @requer_permissao("configuracoes.editar")
    def _go(loja_id):
        from core.lojas_midia import vincular
        result = vincular(loja_id, tipo, arquivo.read(), arquivo.filename, mime_type=arquivo.mimetype or "application/octet-stream")
        if result.get("error"):
            return jsonify(result), 400
        auditar_alteracao("criar", "lojas", "midia", loja_id, dados_depois={"tipo": tipo, "nome": arquivo.filename})
        return jsonify({"midia": result})
    return _go(loja_id=id)


@lojas_midia_bp.route("/<int:id>/midia/<int:midia_id>", methods=["DELETE"])
def remover_midia(id, midia_id):
    @requer_acesso_loja
    @requer_permissao("configuracoes.editar")
    def _go(loja_id):
        from core.lojas_midia import remover
        result = remover(midia_id, loja_id=loja_id)
        if result.get("error"):
            return jsonify(result), 400
        auditar_exclusao("lojas", "midia", loja_id, {"midia_id": midia_id})
        return jsonify({"success": True})
    return _go(loja_id=id)
