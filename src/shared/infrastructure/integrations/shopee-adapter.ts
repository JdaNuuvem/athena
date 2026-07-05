import { HttpClient } from '../http/http-client'

const isDev = process.env['NODE_ENV'] === 'development'

export interface ShopeeProduct {
  item_id?: number
  item_name: string
  description: string
  price: number
  stock: number
  category_id: number
  weight: number
  images: Array<{ url: string }>
}

export interface ShopeeOrder {
  order_sn: string
  order_status: string
  create_time: number
  total_amount: number
  buyer_username: string
  items: Array<{ item_id: number; item_name: string; quantity: number; model_price: number }>
}

export class ShopeeAdapter {
  private client: HttpClient
  private readonly partnerId: string
  private readonly partnerKey: string
  private readonly shopId: string
  private accessToken: string

  constructor() {
    this.partnerId = process.env['SHOPEE_PARTNER_ID'] ?? ''
    this.partnerKey = process.env['SHOPEE_PARTNER_KEY'] ?? ''
    this.shopId = process.env['SHOPEE_SHOP_ID'] ?? ''
    this.accessToken = process.env['SHOPEE_ACCESS_TOKEN'] ?? ''

    this.client = new HttpClient({
      baseURL: 'https://partner.shopeemobile.com/api/v2',
      timeout: 15000,
      retries: 2,
      retryDelay: 500,
    })
  }

  get isConfigured(): boolean {
    if (isDev) return true
    return this.partnerId.length > 0 && this.accessToken.length > 0
  }

  private signParams(path: string, params: Record<string, unknown>): Record<string, unknown> {
    const timestamp = Math.floor(Date.now() / 1000)
    const baseParams = {
      partner_id: Number(this.partnerId),
      timestamp,
      access_token: this.accessToken,
      shop_id: Number(this.shopId),
      sign: '',
    }
    return { ...baseParams, ...params }
  }

  async publishProduct(product: ShopeeProduct): Promise<{ item_id: number } | null> {
    if (!this.isConfigured) return null
    if (isDev && !this.partnerId) return { item_id: 0, sandbox: true } as unknown as { item_id: number }
    const params = this.signParams('/product/add_item', {
      original_item_name: product.item_name,
      description: product.description,
      price: product.price,
      stock: product.stock,
      category_id: product.category_id,
      weight: product.weight,
      image: { image_id_list: product.images.map((_, i) => `img_${i}`) },
    })
    try {
      const resp = await this.client.post<{ response: { item_id: number } }>('/product/add_item', params)
      return resp.data.response
    } catch {
      return null
    }
  }

  async updateStock(itemId: number, stock: number): Promise<boolean> {
    if (!this.isConfigured) return false
    if (isDev && !this.partnerId) return true
    try {
      const params = this.signParams('/product/update_stock', { item_id: itemId, stock })
      await this.client.post('/product/update_stock', params)
      return true
    } catch {
      return false
    }
  }

  async updatePrice(itemId: number, price: number): Promise<boolean> {
    if (!this.isConfigured) return false
    if (isDev && !this.partnerId) return true
    try {
      const params = this.signParams('/product/update_price', { item_id: itemId, price })
      await this.client.post('/product/update_price', params)
      return true
    } catch {
      return false
    }
  }

  async getOrders(status: string = 'READY_TO_SHIP', limit: number = 50): Promise<ShopeeOrder[]> {
    if (!this.isConfigured) return []
    if (isDev && !this.partnerId) return [{ order_sn: 'sandbox', order_status: status, create_time: 0, total_amount: 0, buyer_username: 'sandbox', items: [], sandbox: true } as unknown as ShopeeOrder]
    try {
      const params = this.signParams('/order/get_order_list', { order_status: status, page_size: limit })
      const resp = await this.client.post<{ response: { order_list: ShopeeOrder[] } }>('/order/get_order_list', params)
      return resp.data.response?.order_list ?? []
    } catch {
      return []
    }
  }

  async getOrderDetail(orderSn: string): Promise<ShopeeOrder | null> {
    if (!this.isConfigured) return null
    if (isDev && !this.partnerId) return { order_sn: orderSn, order_status: 'sandbox', create_time: 0, total_amount: 0, buyer_username: 'sandbox', items: [], sandbox: true } as unknown as ShopeeOrder
    try {
      const params = this.signParams('/order/get_order_detail', { order_sn_list: [orderSn] })
      const resp = await this.client.post<{ response: { order_list: ShopeeOrder[] } }>('/order/get_order_detail', params)
      return resp.data.response?.order_list?.[0] ?? null
    } catch {
      return null
    }
  }
}

export const shopeeAdapter = new ShopeeAdapter()
