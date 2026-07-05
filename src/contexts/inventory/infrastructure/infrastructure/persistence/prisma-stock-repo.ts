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
    return this.toDomain(row)
  }

  async findBySkuAndWarehouse(sku: string, warehouseId: string): Promise<StockItem | null> {
    const prisma = getPrisma()
    const row = await prisma.stockItem.findUnique({ where: { sku_warehouseId: { sku, warehouseId } } })
    if (!row) return null
    return this.toDomain(row)
  }

  async findBySku(sku: string): Promise<StockItem[]> {
    const prisma = getPrisma()
    const rows = await prisma.stockItem.findMany({ where: { sku } })
    return rows.map(r => this.toDomain(r))
  }

  async findByWarehouse(warehouseId: string): Promise<StockItem[]> {
    const prisma = getPrisma()
    const rows = await prisma.stockItem.findMany({ where: { warehouseId } })
    return rows.map(r => this.toDomain(r))
  }

  async findLowStock(warehouseId?: string): Promise<StockItem[]> {
    const prisma = getPrisma()
    const where: Record<string, unknown> = {}
    if (warehouseId) where['warehouseId'] = warehouseId
    const rows = await prisma.stockItem.findMany({ where: { ...where, quantity: { lte: prisma.stockItem.fields.reorderPoint } } as never })
    return rows.map(r => this.toDomain(r))
  }

  async delete(id: string): Promise<void> {
    const prisma = getPrisma()
    await prisma.stockItem.delete({ where: { id } })
  }

  private toDomain(row: { id: string; sku: string; warehouseId: string; quantity: number; reorderPoint: number; reservedQty: number }): StockItem {
    const item = new StockItem(row.sku, row.warehouseId, row.quantity, row.id)
    item.setReorderPoint(row.reorderPoint)
    item.reservedQty = row.reservedQty
    return item
  }
}
