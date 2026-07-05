import { getPrisma } from '@shared/infrastructure/persistence/prisma-client'
import type { IStockItemRepository } from '../../domain/repositories'
import { StockItem } from '../../domain/entities'

export class PrismaStockItemRepository implements IStockItemRepository {
  async save(item: StockItem): Promise<void> {
    const prisma = getPrisma()
    await prisma.stockItem.upsert({
      where: { id: item.id },
      create: { id: item.id, sku: item.sku, warehouseId: item.warehouseId, quantity: item.quantity, reorderPoint: item.reorderPoint.quantity, reservedQty: item.reservedQty },
      update: { quantity: item.quantity, reorderPoint: item.reorderPoint.quantity, reservedQty: item.reservedQty },
    })
  }

  async findById(id: string): Promise<StockItem | null> {
    const prisma = getPrisma()
    const row = await prisma.stockItem.findUnique({ where: { id } })
    if (!row) return null
    const item = new StockItem(row.sku, row.warehouseId, row.quantity, row.id)
    item.setReorderPoint(row.reorderPoint); item.reservedQty = row.reservedQty
    return item
  }

  async findBySkuAndWarehouse(sku: string, warehouseId: string): Promise<StockItem | null> {
    const prisma = getPrisma()
    const row = await prisma.stockItem.findUnique({ where: { sku_warehouseId: { sku, warehouseId } } })
    if (!row) return null
    const item = new StockItem(row.sku, row.warehouseId, row.quantity, row.id)
    item.setReorderPoint(row.reorderPoint); item.reservedQty = row.reservedQty
    return item
  }

  async findBySku(sku: string): Promise<StockItem[]> {
    const prisma = getPrisma()
    const rows = await prisma.stockItem.findMany({ where: { sku } })
    return rows.map(r => { const item = new StockItem(r.sku, r.warehouseId, r.quantity, r.id); item.setReorderPoint(r.reorderPoint); item.reservedQty = r.reservedQty; return item })
  }

  async findByWarehouse(warehouseId: string): Promise<StockItem[]> {
    const prisma = getPrisma()
    const rows = await prisma.stockItem.findMany({ where: { warehouseId } })
    return rows.map(r => { const item = new StockItem(r.sku, r.warehouseId, r.quantity, r.id); item.setReorderPoint(r.reorderPoint); item.reservedQty = r.reservedQty; return item })
  }

  async findLowStock(warehouseId?: string): Promise<StockItem[]> {
    const prisma = getPrisma()
    const where: Record<string, unknown> = {}
    if (warehouseId) where['warehouseId'] = warehouseId
    const rows = await prisma.stockItem.findMany({ where: { ...where, quantity: {} } as never })
    return rows.map(r => { const item = new StockItem(r.sku, r.warehouseId, r.quantity, r.id); item.setReorderPoint(r.reorderPoint); item.reservedQty = r.reservedQty; return item })
  }

  async delete(id: string): Promise<void> {
    const prisma = getPrisma()
    await prisma.stockItem.delete({ where: { id } })
  }
}
