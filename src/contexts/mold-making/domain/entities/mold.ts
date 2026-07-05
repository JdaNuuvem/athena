import { AggregateRoot } from '@shared/domain/entities'
export class Mold extends AggregateRoot {
  public status: 'design' | 'fabrication' | 'delivered' | 'installed' | 'retired' = 'design'
  public cavities: number; public steelType: string; public cycleLife: number; public coolingConfig?: string; public ejectorType?: string
  constructor(public readonly moldCode: string, public readonly productId: string, cavities: number, steelType: string, cycleLife: number, id?: string) {
    super(id); this.cavities = cavities; this.steelType = steelType; this.cycleLife = cycleLife
  }
  startFabrication(): void { this.status = 'fabrication' }
  deliver(): void { this.status = 'delivered' }
  install(): void { this.status = 'installed' }
  retire(): void { this.status = 'retired' }
}
export class MaintenanceRecord extends AggregateRoot {
  constructor(public readonly moldId: string, public type: string, public description: string, public cost: number, public performedAt: Date, id?: string) { super(id) }
}
