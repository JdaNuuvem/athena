from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao
from core.api_utils import status_for_resultado as _status_for

atendimento_bp = Blueprint("atendimento", __name__, url_prefix="/api/atendimento")


@atendimento_bp.route("/dashboard", methods=["GET"])
def atend_dashboard():
    from core.atendimento import dashboard as ad
    return jsonify(ad())


@atendimento_bp.route("/tickets/criar", methods=["POST"])
def atend_criar_ticket():
    data = request.json or {}

    @requer_permissao("atendimento.criar")
    def _go():
        from core.atendimento import criar_ticket
        return jsonify(criar_ticket(data.get("cliente", ""), data.get("assunto", ""),
                                    data.get("canal", "whatsapp"), data.get("prioridade", "normal")))
    return _go()


@atendimento_bp.route("/tickets/<int:id>/mensagem", methods=["POST"])
def atend_mensagem(id):
    data = request.json or {}

    @requer_permissao("atendimento.criar")
    def _go():
        from core.atendimento import adicionar_mensagem
        from core.rbac import usuario_atual_da_request
        usuario = usuario_atual_da_request()
        remetente = usuario.get("nome") or usuario.get("email") or data.get("remetente", "")
        return jsonify(adicionar_mensagem(id, remetente, data.get("conteudo", ""), data.get("tipo", "texto")))
    return _go()


@atendimento_bp.route("/tickets/<int:id>/fechar", methods=["POST"])
def atend_fechar(id):
    @requer_permissao("atendimento.editar")
    def _go():
        from core.atendimento import fechar_ticket
        return jsonify(fechar_ticket(id))
    return _go()


@atendimento_bp.route("/tickets/<int:id>/reabrir", methods=["POST"])
def atend_reabrir(id):
    @requer_permissao("atendimento.editar")
    def _go():
        from core.atendimento import reabrir_ticket
        return jsonify(reabrir_ticket(id))
    return _go()


@atendimento_bp.route("/tickets/<int:id>/status", methods=["PUT"])
def atend_mudar_status(id):
    data = request.json or {}

    @requer_permissao("atendimento.editar")
    def _go():
        from core.atendimento import mudar_status_ticket
        resultado = mudar_status_ticket(id, data.get("status", ""))
        return jsonify(resultado), (400 if resultado.get("error") else 200)
    return _go()


@atendimento_bp.route("/tickets/<int:id>/atribuir", methods=["PUT"])
def atend_atribuir(id):
    data = request.json or {}

    @requer_permissao("atendimento.editar")
    def _go():
        atendente_id_raw = data.get("atendente_id")
        if not atendente_id_raw:
            return jsonify({"error": "atendente_id obrigatorio"}), 400
        try:
            atendente_id = int(atendente_id_raw)
        except ValueError:
            return jsonify({"error": "atendente_id invalido"}), 400
        from core.atendimento import atribuir_ticket
        resultado = atribuir_ticket(id, atendente_id)
        return jsonify(resultado), (400 if resultado.get("error") else 200)
    return _go()


@atendimento_bp.route("/tickets/<int:id>/mensagens", methods=["GET"])
def atend_listar_mensagens(id):
    @requer_permissao("atendimento.ver")
    def _go():
        from core.atendimento import listar_mensagens_ticket, _serializar_mensagem_ticket
        from core.chat import conversa_id_do_ticket
        conversa_id = conversa_id_do_ticket(id)
        mensagens = listar_mensagens_ticket(id)
        return jsonify({"data": [_serializar_mensagem_ticket(m, conversa_id) for m in mensagens]})
    return _go()


@atendimento_bp.route("/tickets/<int:id>/anexo", methods=["POST"])
def atend_upload_anexo(id):
    @requer_permissao("atendimento.criar")
    def _go():
        import os, time
        from werkzeug.utils import secure_filename
        from core.rbac import usuario_atual_da_request
        from core.atendimento import adicionar_mensagem

        arquivo = request.files.get("arquivo")
        if not arquivo:
            return jsonify({"error": "arquivo obrigatorio"}), 400
        TAMANHO_MAXIMO_BYTES = 25 * 1024 * 1024
        if request.content_length and request.content_length > TAMANHO_MAXIMO_BYTES:
            return jsonify({"error": "Arquivo maior que 25MB"}), 413
        conteudo = arquivo.read()
        if len(conteudo) > TAMANHO_MAXIMO_BYTES:
            return jsonify({"error": "Arquivo maior que 25MB"}), 413

        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "atendimento")
        os.makedirs(upload_dir, exist_ok=True)
        nome_base = secure_filename(arquivo.filename) or "upload.bin"
        NOME_MAXIMO_CHARS = 100
        if len(nome_base) > NOME_MAXIMO_CHARS:
            raiz, ext = os.path.splitext(nome_base)
            ext = ext[:20]
            nome_base = raiz[:NOME_MAXIMO_CHARS - len(ext)] + ext
        nome_seguro = f"{id}_{int(time.time() * 1000)}_{nome_base}"
        caminho_completo = os.path.realpath(os.path.join(upload_dir, nome_seguro))
        if not caminho_completo.startswith(os.path.realpath(upload_dir) + os.sep):
            return jsonify({"error": "nome de arquivo invalido"}), 400
        try:
            with open(caminho_completo, "wb") as f:
                f.write(conteudo)
        except OSError:
            return jsonify({"error": "falha ao salvar anexo"}), 400

        usuario = usuario_atual_da_request()
        remetente = usuario.get("nome") or usuario.get("email") or ""
        mensagem = adicionar_mensagem(id, remetente, arquivo.filename, "anexo", anexo_url=nome_seguro)
        return jsonify(mensagem)
    return _go()


