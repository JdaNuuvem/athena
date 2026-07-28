"""Rotas REST do Chat Interno — /api/chat/*"""
import os, time
from flask import Blueprint, request, jsonify, send_file
from core.rbac import usuario_atual_da_request
from core.chat import (
    criar_conversa_dm, criar_conversa_grupo, listar_conversas_usuario,
    listar_mensagens, enviar_mensagem, editar_mensagem, excluir_mensagem,
    marcar_lido, adicionar_participante, remover_participante, papel_do_usuario,
    usuario_e_participante, buscar_mensagens, listar_canais_departamento,
    salvar_anexo, obter_anexo, conversa_do_anexo,
)
from core.chat_ws import broadcast_para_participantes

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "chat")
TAMANHO_MAXIMO_BYTES = 25 * 1024 * 1024


def _serializar(mensagem: dict) -> dict:
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in mensagem.items()}


@chat_bp.route("/conversas", methods=["GET"])
def chat_listar_conversas():
    usuario = usuario_atual_da_request()
    if not usuario.get("user_id"):
        return jsonify({"error": "Nao autenticado"}), 401
    return jsonify({"data": listar_conversas_usuario(int(usuario["user_id"]))})


@chat_bp.route("/conversas", methods=["POST"])
def chat_criar_conversa():
    usuario = usuario_atual_da_request()
    if not usuario.get("user_id"):
        return jsonify({"error": "Nao autenticado"}), 401
    data = request.json or {}
    tipo = data.get("tipo")
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
    if not user_id or not usuario_e_participante(conversa_id, int(user_id)):
        return jsonify({"error": "Permissao negada"}), 403
    antes_de = request.args.get("antes_de")
    return jsonify({"data": listar_mensagens(conversa_id, antes_de)})


@chat_bp.route("/conversas/<int:conversa_id>/mensagens", methods=["POST"])
def chat_enviar_mensagem(conversa_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id or not usuario_e_participante(conversa_id, int(user_id)):
        return jsonify({"error": "Permissao negada"}), 403
    data = request.json or {}
    mensagem = enviar_mensagem(conversa_id, int(user_id), data.get("texto", ""),
                                data.get("anexo_id"), data.get("thread_pai_id"))
    if not mensagem.get("error"):
        broadcast_para_participantes(conversa_id, {"evento": "nova_mensagem", "mensagem": _serializar(mensagem)})
    return jsonify(mensagem)


@chat_bp.route("/mensagens/<int:mensagem_id>", methods=["PUT"])
def chat_editar_mensagem(mensagem_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id:
        return jsonify({"error": "Nao autenticado"}), 401
    data = request.json or {}
    mensagem = editar_mensagem(mensagem_id, int(user_id), data.get("texto", ""))
    if not mensagem.get("error"):
        broadcast_para_participantes(mensagem["conversa_id"], {"evento": "mensagem_editada", "mensagem": _serializar(mensagem)})
    return jsonify(mensagem)


@chat_bp.route("/mensagens/<int:mensagem_id>", methods=["DELETE"])
def chat_excluir_mensagem(mensagem_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id:
        return jsonify({"error": "Nao autenticado"}), 401
    mensagem = excluir_mensagem(mensagem_id, int(user_id))
    if not mensagem.get("error"):
        broadcast_para_participantes(mensagem["conversa_id"], {"evento": "mensagem_excluida", "mensagem": _serializar(mensagem)})
    return jsonify(mensagem)


@chat_bp.route("/anexos", methods=["POST"])
def chat_upload_anexo():
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id:
        return jsonify({"error": "Nao autenticado"}), 401
    arquivo = request.files.get("arquivo")
    if not arquivo:
        return jsonify({"error": "arquivo obrigatorio"}), 400
    conteudo = arquivo.read()
    if len(conteudo) > TAMANHO_MAXIMO_BYTES:
        return jsonify({"error": "Arquivo maior que 25MB"}), 413
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    nome_seguro = f"{int(user_id)}_{int(time.time() * 1000)}_{arquivo.filename}"
    with open(os.path.join(UPLOAD_DIR, nome_seguro), "wb") as f:
        f.write(conteudo)
    return jsonify(salvar_anexo(arquivo.filename, arquivo.mimetype, len(conteudo), nome_seguro, int(user_id)))


@chat_bp.route("/anexos/<int:anexo_id>", methods=["GET"])
def chat_download_anexo(anexo_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id:
        return jsonify({"error": "Nao autenticado"}), 401
    conversa_id = conversa_do_anexo(anexo_id)
    if conversa_id is None or not usuario_e_participante(conversa_id, int(user_id)):
        return jsonify({"error": "Permissao negada"}), 403
    anexo = obter_anexo(anexo_id)
    if anexo.get("error"):
        return jsonify(anexo), 404
    return send_file(os.path.join(UPLOAD_DIR, anexo["storage_path"]), download_name=anexo["nome_arquivo"])


@chat_bp.route("/conversas/<int:conversa_id>/participantes", methods=["POST"])
def chat_adicionar_participante(conversa_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id:
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
    if not user_id:
        return jsonify({"error": "Nao autenticado"}), 401
    if papel_do_usuario(conversa_id, int(user_id)) not in ("owner", "admin", "moderador"):
        return jsonify({"error": "Permissao negada"}), 403
    return jsonify(remover_participante(conversa_id, membro_id))


@chat_bp.route("/conversas/<int:conversa_id>/lido", methods=["POST"])
def chat_marcar_lido(conversa_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id or not usuario_e_participante(conversa_id, int(user_id)):
        return jsonify({"error": "Permissao negada"}), 403
    data = request.json or {}
    return jsonify(marcar_lido(conversa_id, int(user_id), data.get("ultima_mensagem_id")))


@chat_bp.route("/busca", methods=["GET"])
def chat_busca():
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id:
        return jsonify({"error": "Nao autenticado"}), 401
    return jsonify({"data": buscar_mensagens(int(user_id), request.args.get("q", ""))})


@chat_bp.route("/canais-departamento", methods=["GET"])
def chat_canais_departamento():
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id:
        return jsonify({"error": "Nao autenticado"}), 401
    return jsonify({"data": listar_canais_departamento(int(user_id))})
