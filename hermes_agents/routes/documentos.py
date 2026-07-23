from flask import Blueprint, request, jsonify, Response

documentos_bp = Blueprint("documentos", __name__, url_prefix="/api/documentos")
seguranca_bp = Blueprint("seguranca", __name__)


@documentos_bp.route("", methods=["GET"])
def doc_listar():
    from core.documentos import listar
    tipo = request.args.get("entidade_tipo", "")
    eid = request.args.get("entidade_id")
    return jsonify({"data": listar(tipo, int(eid) if eid else None)})


@documentos_bp.route("", methods=["POST"])
def doc_upload():
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nome vazio"}), 400
    from core.documentos import upload
    result = upload(file.read(), file.filename,
                    entidade_tipo=request.form.get("entidade_tipo", ""),
                    entidade_id=int(request.form.get("entidade_id", 0)) or None,
                    criado_por=request.form.get("criado_por", ""),
                    mime_type=file.content_type or "application/octet-stream")
    return jsonify(result)


@documentos_bp.route("/<int:id>", methods=["GET"])
def doc_download(id):
    from core.documentos import download
    from flask import send_file
    filepath, nome, mime = download(id)
    if filepath is None:
        return jsonify({"error": "Arquivo nao encontrado"}), 404
    return send_file(filepath, mimetype=mime, as_attachment=False, download_name=nome)


@documentos_bp.route("/<int:id>", methods=["DELETE"])
def doc_deletar(id):
    from core.documentos import deletar
    return jsonify(deletar(id))


@documentos_bp.route("/stats", methods=["GET"])
def doc_stats():
    from core.documentos import stats
    return jsonify(stats())


@seguranca_bp.route("/api/auditoria", methods=["GET"])
def seg_auditoria():
    from core.seguranca import listar_auditoria
    modulo = request.args.get("modulo", "")
    email = request.args.get("email", "")
    entidade = request.args.get("entidade", "")
    return jsonify({"auditoria": listar_auditoria(modulo, email, entidade)})


@seguranca_bp.route("/api/logs", methods=["GET"])
def seg_logs():
    from core.seguranca import listar_logs
    level = request.args.get("level", "")
    modulo = request.args.get("modulo", "")
    return jsonify({"logs": listar_logs(level, modulo)})


@seguranca_bp.route("/api/historico/<entidade>/<int:id>", methods=["GET"])
def seg_historico(entidade, id):
    from core.seguranca import listar_historico
    return jsonify({"historico": listar_historico(entidade, id)})


@seguranca_bp.route("/api/historico/<entidade>", methods=["GET"])
def seg_historico_resumo(entidade):
    from core.seguranca import historico_resumo
    return jsonify({"resumo": historico_resumo(entidade)})
