import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { EventEnvelope } from '../../../../shared/domain/events'
import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'
import { stockMovementRepo } from '../../infrastructure/persistence/stock-item.repo'

interface FulfillmentRoutedPayload {
  orderId: string
  warehouseId: string
  warehouseName?: string
  routedAt: string
  routingStrategy?: string
  estimatedPickTimeMinutes?: number
  distanceKm?: number
}

export class OnFulfillmentRoutedHandler extends BaseEventHandler<FulfillmentRoutedPayload> {
  readonly eventType = 'order-management.v1.fulfillment.routed'

  protected async apply(envelope: EventEnvelope<FulfillmentRoutedPayload>): Promise<void> {
    const { orderId, warehouseId } = envelope.payload
    const p = getPrisma()
    try {
      const rows = await p.$queryRawUnsafe<Array<Record<string, unknown>>>(
        `SELECT sku, quantity FROM "OrderLine" WHERE "orderId"=$1`, orderId,
      )
      for (const r of rows) {
        await stockMovementRepo.record({
          sku: String(r['sku']), warehouseId, type: 'routed',
          quantity: Number(r['quantity']), referenceId: orderId,
        })
      }
    } catch (e) { console.error('[OnFulfillmentRoutedHandler]', e) }
  }
}
