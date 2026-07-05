import { HttpClient } from '../http/http-client'
import { getConfig } from '../config/app-config'

const isDev = process.env['NODE_ENV'] === 'development'

export interface TelegramMessage {
  chatId: string
  text: string
  parseMode?: 'HTML' | 'MarkdownV2'
  replyMarkup?: InlineKeyboardMarkup
}

export interface InlineKeyboardMarkup {
  inlineKeyboard: InlineKeyboardButton[][]
}

export interface InlineKeyboardButton {
  text: string
  callbackData?: string
  url?: string
}

export interface TelegramUser {
  id: number
  firstName: string
  lastName?: string
  username?: string
  languageCode?: string
}

export interface TelegramUpdate {
  updateId: number
  message?: {
    messageId: number
    from: TelegramUser
    chat: { id: number; type: string }
    text?: string
    date: number
  }
  callbackQuery?: {
    id: string
    from: TelegramUser
    message: { messageId: number; chat: { id: number } }
    data: string
  }
}

export class TelegramBot {
  private client: HttpClient
  private readonly token: string
  private webhookUrl: string | null = null

  constructor() {
    const config = getConfig()
    this.token = process.env['TELEGRAM_BOT_TOKEN'] ?? ''
    this.client = new HttpClient({
      baseURL: `https://api.telegram.org/bot${this.token}`,
      timeout: 10000,
      retries: 2,
      retryDelay: 500,
    })
  }

  get isConfigured(): boolean {
    if (isDev) return true
    return this.token.length > 0
  }

  async sendMessage(msg: TelegramMessage): Promise<{ messageId: number } | null> {
    if (!this.token) {
      if (isDev) {
        console.log('[Telegram] Sandbox mode — message not sent:', msg.text.slice(0, 80))
        return { messageId: 0 }
      }
      console.warn('[Telegram] Bot token not configured — message not sent')
      return null
    }
    const body: Record<string, unknown> = {
      chat_id: msg.chatId,
      text: msg.text,
      parse_mode: msg.parseMode ?? 'HTML',
    }
    if (msg.replyMarkup) {
      body['reply_markup'] = msg.replyMarkup
    }
    try {
      const resp = await this.client.post<{ result: { message_id: number } }>('/sendMessage', body)
      return { messageId: resp.data.result.message_id }
    } catch (err) {
      console.error('[Telegram] sendMessage failed:', err)
      return null
    }
  }

  async sendProductCard(chatId: string, product: { name: string; description: string; price: number; imageUrl?: string; sku: string }): Promise<void> {
    const text = `<b>${product.name}</b>\n\n${product.description}\n\n💰 <b>R$ ${product.price.toFixed(2)}</b>\n📦 SKU: ${product.sku}`
    await this.sendMessage({
      chatId,
      text,
      parseMode: 'HTML',
      replyMarkup: {
        inlineKeyboard: [
          [{ text: '🛒 Comprar', callbackData: `buy:${product.sku}` }],
          [{ text: '📋 Mais detalhes', callbackData: `details:${product.sku}` }, { text: '⭐ Favoritar', callbackData: `fav:${product.sku}` }],
        ],
      },
    })
  }

  async sendOrderStatus(chatId: string, orderId: string, status: string, tracking?: string): Promise<void> {
    const statusEmoji: Record<string, string> = {
      confirmed: '✅', shipped: '🚚', delivered: '📦', cancelled: '❌',
    }
    const emoji = statusEmoji[status] ?? '📋'
    let text = `${emoji} Pedido <b>#${orderId}</b>\nStatus: <b>${status}</b>`
    if (tracking) text += `\n📮 Rastreio: <code>${tracking}</code>`
    await this.sendMessage({
      chatId,
      text,
      parseMode: 'HTML',
      replyMarkup: {
        inlineKeyboard: [[{ text: '📊 Ver detalhes', callbackData: `order:${orderId}` }]],
      },
    })
  }

  async sendAlert(chatId: string, title: string, message: string, severity: 'info' | 'warning' | 'critical'): Promise<void> {
    const icons = { info: 'ℹ️', warning: '⚠️', critical: '🚨' }
    await this.sendMessage({
      chatId,
      text: `${icons[severity]} <b>${title}</b>\n\n${message}`,
      parseMode: 'HTML',
    })
  }

  async setWebhook(url: string): Promise<boolean> {
    if (!this.token) return isDev ? (console.log('[Telegram] Sandbox — webhook skipped'), true) : false
    if (!this.isConfigured) return false
    try {
      await this.client.post('/setWebhook', { url })
      this.webhookUrl = url
      console.log('[Telegram] Webhook set to:', url)
      return true
    } catch (err) {
      console.error('[Telegram] setWebhook failed:', err)
      return false
    }
  }

  async deleteWebhook(): Promise<void> {
    if (!this.token) return
    if (!this.isConfigured) return
    try {
      await this.client.post('/deleteWebhook', {})
      this.webhookUrl = null
    } catch { /* ignore */ }
  }

  parseUpdate(body: Record<string, unknown>): TelegramUpdate | null {
    if (!body['update_id']) return null
    return body as unknown as TelegramUpdate
  }
}

export const telegramBot = new TelegramBot()
