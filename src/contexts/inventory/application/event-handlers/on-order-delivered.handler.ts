import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { EventEnvelope } from '../../../../shared/domain/events'
import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'
import { stockMovementRepo } from '../../infrastructure/persistence/stock-item.repo'

interface OrderDeliveredPayload {
  orderId: string
  deliveredAt: string
  receivedBy?: string
  deliveryNotes?: string
  onTime?: boolean
  deliveryAttempts?: number
}

export class OnOrderDeliveredHandler extends BaseEventHandler<OrderDeliveredPayload> {
  readonly eventType = 'order-management.v1.order.delivered'

  protected async apply(envelope: EventEnvelope<OrderDeliveredPayload>): Promise<void> {
    const { orderId } = envelope.payload
    const p = getPrisma()
    try {
      const rows = await p.$queryRawUnsafe<Array<Record<string, unknown>>>(
        `SELECT sku, quantity FROM "OrderLine" WHERE "orderId"=$1`, orderId,
      )
      for (const r of rows) {
        await stockMovementRepo.record({
          sku: String(r['sku']), warehouseId: 'warehouse-001', type: 'delivered',
          quantity: Number(r['quantity']), referenceId: orderId,
        })
      }
    } catch (e) { console.error('[OnOrderDeliveredHandler]', e) }
  }
}
