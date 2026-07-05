import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { EventEnvelope } from '../../../../shared/domain/events'
import { InMemoryMoldRepository } from '../../infrastructure/persistence/in-memory-mold.repository'
import { Mold } from '../../domain/entities/mold-entities'

// Mold Designed → create mold projection
export class OnMoldDesignedHandler extends BaseEventHandler {
  readonly eventType = 'mold-making.v1.mold.designed'
  constructor(private readonly repo: InMemoryMoldRepository) { super() }
  protected async apply(env: any) {
    const { moldId, productId, moldCode, cavityCount, steelType, estimatedCycleLife, designedAt } = env.payload
    await this.repo.save({ id: moldId, moldCode: moldCode ?? '', productId, cavityCount, steelType, cycleLife: estimatedCycleLife ?? 100000, currentCycles: 0, status: 'designed', createdAt: designedAt, updatedAt: designedAt })
  }
}

// Mold Fabrication Completed → update status
export class OnMoldFabricationCompletedHandler extends BaseEventHandler {
  readonly eventType = 'mold-making.v1.mold.fabrication.completed'
  constructor(private readonly repo: InMemoryMoldRepository) { super() }
  protected async apply(env: any) {
    const mold = await this.repo.findById(env.payload.moldId)
    if (!mold) return
    mold.status = 'fabricated'; mold.updatedAt = env.payload.completedAt
    await this.repo.save(mold)
  }
}

// Mold Delivered → update status
export class OnMoldDeliveredHandler extends BaseEventHandler {
  readonly eventType = 'mold-making.v1.mold.delivered'
  constructor(private readonly repo: InMemoryMoldRepository) { super() }
  protected async apply(env: any) {
    const mold = await this.repo.findById(env.payload.moldId)
    if (!mold) return
    mold.status = 'delivered'; mold.updatedAt = env.payload.deliveredAt
    await this.repo.save(mold)
  }
}

// Mold Installed → update status, record machine
export class OnMoldInstalledHandler extends BaseEventHandler {
  readonly eventType = 'mold-making.v1.mold.installed'
  constructor(private readonly repo: InMemoryMoldRepository) { super() }
  protected async apply(env: any) {
    const mold = await this.repo.findById(env.payload.moldId)
    if (!mold) return
    mold.status = 'installed'; mold.installedMachineId = env.payload.machineId; mold.updatedAt = env.payload.installedAt
    await this.repo.save(mold)
  }
}

// Cycle Limit Reached → record alert
export class OnCycleLimitReachedHandler extends BaseEventHandler {
  readonly eventType = 'mold-making.v1.cycle.limit.reached'
  constructor(private readonly repo: InMemoryMoldRepository) { super() }
  protected async apply(env: any) {
    const mold = await this.repo.findById(env.payload.moldId)
    if (!mold) return
    mold.currentCycles = env.payload.currentCycles; mold.updatedAt = env.payload.detectedAt
    await this.repo.save(mold)
  }
}

// Maintenance Performed → record in history
export class OnMaintenancePerformedHandler extends BaseEventHandler {
  readonly eventType = 'mold-making.v1.maintenance.performed'
  constructor(private readonly repo: InMemoryMoldRepository) { super() }
  protected async apply(env: any) {
    await this.repo.maintenances.save({
      id: env.payload.maintenanceId, moldId: env.payload.moldId, type: env.payload.type ?? 'corrective',
      performedAt: env.payload.performedAt, findings: env.payload.findings,
      partsReplaced: env.payload.partsReplaced ?? [], downtimeHours: env.payload.downtimeHours ?? 0,
      nextMaintenanceCycles: env.payload.nextMaintenanceCycles,
    })
  }
}
