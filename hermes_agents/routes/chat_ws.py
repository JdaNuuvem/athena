"""WebSocket do chat interno — /ws/chat."""
import json
from flask import request
from flask_sock import Sock

from core.rbac import verificar_token_sessao
from core.chat import enviar_mensagem, participantes_ids, atualizar_presenca, marcar_lido
from core.chat_ws import registrar_conexao, remover_conexao, broadcast_para_participantes, enviar_para_usuario

sock = Sock()


def init_sock(app):
    sock.init_app(app)

    @sock.route("/ws/chat")
    def chat_socket(ws):
        token = request.args.get("token", "")
        payload = verificar_token_sessao(token)
        if not payload or not payload.get("user_id"):
            ws.close()
            return
        user_id = int(payload["user_id"])
        registrar_conexao(user_id, ws)
        atualizar_presenca(user_id, "online")
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


def _processar_evento(user_id: int, dados: dict) -> None:
    tipo = dados.get("tipo")
    if tipo == "enviar_mensagem":
        conversa_id = dados.get("conversa_id")
        if user_id not in participantes_ids(conversa_id):
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
        marcar_lido(conversa_id, user_id, ultima_id)
        broadcast_para_participantes(conversa_id, {
            "evento": "confirmacao_leitura", "conversa_id": conversa_id,
            "user_id": user_id, "ultima_mensagem_id": ultima_id,
        })
