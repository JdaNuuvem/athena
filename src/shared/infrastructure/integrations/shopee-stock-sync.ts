import { Pool } from 'pg'
import { shopeeAdapter } from './shopee-adapter'

export const pool = new Pool({ connectionString: process.env['DATABASE_URL'] ?? 'postgresql://athena:athena@localhost:5433/athena', max: 5 })

async function query(text: string, params?: unknown[]) {
  const result = await pool.query(text, params)
  return result.rows
}

const INIT_SQL = `
  CREATE TABLE IF NOT EXISTS "ShopeeProduct" (
    "item_id" BIGINT PRIMARY KEY,
    "item_sku" TEXT NOT NULL DEFAULT '',
    "item_name" TEXT NOT NULL DEFAULT '',
    "item_status" TEXT NOT NULL DEFAULT 'NORMAL',
    "stock" INTEGER NOT NULL DEFAULT 0,
    "reserved_stock" INTEGER NOT NULL DEFAULT 0,
    "has_model" BOOLEAN NOT NULL DEFAULT false,
    "price" DECIMAL(10,2) NOT NULL DEFAULT 0,
    "last_synced_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    "created_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    "updated_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
  );
  CREATE INDEX IF NOT EXISTS "idx_shopee_product_sku" ON "ShopeeProduct"("item_sku");
  CREATE INDEX IF NOT EXISTS "idx_shopee_product_status" ON "ShopeeProduct"("item_status");
`

export async function initShopeeTable(): Promise<void> {
  try {
    await query(INIT_SQL)
  } catch (err) {
    console.warn('[ShopeeSync] init failed:', err)
  }
}

export async function syncShopeeProducts(): Promise<{ count: number; errors: string[] }> {
  const errors: string[] = []
  try {
    const items = await shopeeAdapter.syncAllItems()
    for (const item of items) {
      try {
        await query(`
          INSERT INTO "ShopeeProduct" ("item_id", "item_sku", "item_name", "item_status", "stock", "reserved_stock", "has_model", "price", "last_synced_at")
          VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
          ON CONFLICT ("item_id") DO UPDATE SET
            "item_sku" = EXCLUDED."item_sku",
            "item_name" = EXCLUDED."item_name",
            "item_status" = EXCLUDED."item_status",
            "stock" = EXCLUDED."stock",
            "reserved_stock" = EXCLUDED."reserved_stock",
            "has_model" = EXCLUDED."has_model",
            "price" = EXCLUDED."price",
            "last_synced_at" = NOW(),
            "updated_at" = NOW()
        `, [item.item_id, item.sku, item.name, item.status, item.stock, item.reserved, item.hasModel, item.price])
      } catch (err) {
        errors.push(`Item ${item.item_id}: ${err}`)
      }
    }
    return { count: items.length, errors }
  } catch (err) {
    return { count: 0, errors: [String(err)] }
  }
}

export async function getShopeeProducts(): Promise<any[]> {
  return query(`SELECT * FROM "ShopeeProduct" ORDER BY "item_name" ASC`)
}

export async function getShopeeProduct(itemId: number): Promise<any | null> {
  const rows = await query(`SELECT * FROM "ShopeeProduct" WHERE "item_id"=$1`, [itemId])
  return rows[0] ?? null
}

export async function closePool(): Promise<void> {
  await pool.end()
}

export async function updateShopeeStockOnOrder(items: Array<{ sku: string; quantity: number }>): Promise<void> {
  const pg = await pool.connect()
  try {
    for (const item of items) {
      await pg.query('BEGIN')
      // ponytail: row lock prevents concurrent overselling on ShopeeProduct cache
      const { rows } = await pg.query(`SELECT stock FROM "ShopeeProduct" WHERE "item_sku"=$1 FOR UPDATE`, [item.sku])
      if (rows.length > 0) {
        await pg.query(`UPDATE "ShopeeProduct" SET "stock" = GREATEST("stock" - $1, 0), "updated_at" = NOW() WHERE "item_sku"=$2`, [item.quantity, item.sku])
      }
      await pg.query('COMMIT')
    }
  } catch {
    // ponytail: best-effort cache update
  } finally {
    pg.release()
  }
}

