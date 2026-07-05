import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { EventEnvelope } from '../../../../shared/domain/events'
import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'
import { stockItemRepo, stockMovementRepo } from '../../infrastructure/persistence/stock-item.repo'
import { StockItem } from '../../domain/entities/stock-item.entity'

interface InjectionBatchCompletedPayload {
  batchId: string
  runId: string
  productId: string
  totalPartsProduced?: number
  defectiveParts?: number
  completedAt: string
}

export class OnInjectionBatchCompletedHandler extends BaseEventHandler<InjectionBatchCompletedPayload> {
  readonly eventType = 'injection-molding.v1.batch.completed'

  protected async apply(e: EventEnvelope<InjectionBatchCompletedPayload>): Promise<void> {
    const { productId, totalPartsProduced, completedAt, runId } = e.payload
    const produced = totalPartsProduced ?? 0
    if (produced <= 0) return

    try {
      const p = getPrisma()
      const rows = await p.$queryRawUnsafe<Array<Record<string, unknown>>>(
        `SELECT sku FROM "Product" WHERE id=$1 LIMIT 1`, productId,
      )
      const sku = rows.length > 0 ? String(rows[0]!['sku']) : productId
      const warehouseId = 'inj-warehouse'

      const existing = await stockItemRepo.findBySku(sku, warehouseId)
      if (existing) {
        existing.receive(produced)
        await stockItemRepo.save(existing)
      } else {
        await stockItemRepo.save(new StockItem(sku, warehouseId, produced, 10, 0, 'units'))
      }
      await stockMovementRepo.record({
        sku, warehouseId, type: 'production_received',
        quantity: produced, referenceId: runId,
      })
    } catch (err) { console.error('[OnInjectionBatchCompletedHandler]', err) }
  }
}
