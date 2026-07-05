import { IRepository } from '../../../../shared/domain/repositories'
import { CatalogEntry } from '../../domain/entities/catalog-entry'

export interface ICatalogEntryRepository extends IRepository<CatalogEntry> {
  findByProductId(productId: string): Promise<CatalogEntry | null>
  findBySku(sku: string): Promise<CatalogEntry | null>
}
