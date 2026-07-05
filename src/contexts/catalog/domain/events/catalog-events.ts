import { DomainEvent, EventEnvelope } from '@shared/domain/events'

export interface ProductPublishedPayload {
  productId: string
  sku?: string
  title: string
  description?: string
  bulletPoints?: string[]
  categoryId?: string
  brand?: string
  gtin?: string
  ncm?: string
  status: 'draft' | 'published' | 'archived'
  seoMetadata?: { metaTitle?: string; metaDescription?: string; keywords?: string[] }
  publishedAt?: string
}

export class ProductPublishedEvent implements DomainEvent<ProductPublishedPayload> {
  readonly eventType = 'catalog.v1.product.published'
  readonly eventVersion = '1.0'

  constructor(readonly payload: ProductPublishedPayload) {}

  toEnvelope(props: Omit<EventEnvelope<ProductPublishedPayload>, 'eventType' | 'eventVersion' | 'payload'>): EventEnvelope<ProductPublishedPayload> {
    return { ...props, eventType: this.eventType, eventVersion: this.eventVersion, payload: this.payload }
  }
}

export interface ProductUpdatedPayload {
  productId: string
  sku?: string
  changedFields: string[]
  newValues?: { title?: string; description?: string; price?: number; categoryId?: string; status?: string }
}

export class ProductUpdatedEvent implements DomainEvent<ProductUpdatedPayload> {
  readonly eventType = 'catalog.v1.product.updated'
  readonly eventVersion = '1.0'

  constructor(readonly payload: ProductUpdatedPayload) {}

  toEnvelope(props: Omit<EventEnvelope<ProductUpdatedPayload>, 'eventType' | 'eventVersion' | 'payload'>): EventEnvelope<ProductUpdatedPayload> {
    return { ...props, eventType: this.eventType, eventVersion: this.eventVersion, payload: this.payload }
  }
}

export interface VariantCreatedPayload {
  variantId: string
  productId: string
  sku: string
  attributes: { color?: string; size?: string; material?: string; finish?: string }
  price: number
  stockQuantity: number
  isDefault?: boolean
}

export class VariantCreatedEvent implements DomainEvent<VariantCreatedPayload> {
  readonly eventType = 'catalog.v1.variant.created'
  readonly eventVersion = '1.0'

  constructor(readonly payload: VariantCreatedPayload) {}

  toEnvelope(props: Omit<EventEnvelope<VariantCreatedPayload>, 'eventType' | 'eventVersion' | 'payload'>): EventEnvelope<VariantCreatedPayload> {
    return { ...props, eventType: this.eventType, eventVersion: this.eventVersion, payload: this.payload }
  }
}

export interface MediaAddedPayload {
  mediaId: string
  productId: string
  type: 'image' | 'video' | 'manual' | 'spec_sheet' | 'certificate'
  url: string
  filename?: string
  sortOrder?: number
  tags?: string[]
  isMain?: boolean
}

export class MediaAddedEvent implements DomainEvent<MediaAddedPayload> {
  readonly eventType = 'catalog.v1.media.added'
  readonly eventVersion = '1.0'

  constructor(readonly payload: MediaAddedPayload) {}

  toEnvelope(props: Omit<EventEnvelope<MediaAddedPayload>, 'eventType' | 'eventVersion' | 'payload'>): EventEnvelope<MediaAddedPayload> {
    return { ...props, eventType: this.eventType, eventVersion: this.eventVersion, payload: this.payload }
  }
}
