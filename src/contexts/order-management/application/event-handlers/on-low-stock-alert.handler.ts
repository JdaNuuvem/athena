import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { EventEnvelope } from '../../../../shared/domain/events'
import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'

interface LowStockAlertPayload {
  sku: string
  productName?: string
  warehouseId: string
  warehouseName?: string
  currentQuantity: number
  reorderPoint: number
  safetyStock?: number
  averageDailyDemand?: number
  daysUntilStockout?: number
  triggeredAt: string
  severity: 'warning' | 'critical' | 'stockout'
}

export class OnLowStockAlertHandler extends BaseEventHandler<LowStockAlertPayload> {
  readonly eventType = 'inventory.v1.low.stock.alert'

  protected async apply(envelope: EventEnvelope<LowStockAlertPayload>): Promise<void> {
    const { sku, warehouseId, severity, currentQuantity, reorderPoint, productName, daysUntilStockout } = envelope.payload
    const p = getPrisma()
    try {
      await p.$executeRawUnsafe(
        `INSERT INTO "Insight" (id, title, description, context, severity) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (id) DO NOTHING`,
        `low-stock-${sku}-${warehouseId}-${severity}`,
        `Low stock ${severity} for ${productName ?? sku}`,
        `${productName ?? sku}: ${currentQuantity} units (reorder at ${reorderPoint})${daysUntilStockout ? ', ' + daysUntilStockout + ' days until stockout' : ''}`,
        'order-management-low-stock', severity,
      )

      if (severity === 'stockout') {
        await p.$executeRawUnsafe(
          `UPDATE "Order" SET status='on_hold' WHERE status='confirmed' AND id IN (SELECT DISTINCT ol."orderId" FROM "OrderLine" ol WHERE ol.sku=$1 AND ol."orderId" IN (SELECT id FROM "Order" WHERE status='confirmed'))`,
          sku,
        )
      }
    } catch (e) { console.error('[OnLowStockAlertHandler]', e) }
  }
}
