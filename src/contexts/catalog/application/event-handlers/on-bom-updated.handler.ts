import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { EventEnvelope } from '../../../../shared/domain/events'
import { ICatalogEntryRepository } from '../../domain/repositories/catalog-entry.repository'

interface Payload {
  bomId: string; productId: string; revisionNumber?: string
  components: Array<{ componentId: string; name: string; quantity: number; materialSpec?: string; notes?: string }>
  totalComponents?: number
}

export class OnBOMUpdatedHandler extends BaseEventHandler<Payload> {
  readonly eventType = 'product-engineering.v1.bom.updated'

  constructor(private readonly catalogRepo: ICatalogEntryRepository) { super() }

  protected async apply(envelope: EventEnvelope<Payload>): Promise<void> {
    const { productId } = envelope.payload

    const entry = await this.catalogRepo.findByProductId(productId)
    if (!entry) return

    entry.updatedAt = envelope.timestamp
    await this.catalogRepo.save(entry)
  }
}
