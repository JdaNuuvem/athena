import { AggregateRoot } from '../../../../shared/domain/entities/aggregate-root'
import { Money } from '../../../../shared/domain/value-objects/money'

export class ProductCard extends AggregateRoot {
  public title: string
  public description: string
  public category: string
  public sku: string
  public gtin: string
  public ncm: string
  public brand: string
  public status: 'draft' | 'published' | 'archived'
  public variants: ProductVariant[] = []
  public images: ProductImage[] = []

  constructor(
    id: string,
    title: string,
    sku: string,
    category: string,
  ) {
    super(id)
    this.title = title
    this.sku = sku
    this.category = category
    this.description = ''
    this.gtin = ''
    this.ncm = ''
    this.brand = ''
    this.status = 'draft'
  }

  publish(): void {
    if (this.status === 'archived') throw new Error('Cannot publish archived product')
    this.status = 'published'
  }

  archive(): void {
    this.status = 'archived'
  }
}

export class ProductVariant {
  constructor(
    public readonly variantId: string,
    public readonly sku: string,
    public readonly attributes: Record<string, string>,
    public price: Money,
    public stockQuantity: number = 0,
  ) {}
}

export class ProductImage {
  constructor(
    public readonly url: string,
    public readonly alt: string,
    public readonly order: number = 0,
    public readonly type: 'main' | 'gallery' | 'detail' = 'gallery',
  ) {}
}
