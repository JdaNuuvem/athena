import type { IProductRepository } from '../../domain/repositories'
import type { IBOMRepository } from '../../domain/repositories'

export class GetProductQuery {
  constructor(private productRepo: IProductRepository) {}

  async byId(id: string) { return this.productRepo.findById(id) }
  async bySku(sku: string) { return this.productRepo.findBySku(sku) }
  async byCategory(category: string) { return this.productRepo.findByCategory(category) }
  async active() { return this.productRepo.findActive() }
}

export class GetBOMQuery {
  constructor(private bomRepo: IBOMRepository) {}

  async byId(id: string) { return this.bomRepo.findById(id) }
  async byProductId(productId: string) { return this.bomRepo.findByProductId(productId) }
}
