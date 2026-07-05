import { AggregateRoot } from '@shared/domain/entities'
export class CNCJob extends AggregateRoot {
  public status: 'scheduled' | 'running' | 'completed' | 'failed' = 'scheduled'
  public machineId?: string; public programId?: string
  constructor(public readonly partNumber: string, public estimatedHours: number, public priority: number = 1, id?: string) { super(id) }
  start(machineId: string): void { this.machineId = machineId; this.status = 'running' }
  complete(): void { this.status = 'completed' }
  fail(): void { this.status = 'failed' }
}
