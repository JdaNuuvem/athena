import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'
import { StockItem } from '../../domain/entities/stock-item.entity'

export const stockItemRepo = {
  async save(item: StockItem): Promise<void> {
    const p = getPrisma()
    try {
      await p.$executeRawUnsafe(
        `INSERT INTO "StockItem" (id, sku, "warehouseId", quantity, "reorderPoint", "reservedQty", unit) VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (id) DO UPDATE SET quantity=$4, "reorderPoint"=$5, "reservedQty"=$6`,
        item.id, item.sku, item.warehouseId, item.quantity, item.reorderPoint, item.reservedQty, item.unit,
      )
    } catch { /* offline */ }
  },

  async findBySku(sku: string, warehouseId: string): Promise<StockItem | null> {
    const p = getPrisma()
    try {
      const rows = await p.$queryRawUnsafe<Array<Record<string, unknown>>>(
        `SELECT * FROM "StockItem" WHERE sku=$1 AND "warehouseId"=$2 LIMIT 1`, sku, warehouseId,
      )
      if (rows.length === 0) return null
      const r = rows[0]!
      return new StockItem(String(r['sku']), String(r['warehouseId']), Number(r['quantity']), Number(r['reorderPoint']), Number(r['reservedQty']), String(r['unit'] ?? 'units'), String(r['id']))
    } catch { return null }
  },

  async findLowStock(threshold = 1): Promise<StockItem[]> {
    const p = getPrisma()
    try {
      const rows = await p.$queryRawUnsafe<Array<Record<string, unknown>>>(
        `SELECT * FROM "StockItem" WHERE quantity - "reservedQty" <= "reorderPoint" * $1`, threshold,
      )
      return rows.map(r => new StockItem(String(r['sku']), String(r['warehouseId']), Number(r['quantity']), Number(r['reorderPoint']), Number(r['reservedQty']), String(r['unit'] ?? 'units'), String(r['id'])))
    } catch { return [] }
  },
}

export const warehouseRepo = {
  async list(): Promise<Array<{ id: string; name: string; city: string; state: string }>> {
    const p = getPrisma()
    try {
      const rows = await p.$queryRawUnsafe<Array<Record<string, unknown>>>(
        `SELECT id, name, city, state FROM "Warehouse" WHERE active=true`,
      )
      return rows.map(r => ({ id: String(r['id']), name: String(r['name']), city: String(r['city']), state: String(r['state']) }))
    } catch { return [] }
  },
}

export const stockMovementRepo = {
  async record(params: { sku: string; warehouseId: string; type: string; quantity: number; referenceId?: string; reason?: string }): Promise<void> {
    const p = getPrisma()
    try {
      await p.$executeRawUnsafe(
        `INSERT INTO "StockMovement" (id, sku, "warehouseId", type, quantity, "referenceId", reason) VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6)`,
        params.sku, params.warehouseId, params.type, params.quantity, params.referenceId ?? null, params.reason ?? null,
      )
    } catch { /* offline */ }
  },
}
