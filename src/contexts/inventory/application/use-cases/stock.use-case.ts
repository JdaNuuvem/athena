import type { IStockItemRepository } from '../../domain/repositories'
import { StockItem } from '../../domain/entities'
import type { IEventBus } from '@shared/domain/events'

export class ReceiveStockUseCase {
  constructor(
    private stockRepo: IStockItemRepository,
    private eventBus: IEventBus,
  ) {}

  async execute(sku: string, warehouseId: string, quantity: number, referenceId?: string): Promise<StockItem> {
    let item = await this.stockRepo.findBySkuAndWarehouse(sku, warehouseId)
    if (!item) {
      item = new StockItem(sku, warehouseId, 0)
    }
    item.receive(quantity, referenceId)
    await this.stockRepo.save(item)
    for (const event of item.pullDomainEvents()) await this.eventBus.publish(event)
    return item
  }
}

export class ReserveStockUseCase {
  constructor(
    private stockRepo: IStockItemRepository,
    private eventBus: IEventBus,
  ) {}

  async execute(sku: string, warehouseId: string, quantity: number, orderId: string): Promise<StockItem> {
    const item = await this.stockRepo.findBySkuAndWarehouse(sku, warehouseId)
    if (!item) throw new Error('Stock not found')
    item.reserve(quantity, orderId)
    await this.stockRepo.save(item)
    for (const event of item.pullDomainEvents()) await this.eventBus.publish(event)
    return item
  }
}

export class ShipStockUseCase {
  constructor(
    private stockRepo: IStockItemRepository,
    private eventBus: IEventBus,
  ) {}

  async execute(sku: string, warehouseId: string, quantity: number, orderId: string): Promise<StockItem> {
    const item = await this.stockRepo.findBySkuAndWarehouse(sku, warehouseId)
    if (!item) throw new Error('Stock not found')
    item.ship(quantity, orderId)
    await this.stockRepo.save(item)
    for (const event of item.pullDomainEvents()) await this.eventBus.publish(event)
    return item
  }
}

export class AdjustStockUseCase {
  constructor(
    private stockRepo: IStockItemRepository,
    private eventBus: IEventBus,
  ) {}

  async execute(sku: string, warehouseId: string, newQuantity: number, reason: string): Promise<StockItem> {
    const item = await this.stockRepo.findBySkuAndWarehouse(sku, warehouseId)
    if (!item) throw new Error('Stock not found')
    item.adjust(newQuantity, reason)
    await this.stockRepo.save(item)
    for (const event of item.pullDomainEvents()) await this.eventBus.publish(event)
    return item
  }
}
