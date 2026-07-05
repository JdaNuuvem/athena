import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { EventEnvelope } from '../../../../shared/domain/events'
import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'
import { stockMovementRepo } from '../../infrastructure/persistence/stock-item.repo'

interface OrderConfirmedPayload {
  orderId: string
  fraudCheckResult?: string
  confirmedAt: string
  confirmedBy?: string
  estimatedShipDate?: string
}

export class OnOrderConfirmedHandler extends BaseEventHandler<OrderConfirmedPayload> {
  readonly eventType = 'order-management.v1.order.confirmed'

  protected async apply(envelope: EventEnvelope<OrderConfirmedPayload>): Promise<void> {
    const { orderId } = envelope.payload
    const p = getPrisma()
    try {
      const rows = await p.$queryRawUnsafe<Array<Record<string, unknown>>>(
        `SELECT sku, quantity, "unitPrice" FROM "OrderLine" WHERE "orderId"=$1`, orderId,
      )
      for (const r of rows) {
        await stockMovementRepo.record({
          sku: String(r['sku']), warehouseId: 'warehouse-001', type: 'confirmed',
          quantity: Number(r['quantity']), referenceId: orderId,
        })
      }
    } catch (e) { console.error('[OnOrderConfirmedHandler]', e) }
  }
}
