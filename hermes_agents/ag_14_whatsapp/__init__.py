"""
AG-14: Vendedor WhatsApp (port do ATHENA whatsapp-seller)
Canal de vendas via WhatsApp usando Evolution API.
"""
import sys, os, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from core import log, run_async, get_db, hoje

AGENT = "AG-14 | Vendedor WhatsApp"

EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL", "http://localhost:8080")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY", "")
INSTANCE_NAME = os.environ.get("WHATSAPP_INSTANCE", "hermes")

def _headers():
    return {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}

def configurado() -> bool:
    return bool(EVOLUTION_API_KEY)

def status_conexao() -> str:
    try:
        r = requests.get(f"{EVOLUTION_API_URL}/instance/connectionState/{INSTANCE_NAME}", headers=_headers(), timeout=10)
        return r.json().get("instance", {}).get("state", "disconnected")
    except:
        return "disconnected"

def conectar(phone_number: str = None) -> dict:
    try:
        body = {"phoneNumber": phone_number} if phone_number else {}
        r = requests.post(f"{EVOLUTION_API_URL}/instance/connect/{INSTANCE_NAME}", headers=_headers(), json=body, timeout=30)
        data = r.json()
        return {"qrCode": data.get("base64"), "status": "scan_qrCode"}
    except Exception as e:
        return {"error": str(e), "status": "connection_failed"}

def criar_instancia() -> dict:
    try:
        r = requests.post(f"{EVOLUTION_API_URL}/instance/create", headers=_headers(), json={
            "instanceName": INSTANCE_NAME, "token": EVOLUTION_API_KEY,
            "qrcode": True, "integration": "WHATSAPP-BAILEYS"
        }, timeout=15)
        data = r.json()
        return {
            "qrCode": data.get("instance", {}).get("qrcode", {}).get("base64"),
            "pairingCode": data.get("instance", {}).get("pairingCode"),
        }
    except:
        return {}

def enviar_texto(phone: str, text: str) -> bool:
    if not configurado():
        return False
    try:
        r = requests.post(f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}",
            headers=_headers(), json={"number": re.sub(r'\D', '', phone), "text": text, "delay": 500}, timeout=15)
        return r.ok
    except:
        return False

def enviar_botoes(phone: str, text: str, botoes: list, titulo: str = "", rodape: str = "") -> bool:
    if not configurado():
        return False
    try:
        r = requests.post(f"{EVOLUTION_API_URL}/message/sendButtons/{INSTANCE_NAME}",
            headers=_headers(), json={
                "number": re.sub(r'\D', '', phone), "title": titulo,
                "description": text, "footer": rodape,
                "buttons": [{"buttonText": b["text"], "buttonId": b["id"]} for b in botoes],
            }, timeout=15)
        return r.ok
    except:
        return False

def enviar_card_produto(phone: str, nome: str, descricao: str, preco: float, sku: str) -> bool:
    text = f"*{nome}*\n\n{descricao}\n\n💰 *R${preco:.2f}*\n📦 SKU: {sku}"
    return enviar_botoes(phone, text, [
        {"text": "🛒 Comprar", "id": f"buy:{sku}"},
        {"text": "📋 Detalhes", "id": f"details:{sku}"},
    ], titulo=nome, rodape=f"SKU: {sku}")

def enviar_status_pedido(phone: str, pedido_id: str, status: str, tracking: str = "") -> bool:
    emoji = {"confirmed": "✅", "in_production": "🏭", "shipped": "🚚", "delivered": "📦", "cancelled": "❌"}
    e = emoji.get(status, "📋")
    text = f"{e} *Pedido #{pedido_id[:8]}*\nStatus: *{status}*"
    if tracking:
        text += f"\n📮 Rastreio: `{tracking}`"
    return enviar_texto(phone, text)

def enviar_catalogo(phone: str, produtos: list) -> bool:
    text = "📋 *Nosso Catálogo*\n\n"
    for i, p in enumerate(produtos, 1):
        text += f"{i}️⃣ *{p['nome']}*\n   💰 R${p['preco']:.2f}\n   📦 {p.get('sku','')}\n   {p['descricao'][:100]}\n\n"
    text += "Responda com o número ou nome do produto para mais detalhes!"
    return enviar_texto(phone, text)

def enviar_promocao(phone: str, titulo: str, corpo: str, cupom: str = "") -> bool:
    text = f"🎯 *{titulo}*\n\n{corpo}"
    if cupom:
        text += f"\n\n🎫 Cupom: *{cupom}*"
    return enviar_texto(phone, text)

def enviar_carrinho_abandonado(phone: str, cliente: str, produto: str, total: float) -> bool:
    text = (f"👋 Olá *{cliente}*!\n\n"
            f"Percebemos que você deixou *{produto}* no carrinho.\n\n"
            f"💰 Valor: *R${total:.2f}*\n\n"
            f"Ainda tem interesse? Responda *SIM* e eu finalizo seu pedido agora mesmo!")
    return enviar_texto(phone, text)

CATALOGO_PADRAO = [
    {"nome": "Balde Plástico 20L", "preco": 49.90, "sku": "BLD-001", "descricao": "Balde industrial reforçado, polipropileno virgem, alça metálica"},
    {"nome": "Tampa Pressão 20L", "preco": 19.90, "sku": "TMP-001", "descricao": "Tampa com vedação para balde 20L, trava de segurança"},
    {"nome": "Mangueira Cristal 1/2\"", "preco": 12.90, "sku": "MNG-001", "descricao": "Mangueira PVC cristal, atóxica, rolo 10m"},
    {"nome": "Caixa Plástica 60L", "preco": 79.90, "sku": "CXA-001", "descricao": "Caixa organizadora industrial, empilhável, reforçada"},
    {"nome": "Combo Limpeza", "preco": 99.90, "sku": "CMB-001", "descricao": "Balde 20L + Tampa + Mangueira 10m — 15% de desconto"},
]

