import type { EventEnvelope } from '../../../../shared/domain/events'
import { stockItemRepo, stockMovementRepo } from '../../infrastructure/persistence/stock-item.repo'
import { StockItem } from '../../domain/entities/stock-item.entity'

export const inventoryEventHandlers: Record<string, (envelope: EventEnvelope) => Promise<void>> = {
  'inventory.v1.stock.adjusted': async (env) => {
    const p = env.payload as Record<string, unknown>
    const item = await stockItemRepo.findBySku(String(p['sku'] ?? ''), String(p['warehouseId'] ?? ''))
    if (!item) {
      const newItem = new StockItem(String(p['sku']), String(p['warehouseId']), Number(p['newQuantity'] ?? 0), Number(p['reorderPoint'] ?? 10))
      await stockItemRepo.save(newItem)
    } else {
      item.quantity = Number(p['newQuantity'] ?? item.quantity)
      await stockItemRepo.save(item)
    }
    await stockMovementRepo.record({ sku: String(p['sku']), warehouseId: String(p['warehouseId']), type: 'adjusted', quantity: Number(p['newQuantity'] ?? 0), reason: String(p['reason'] ?? '') })
  },

  'inventory.v1.stock.reserved': async (env) => {
    const p = env.payload as Record<string, unknown>
    const item = await stockItemRepo.findBySku(String(p['sku'] ?? ''), String(p['warehouseId'] ?? ''))
    if (item) {
      item.reserve(Number(p['quantity'] ?? 0))
      await stockItemRepo.save(item)
      await stockMovementRepo.record({ sku: item.sku, warehouseId: item.warehouseId, type: 'reserved', quantity: Number(p['quantity']), referenceId: String(p['orderId'] ?? '') })
    }
  },

  'inventory.v1.stock.shipped': async (env) => {
    const p = env.payload as Record<string, unknown>
    const item = await stockItemRepo.findBySku(String(p['sku'] ?? ''), String(p['warehouseId'] ?? ''))
    if (item) {
      item.ship(Number(p['quantity'] ?? 0))
      await stockItemRepo.save(item)
      await stockMovementRepo.record({ sku: item.sku, warehouseId: item.warehouseId, type: 'shipped', quantity: Number(p['quantity']), referenceId: String(p['orderId'] ?? '') })
    }
  },

  'inventory.v1.stock.received': async (env) => {
    const p = env.payload as Record<string, unknown>
    const item = await stockItemRepo.findBySku(String(p['sku'] ?? ''), String(p['warehouseId'] ?? ''))
    if (item) {
      item.receive(Number(p['quantity'] ?? 0))
    } else {
      const newItem = new StockItem(String(p['sku']), String(p['warehouseId']), Number(p['quantity'] ?? 0), Number(p['reorderPoint'] ?? 10))
      await stockItemRepo.save(newItem)
      return
    }
    await stockItemRepo.save(item)
    await stockMovementRepo.record({ sku: String(p['sku']), warehouseId: String(p['warehouseId']), type: 'received', quantity: Number(p['quantity']), referenceId: String(p['purchaseOrderId'] ?? '') })
  },
}
