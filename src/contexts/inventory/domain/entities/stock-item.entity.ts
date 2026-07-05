import { AggregateRoot } from '../../../../shared/domain/entities/aggregate-root'

export class StockItem extends AggregateRoot {
  constructor(
    public sku: string,
    public warehouseId: string,
    public quantity: number,
    public reorderPoint: number,
    public reservedQty: number = 0,
    public unit: string = 'units',
    id?: string,
  ) {
    super(id)
  }

  get available(): number { return this.quantity - this.reservedQty }

  get status(): string {
    if (this.available <= 0) return 'critical'
    if (this.available <= this.reorderPoint) return 'low'
    return 'ok'
  }

  reserve(qty: number): void {
    if (qty > this.available) throw new Error(`Cannot reserve ${qty}: only ${this.available} available`)
    this.reservedQty += qty
  }

  ship(qty: number): void {
    if (qty > this.reservedQty) throw new Error(`Cannot ship ${qty}: only ${this.reservedQty} reserved`)
    this.quantity -= qty
    this.reservedQty -= qty
  }

  receive(qty: number): void {
    this.quantity += qty
  }

  needsReorder(): boolean { return this.available <= this.reorderPoint }
}
