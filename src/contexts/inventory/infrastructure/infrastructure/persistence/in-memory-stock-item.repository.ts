import { InMemoryRepository } from '../../../../shared/infrastructure/persistence/in-memory-repository'
import { StockItem, StockMovement } from '../../domain/entities/stock-item'
import { IStockItemRepository } from '../../domain/repositories/stock-item.repository'

export class InMemoryStockItemRepository extends InMemoryRepository<StockItem> implements IStockItemRepository {
  private movements: StockMovement[] = []

  async findBySkuAndWarehouse(sku: string, warehouseId: string): Promise<StockItem | null> {
    return this.findBy(item => item.sku === sku && item.warehouseId === warehouseId)[0] ?? null
  }

  async reserve(sku: string, warehouseId: string, quantity: number, orderId: string): Promise<boolean> {
    const item = await this.findBySkuAndWarehouse(sku, warehouseId)
    if (!item || item.available < quantity) return false
    item.reserved += quantity
    item.available -= quantity
    item.updatedAt = new Date().toISOString()
    await this.save(item)
    this.movements.push({ id: `${orderId}_reserve_${Date.now()}`, type: 'reserve', sku, warehouseId, quantity, reference: orderId, timestamp: new Date().toISOString() })
    return true
  }

  async release(sku: string, warehouseId: string, quantity: number, orderId: string): Promise<boolean> {
    const item = await this.findBySkuAndWarehouse(sku, warehouseId)
    if (!item || item.reserved < quantity) return false
    item.reserved -= quantity
    item.available += quantity
    item.updatedAt = new Date().toISOString()
    await this.save(item)
    this.movements.push({ id: `${orderId}_release_${Date.now()}`, type: 'release', sku, warehouseId, quantity, reference: orderId, timestamp: new Date().toISOString() })
    return true
  }

  async deduct(sku: string, warehouseId: string, quantity: number, orderId: string): Promise<boolean> {
    const item = await this.findBySkuAndWarehouse(sku, warehouseId)
    if (!item || item.quantity < quantity) return false
    item.quantity -= quantity
    item.reserved = Math.max(0, item.reserved - quantity)
    item.available = item.quantity - item.reserved
    item.updatedAt = new Date().toISOString()
    await this.save(item)
    this.movements.push({ id: `${orderId}_deduct_${Date.now()}`, type: 'out', sku, warehouseId, quantity, reference: orderId, timestamp: new Date().toISOString() })
    return true
  }

  getMovements(): StockMovement[] {
    return [...this.movements]
  }
}
