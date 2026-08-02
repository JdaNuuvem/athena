"""WebSocket do chat interno — /ws/chat."""
import json
from flask import request
from flask_sock import Sock

from core.rbac import verificar_token_sessao
from core.chat import (
    enviar_mensagem, participantes_ids, atualizar_presenca, marcar_lido,
    obter_anexo, listar_conversas_usuario,
)
from core.chat_ws import registrar_conexao, remover_conexao, broadcast_para_participantes, enviar_para_usuario

sock = Sock()


def _notificar_presenca(user_id: int, status: str) -> None:
    """Avisa todo mundo que compartilha alguma conversa com este usuario que ele
    ficou online/offline — sem isso o indicador de presenca nunca aparece."""
    notificados = set()
    for conversa in listar_conversas_usuario(user_id):
        for outro_id in participantes_ids(conversa["id"]):
            if outro_id != user_id and outro_id not in notificados:
                enviar_para_usuario(outro_id, {"evento": "presenca_atualizada", "user_id": user_id, "status": status})
                notificados.add(outro_id)


def init_sock(app):
    sock.init_app(app)

    @sock.route("/ws/chat")
    def chat_socket(ws):
        token = request.args.get("token", "")
        payload = verificar_token_sessao(token)
        # ponytail: conta master (login ATHENA_ADMIN_EMAIL) tem user_id=0 —
        # "not payload.get('user_id')" tratava 0 como falsy e fechava a conexao
        # na hora. 0 e' um user_id valido, so' payload ausente e' nao-autenticado.
        if not payload or payload.get("user_id") is None:
            ws.close()
            return
        user_id = int(payload["user_id"])
        registrar_conexao(user_id, ws)
        atualizar_presenca(user_id, "online")
        _notificar_presenca(user_id, "online")
        try:
            while True:
                raw = ws.receive()
                if raw is None:
                    break
                try:
                    dados = json.loads(raw)
                except ValueError:
                    continue
                _processar_evento(user_id, dados)
        finally:
            remover_conexao(user_id, ws)
            atualizar_presenca(user_id, "offline")
            _notificar_presenca(user_id, "offline")


def _processar_evento(user_id: int, dados: dict) -> None:
    tipo = dados.get("tipo")
    if tipo == "enviar_mensagem":
        conversa_id = dados.get("conversa_id")
        if user_id not in participantes_ids(conversa_id):
            return
        anexo_id = dados.get("anexo_id")
        if anexo_id:
            anexo = obter_anexo(int(anexo_id))
            if anexo.get("error") or anexo.get("enviado_por") != user_id:
                return
        mensagem = enviar_mensagem(conversa_id, user_id, dados.get("texto", ""),
                                    dados.get("anexo_id"), dados.get("thread_pai_id"))
        if not mensagem.get("error"):
            broadcast_para_participantes(conversa_id, {
                "evento": "nova_mensagem",
                "mensagem": {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in mensagem.items()},
            })
    elif tipo == "digitando":
        conversa_id = dados.get("conversa_id")
        if user_id not in participantes_ids(conversa_id):
            return
        broadcast_para_participantes(conversa_id, {
            "evento": "usuario_digitando", "conversa_id": conversa_id, "user_id": user_id,
        })
    elif tipo == "presenca":
        status = dados.get("status", "online")
        atualizar_presenca(user_id, status)
        for outro_id in dados.get("notificar", []):
            enviar_para_usuario(outro_id, {"evento": "presenca_atualizada", "user_id": user_id, "status": status})
    elif tipo == "lido":
        conversa_id = dados.get("conversa_id")
        ultima_id = dados.get("ultima_mensagem_id")
        if user_id not in participantes_ids(conversa_id):
            return
        marcar_lido(conversa_id, user_id, ultima_id)
        broadcast_para_participantes(conversa_id, {
            "evento": "confirmacao_leitura", "conversa_id": conversa_id,
            "user_id": user_id, "ultima_mensagem_id": ultima_id,
        })
