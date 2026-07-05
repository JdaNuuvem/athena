import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { EventEnvelope } from '../../../../shared/domain/events'
import { ICatalogEntryRepository } from '../../domain/repositories/catalog-entry.repository'
import { CatalogEntry } from '../../domain/entities/catalog-entry'

interface Payload {
  productId: string; sku: string; name: string; description?: string
  category: string; materials: Array<{ materialId: string; name: string; type: string }>
  dimensions?: { lengthMm: number; widthMm: number; heightMm: number; weightG: number }
  bomId?: string
}

export class OnProductDesignedHandler extends BaseEventHandler<Payload> {
  readonly eventType = 'product-engineering.v1.product.designed'

  constructor(private readonly catalogRepo: ICatalogEntryRepository) { super() }

  protected async apply(envelope: EventEnvelope<Payload>): Promise<void> {
    const { productId, sku, name, description, category, materials, dimensions } = envelope.payload

    const existing = await this.catalogRepo.findByProductId(productId)

    const entry: CatalogEntry = {
      id: existing?.id ?? productId,
      productId,
      sku,
      title: name,
      description: description ?? '',
      category,
      materials: materials.map(m => m.name),
      status: existing?.status ?? 'draft',
      variants: existing?.variants ?? [],
      media: existing?.media ?? [],
      createdAt: existing?.createdAt ?? envelope.timestamp,
      updatedAt: envelope.timestamp,
    }

    await this.catalogRepo.save(entry)
  }
}
