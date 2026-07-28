"""Rotas de midia da loja (logo/banner/fotos/galeria/video) — ver
core/lojas_midia.py (wrapper sobre o upload generico de core/documentos.py)."""
from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao
from core.seguranca import auditar_alteracao, auditar_exclusao

lojas_midia_bp = Blueprint("lojas_midia", __name__, url_prefix="/api/lojas/manage")


@lojas_midia_bp.route("/<int:id>/midia", methods=["GET"])
def listar_midia(id):
    @requer_permissao("configuracoes.editar")
    def _go():
        from core.lojas_midia import listar
        tipo = request.args.get("tipo")
        return jsonify({"midia": listar(id, tipo=tipo)})
    return _go()


@lojas_midia_bp.route("/<int:id>/midia", methods=["POST"])
def vincular_midia(id):
    tipo = request.form.get("tipo", "")
    arquivo = request.files.get("arquivo")
    if not arquivo:
        return jsonify({"error": "Arquivo e obrigatorio"}), 400

    @requer_permissao("configuracoes.editar")
    def _go():
        from core.lojas_midia import vincular
        result = vincular(id, tipo, arquivo.read(), arquivo.filename, mime_type=arquivo.mimetype or "application/octet-stream")
        if result.get("error"):
            return jsonify(result), 400
        auditar_alteracao("criar", "lojas", "midia", id, dados_depois={"tipo": tipo, "nome": arquivo.filename})
        return jsonify({"midia": result})
    return _go()


@lojas_midia_bp.route("/<int:id>/midia/<int:midia_id>", methods=["DELETE"])
def remover_midia(id, midia_id):
    @requer_permissao("configuracoes.editar")
    def _go():
        from core.lojas_midia import remover
        result = remover(midia_id)
        if result.get("error"):
            return jsonify(result), 400
        auditar_exclusao("lojas", "midia", id, {"midia_id": midia_id})
        return jsonify({"success": True})
    return _go()
