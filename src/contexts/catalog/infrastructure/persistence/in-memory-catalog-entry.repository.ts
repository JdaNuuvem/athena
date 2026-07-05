import { InMemoryRepository } from '../../../../shared/infrastructure/persistence/in-memory-repository'
import { CatalogEntry } from '../../domain/entities/catalog-entry'
import { ICatalogEntryRepository } from '../../domain/repositories/catalog-entry.repository'

export class InMemoryCatalogEntryRepository extends InMemoryRepository<CatalogEntry> implements ICatalogEntryRepository {
  async findByProductId(productId: string): Promise<CatalogEntry | null> {
    return this.findBy(item => item.productId === productId)[0] ?? null
  }
  async findBySku(sku: string): Promise<CatalogEntry | null> {
    return this.findBy(item => item.sku === sku)[0] ?? null
  }
}
