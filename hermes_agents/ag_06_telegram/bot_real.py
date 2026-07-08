"""
Bot Telegram Real - AG-06
Usa python-telegram-bot com webhook.
Token configurável via painel frontend.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.ext.filters import TEXT

from ag_06_telegram import classificar_cliente, recomendar_produtos, calcular_desconto, gerar_pedido, processar_mensagem
from ag_06_telegram.nlp import classificar_intencao, gerar_resposta_por_intencao, extrair_produtos_da_mensagem
from core import log
from core.config import get_config, set_config

AGENT = "AG-06 | Bot Telegram Real"

def get_token() -> str:
    """Retorna token configurado."""
    return get_config("telegram", "token")

def set_token(token: str):
    """Configura token do bot (chamado pelo frontend)."""
    set_config("telegram", "token", token)
    log(AGENT, f"Token configurado: {token[:10]}***{token[-4:]}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa mensagem do usuário."""
    if not update.message or not update.message.text:
        return
    
    user_id = str(update.effective_user.id)
    mensagem = update.message.text
    
    log(AGENT, f"Mensagem de {user_id}: {mensagem[:50]}")
    
    # Processar com AG-06
    resultado = processar_mensagem(user_id, mensagem, update.effective_user.first_name or "")
    
    # Criar keyboard com produtos
    keyboard = criar_keyboard_produtos(resultado.get("produtos_sugeridos", []))
    
    # Enviar resposta
    await update.message.reply_text(
        resultado["resposta"],
        reply_markup=keyboard
    )

def criar_keyboard_produtos(produtos: list) -> InlineKeyboardMarkup:
    """Cria keyboard inline com produtos."""
    buttons = []
    for p in produtos[:5]:
        buttons.append([InlineKeyboardButton(
            f"{p.get('nome', p.get('sku', 'Produto'))} - R${p.get('preco', 0):.2f}",
            callback_data=f"buy_{p.get('sku', '')}"
        )])
    
    # Botão de catalogo
    buttons.append([InlineKeyboardButton("📦 Ver Catálogo", callback_data="catalog")])
    buttons.append([InlineKeyboardButton("💼 Atacado?", callback_data="wholesale")])
    
    return InlineKeyboardMarkup(buttons)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle botão inline."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("buy_"):
        sku = data[4:]
        # Compra direta - criar pedido
        user_id = str(update.effective_user.id)
        
        cliente = classificar_cliente(user_id)
        pedido = gerar_pedido(user_id, [{"sku": sku, "qtd": 1}])
        
        await query.edit_message_text(
            f"✅ Pedido criado: {pedido['pedido_id']}\n\n"
            f"Total: R$ {pedido['desconto']['valor_final']:.2f}\n"
            f"Pagamento via Pix\n\n"
            f"Aguardando pagamento..."
        )
    
    elif data == "catalog":
        await query.edit_message_text("📦 Catálogo disponível via API:\nGET /api/agent/ag_06_telegram/stats")
    
    elif data == "wholesale":
        await query.edit_message_text(
            "💼 **Atacado:**\n\n"
            "Descontos progressivos:\n"
            "• R$200+: 5% off\n"
            "• R$500+: 10% off\n"
            "• R$1000+: 15% off\n\n"
            "Fale conosco para maiores quantidades!"
        )

def main():
    """Inicia o bot."""
    token = get_token()
    if not token:
        log(AGENT, "❌ Token não configurado. Configure via frontend primeiro.")
        return
    
    application = Application.builder().token(token).build()
    
    # Handlers
    application.add_handler(MessageHandler(TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Webhook - Coolify server
    webhook_url = get_config("telegram", "webhook_url") or "https://177.7.45.242:8000/telegram/webhook"
    
    application.run_webhook(
        listen="0.0.0.0",
        port=8443,
        webhook_url=webhook_url
    )

if __name__ == "__main__":
    log(AGENT, "Iniciando bot Telegram...")
    main()