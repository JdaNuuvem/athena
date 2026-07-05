import type { StockItem } from '../entities'

export interface IStockItemRepository {
  save(item: StockItem): Promise<void>
  findById(id: string): Promise<StockItem | null>
  findBySkuAndWarehouse(sku: string, warehouseId: string): Promise<StockItem | null>
  findBySku(sku: string): Promise<StockItem[]>
  findByWarehouse(warehouseId: string): Promise<StockItem[]>
  findLowStock(warehouseId?: string): Promise<StockItem[]>
  delete(id: string): Promise<void>
}
