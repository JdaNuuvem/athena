import type { MercuriusContext } from 'mercurius'
import { athenaPubSub } from './pubsub'
import { Pool } from 'pg'
import DataLoader from 'dataloader'

const pool = new Pool({ connectionString: 'postgresql://athena:athena@localhost:5433/athena', max: 10 })

async function query(text: string, params?: unknown[]) {
  const result = await pool.query(text, params)
  return result.rows
}

// ponytail: DataLoader per-request for customer batching; upgrade to per-query cache if throughput matters
function createLoaders() {
  return {
    customer: new DataLoader(async (ids: readonly string[]) => {
      const rows = await query(`SELECT * FROM "Customer" WHERE id = ANY($1)`, [[...ids]])
      const map = new Map(rows.map((r: any) => [r.id, r]))
      return ids.map(id => map.get(id) ?? null)
    }),
  }
}

const resolvers = {
  JSON: {
    serialize: (v: unknown) => typeof v === 'string' ? JSON.parse(v) : v,
    parseValue: (v: unknown) => v,
  },

  Query: {
    health: async () => ({
      status: 'ok',
      timestamp: new Date().toISOString(),
      env: process.env['NODE_ENV'] ?? 'development',
      uptime: process.uptime(),
    }),

    orders: async () => query(`SELECT id, channel, "customerId", status, subtotal, "shippingCost", discount, "grandTotal", currency, "shippingAddress", "correlationId", "createdAt", "updatedAt" FROM "Order" ORDER BY "createdAt" DESC`),

    order: async (_: any, args: { id: string }) => {
      const rows = await query(`SELECT * FROM "Order" WHERE id=$1`, [args.id])
      return rows[0] ?? null
    },

    ordersByStatus: async () => query(`SELECT status, count(*)::int as count FROM "Order" GROUP BY status`),

    products: async () => query(`SELECT * FROM "Product" ORDER BY name`),

    product: async (_: any, args: { id: string }) => {
      const rows = await query(`SELECT * FROM "Product" WHERE id=$1`, [args.id])
      return rows[0] ?? null
    },

    productBySku: async (_: any, args: { sku: string }) => {
      const rows = await query(`SELECT * FROM "Product" WHERE sku=$1`, [args.sku])
      return rows[0] ?? null
    },

    catalogEntries: async () => {
      const rows = await query(`SELECT * FROM "ProductCard" ORDER BY name`)
      return rows.map((r: any) => ({
        id: r.id,
        productId: r.productId,
        sku: r.productId,
        title: r.name,
        description: r.description ?? '',
        category: r.categoryId ?? '',
        status: r.status,
        materials: [],
        variants: typeof r.variants === 'string' ? JSON.parse(r.variants) : (r.variants ?? []),
        media: [],
        createdAt: r.createdAt ?? new Date().toISOString(),
        updatedAt: r.updatedAt ?? new Date().toISOString(),
      }))
    },

    catalogEntry: async (_: any, args: { productId: string }) => {
      const rows = await query(`SELECT * FROM "ProductCard" WHERE "productId"=$1`, [args.productId])
      const r = rows[0] as any
      if (!r) return null
      return {
        id: r.id, productId: r.productId, sku: r.productId, title: r.name,
        description: r.description ?? '', category: r.categoryId ?? '', status: r.status,
        materials: [], variants: typeof r.variants === 'string' ? JSON.parse(r.variants) : (r.variants ?? []),
        media: [], createdAt: r.createdAt ?? '', updatedAt: r.updatedAt ?? '',
      }
    },

    stockItems: async () => query(`SELECT id, sku, "warehouseId", quantity, "reorderPoint", 0 as "reserved", (quantity - 0) as "available", 0 as "safetyStock", 0 as "unitCost", NOW() as "updatedAt" FROM "StockItem"`),

    stockItem: async (_: any, args: { sku: string; warehouseId: string }) => {
      const rows = await query(`SELECT * FROM "StockItem" WHERE sku=$1 AND "warehouseId"=$2`, [args.sku, args.warehouseId])
      return rows[0] ?? null
    },

    stockMovements: async () => query(`SELECT * FROM "StockMovement" ORDER BY timestamp DESC LIMIT 50`),

    shopeeProducts: async () => {
      const { getShopeeProducts } = await import('../shared/infrastructure/integrations/shopee-stock-sync')
      const rows = await getShopeeProducts()
      return rows.map((r: any) => ({
        itemId: Number(r.item_id),
        itemSku: r.item_sku,
        itemName: r.item_name,
        itemStatus: r.item_status,
        stock: Number(r.stock),
        reservedStock: Number(r.reserved_stock),
        hasModel: r.has_model,
        price: Number(r.price),
        lastSyncedAt: r.last_synced_at,
      }))
    },

    shopeeProduct: async (_: any, args: { itemId: number }) => {
      const { getShopeeProduct } = await import('../shared/infrastructure/integrations/shopee-stock-sync')
      const r = await getShopeeProduct(args.itemId)
      if (!r) return null
      return {
        itemId: Number(r.item_id),
        itemSku: r.item_sku,
        itemName: r.item_name,
        itemStatus: r.item_status,
        stock: Number(r.stock),
        reservedStock: Number(r.reserved_stock),
        hasModel: r.has_model,
        price: Number(r.price),
        lastSyncedAt: r.last_synced_at,
      }
    },

    customers: async () => query(`SELECT id, name, email, phone, 'manual' as "channelOrigin", tier, 0 as "loyaltyPoints", 0 as "totalOrders", 0::float as "lifetimeValue", "createdAt" as "registeredAt" FROM "Customer"`),

    customer: async (_: any, args: { id: string }) => {
      const rows = await query(`SELECT * FROM "Customer" WHERE id=$1`, [args.id])
      return rows[0] ?? null
    },

    customerSegments: async () => [],

    shipments: async () => query(`SELECT id, "orderId", "carrierId" as carrier, "trackingCode", status, 0::float as "shippingCost", NOW() as "estimatedDeliveryDate", NULL as "deliveredAt", NOW() as "createdAt", NOW() as "updatedAt" FROM "Fulfillment"`),

    shipment: async (_: any, args: { id: string }) => {
      const rows = await query(`SELECT * FROM "Fulfillment" WHERE id=$1`, [args.id])
      return rows[0] ?? null
    },

    trackingEvents: async () => [],

    molds: async () => query(`SELECT id, "moldCode", "productId", cavities as "cavityCount", "steelType", "cycleLife", 0 as "currentCycles", status, NULL as "installedMachineId", "createdAt" FROM "Mold"`),

    mold: async (_: any, args: { id: string }) => {
      const rows = await query(`SELECT * FROM "Mold" WHERE id=$1`, [args.id])
      return rows[0] ?? null
    },

    productionRuns: async () => query(`SELECT * FROM "ProductionRun"`),

    cncJobs: async () => query(`SELECT * FROM "CNCJob"`),

    kpiSummary: async () => {
      const [orders] = await query(`SELECT count(*)::int as c, coalesce(sum("totalAmount"),0)::float as r FROM "Order"`)
      return {
        totalOrders: (orders as any).c ?? 0,
        totalRevenue: (orders as any).r ?? 0,
        totalProduction: 0,
        defectRate: 0,
        oee: 0,
        shippingOnTimeRate: 0,
      }
    },

    anomalies: async () => [],
  },

  Order: {
    items: async (parent: any) => query(`SELECT * FROM "OrderLine" WHERE "orderId"=$1`, [parent.id]),
    totals: (parent: any) => ({
      subtotal: parent.subtotal ?? 0,
      shipping: parent.shippingCost ?? 0,
      discount: parent.discount ?? 0,
      grandTotal: parent.grandTotal ?? 0,
      currency: parent.currency ?? 'BRL',
    }),
    customer: async (parent: any, _args: any, ctx: any) => ctx.loaders.customer.load(parent.customerId),
    fulfillment: async (parent: any) => {
      const rows = await query(`SELECT * FROM "Fulfillment" WHERE "orderId"=$1`, [parent.id])
      return rows[0] ?? null
    },
  },

  Product: {
    materials: () => [],
    dimensions: () => null,
    bom: async (parent: any) => {
      const rows = await query(`SELECT * FROM "BOM" WHERE "productId"=$1`, [parent.id])
      return rows[0] ?? null
    },
    revisions: async (parent: any) => query(`SELECT * FROM "Revision" WHERE "productId"=$1 ORDER BY "createdAt" DESC`, [parent.id]),
  },

  ProductionRun: {
    qualityChecks: async (parent: any) => query(`SELECT * FROM "QualityCheck" WHERE "runId"=$1`, [parent.id]),
  },

  Mutation: {
    syncShopeeStock: async () => {
      const { syncShopeeProducts } = await import('../shared/infrastructure/integrations/shopee-stock-sync')
      const result = await syncShopeeProducts()
      return result
    },
  },

  Subscription: {
    orderUpdated: { subscribe: () => athenaPubSub.subscribe('order.updated') },
    orderPlaced: { subscribe: () => athenaPubSub.subscribe('order.placed') },
    productionProgress: { subscribe: () => athenaPubSub.subscribe('production.progress') },
    inventoryChanged: { subscribe: () => athenaPubSub.subscribe('inventory.changed') },
    moldStatusChanged: { subscribe: () => athenaPubSub.subscribe('mold.changed') },
    kpiSnapshot: { subscribe: () => athenaPubSub.subscribe('kpi.snapshot') },
    anomalyAlert: { subscribe: () => athenaPubSub.subscribe('anomaly.detected') },
    shipmentStatusChanged: { subscribe: () => athenaPubSub.subscribe('shipment.changed') },
  },
}

export { resolvers, createLoaders }
