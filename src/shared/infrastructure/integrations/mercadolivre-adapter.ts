import { HttpClient } from '../http/http-client'
import { getConfig } from '../config/app-config'

const isDev = process.env['NODE_ENV'] === 'development'

export interface MLProduct {
  id?: string
  title: string
  category_id: string
  price: number
  available_quantity: number
  description: string
  pictures: Array<{ source: string }>
  attributes: Array<{ id: string; value_name: string }>
  shipping: { mode: string; free_shipping: boolean }
}

export interface MLOrder {
  id: number
  status: string
  date_created: string
  total_amount: number
  buyer: { id: number; nickname: string }
  order_items: Array<{ item: { id: string; title: string }; quantity: number; unit_price: number }>
}

export interface MLQuestion {
  id: number
  item_id: string
  text: string
  status: string
  from: { id: number; nickname: string }
  date_created: string
}

export class MercadoLivreAdapter {
  private client: HttpClient
  private accessToken: string
  private refreshToken: string
  private readonly clientId: string
  private readonly clientSecret: string
  private readonly userId: string

  constructor() {
    const config = getConfig()
    this.accessToken = process.env['ML_ACCESS_TOKEN'] ?? ''
    this.refreshToken = process.env['ML_REFRESH_TOKEN'] ?? ''
    this.clientId = process.env['ML_CLIENT_ID'] ?? ''
    this.clientSecret = process.env['ML_CLIENT_SECRET'] ?? ''
    this.userId = process.env['ML_USER_ID'] ?? ''

    this.client = new HttpClient({
      baseURL: 'https://api.mercadolibre.com',
      timeout: 15000,
      retries: 3,
      retryDelay: 1000,
      headers: this.accessToken ? { Authorization: `Bearer ${this.accessToken}` } : {},
    })
  }

  get isConfigured(): boolean {
    if (isDev) return true
    return this.accessToken.length > 0
  }

  private get sandbox(): boolean {
    return isDev && !this.accessToken
  }

  async refreshAccessToken(): Promise<boolean> {
    if (this.sandbox) return true
    try {
      const resp = await this.client.post<{ access_token: string; refresh_token: string }>('/oauth/token', {
        grant_type: 'refresh_token',
        client_id: this.clientId,
        client_secret: this.clientSecret,
        refresh_token: this.refreshToken,
      })
      this.accessToken = resp.data.access_token
      this.refreshToken = resp.data.refresh_token
      return true
    } catch {
      return false
    }
  }

  async publishProduct(product: MLProduct): Promise<{ id: string; permalink: string } | null> {
    if (!this.isConfigured) return null
    if (this.sandbox) return { id: 'sandbox', permalink: 'https://sandbox.mercadolivre.com.br', sandbox: true } as unknown as { id: string; permalink: string }
    try {
      const resp = await this.client.post<{ id: string; permalink: string }>('/items', product)
      return resp.data
    } catch {
      return null
    }
  }

  async updateProduct(mlId: string, updates: Partial<MLProduct>): Promise<boolean> {
    if (!this.isConfigured) return false
    if (this.sandbox) return true
    try {
      await this.client.put(`/items/${mlId}`, updates)
      return true
    } catch {
      return false
    }
  }

  async updateStock(mlId: string, quantity: number): Promise<boolean> {
    return this.updateProduct(mlId, { available_quantity: quantity } as Partial<MLProduct>)
  }

  async updatePrice(mlId: string, price: number): Promise<boolean> {
    return this.updateProduct(mlId, { price } as Partial<MLProduct>)
  }

  async getOrders(options: { seller?: string; status?: string; limit?: number; offset?: number } = {}): Promise<MLOrder[]> {
    if (!this.isConfigured) return []
    if (this.sandbox) return [{ id: 0, status: 'sandbox', date_created: new Date().toISOString(), total_amount: 0, buyer: { id: 0, nickname: 'sandbox' }, order_items: [], sandbox: true } as unknown as MLOrder]
    const seller = options.seller ?? this.userId
    const params = new URLSearchParams({ seller, 'order.status': options.status ?? 'paid', limit: String(options.limit ?? 50), offset: String(options.offset ?? 0) })
    try {
      const resp = await this.client.get<{ results: MLOrder[] }>(`/orders/search?${params}`)
      return resp.data.results
    } catch {
      return []
    }
  }

  async answerQuestion(questionId: number, text: string): Promise<boolean> {
    if (!this.isConfigured) return false
    if (this.sandbox) return true
    try {
      await this.client.post('/answers', { question_id: questionId, text })
      return true
    } catch {
      return false
    }
  }

  async getReputation(): Promise<Record<string, unknown> | null> {
    if (!this.isConfigured || !this.userId) return null
    if (this.sandbox) return { sandbox: true, reputation: 'excellent' }
    try {
      const resp = await this.client.get<Record<string, unknown>>(`/users/${this.userId}/reputation`)
      return resp.data
    } catch {
      return null
    }
  }
}

export const mercadoLivreAdapter = new MercadoLivreAdapter()
