import { AggregateRoot } from '../../../../shared/domain/entities/aggregate-root'

export class Product extends AggregateRoot {
  public name: string
  public description: string | null = null
  public category: string
  public status: string
  public revision: string
  public cadFileHash: string | null = null
  public sku: string

  constructor(id: string, sku: string, name: string, category: string) {
    super(id)
    this.sku = sku
    this.name = name
    this.category = category
    this.status = 'draft'
    this.revision = '1.0'
  }

  publish(): void { this.status = 'published' }
  archive(): void { this.status = 'archived' }
}
