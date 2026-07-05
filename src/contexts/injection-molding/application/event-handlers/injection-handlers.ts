import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { InMemoryInjectionRepository } from '../../infrastructure/persistence/in-memory-injection.repository'

export class OnRunStartedHandler extends BaseEventHandler {
  readonly eventType = 'injection-molding.v1.run.started'
  constructor(private readonly repo: InMemoryInjectionRepository) { super() }
  protected async apply(env: any) {
    const { runId, machineId, moldId, productId, materialLot, startedAt } = env.payload
    await this.repo.runs.save({ id: runId, machineId, moldId, productId, materialLot: materialLot ?? '', status: 'running', totalCycles: 0, totalPartsProduced: 0, totalDefectives: 0, totalMaterialKg: 0, oee: 0, startedAt, createdAt: startedAt, updatedAt: startedAt })
  }
}

export class OnBatchCompletedHandler extends BaseEventHandler {
  readonly eventType = 'injection-molding.v1.batch.completed'
  constructor(private readonly repo: InMemoryInjectionRepository) { super() }
  protected async apply(env: any) {
    const { batchId, runId, productId, totalCycles, totalPartsProduced, defectiveParts, scrapRatePercent, completedAt, qualityStatus } = env.payload
    await this.repo.batches.save({ id: batchId, runId, productId, cycles: totalCycles ?? 0, partsProduced: totalPartsProduced ?? 0, defectiveParts: defectiveParts ?? 0, scrapRatePercent: scrapRatePercent ?? 0, qualityStatus: qualityStatus ?? 'quarantine', completedAt })

    const run = await this.repo.runs.findById(runId)
    if (run) { run.totalCycles += (totalCycles ?? 0); run.totalPartsProduced += (totalPartsProduced ?? 0); run.totalDefectives += (defectiveParts ?? 0); run.updatedAt = completedAt; await this.repo.runs.save(run) }
  }
}

export class OnRunCompletedHandler extends BaseEventHandler {
  readonly eventType = 'injection-molding.v1.run.completed'
  constructor(private readonly repo: InMemoryInjectionRepository) { super() }
  protected async apply(env: any) {
    const run = await this.repo.runs.findById(env.payload.runId)
    if (!run) return
    run.status = 'completed'; run.totalMaterialKg = env.payload.totalMaterialKg ?? 0; run.oee = env.payload.avgOEE ?? 0; run.completedAt = env.payload.completedAt; run.updatedAt = env.payload.completedAt
    await this.repo.runs.save(run)
  }
}

export class OnDefectDetectedHandler extends BaseEventHandler {
  readonly eventType = 'injection-molding.v1.defect.detected'
  constructor(private readonly repo: InMemoryInjectionRepository) { super() }
  protected async apply(env: any) {
    await this.repo.defects.save({ id: env.payload.defectId, batchId: '', runId: env.payload.runId, defectType: env.payload.defectType, quantity: env.payload.quantity, detectedAt: env.payload.detectedAt })
  }
}
