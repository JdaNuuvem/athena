import type { IStockItemRepository } from '../../domain/repositories'

export class GetStockQuery {
  constructor(private stockRepo: IStockItemRepository) {}

  async bySku(sku: string) { return this.stockRepo.findBySku(sku) }
  async byWarehouse(warehouseId: string) { return this.stockRepo.findByWarehouse(warehouseId) }
  async lowStock(warehouseId?: string) { return this.stockRepo.findLowStock(warehouseId) }
}
