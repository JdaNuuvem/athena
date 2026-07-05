import { HttpClient } from '../http/http-client'

const isDev = process.env['NODE_ENV'] === 'development'

export interface WhatsAppMessage {
  phone: string
  text: string
  delay?: number
}

export interface WhatsAppButtonMessage {
  phone: string
  text: string
  buttons: Array<{ text: string; id: string }>
  title?: string
  footer?: string
}

export interface WhatsAppProductCard {
  phone: string
  name: string
  description: string
  price: number
  sku: string
  imageUrl?: string
}

export interface WhatsAppWebhookPayload {
  event: string
  instance: string
  data: {
    id: string
    remoteJid: string
    pushName: string
    messageType: string
    text?: { message: string }
    message?: { conversation?: string; extendedTextMessage?: { text: string } }
    buttonResponse?: { selectedButtonId: string; selectedDisplayText: string }
    source?: string
    fromMe?: boolean
  }
  destination?: string
  date_time?: string
  sender?: string
  server_url?: string
  apikey?: string
}

export class WhatsAppAdapter {
  private client: HttpClient
  private readonly apiKey: string
  private readonly baseUrl: string
  private readonly instanceName: string

  constructor() {
    this.apiKey = process.env['EVOLUTION_API_KEY'] ?? 'athena-evolution-key'
    this.baseUrl = process.env['EVOLUTION_API_URL'] ?? 'http://localhost:8080'
    this.instanceName = 'athena'
    this.client = new HttpClient({
      baseURL: this.baseUrl,
      timeout: 15000,
      retries: 2,
      retryDelay: 1000,
      headers: { 'apikey': this.apiKey, 'Content-Type': 'application/json' },
    })
  }

  get isConfigured(): boolean {
    if (isDev) return true
    return this.apiKey.length > 0
  }

  async createInstance(): Promise<{ qrCode?: string; pairingCode?: string }> {
    try {
      const resp = await this.client.post<{ instance: { instanceName: string; status: string; qrcode?: { base64: string }; pairingCode?: string } }>(
        '/instance/create',
        { instanceName: this.instanceName, token: this.apiKey, qrcode: true, integration: 'WHATSAPP-BAILEYS' },
      )
      return {
        qrCode: resp.data.instance?.qrcode?.base64,
        pairingCode: resp.data.instance?.pairingCode,
      }
    } catch (err) {
      if (isDev) console.log('[WhatsApp] Instance creation skipped in dev (instance may already exist)')
      return {}
    }
  }

  async connectInstance(phoneNumber?: string): Promise<{ qrCode?: string }> {
    try {
      const resp = await this.client.post<{ base64?: string; pairingCode?: string }>(
        `/instance/connect/${this.instanceName}`,
        phoneNumber ? { phoneNumber } : {},
      )
      return { qrCode: resp.data?.base64 }
    } catch (err) {
      console.error('[WhatsApp] connectInstance failed:', err)
      return {}
    }
  }

  async instanceStatus(): Promise<string> {
    try {
      const resp = await this.client.get<{ instance: { state: string } }>(`/instance/connectionState/${this.instanceName}`)
      return resp.data.instance?.state ?? 'disconnected'
    } catch {
      return 'disconnected'
    }
  }

  async sendText(phone: string, text: string): Promise<boolean> {
    if (!this.isConfigured && !isDev) return false
    try {
      await this.client.post(`/message/sendText/${this.instanceName}`, {
        number: phone.replace(/\D/g, ''),
        text,
        delay: 500,
      })
      return true
    } catch (err) {
      if (isDev) console.log(`[WhatsApp] Sandbox — texto não enviado para ${phone}:`, text.slice(0, 80))
      return false
    }
  }

  async sendButtons(msg: WhatsAppButtonMessage): Promise<boolean> {
    if (!this.isConfigured && !isDev) return false
    try {
      await this.client.post(`/message/sendButtons/${this.instanceName}`, {
        number: msg.phone.replace(/\D/g, ''),
        title: msg.title ?? '',
        description: msg.text,
        footer: msg.footer ?? '',
        buttons: msg.buttons.map(b => ({ buttonText: b.text, buttonId: b.id })),
      })
      return true
    } catch (err) {
      if (isDev) console.log(`[WhatsApp] Sandbox — botões não enviados para ${msg.phone}`)
      return false
    }
  }

  async sendProductCard(phone: string, product: WhatsAppProductCard): Promise<boolean> {
    const text = `*${product.name}*\n\n${product.description}\n\n💰 *R$ ${product.price.toFixed(2)}*\n📦 SKU: ${product.sku}`
    const buttons = [
      { text: '🛒 Comprar', id: `buy:${product.sku}` },
      { text: '📋 Detalhes', id: `details:${product.sku}` },
    ]
    return this.sendButtons({
      phone,
      text,
      title: product.name,
      footer: `SKU: ${product.sku}`,
      buttons,
    })
  }

  async sendOrderStatus(phone: string, orderId: string, status: string, tracking?: string): Promise<boolean> {
    const statusEmoji: Record<string, string> = {
      confirmed: '✅', in_production: '🏭', shipped: '🚚', delivered: '📦', cancelled: '❌',
    }
    const emoji = statusEmoji[status] ?? '📋'
    let text = `${emoji} *Pedido #${orderId.slice(0, 8)}*\nStatus: *${status}*`
    if (tracking) text += `\n📮 Rastreio: \`${tracking}\``
    return this.sendText(phone, text)
  }

  async sendPromotion(phone: string, title: string, body: string, couponCode?: string): Promise<boolean> {
    let text = `🎯 *${title}*\n\n${body}`
    if (couponCode) text += `\n\n🎫 Cupom: *${couponCode}*`
    return this.sendText(phone, text)
  }

  async sendAbandonedCart(phone: string, customerName: string, productName: string, total: number): Promise<boolean> {
    const text = `👋 Olá *${customerName}*!\n\nPercebemos que você deixou *${productName}* no carrinho.\n\n💰 Valor: *R$ ${total.toFixed(2)}*\n\nAinda tem interesse? Responda *SIM* e eu finalizo seu pedido agora mesmo!`
    return this.sendText(phone, text)
  }

  parseWebhook(body: Record<string, unknown>): WhatsAppWebhookPayload | null {
    if (!body['data']) return null
    return body as unknown as WhatsAppWebhookPayload
  }

  async sendCatalog(phone: string, products: Array<{ name: string; price: number; sku: string; description: string }>): Promise<boolean> {
    if (!this.isConfigured && !isDev) return false
    const text = products.map((p, i) =>
      `${i + 1}️⃣ *${p.name}*\n   💰 R$ ${p.price.toFixed(2)}\n   📦 ${p.sku}\n   ${p.description.slice(0, 100)}`
    ).join('\n\n')
    return this.sendText(phone, `📋 *Nosso Catálogo*\n\n${text}\n\nResponda com o número do produto para mais detalhes!`)
  }
}

export const whatsappAdapter = new WhatsAppAdapter()
