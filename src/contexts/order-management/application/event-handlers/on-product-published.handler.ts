import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { EventEnvelope } from '../../../../shared/domain/events'
import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'

interface ProductPublishedPayload {
  productId: string
  sku?: string
  title: string
  description?: string
  bulletPoints?: string[]
  categoryId?: string
  brand?: string
  gtin?: string
  ncm?: string
  status: string
  seoMetadata?: { metaTitle?: string; metaDescription?: string; keywords?: string[] }
  publishedAt?: string
}

export class OnProductPublishedHandler extends BaseEventHandler<ProductPublishedPayload> {
  readonly eventType = 'catalog.v1.product.published'

  protected async apply(envelope: EventEnvelope<ProductPublishedPayload>): Promise<void> {
    const { productId, title, description, categoryId, status, sku, brand, gtin, ncm, seoMetadata } = envelope.payload

    const p = getPrisma()
    try {
      await p.$executeRawUnsafe(
        `INSERT INTO "ProductCard" (id, "productId", name, "categoryId", status, description) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT ("productId") DO UPDATE SET name=$3, "categoryId"=$4, status=$5, description=$6`,
        `card-${productId}`, productId, title, categoryId ?? '', status, description ?? null,
      )
    } catch (e) { console.error('[OnProductPublishedHandler]', e) }
  }
}
