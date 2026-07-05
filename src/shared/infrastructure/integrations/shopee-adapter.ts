import { createHmac } from 'crypto'
import { HttpClient } from '../http/http-client'

const isDev = process.env['NODE_ENV'] === 'development'
const SHOPEE_SANDBOX = process.env['SHOPEE_SANDBOX'] === 'true'

const BASE_URL_LIVE = 'https://partner.shopeemobile.com/api/v2'
const BASE_URL_BRAZIL = 'https://openplatform.shopee.com.br/api/v2'
const BASE_URL_SANDBOX = 'https://openplatform.sandbox.test-stable.shopee.sg/api/v2'

export interface ShopeeItem {
  item_id: number
  item_status: string
  update_time: number
}

export interface ShopeeStockInfo {
  summary_info?: { total_reserved_stock: number; total_available_stock: number }
  total_reserved_stock?: number
  total_available_stock?: number
  seller_stock: Array<{ location_id?: string; stock: number; if_saleable?: boolean }>
  shopee_stock?: Array<{ location_id?: string; stock: number }>
}

export interface ShopeeModel {
  model_id: number
  model_sku: string
  model_status: string
  stock_info_v2: ShopeeStockInfo
  price_info?: Array<{ currency: string; current_price: number; original_price: number }>
}

export interface ShopeeItemDetail {
  item_id: number
  item_name: string
  item_sku: string
  item_status: string
  stock_info_v2: ShopeeStockInfo
  has_model: boolean
  price_info?: Array<{ currency: string; current_price: number; original_price: number }>
}

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
  shipping_carrier?: string
  tracking_no?: string
  currency?: string
  recipient_address?: {
    name: string
    phone: string
    full_address: string
  }
  estimated_shipping_fee?: number
  items: Array<{
    item_id: number
    item_name: string
    item_sku?: string
    quantity: number
    model_id?: number
    model_quantity_purchased?: number
    model_original_price?: number
    model_promotion_price?: number
    is_wholesale?: boolean
    weight?: number
  }>
}

export interface ShopeeUpdateStockRequest {
  item_id: number
  stock_list: Array<{
    model_id?: number
    seller_stock: Array<{ location_id?: string; stock: number }>
  }>
}

export class ShopeeAdapter {
  private client: HttpClient
  private readonly partnerId: string
  private readonly partnerKey: string
  private readonly shopId: string
  private accessToken: string
  private baseUrl: string

  constructor() {
    this.partnerId = process.env['SHOPEE_PARTNER_ID'] ?? ''
    this.partnerKey = process.env['SHOPEE_PARTNER_KEY'] ?? ''
    this.shopId = process.env['SHOPEE_SHOP_ID'] ?? ''
    this.accessToken = process.env['SHOPEE_ACCESS_TOKEN'] ?? ''

    if (SHOPEE_SANDBOX) {
      this.baseUrl = BASE_URL_SANDBOX
    } else {
      this.baseUrl = process.env['SHOPEE_REGION'] === 'br' ? BASE_URL_BRAZIL : BASE_URL_LIVE
    }

    this.client = new HttpClient({
      baseURL: this.baseUrl,
      timeout: 15000,
      retries: 2,
      retryDelay: 500,
    })
  }

  get isConfigured(): boolean {
    if (isDev && !this.partnerId) return true // sandbox dev mode
    return this.partnerId.length > 0 && this.partnerKey.length > 0 && this.accessToken.length > 0
  }

  // ponytail: HMAC-SHA256 per the Shopee signature spec
  // sign = HMAC-SHA256(partner_id + api_path + timestamp + access_token + shop_id + partner_key)
  private sign(path: string): { partner_id: number; timestamp: number; access_token: string; shop_id: number; sign: string } {
    const base = {
      partner_id: Number(this.partnerId),
      timestamp: Math.floor(Date.now() / 1000),
      access_token: this.accessToken,
      shop_id: Number(this.shopId),
    }
    const signStr = `${base.partner_id}${path}${base.timestamp}${base.access_token}${base.shop_id}${this.partnerKey}`
    const sign = createHmac('sha256', this.partnerKey).update(signStr).digest('hex')
    return { ...base, sign }
  }

