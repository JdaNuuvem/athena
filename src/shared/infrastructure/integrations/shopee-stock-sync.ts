import { Pool } from 'pg'
import { shopeeAdapter } from './shopee-adapter'

const pool = new Pool({ connectionString: process.env['DATABASE_URL'] ?? 'postgresql://athena:athena@localhost:5433/athena', max: 5 })

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
      let price = 0
      try {
        const detail = await shopeeAdapter.getItemBaseInfo([item.item_id])
        if (detail[0]?.price_info?.[0]) {
          price = detail[0].price_info[0].current_price
        }
      } catch { /* price fetch optional */ }

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
        `, [item.item_id, item.sku, item.name, item.status, item.stock, item.reserved, item.hasModel, price])
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

export async function updateShopeeStockOnOrder(items: Array<{ sku: string; quantity: number }>): Promise<void> {
  for (const item of items) {
    await query(`UPDATE "ShopeeProduct" SET "stock" = GREATEST("stock" - $1, 0), "updated_at" = NOW() WHERE "item_sku"=$2`, [item.quantity, item.sku])
  }
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
  // Run immediately on start
  syncShopeeProducts().then(r => console.log(`[ShopeeSync] initial sync: ${r.count} items`))
}

export function stopShopeeSync(): void {
  if (syncInterval) {
    clearInterval(syncInterval)
    syncInterval = null
  }
}
