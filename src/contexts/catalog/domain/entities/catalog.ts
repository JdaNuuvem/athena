import { AggregateRoot } from '@shared/domain/entities'; import { Money } from '@shared/domain/value-objects/money'
export class ProductCard extends AggregateRoot {
  public status: 'draft' | 'published' | 'archived' = 'draft'
  public description?: string; public images: string[] = []; public videos: string[] = []; public attributes: Record<string, string> = {}
  public seoTitle?: string; public seoDescription?: string; public seoKeywords?: string[]
  public variants: ProductVariant[] = []
  public price?: Money

  constructor(public readonly productId: string, public name: string, public readonly categoryId: string, id?: string) { super(id); if (!productId) throw new Error('Requires productId') }

  publish(): void { this.status = 'published' }
  archive(): void { this.status = 'archived' }
  addImage(url: string): void { if (!this.images.includes(url)) this.images.push(url) }
  addVariant(variant: ProductVariant): void { this.variants.push(variant) }
  setSEO(title: string, description: string, keywords: string[]): void { this.seoTitle = title; this.seoDescription = description; this.seoKeywords = keywords }
}

export interface ProductVariant { sku: string; name: string; attributes: Record<string, string>; price?: number; stockQuantity?: number }