  private queryString(path: string): string {
    const p = this.sign(path)
    return `?partner_id=${p.partner_id}&timestamp=${p.timestamp}&access_token=${p.access_token}&shop_id=${p.shop_id}&sign=${p.sign}`
  }

  async getItems(status: string = 'NORMAL', offset: number = 0, pageSize: number = 100): Promise<{ items: ShopeeItem[]; total: number; hasMore: boolean; nextOffset: number }> {
    if (!this.isConfigured) return { items: [], total: 0, hasMore: false, nextOffset: 0 }
    if (isDev && !this.partnerId) return { items: [], total: 0, hasMore: false, nextOffset: 0 }
    try {
      const resp = await this.client.get<{ response: { item: ShopeeItem[]; total_count: number; has_next_page: boolean; next_offset: number } }>(
        `/product/get_item_list${this.queryString('/api/v2/product/get_item_list')}&item_status=${encodeURIComponent(JSON.stringify([status]))}&offset=${offset}&page_size=${pageSize}`,
      )
      const r = resp.data.response
      return { items: r.item ?? [], total: r.total_count ?? 0, hasMore: r.has_next_page ?? false, nextOffset: r.next_offset ?? 0 }
    } catch (err) {
      console.error('[Shopee] getItems failed:', err)
      return { items: [], total: 0, hasMore: false, nextOffset: 0 }
    }
  }

  async getItemBaseInfo(itemIds: number[]): Promise<ShopeeItemDetail[]> {
    if (!this.isConfigured || itemIds.length === 0) return []
    if (isDev && !this.partnerId) return []
    try {
      const resp = await this.client.get<{ response: { item_list: ShopeeItemDetail[] } }>(
        `/product/get_item_base_info${this.queryString('/api/v2/product/get_item_base_info')}&item_id_list=${encodeURIComponent(JSON.stringify(itemIds))}`,
      )
      return resp.data.response?.item_list ?? []
    } catch (err) {
      console.error('[Shopee] getItemBaseInfo failed:', err)
      return []
    }
  }

  async getModelList(itemId: number): Promise<ShopeeModel[]> {
    if (!this.isConfigured) return []
    if (isDev && !this.partnerId) return []
    try {
      const resp = await this.client.get<{ response: { model: ShopeeModel[] } }>(
        `/product/get_model_list${this.queryString('/api/v2/product/get_model_list')}&item_id=${itemId}`,
      )
      return resp.data.response?.model ?? []
    } catch (err) {
      console.error('[Shopee] getModelList failed:', err)
      return []
    }
  }

  async updateStock(req: ShopeeUpdateStockRequest): Promise<{ success: boolean; failureList?: Array<{ model_id?: number; failed_reason: string }> }> {
    if (!this.isConfigured) return { success: false }
    if (isDev && !this.partnerId) return { success: true }
    try {
      const resp = await this.client.post<{ response: { failure_list?: Array<{ model_id?: number; failed_reason: string }>; success_list?: Array<{ model_id?: number }> } }>(
        `/product/update_stock${this.queryString('/api/v2/product/update_stock')}`,
        req,
      )
      const r = resp.data.response
      const hasErrors = r?.failure_list && r.failure_list.length > 0
      return { success: !hasErrors, failureList: r?.failure_list }
    } catch (err) {
      console.error('[Shopee] updateStock failed:', err)
      return { success: false }
    }
  }

  async batchUpdateStock(items: Array<{ outlet_shop_id: number; item_id: number; stock_list: ShopeeUpdateStockRequest['stock_list'] }>): Promise<{ taskId?: number; success: boolean }> {
    if (!this.isConfigured) return { success: false }
    if (isDev && !this.partnerId) return { success: true, taskId: 0 }
    try {
      const resp = await this.client.post<{ response: { task_id: number } }>(
        `/product/batch_update_outlet_stock${this.queryString('/api/v2/product/batch_update_outlet_stock')}`,
        { item_list: items },
      )
      return { taskId: resp.data.response?.task_id, success: true }
    } catch (err) {
      console.error('[Shopee] batchUpdateStock failed:', err)
      return { success: false }
    }
  }

