"""Chat WebSocket — registro de conexoes em memoria (processo unico) e broadcast."""
import json, threading

_lock = threading.Lock()
_conexoes = {}  # user_id -> list[ws]


def registrar_conexao(user_id: int, ws) -> None:
    with _lock:
        _conexoes.setdefault(user_id, []).append(ws)


def remover_conexao(user_id: int, ws) -> None:
    with _lock:
        conexoes = _conexoes.get(user_id, [])
        if ws in conexoes:
            conexoes.remove(ws)
        if not conexoes and user_id in _conexoes:
            del _conexoes[user_id]


def enviar_para_usuario(user_id: int, evento: dict) -> None:
    with _lock:
        conexoes = list(_conexoes.get(user_id, []))
    payload = json.dumps(evento)
    for ws in conexoes:
        try:
            ws.send(payload)
        except Exception:
            remover_conexao(user_id, ws)


def broadcast_para_participantes(conversa_id: int, evento: dict) -> None:
    from core.chat import participantes_ids
    for user_id in participantes_ids(conversa_id):
        enviar_para_usuario(user_id, evento)
