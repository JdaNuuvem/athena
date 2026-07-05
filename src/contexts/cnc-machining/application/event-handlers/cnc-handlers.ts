import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { InMemoryCNCRepository } from '../../infrastructure/persistence/in-memory-cnc.repository'

export class OnCNCJobScheduledHandler extends BaseEventHandler {
  readonly eventType = 'cnc-machining.v1.job.scheduled'
  constructor(private readonly repo: InMemoryCNCRepository) { super() }
  protected async apply(env: any) {
    const { jobId, machineId, programId, materialType, scheduledAt } = env.payload
    await this.repo.jobs.save({ id: jobId, machineId, programId: programId ?? '', materialType: materialType ?? '', status: 'scheduled', partsProduced: 0, partsDefective: 0, scheduledAt, createdAt: scheduledAt })
  }
}

export class OnCNCMachiningCompletedHandler extends BaseEventHandler {
  readonly eventType = 'cnc-machining.v1.machining.completed'
  constructor(private readonly repo: InMemoryCNCRepository) { super() }
  protected async apply(env: any) {
    const job = await this.repo.jobs.findById(env.payload.jobId)
    if (!job) return
    job.status = 'completed'; job.partsProduced = env.payload.partsProduced ?? 0; job.partsDefective = env.payload.partsDefective ?? 0; job.completedAt = env.payload.completedAt
    await this.repo.jobs.save(job)
  }
}

export class OnToolWearAlertHandler extends BaseEventHandler {
  readonly eventType = 'cnc-machining.v1.tool.wear.alert'
  constructor(private readonly repo: InMemoryCNCRepository) { super() }
  protected async apply(env: any) {
    const { toolId, toolNumber, machineId, wearMicrons, thresholdMicrons, cyclesCompleted, estimatedCyclesRemaining, severity } = env.payload
    await this.repo.tools.save({ id: toolId, toolNumber: toolNumber ?? 0, machineId, wearMicrons, thresholdMicrons, cyclesCompleted: cyclesCompleted ?? 0, estimatedCyclesRemaining: estimatedCyclesRemaining ?? 0, status: severity === 'immediate' ? 'replaced' : 'warning' })
  }
}