@atendimento_bp.route("/tickets/<int:id>/anexo/<path:nome_arquivo>", methods=["GET"])
def atend_download_anexo(id, nome_arquivo):
    @requer_permissao("atendimento.ver")
    def _go():
        import os
        from flask import send_file
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "atendimento")
        caminho_completo = os.path.realpath(os.path.join(upload_dir, nome_arquivo))
        if not caminho_completo.startswith(os.path.realpath(upload_dir) + os.sep) or not os.path.isfile(caminho_completo):
            return jsonify({"error": "anexo invalido"}), 404
        return send_file(caminho_completo, as_attachment=True)
    return _go()


@atendimento_bp.route("/tickets", methods=["GET"])
def atend_listar_tickets():
    @requer_permissao("atendimento.ver")
    def _go():
        from core.atendimento import listar_tickets_filtrado
        atendente_id_raw = request.args.get("atendente_id")
        atendente_id = None
        if atendente_id_raw:
            try:
                atendente_id = int(atendente_id_raw)
            except ValueError:
                return jsonify({"error": "atendente_id invalido"}), 400
        return jsonify({"data": listar_tickets_filtrado(
            status=request.args.get("status") or None,
            prioridade=request.args.get("prioridade") or None,
            canal=request.args.get("canal") or None,
            atendente_id=atendente_id,
            q=request.args.get("q") or None,
            de=request.args.get("de") or None,
            ate=request.args.get("ate") or None,
        )})
    return _go()


@atendimento_bp.route("/atendentes", methods=["GET"])
def atend_listar_atendentes():
    @requer_permissao("atendimento.ver")
    def _go():
        from core.atendimento import listar_atendentes
        return jsonify({"data": listar_atendentes()})
    return _go()


@atendimento_bp.route("/kb_artigos/<int:id>/visualizar", methods=["POST"])
def atend_kb_visualizar(id):
    @requer_permissao("atendimento.ver")
    def _go():
        from core.atendimento import visualizar_artigo_kb
        resultado = visualizar_artigo_kb(id)
        return jsonify(resultado), _status_for(resultado)
    return _go()


@atendimento_bp.route("/kb_artigos/<int:id>/votar", methods=["POST"])
def atend_kb_votar(id):
    data = request.json or {}

    @requer_permissao("atendimento.ver")
    def _go():
        from core.atendimento import votar_artigo_kb
        resultado = votar_artigo_kb(id, bool(data.get("util")))
        return jsonify(resultado), _status_for(resultado)
    return _go()


@atendimento_bp.route("/<tabela>", methods=["GET"])
def atend_list(tabela):
    from core.atendimento import list as al, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("atendimento.ver")
    def _go():
        return jsonify({"data": al(tabela)})
    return _go()


@atendimento_bp.route("/<tabela>", methods=["POST"])
def atend_create(tabela):
    from core.atendimento import create as ac, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}

    @requer_permissao("atendimento.criar")
    def _go():
        resultado = ac(tabela, data)
        return jsonify(resultado), _status_for(resultado)
    return _go()


@atendimento_bp.route("/<tabela>/<int:id>", methods=["GET"])
def atend_get(tabela, id):
    from core.atendimento import get as ag, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("atendimento.ver")
    def _go():
        resultado = ag(tabela, id)
        return jsonify(resultado), _status_for(resultado)
    return _go()


@atendimento_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def atend_update(tabela, id):
    from core.atendimento import update as au, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}

    @requer_permissao("atendimento.editar")
    def _go():
        resultado = au(tabela, id, data)
        return jsonify(resultado), _status_for(resultado)
    return _go()


@atendimento_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def atend_delete(tabela, id):
    from core.atendimento import get as ag, delete as ad, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("atendimento.excluir")
    def _go():
        from core.seguranca import auditar_exclusao
        dados_antes = ag(tabela, id)
        resultado = ad(tabela, id)
        if not resultado.get("error"):
            auditar_exclusao("atendimento", tabela, id, dados_antes if not dados_antes.get("error") else None)
        return jsonify(resultado), _status_for(resultado)
    return _go()