  async updatePrice(itemId: number, price: number): Promise<boolean> {
    if (!this.isConfigured) return false
    if (isDev && !this.partnerId) return true
    try {
      await this.client.post(`/product/update_price${this.queryString('/api/v2/product/update_price')}`, { item_id: itemId, price })
      return true
    } catch {
      return false
    }
  }

  async getOrders(status: string = 'READY_TO_SHIP', limit: number = 50): Promise<ShopeeOrder[]> {
    if (!this.isConfigured) return []
    if (isDev && !this.partnerId) return [{ order_sn: 'sandbox', order_status: status, create_time: 0, total_amount: 0, buyer_username: 'sandbox', items: [] } as unknown as ShopeeOrder]
    try {
      const resp = await this.client.post<{ response: { order_list: ShopeeOrder[] } }>(
        `/order/get_order_list${this.queryString('/api/v2/order/get_order_list')}`, { order_status: status, page_size: limit })
      return resp.data.response?.order_list ?? []
    } catch {
      return []
    }
  }

  async getOrdersByTimeRange(startTime: number, endTime: number, statuses: string[] = ['READY_TO_SHIP', 'PROCESSED'], limit: number = 50): Promise<ShopeeOrder[]> {
    if (!this.isConfigured) return []
    if (isDev && !this.partnerId) return []
    try {
      const resp = await this.client.post<{ response: { order_list: ShopeeOrder[] } }>(
        `/order/get_order_list${this.queryString('/api/v2/order/get_order_list')}`,
        { order_status: statuses.join(','), create_time_from: startTime, create_time_to: endTime, page_size: limit }
      )
      return resp.data.response?.order_list ?? []
    } catch {
      return []
    }
  }

  async getOrderDetail(orderSn: string): Promise<ShopeeOrder | null> {
    if (!this.isConfigured) return null
    if (isDev && !this.partnerId) return { order_sn: orderSn, order_status: 'sandbox', create_time: 0, total_amount: 0, buyer_username: 'sandbox', items: [] } as unknown as ShopeeOrder
    try {
      const resp = await this.client.post<{ response: { order_list: ShopeeOrder[] } }>(
        `/order/get_order_detail${this.queryString('/api/v2/order/get_order_detail')}`, { order_sn_list: [orderSn] })
      return resp.data.response?.order_list?.[0] ?? null
    } catch {
      return null
    }
  }

  async publishProduct(product: ShopeeProduct): Promise<{ item_id: number } | null> {
    if (!this.isConfigured) return null
    if (isDev && !this.partnerId) return { item_id: 0 } as { item_id: number }
    try {
      const resp = await this.client.post<{ response: { item_id: number } }>(
        `/product/add_item${this.queryString('/api/v2/product/add_item')}`,
        { original_item_name: product.item_name, description: product.description, price: product.price, stock: product.stock, category_id: product.category_id, weight: product.weight, image: { image_id_list: product.images.map((_, i) => `img_${i}`) } },
      )
      return resp.data.response
    } catch {
      return null
    }
  }

  // Sync: fetch all items with stock from Shopee
  async syncAllItems(): Promise<Array<{ item_id: number; sku: string; name: string; status: string; stock: number; reserved: number; hasModel: boolean }>> {
    if (!this.isConfigured) return []
    const all: Array<{ item_id: number; sku: string; name: string; status: string; stock: number; reserved: number; hasModel: boolean }> = []
    let offset = 0
    let hasMore = true
    while (hasMore) {
      const page = await this.getItems('NORMAL', offset)
      if (page.items.length === 0) break
      const details = await this.getItemBaseInfo(page.items.map(i => i.item_id))
      for (const d of details) {
        all.push({
          item_id: d.item_id,
          sku: d.item_sku ?? String(d.item_id),
          name: d.item_name,
          status: d.item_status,
          stock: d.stock_info_v2?.summary_info?.total_available_stock ?? d.stock_info_v2?.total_available_stock ?? d.stock_info_v2?.seller_stock?.[0]?.stock ?? 0,
          reserved: d.stock_info_v2?.summary_info?.total_reserved_stock ?? d.stock_info_v2?.total_reserved_stock ?? 0,
          hasModel: d.has_model,
        })
      }
      hasMore = page.hasMore
      offset = page.nextOffset
    }
    return all
  }
}

export const shopeeAdapter = new ShopeeAdapter()
