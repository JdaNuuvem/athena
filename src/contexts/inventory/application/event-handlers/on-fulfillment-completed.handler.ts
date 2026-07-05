import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { EventEnvelope } from '../../../../shared/domain/events'
import { stockItemRepo, stockMovementRepo } from '../../infrastructure/persistence/stock-item.repo'

interface FulfillmentCompletedPayload {
  fulfillmentId: string
  orderId: string
  warehouseId: string
  items?: { sku: string; quantityPicked: number; quantityOrdered: number }[]
  completedAt: string
  completedBy?: string
  durationSeconds?: number
}

export class OnFulfillmentCompletedHandler extends BaseEventHandler<FulfillmentCompletedPayload> {
  readonly eventType = 'order-management.v1.fulfillment.completed'

  protected async apply(envelope: EventEnvelope<FulfillmentCompletedPayload>): Promise<void> {
    const { orderId, warehouseId, items } = envelope.payload
    if (!items) return

    try {
      for (const it of items) {
        const stock = await stockItemRepo.findBySku(it.sku, warehouseId)
        if (stock) {
          stock.ship(it.quantityPicked)
          await stockItemRepo.save(stock)
        }
        await stockMovementRepo.record({
          sku: it.sku, warehouseId, type: 'picked',
          quantity: it.quantityPicked, referenceId: orderId,
        })
      }
    } catch (e) { console.error('[OnFulfillmentCompletedHandler]', e) }
  }
}
