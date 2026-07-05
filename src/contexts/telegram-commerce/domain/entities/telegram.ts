import { AggregateRoot } from '@shared/domain/entities'
export class ChatOrder extends AggregateRoot {
  public status: 'browsing' | 'confirmed' | 'paid' | 'cancelled' = 'browsing'
  constructor(public readonly telegramUserId: string, public readonly items: Array<{ sku: string; name: string; quantity: number; unitPrice: number }>, public totalAmount: number, id?: string) { super(id) }
  confirm(): void { this.status = 'confirmed' }
  pay(): void { this.status = 'paid' }
  cancel(): void { this.status = 'cancelled' }
}
export class ChatSession extends AggregateRoot {
  public state: Record<string, unknown> = {}
  constructor(public readonly telegramUserId: string, public readonly username: string, id?: string) { super(id) }
  updateState(data: Record<string, unknown>): void { this.state = { ...this.state, ...data } }
}