export async function decrementAndPushStock(
  orderId: string,
  items: Array<{ sku: string; quantity: number }>
): Promise<{ success: boolean; errors: Array<{ sku: string; reason: string; available?: number; requested?: number }> }> {
  const errors: Array<{ sku: string; reason: string; available?: number; requested?: number }> = []

  for (const item of items) {
    const rows = await query(`SELECT "item_id", "stock" FROM "ShopeeProduct" WHERE "item_sku"=$1`, [item.sku])
    if (rows.length === 0) {
      errors.push({ sku: item.sku, reason: 'SKU not found in Shopee catalog' })
      continue
    }

    const itemId = Number(rows[0].item_id)
    const localStock = Number(rows[0].stock)

    if (localStock < item.quantity) {
      errors.push({ sku: item.sku, reason: 'insufficient_local_stock', available: localStock, requested: item.quantity })
      continue
    }

    const shopee = await shopeeAdapter.checkStock(itemId)
    if (shopee.available < item.quantity) {
      errors.push({ sku: item.sku, reason: 'insufficient_shopee_stock', available: shopee.available, requested: item.quantity })
      continue
    }
  }

  if (errors.length > 0) {
    return { success: false, errors }
  }

  await updateShopeeStockOnOrder(items)

  // ponytail: transaction to prevent partial decrement on error
  const client = await pool.connect()
  try {
    await client.query('BEGIN')
    for (const item of items) {
      const { rows: stockRows } = await client.query(`SELECT quantity FROM "StockItem" WHERE sku=$1 FOR UPDATE`, [item.sku])
      if (Number(stockRows[0]?.quantity ?? 0) < item.quantity) {
        await client.query('ROLLBACK')
        return { success: false, errors: [{ sku: item.sku, reason: 'concurrent_stock_exhausted', available: Number(stockRows[0]?.quantity ?? 0), requested: item.quantity }] }
      }
      await client.query(`UPDATE "StockItem" SET quantity = GREATEST(quantity - $1, 0) WHERE sku=$2`, [item.quantity, item.sku])
      await client.query(`INSERT INTO "StockMovement" (id, type, sku, "warehouseId", quantity, reference, timestamp) VALUES (gen_random_uuid()::text, 'out', $1, 'shopee', $2, $3, NOW())`, [item.sku, item.quantity, `order:${orderId}`])

      const rows = await query(`SELECT "item_id" FROM "ShopeeProduct" WHERE "item_sku"=$1`, [item.sku])
      const itemId = Number(rows[0]?.item_id)
      if (itemId) {
        const sp = rows[0]
        const newQty = Math.max(0, Number(sp.stock) - item.quantity)
        shopeeAdapter.updateStock({ item_id: itemId, stock_list: [{ seller_stock: [{ stock: newQty }] }] }).catch(() => {})
      }
    }
    await client.query('COMMIT')
  } catch (err) {
    await client.query('ROLLBACK')
    throw err
  } finally {
    client.release()
  }

  return { success: true, errors: [] }
}

// ponytail: simple interval, not a full scheduler daemon
let syncInterval: ReturnType<typeof setInterval> | null = null

export function startShopeeSync(intervalMs: number = 300000): void {
  if (syncInterval) return
  if (!shopeeAdapter.isConfigured) {
    console.log('[ShopeeSync] not configured, skipping auto-sync')
    return
  }
  syncInterval = setInterval(async () => {
    const result = await syncShopeeProducts()
    if (result.errors.length > 0) {
      console.warn(`[ShopeeSync] synced ${result.count} items with ${result.errors.length} errors`)
    }
  }, intervalMs)
  console.log(`[ShopeeSync] sync every ${intervalMs / 1000}s`)
  syncShopeeProducts().then(r => console.log(`[ShopeeSync] initial sync: ${r.count} items`))
}

export function stopShopeeSync(): void {
  if (syncInterval) {
    clearInterval(syncInterval)
    syncInterval = null
  }
}

// ─── ShopeeOrder sync ─────────────────────────────────────────

