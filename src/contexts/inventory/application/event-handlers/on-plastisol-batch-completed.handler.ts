import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { EventEnvelope } from '../../../../shared/domain/events'
import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'
import { stockItemRepo, stockMovementRepo } from '../../infrastructure/persistence/stock-item.repo'
import { StockItem } from '../../domain/entities/stock-item.entity'

interface PlastisolBatchCompletedPayload {
  batchId: string
  formulationId: string
  productId: string
  quantityProduced?: number
  defectives?: number
  completedAt: string
}

export class OnPlastisolBatchCompletedHandler extends BaseEventHandler<PlastisolBatchCompletedPayload> {
  readonly eventType = 'plastisol-processing.v1.batch.completed'

  protected async apply(e: EventEnvelope<PlastisolBatchCompletedPayload>): Promise<void> {
    const { productId, quantityProduced, completedAt, batchId } = e.payload
    const produced = quantityProduced ?? 0
    if (produced <= 0) return

    try {
      const p = getPrisma()
      const rows = await p.$queryRawUnsafe<Array<Record<string, unknown>>>(
        `SELECT sku FROM "Product" WHERE id=$1 LIMIT 1`, productId,
      )
      const sku = rows.length > 0 ? String(rows[0]!['sku']) : productId
      const warehouseId = 'plast-warehouse'

      const existing = await stockItemRepo.findBySku(sku, warehouseId)
      if (existing) {
        existing.receive(produced)
        await stockItemRepo.save(existing)
      } else {
        await stockItemRepo.save(new StockItem(sku, warehouseId, produced, 10, 0, 'units'))
      }
      await stockMovementRepo.record({
        sku, warehouseId, type: 'production_received',
        quantity: produced, referenceId: batchId,
      })
    } catch (err) { console.error('[OnPlastisolBatchCompletedHandler]', err) }
  }
}
