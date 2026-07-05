import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { EventEnvelope } from '../../../../shared/domain/events'
import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'
import { stockMovementRepo } from '../../infrastructure/persistence/stock-item.repo'

interface ReturnRequestedPayload {
  returnId: string
  orderId: string
  reason: string
  reasonDetail?: string
  items?: { sku: string; quantity: number; returnReason?: string }[]
  requestedAt: string
  refundExpected?: boolean
  returnLabelGenerated?: boolean
}

export class OnReturnRequestedHandler extends BaseEventHandler<ReturnRequestedPayload> {
  readonly eventType = 'order-management.v1.return.requested'

  protected async apply(envelope: EventEnvelope<ReturnRequestedPayload>): Promise<void> {
    const { returnId, orderId, items, reason, reasonDetail } = envelope.payload
    if (!items) return

    try {
      for (const it of items) {
        await stockMovementRepo.record({
          sku: it.sku, warehouseId: 'warehouse-001', type: 'return_requested',
          quantity: it.quantity, referenceId: returnId, reason: it.returnReason ?? reason,
        })
      }
      const p = getPrisma()
      await p.$executeRawUnsafe(
        `INSERT INTO "Return" (id, "orderId", reason, items) VALUES ($1, $2, $3, $4) ON CONFLICT (id) DO NOTHING`,
        returnId, orderId, `${reason}${reasonDetail ? ': ' + reasonDetail : ''}`, JSON.stringify(items),
      )
    } catch (e) { console.error('[OnReturnRequestedHandler]', e) }
  }
}
