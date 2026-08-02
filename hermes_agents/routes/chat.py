"""Rotas REST do Chat Interno — /api/chat/*"""
import os, time
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, send_file
from core.rbac import usuario_atual_da_request
from core.chat import (
    criar_conversa_dm, criar_conversa_grupo, listar_conversas_usuario,
    listar_mensagens, enviar_mensagem, editar_mensagem, excluir_mensagem,
    marcar_lido, adicionar_participante, remover_participante, papel_do_usuario,
    usuario_e_participante, buscar_mensagens, listar_canais_departamento,
    salvar_anexo, obter_anexo, conversa_do_anexo, obter_conversa, participantes_info,
    processar_mencoes,
)
from core.chat_ws import broadcast_para_participantes

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "chat")
TAMANHO_MAXIMO_BYTES = 25 * 1024 * 1024


def _serializar(mensagem: dict) -> dict:
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in mensagem.items()}


def _adaptar_mensagem_ticket(m: dict, conversa_id: int) -> dict:
    """atend_mensagens -> shape de MensagemChat esperado pelo frontend.

    Limitacao conhecida e aceita nesta fase: atend_mensagens guarda o remetente
    como texto livre (nome/telefone do cliente ou nome do atendente), nao como
    id do RBAC. Por isso remetente_id fica None e a UI renderiza toda mensagem
    de ticket como 'recebida', mesmo quando foi o agente que respondeu."""
    return {
        "id": m["id"], "conversa_id": conversa_id, "thread_pai_id": None,
        "remetente_id": None, "texto": m.get("conteudo"),
        "anexo_id": None, "created_at": m.get("enviado_em"),
        "editado_em": None, "excluido_em": None,
    }


@chat_bp.route("/usuarios", methods=["GET"])
def chat_listar_usuarios():
    """Lista enxuta (id, nome) de usuarios ativos pra escolher em nova DM/grupo.

    ponytail: /api/rbac/usuarios exige "configuracoes.ver" (permissao
    administrativa) e devolve email/role_id/ativo — nao da pra reusar aqui
    sem quebrar pra qualquer usuario comum tentando so' iniciar uma conversa.
    Exposicao minima: so' id+nome, so' ativos, sem permissao extra alem de
    estar logado (mesmo requisito de qualquer outra rota do chat)."""
    usuario = usuario_atual_da_request()
    if usuario.get("user_id") is None:
        return jsonify({"error": "Nao autenticado"}), 401
    from core.rbac import list_usuarios
    todos = list_usuarios()
    return jsonify({"data": [{"id": u["id"], "nome": u["nome"]} for u in todos if u.get("ativo")]})


@chat_bp.route("/conversas", methods=["GET"])
def chat_listar_conversas():
    usuario = usuario_atual_da_request()
    # ponytail: user_id da conta master (login ATHENA_ADMIN_EMAIL) e' 0 —
    # "if not usuario.get('user_id')" tratava 0 como falsy e barrava a conta
    # master de TODO o chat (redirecionava pro login). 0 e' um user_id valido,
    # so' ausencia de token (None) e' que significa nao-autenticado.
    if usuario.get("user_id") is None:
        return jsonify({"error": "Nao autenticado"}), 401
    return jsonify({"data": listar_conversas_usuario(int(usuario["user_id"]), bool(usuario.get("is_master")))})


@chat_bp.route("/conversas", methods=["POST"])
def chat_criar_conversa():
    usuario = usuario_atual_da_request()
    if usuario.get("user_id") is None:
        return jsonify({"error": "Nao autenticado"}), 401
    data = request.json or {}
    tipo = data.get("tipo")
    if tipo in ("dm", "grupo") and usuario.get("is_master"):
        # ponytail: conta master nao tem linha em rbac_usuarios (login via env
        # var, sem cadastro real) — chat_participantes.user_id e' FK+PK pra
        # rbac_usuarios(id), entao o INSERT quebraria com erro cru de FK.
        # Bloqueia cedo com mensagem clara em vez de deixar estourar no banco.
        return jsonify({"error": "Conta master (login administrativo via variavel de ambiente) nao pode iniciar mensagens diretas ou grupos — entre com uma conta de usuario cadastrada para isso."}), 400
    criado_por = int(usuario["user_id"])
    if tipo == "dm":
        outro_user_id = data.get("user_id")
        if not outro_user_id:
            return jsonify({"error": "user_id obrigatorio para DM"}), 400
        return jsonify(criar_conversa_dm(criado_por, int(outro_user_id)))
    if tipo == "grupo":
        return jsonify(criar_conversa_grupo(
            data.get("nome", ""), data.get("descricao", ""), criado_por,
            [int(u) for u in data.get("participantes", [])],
            data.get("departamento"), data.get("loja_id")))
    return jsonify({"error": "tipo invalido"}), 400