const INIT_ORDERS_SQL = `
  CREATE TABLE IF NOT EXISTS "ShopeeOrder" (
    "order_sn" TEXT PRIMARY KEY,
    "order_status" TEXT NOT NULL,
    "buyer" TEXT NOT NULL DEFAULT '',
    "total_amount" DECIMAL(10,2) NOT NULL DEFAULT 0,
    "currency" TEXT NOT NULL DEFAULT 'BRL',
    "shipping_carrier" TEXT NOT NULL DEFAULT '',
    "tracking_no" TEXT NOT NULL DEFAULT '',
    "items" JSONB NOT NULL DEFAULT '[]',
    "recipient" JSONB,
    "ordered_at" TIMESTAMP WITH TIME ZONE,
    "imported_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    "synced_to_athena" BOOLEAN NOT NULL DEFAULT false
  );
  CREATE INDEX IF NOT EXISTS "idx_shopee_order_status" ON "ShopeeOrder"("order_status");
`

export async function initShopeeOrdersTable(): Promise<void> {
  try {
    await query(INIT_ORDERS_SQL)
  } catch (err) {
    console.warn('[ShopeeOrders] init failed:', err)
  }
}

export async function syncShopeeOrders(): Promise<{ imported: number; errors: string[] }> {
  const errors: string[] = []
  let imported = 0
  try {
    const statuses = ['READY_TO_SHIP', 'PROCESSED', 'SHIPPED', 'COMPLETED']
    for (const status of statuses) {
      const orders = await shopeeAdapter.getOrders(status, 50)
      for (const o of orders) {
        try {
          const existing = await query(`SELECT "order_sn" FROM "ShopeeOrder" WHERE "order_sn"=$1`, [o.order_sn])
          if (existing.length > 0) continue

          const itemsJson = JSON.stringify(o.items.map(i => ({
            item_id: i.item_id,
            item_name: i.item_name,
            item_sku: i.item_sku ?? '',
            quantity: i.quantity,
            model_original_price: i.model_original_price ?? 0,
          })))

          await query(`
            INSERT INTO "ShopeeOrder" ("order_sn", "order_status", "buyer", "total_amount", "currency", "shipping_carrier", "tracking_no", "items", "recipient", "ordered_at")
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, to_timestamp($10))
            ON CONFLICT ("order_sn") DO UPDATE SET
              "order_status" = EXCLUDED."order_status",
              "shipping_carrier" = EXCLUDED."shipping_carrier",
              "tracking_no" = EXCLUDED."tracking_no"
          `, [
            o.order_sn, o.order_status, o.buyer_username,
            o.total_amount, o.currency ?? 'BRL',
            o.shipping_carrier ?? '', o.tracking_no ?? '',
            itemsJson,
            o.recipient_address ? JSON.stringify(o.recipient_address) : '{}',
            o.create_time,
          ])
          imported++
        } catch (err) {
          errors.push(`Order ${o.order_sn}: ${err}`)
        }
      }
    }
    return { imported, errors }
  } catch (err) {
    return { imported: 0, errors: [String(err)] }
  }
}

export async function getShopeeOrders(): Promise<any[]> {
  return query(`SELECT * FROM "ShopeeOrder" ORDER BY "ordered_at" DESC NULLS LAST`)
}

export async function getShopeeOrder(orderSn: string): Promise<any | null> {
  const rows = await query(`SELECT * FROM "ShopeeOrder" WHERE "order_sn"=$1`, [orderSn])
  return rows[0] ?? null
}

let orderSyncInterval: ReturnType<typeof setInterval> | null = null

export function startShopeeOrderSync(intervalMs: number = 60000): void {
  if (orderSyncInterval) return
  if (!shopeeAdapter.isConfigured) {
    console.log('[ShopeeOrders] not configured, skipping auto-sync')
    return
  }
  orderSyncInterval = setInterval(async () => {
    const result = await syncShopeeOrders()
    if (result.imported > 0 || result.errors.length > 0) {
      console.log(`[ShopeeOrders] synced: ${result.imported} new, ${result.errors.length} errors`)
    }
  }, intervalMs)
  console.log(`[ShopeeOrders] sync every ${intervalMs / 1000}s`)
  syncShopeeOrders().then(r => console.log(`[ShopeeOrders] initial sync: ${r.imported} orders`))
}

export function stopShopeeOrderSync(): void {
  if (orderSyncInterval) {
    clearInterval(orderSyncInterval)
    orderSyncInterval = null
  }
}
