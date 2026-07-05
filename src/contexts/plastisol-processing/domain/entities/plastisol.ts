import { AggregateRoot } from '@shared/domain/entities'
export class PlastisolFormulation extends AggregateRoot {
  public viscosity: number; public gelTemperature: number; public curingProfile?: Record<string, number>
  constructor(public readonly formulaCode: string, public components: Array<{ materialId: string; name: string; percentage: number }>, id?: string) { super(id); this.viscosity = 0; this.gelTemperature = 0 }
}
export class CuringCycle extends AggregateRoot {
  public status: 'started' | 'curing' | 'completed' | 'failed' = 'started'; public actualTemperature?: number; public actualDuration?: number
  constructor(public readonly formulationId: string, public readonly lineId: string, public targetTemperature: number, public targetDuration: number, id?: string) { super(id) }
  complete(actualTemp: number, actualDuration: number): void { this.status = 'completed'; this.actualTemperature = actualTemp; this.actualDuration = actualDuration }
  fail(): void { this.status = 'failed' }
}
