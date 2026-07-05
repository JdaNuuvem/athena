import { DomainEvent, EventEnvelope } from '@shared/domain/events'

export interface ConversationStartedPayload {
  chatId: string; telegramUserId: string; username?: string; firstName?: string; languageCode?: string
  entryPoint?: string; startedAt: string
}
export class ConversationStartedEvent implements DomainEvent<ConversationStartedPayload> {
  readonly eventType = 'telegram-commerce.v1.conversation.started'; readonly eventVersion = '1.0'
  constructor(readonly payload: ConversationStartedPayload) {}
  toEnvelope(props: Omit<EventEnvelope<ConversationStartedPayload>, 'eventType' | 'eventVersion' | 'payload'>): EventEnvelope<ConversationStartedPayload> {
    return { ...props, eventType: this.eventType, eventVersion: this.eventVersion, payload: this.payload }
  }
}

export interface OrderConfirmedViaChatPayload {
  chatOrderId: string; telegramUserId: string; chatId: string
  items: Array<{ sku: string; quantity: number; unitPrice: number; total?: number }>
  shippingAddress: { recipientName: string; street?: string; number?: string; neighborhood?: string; city: string; state: string; zipCode: string }
  totals: { subtotal: number; shipping?: number; discount?: number; grandTotal: number; currency: string }
  confirmedAt: string
}
export class OrderConfirmedViaChatEvent implements DomainEvent<OrderConfirmedViaChatPayload> {
  readonly eventType = 'telegram-commerce.v1.order.confirmed'; readonly eventVersion = '1.0'
  constructor(readonly payload: OrderConfirmedViaChatPayload) {}
  toEnvelope(props: Omit<EventEnvelope<OrderConfirmedViaChatPayload>, 'eventType' | 'eventVersion' | 'payload'>): EventEnvelope<OrderConfirmedViaChatPayload> {
    return { ...props, eventType: this.eventType, eventVersion: this.eventVersion, payload: this.payload }
  }
}

export interface PaymentCompletedPayload {
  paymentId: string; chatOrderId: string; amount: number; method: string; installments?: number
  transactionId?: string; completedAt: string
}
export class PaymentCompletedEvent implements DomainEvent<PaymentCompletedPayload> {
  readonly eventType = 'telegram-commerce.v1.payment.completed'; readonly eventVersion = '1.0'
  constructor(readonly payload: PaymentCompletedPayload) {}
  toEnvelope(props: Omit<EventEnvelope<PaymentCompletedPayload>, 'eventType' | 'eventVersion' | 'payload'>): EventEnvelope<PaymentCompletedPayload> {
    return { ...props, eventType: this.eventType, eventVersion: this.eventVersion, payload: this.payload }
  }
}
