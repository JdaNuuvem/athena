import { AggregateRoot } from '../../../../shared/domain/entities/aggregate-root'

export class Mold extends AggregateRoot {
  public status: string
  public cycleCount: number

  constructor(
    public moldCode: string,
    public productId: string,
    public steelType: string,
    public cycleLife: number,
    public cavities: number = 1,
    id?: string,
  ) {
    super(id)
    this.status = 'design'
    this.cycleCount = 0
  }

  get remainingLife(): number { return Math.max(0, this.cycleLife - this.cycleCount) }
  get needsMaintenance(): boolean { return this.remainingLife < this.cycleLife * 0.1 }
  manufacture(): void { this.status = 'manufacturing' }
  ready(): void { this.status = 'ready' }
  inUse(): void { this.status = 'in_use' }
  maintenance(): void { this.status = 'maintenance' }
  incrementCycles(count: number): void { this.cycleCount += count }

  static fromRow(r: Record<string, unknown>): Mold {
    const mold = new Mold(String(r['moldCode']), String(r['productId']), String(r['steelType']), Number(r['cycleLife']), Number(r['cavities']), String(r['id']))
    mold.status = String(r['status'] ?? 'design')
    return mold
  }
}
