import { AggregateRoot } from '../../../../shared/domain/entities/aggregate-root'

export class Order extends AggregateRoot {
  public customerId: string
  public channel: string
  public status: string
  public totalAmount: number
  public shippingAddress: Record<string, unknown> | null = null

  constructor(id: string, customerId: string, channel = 'manual') {
    super(id)
    this.customerId = customerId
    this.channel = channel
    this.status = 'draft'
    this.totalAmount = 0
  }

  place(): void { this.status = 'placed' }
  confirm(): void { this.status = 'confirmed' }
  fulfill(): void { this.status = 'fulfilled' }
  ship(): void { this.status = 'shipped' }
  deliver(): void { this.status = 'delivered' }
  cancel(): void { this.status = 'cancelled' }
  return(): void { this.status = 'returned' }
}
