import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { InMemoryPlastisolRepository } from '../../infrastructure/persistence/in-memory-plastisol.repository'

export class OnFormulationMixedHandler extends BaseEventHandler {
  readonly eventType = 'plastisol-processing.v1.formulation.mixed'
  constructor(private readonly repo: InMemoryPlastisolRepository) { super() }
  protected async apply(env: any) {
    const { formulationId, productId, batchSizeL, components, actualViscosityCp, mixedAt } = env.payload
    await this.repo.formulations.save({ id: formulationId, productId, batchSizeL, viscosityCp: actualViscosityCp ?? 0, status: 'mixed', components: components ?? [], mixedAt })
  }
}

export class OnPlastisolBatchCompletedHandler extends BaseEventHandler {
  readonly eventType = 'plastisol-processing.v1.batch.completed'
  constructor(private readonly repo: InMemoryPlastisolRepository) { super() }
  protected async apply(env: any) {
    const { batchId, formulationId, productId, quantityProduced, defectives, avgGelThicknessMm, avgHardnessShoreA, completedAt, qualityStatus } = env.payload
    await this.repo.batches.save({ id: batchId, formulationId, productId, quantityProduced: quantityProduced ?? 0, defectives: defectives ?? 0, avgGelThicknessMm: avgGelThicknessMm ?? 0, avgHardnessShoreA: avgHardnessShoreA ?? 0, qualityStatus: qualityStatus ?? 'quarantine', completedAt })
  }
}
