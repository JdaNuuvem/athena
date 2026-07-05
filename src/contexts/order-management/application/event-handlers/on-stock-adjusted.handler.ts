import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { EventEnvelope } from '../../../../shared/domain/events'
import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'

interface StockAdjustedPayload {
  adjustmentId: string
  warehouseId: string
  items: { sku: string; previousQuantity: number; newQuantity: number; difference: number; location?: string }[]
  reason: string
  adjustedAt: string
  adjustedBy?: string
}

export class OnStockAdjustedHandler extends BaseEventHandler<StockAdjustedPayload> {
  readonly eventType = 'inventory.v1.stock.adjusted'

  protected async apply(envelope: EventEnvelope<StockAdjustedPayload>): Promise<void> {
    const { items, reason, warehouseId, adjustmentId } = envelope.payload
    const p = getPrisma()
    try {
      for (const it of items) {
        if (it.difference >= 0) continue
        const rows = await p.$queryRawUnsafe<Array<Record<string, unknown>>>(
          `SELECT id, sku, "reservedQty" FROM "StockItem" WHERE sku=$1 AND "warehouseId"=$2 LIMIT 1`,
          it.sku, warehouseId,
        )
        if (rows.length === 0) continue
        const stock = rows[0]!
        if (Number(stock['reservedQty']) > it.newQuantity) {
          await p.$executeRawUnsafe(
            `INSERT INTO "Insight" (id, title, description, context, severity) VALUES ($1, $2, $3, $4, $5)`,
            `adj-conflict-${it.sku}-${adjustmentId}`,
            `Stock adjusted below reservations for ${it.sku}`,
            `Reserved ${stock['reservedQty']} but only ${it.newQuantity} available after ${reason}. Review pending orders.`,
            'order-management-adjustment', 'critical',
          )
        }
      }
    } catch (e) { console.error('[OnStockAdjustedHandler]', e) }
  }
}
