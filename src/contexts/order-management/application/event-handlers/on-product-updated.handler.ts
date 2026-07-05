import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { EventEnvelope } from '../../../../shared/domain/events'
import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'

interface ProductUpdatedPayload {
  productId: string
  sku?: string
  changedFields: string[]
  newValues?: { title?: string; description?: string; price?: number; categoryId?: string; status?: string }
}

export class OnProductUpdatedHandler extends BaseEventHandler<ProductUpdatedPayload> {
  readonly eventType = 'catalog.v1.product.updated'

  protected async apply(envelope: EventEnvelope<ProductUpdatedPayload>): Promise<void> {
    const { productId, newValues } = envelope.payload
    if (!newValues) return

    const p = getPrisma()
    try {
      await p.$executeRawUnsafe(
        `INSERT INTO "ProductCard" (id, "productId", name, "categoryId", status) VALUES ($1, $2, $3, $4, $5) ON CONFLICT ("productId") DO UPDATE SET name=COALESCE($3, "ProductCard".name), "categoryId"=COALESCE($4, "ProductCard"."categoryId"), status=COALESCE($5, "ProductCard".status)`,
        `card-${productId}`, productId, newValues.title ?? null, newValues.categoryId ?? null, newValues.status ?? null,
      )
    } catch (e) { console.error('[OnProductUpdatedHandler]', e) }
  }
}