@chat_bp.route("/conversas/<int:conversa_id>/mensagens", methods=["GET"])
def chat_listar_mensagens(conversa_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    is_master = bool(usuario.get("is_master"))
    if user_id is None or not usuario_e_participante(conversa_id, int(user_id), is_master):
        return jsonify({"error": "Permissao negada"}), 403
    conversa = obter_conversa(conversa_id)
    if conversa and conversa.get("tipo") == "ticket":
        from core.atendimento import listar_mensagens_ticket
        mensagens = listar_mensagens_ticket(conversa["ticket_ref_id"])
        return jsonify({"data": [_adaptar_mensagem_ticket(m, conversa_id) for m in mensagens]})
    antes_de = request.args.get("antes_de")
    return jsonify({"data": listar_mensagens(conversa_id, antes_de)})


@chat_bp.route("/conversas/<int:conversa_id>/mensagens", methods=["POST"])
def chat_enviar_mensagem(conversa_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    is_master = bool(usuario.get("is_master"))
    if user_id is None or not usuario_e_participante(conversa_id, int(user_id), is_master):
        return jsonify({"error": "Permissao negada"}), 403
    data = request.json or {}
    anexo_id = data.get("anexo_id")
    if anexo_id:
        anexo = obter_anexo(int(anexo_id))
        if anexo.get("error") or anexo.get("enviado_por") != int(user_id):
            return jsonify({"error": "Anexo invalido"}), 403
    conversa = obter_conversa(conversa_id)
    if conversa and conversa.get("tipo") == "ticket":
        from core.atendimento import adicionar_mensagem
        texto_processado = processar_mencoes(conversa_id, data.get("texto", ""))
        criada = adicionar_mensagem(conversa["ticket_ref_id"],
                                    usuario.get("nome") or usuario.get("email"),
                                    texto_processado, "texto")
        if criada.get("error"):
            return jsonify(criada)
        mensagem = _adaptar_mensagem_ticket(criada, conversa_id)
        broadcast_para_participantes(conversa_id, {"evento": "nova_mensagem", "mensagem": _serializar(mensagem)})
        return jsonify(mensagem)
    if is_master:
        # ponytail: chat_mensagens.remetente_id e' FK pra rbac_usuarios(id) —
        # conta master nao tem linha real la. So' consegue ver canal/ticket
        # (acima), nao enviar. Ticket escapa disso porque atend_mensagens
        # guarda o remetente como texto livre, nao FK.
        return jsonify({"error": "Conta master (login administrativo via variavel de ambiente) pode visualizar este canal, mas nao pode enviar mensagens — entre com uma conta de usuario cadastrada para participar."}), 400
    mensagem = enviar_mensagem(conversa_id, int(user_id), data.get("texto", ""),
                                data.get("anexo_id"), data.get("thread_pai_id"))
    if not mensagem.get("error"):
        broadcast_para_participantes(conversa_id, {"evento": "nova_mensagem", "mensagem": _serializar(mensagem)})
    return jsonify(mensagem)


@chat_bp.route("/mensagens/<int:mensagem_id>", methods=["PUT"])
def chat_editar_mensagem(mensagem_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if user_id is None:
        return jsonify({"error": "Nao autenticado"}), 401
    data = request.json or {}
    mensagem = editar_mensagem(mensagem_id, int(user_id), data.get("texto", ""))
    if mensagem.get("error"):
        return jsonify(mensagem), 403
    broadcast_para_participantes(mensagem["conversa_id"], {"evento": "mensagem_editada", "mensagem": _serializar(mensagem)})
    return jsonify(mensagem)


@chat_bp.route("/mensagens/<int:mensagem_id>", methods=["DELETE"])
def chat_excluir_mensagem(mensagem_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if user_id is None:
        return jsonify({"error": "Nao autenticado"}), 401
    mensagem = excluir_mensagem(mensagem_id, int(user_id))
    if mensagem.get("error"):
        return jsonify(mensagem), 403
    broadcast_para_participantes(mensagem["conversa_id"], {"evento": "mensagem_excluida", "mensagem": _serializar(mensagem)})
    return jsonify(mensagem)


@chat_bp.route("/anexos", methods=["POST"])
def chat_upload_anexo():
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if user_id is None:
        return jsonify({"error": "Nao autenticado"}), 401
    if usuario.get("is_master"):
        # chat_anexos.enviado_por e' FK pra rbac_usuarios(id) — conta master
        # nao tem linha real la, o INSERT quebraria com erro cru de FK.
        return jsonify({"error": "Conta master (login administrativo via variavel de ambiente) nao pode enviar anexos no chat — entre com uma conta de usuario cadastrada."}), 400
    if request.content_length and request.content_length > TAMANHO_MAXIMO_BYTES:
        return jsonify({"error": "Arquivo maior que 25MB"}), 413
    arquivo = request.files.get("arquivo")
    if not arquivo:
        return jsonify({"error": "arquivo obrigatorio"}), 400
    conteudo = arquivo.read()
    if len(conteudo) > TAMANHO_MAXIMO_BYTES:
        return jsonify({"error": "Arquivo maior que 25MB"}), 413
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    nome_base = secure_filename(arquivo.filename) or "upload.bin"
    nome_seguro = f"{int(user_id)}_{int(time.time() * 1000)}_{nome_base}"
    caminho_completo = os.path.realpath(os.path.join(UPLOAD_DIR, nome_seguro))
    if not caminho_completo.startswith(os.path.realpath(UPLOAD_DIR) + os.sep):
        return jsonify({"error": "nome de arquivo invalido"}), 400
    with open(caminho_completo, "wb") as f:
        f.write(conteudo)
    return jsonify(salvar_anexo(arquivo.filename, arquivo.mimetype, len(conteudo), nome_seguro, int(user_id)))


@chat_bp.route("/anexos/<int:anexo_id>", methods=["GET"])
def chat_download_anexo(anexo_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if user_id is None:
        return jsonify({"error": "Nao autenticado"}), 401
    conversa_id = conversa_do_anexo(anexo_id)
    if conversa_id is None or not usuario_e_participante(conversa_id, int(user_id), bool(usuario.get("is_master"))):
        return jsonify({"error": "Permissao negada"}), 403
    anexo = obter_anexo(anexo_id)
    if anexo.get("error"):
        return jsonify(anexo), 404
    caminho_completo = os.path.realpath(os.path.join(UPLOAD_DIR, anexo["storage_path"]))
    if not caminho_completo.startswith(os.path.realpath(UPLOAD_DIR) + os.sep):
        return jsonify({"error": "anexo invalido"}), 400
    return send_file(caminho_completo, download_name=anexo["nome_arquivo"], as_attachment=True, mimetype="application/octet-stream")


@chat_bp.route("/conversas/<int:conversa_id>/participantes", methods=["POST"])
def chat_adicionar_participante(conversa_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if user_id is None:
        return jsonify({"error": "Nao autenticado"}), 401
    if papel_do_usuario(conversa_id, int(user_id)) not in ("owner", "admin", "moderador"):
        return jsonify({"error": "Permissao negada"}), 403
    data = request.json or {}
    novo_user_id = data.get("user_id")
    if not novo_user_id:
        return jsonify({"error": "user_id obrigatorio"}), 400
    return jsonify(adicionar_participante(conversa_id, int(novo_user_id)))


@chat_bp.route("/conversas/<int:conversa_id>/participantes/<int:membro_id>", methods=["DELETE"])
def chat_remover_participante(conversa_id, membro_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if user_id is None:
        return jsonify({"error": "Nao autenticado"}), 401
    if papel_do_usuario(conversa_id, int(user_id)) not in ("owner", "admin", "moderador"):
        return jsonify({"error": "Permissao negada"}), 403
    return jsonify(remover_participante(conversa_id, membro_id))


@chat_bp.route("/conversas/<int:conversa_id>/lido", methods=["POST"])
def chat_marcar_lido(conversa_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    is_master = bool(usuario.get("is_master"))
    if user_id is None or not usuario_e_participante(conversa_id, int(user_id), is_master):
        return jsonify({"error": "Permissao negada"}), 403
    if is_master:
        # chat_leituras.user_id e' FK pra rbac_usuarios(id) — sem linha real,
        # so' devolve sucesso sem persistir (master nao tem estado de leitura
        # proprio pra rastrear).
        return jsonify({"success": True})
    data = request.json or {}
    return jsonify(marcar_lido(conversa_id, int(user_id), data.get("ultima_mensagem_id")))


@chat_bp.route("/conversas/<int:conversa_id>/participantes", methods=["GET"])
def chat_listar_participantes(conversa_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if user_id is None or not usuario_e_participante(conversa_id, int(user_id), bool(usuario.get("is_master"))):
        return jsonify({"error": "Permissao negada"}), 403
    return jsonify({"data": participantes_info(conversa_id)})


@chat_bp.route("/busca", methods=["GET"])
def chat_busca():
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if user_id is None:
        return jsonify({"error": "Nao autenticado"}), 401
    return jsonify({"data": buscar_mensagens(int(user_id), request.args.get("q", ""), bool(usuario.get("is_master")))})


@chat_bp.route("/canais-departamento", methods=["GET"])
def chat_canais_departamento():
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if user_id is None:
        return jsonify({"error": "Nao autenticado"}), 401
    return jsonify({"data": listar_canais_departamento(int(user_id), bool(usuario.get("is_master")))})
