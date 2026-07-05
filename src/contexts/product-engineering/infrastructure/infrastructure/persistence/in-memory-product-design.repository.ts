import { InMemoryRepository } from '../../../../shared/infrastructure/persistence/in-memory-repository'
import { ProductDesign } from '../../domain/entities/product-design'
import { IProductDesignRepository } from '../../domain/repositories/product-design.repository'

export class InMemoryProductDesignRepository extends InMemoryRepository<ProductDesign> implements IProductDesignRepository {
  async findBySku(sku: string): Promise<ProductDesign | null> {
    return this.findBy(item => item.sku === sku)[0] ?? null
  }
}