TABELA_PRECOS = (
    "💰 *Tabela de Preços*\n\n"
    "1️⃣ Balde 20L — R$ 49,90\n"
    "2️⃣ Tampa Pressão — R$ 19,90\n"
    "3️⃣ Mangueira Cristal — R$ 12,90\n"
    "4️⃣ Caixa 60L — R$ 79,90\n"
    "5️⃣ Combo Limpeza — R$ 99,90\n\n"
    "🚚 *Frete grátis acima de R$ 150!*\n\n"
    "Digite o número para detalhes!"
)

def processar_mensagem(phone: str, texto: str) -> dict:
    t = texto.lower().strip()

    if re.search(r'ola|oi|bom dia|boa tarde|boa noite|inicio|start', t):
        enviar_texto(phone, (
            "👋 Olá! Sou o assistente de vendas da *ATHENA OS*.\n\n"
            "📋 Digite *catálogo* para ver produtos\n"
            "💰 Digite *preços* para valores\n"
            "🛒 Digite *comprar* para fazer pedido\n"
            "👤 Digite *atendente* para falar com pessoa"
        ))
        return {"intencao": "saudacao"}

    if re.search(r'catalogo|produtos|servicos|lista|tem|vende', t):
        enviar_catalogo(phone, CATALOGO_PADRAO)
        return {"intencao": "catalogo"}

    if re.search(r'preco|valor|custa|quanto', t):
        enviar_texto(phone, TABELA_PRECOS)
        return {"intencao": "precos"}

    if re.search(r'comprar|quero|pedido|pagar|fechar', t):
        enviar_texto(phone, (
            "🛒 Para finalizar seu pedido, preciso de:\n\n"
            "📝 *Nome completo*\n"
            "📍 *Endereço de entrega*\n"
            "💳 *Forma de pagamento* (PIX/cartão)\n"
            "📦 *Produto desejado* (nome ou SKU)\n\n"
            "Me envie essas informações e confirmo na hora! ✅"
        ))
        return {"intencao": "compra"}

    if re.search(r'atendente|humano|pessoa|falar|ajuda', t):
        enviar_texto(phone, (
            "⏳ Um momento, vou transferir para um atendente humano...\n\n"
            "Enquanto isso, pode adiantar qual é sua dúvida?"
        ))
        return {"intencao": "humano"}

    enviar_texto(phone, (
        "Desculpe, não entendi. 😅\n\n"
        "Tente:\n"
        "• *catálogo* — ver produtos\n"
        "• *preços* — ver valores\n"
        "• *comprar* — fazer pedido\n"
        "• *atendente* — falar com pessoa"
    ))
    return {"intencao": "fallback"}

def criar_pedido(phone: str, cliente: str, itens: list) -> dict:
    pedido_id = f"WA-{hoje()}-{phone[-6:]}"
    total = sum(i.get("preco", 0) * i.get("qtd", 1) for i in itens)
    enviar_texto(phone, (
        f"✅ *Pedido Confirmado!*\n\n"
        f"📦 Nº *{pedido_id}*\n"
        f"👤 {cliente}\n"
        f"💰 Total: *R${total:.2f}*\n"
        f"📋 {len(itens)} item(ns)\n\n"
        f"Acompanhe seu pedido enviando *STATUS* a qualquer momento."
    ))
    async def _save():
        db = await get_db()
        await db.execute("""
            INSERT INTO pedidos_whatsapp (pedido_id, phone, cliente, itens, total, status)
            VALUES ($1, $2, $3, $4, $5, 'confirmado')
        """, pedido_id, phone, cliente, json.dumps(itens), total)
    try:
        run_async(_save())
    except Exception as e:
        log(AGENT, f"⚠️ Erro ao salvar pedido: {e}")
    return {"pedido_id": pedido_id, "total": total, "itens": len(itens)}

def parse_webhook(body: dict) -> dict | None:
    data = body.get("data")
    if not data:
        return None
    remote_jid = data.get("remoteJid", "")
    phone = remote_jid.split("@")[0] if remote_jid else ""
    msg_type = data.get("messageType", "")
    texto = ""
    if msg_type == "conversation":
        texto = data.get("text", {}).get("message", "")
    elif msg_type == "extendedTextMessage":
        texto = data.get("message", {}).get("extendedTextMessage", {}).get("text", "")
    elif msg_type == "buttonMessage":
        texto = data.get("buttonResponse", {}).get("selectedDisplayText", "")
    if data.get("fromMe"):
        return None
    if not phone or not texto:
        return None
    return {"phone": phone, "text": texto, "data": data}

def obter_estatisticas() -> dict:
    async def _go():
        db = await get_db()
        total_pedidos = await db.fetchval("SELECT COUNT(*) FROM pedidos_whatsapp") or 0
        faturamento = await db.fetchval("SELECT COALESCE(SUM(total), 0) FROM pedidos_whatsapp") or 0
        return {
            "conectado": status_conexao(),
            "total_pedidos": total_pedidos,
            "faturamento_total": float(faturamento),
            "data": hoje(),
        }
    return run_async(_go())

if __name__ == "__main__":
    log(AGENT, "Auto-teste")
    log(AGENT, f"Configurado: {configurado()}")
    log(AGENT, f"Status: {status_conexao()}")
    log(AGENT, f"Catálogo: {len(CATALOGO_PADRAO)} produtos")
    log(AGENT, f"Processar saudação: {processar_mensagem('5511999999999', 'ola')}")
