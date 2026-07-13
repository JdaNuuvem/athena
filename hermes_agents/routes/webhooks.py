from datetime import date, timedelta
from flask import Blueprint, request, jsonify
from core import get_db, run_async

webhooks_bp = Blueprint("webhooks", __name__)


@webhooks_bp.route("/webhook/whatsapp", methods=["POST"])
def whatsapp_webhook():
    from ag_14_whatsapp import parse_webhook, processar_mensagem
    parsed = parse_webhook(request.json)
    if not parsed:
        return jsonify({"ignored": True})
    resultado = processar_mensagem(parsed["phone"], parsed["text"])
    return jsonify({"processed": True, "resultado": resultado})


@webhooks_bp.route("/webhook/bling/pedido", methods=["POST"])
def bling_pedido_webhook():
    from bling_erp import webhook_bling_pedido
    return jsonify(webhook_bling_pedido(request.json))


@webhooks_bp.route("/webhook/shopee/pedido", methods=["POST"])
def shopee_pedido_webhook():
    from shopee import webhook_shopee_pedido
    return jsonify(webhook_shopee_pedido(request.json))


# Bling webhook with DB persistence (replaces the duplicate route from old athena_bridge)
@webhooks_bp.route("/webhook/bling/pedido/v2", methods=["POST"])
def bling_pedido_webhook_v2():
    async def _go():
        try:
            db = await get_db()
            payload = request.json or {}
            pedido = payload.get("pedido", payload)
            for item in pedido.get("itens", []):
                sku = item.get("codigo", "")
                qtd = int(item.get("quantidade", 1))
                preco = float(item.get("valorUnitario", 0))
                await db.execute(
                    "INSERT INTO vendas (data, sku, marketplace, quantidade, preco_venda, receita_bruta) VALUES ($1,$2,'bling',$3,$4,$5)",
                    date.today(), sku, qtd, preco, preco * qtd)
            from ag_04_planejador import adicionar_pedido_producao
            for item in pedido.get("itens", []):
                adicionar_pedido_producao(
                    sku=item.get("codigo", ""), quantidade=int(item.get("quantidade", 1)),
                    prazo=date.today() + timedelta(days=3), prioridade=5,
                    cliente_id=pedido.get("contato", {}).get("nome", ""))
            return {"success": True, "itens": len(pedido.get("itens", []))}
        except Exception as e:
            return {"error": str(e)}
    return jsonify(run_async(_go()))


# ── Bling Webhook Receiver (Task 4) ──

from hermes_agents.bling_erp import validar_assinatura_webhook, processar_evento_webhook as processar_evento

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
