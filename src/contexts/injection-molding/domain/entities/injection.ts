import { AggregateRoot } from '@shared/domain/entities'
export class ProductionRun extends AggregateRoot {
  public status: 'scheduled' | 'running' | 'paused' | 'completed' | 'stopped' = 'scheduled'
  public targetQuantity: number; public producedQuantity = 0; public scrapQuantity = 0; public defectRate = 0
  constructor(public readonly moldId: string, public readonly machineId: string, public readonly productSku: string, targetQuantity: number, id?: string) { super(id); this.targetQuantity = targetQuantity }
  start(): void { this.status = 'running' }
  recordCycle(ok: boolean): void { this.producedQuantity++; if (!ok) this.scrapQuantity++; this.defectRate = Math.round((this.scrapQuantity / this.producedQuantity) * 100) / 100 }
  complete(): void { this.status = 'completed' }
  stop(): void { this.status = 'stopped' }
}
export class QualityCheck extends AggregateRoot {
  constructor(public readonly runId: string, public passed: boolean, public defects: string[], public parameters: Record<string, number>, id?: string) { super(id) }
}
