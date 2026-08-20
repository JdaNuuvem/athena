from flask import Blueprint, request, jsonify

webhooks_bp = Blueprint("webhooks", __name__)


@webhooks_bp.route("/webhook/whatsapp", methods=["POST"])
def whatsapp_webhook():
    from ag_14_whatsapp import parse_webhook, processar_mensagem
    parsed = parse_webhook(request.json)
    if not parsed:
        return jsonify({"ignored": True})
    resultado = processar_mensagem(parsed["phone"], parsed["text"])
    return jsonify({"processed": True, "resultado": resultado})


@webhooks_bp.route("/webhook/shopee/pedido", methods=["POST"])
def shopee_pedido_webhook():
    from shopee import webhook_shopee_pedido
    return jsonify(webhook_shopee_pedido(request.json))


# ── Bling Webhook Receiver (Task 4) ──

from bling_erp import validar_assinatura_webhook, processar_evento_webhook as processar_evento

EVENTOS_BLING = [
    "pedido.criado", "pedido.alterado", "pedido.cancelado",
    "produto.criado", "produto.alterado", "produto.excluido",
    "estoque.alterado",
    "contato.criado", "contato.alterado", "contato.excluido",
    "nota-fiscal.criada", "nota-fiscal.alterada", "nota-fiscal.cancelada",
    "conta-receber.criada", "conta-receber.alterada", "conta-receber.cancelada",
    "conta-pagar.criada", "conta-pagar.alterada", "conta-pagar.cancelada",
]

webhook_bp = Blueprint("bling_webhook", __name__)


@webhook_bp.route("/webhook/bling", methods=["POST"])
def receber_webhook_bling():
    signature = request.headers.get("X-Bling-Signature-256", "")
    raw_body = request.get_data()
    if not validar_assinatura_webhook(raw_body, signature):
        return jsonify({"error": "Assinatura inválida"}), 401
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Payload inválido ou vazio"}), 400
    evento = payload.get("evento", payload.get("event", ""))
    if not evento:
        if "pedido" in payload:
            evento = "pedido.criado"
        elif "produto" in payload:
            evento = "produto.criado"
        elif "estoque" in payload:
            evento = "estoque.alterado"
        else:
            evento = "desconhecido"
    result = processar_evento(evento, payload)
    return jsonify({
        "received": True,
        "evento": evento,
        "processed": result.get("processed", False),
        "error": result.get("error"),
    })


@webhook_bp.route("/webhook/bling/eventos", methods=["GET"])
def listar_eventos_suportados():
    return jsonify({"total": len(EVENTOS_BLING), "eventos": EVENTOS_BLING})


@webhook_bp.route("/webhook/bling", methods=["GET"])
def status_webhook():
    return jsonify({
        "ativo": True,
        "eventos_suportados": len(EVENTOS_BLING),
        "endpoint": "/webhook/bling",
        "metodo": "POST",
        "autenticacao": "HMAC-SHA256 (X-Bling-Signature-256)",
    })
