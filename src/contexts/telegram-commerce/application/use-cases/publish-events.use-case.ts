import { v4 as uuidv4 } from 'uuid'
import { IEventPublisher } from '../../../../shared/application/ports/messaging'
import { EventEnvelope } from '../../../../shared/domain/events'
import { ConversationStartedEvent, ConversationStartedPayload, OrderConfirmedViaChatEvent, OrderConfirmedViaChatPayload, PaymentCompletedEvent, PaymentCompletedPayload } from '../../domain/events'
import { ConversationStartedPayload as ZCS, OrderConfirmedViaChatPayload as ZOC, PaymentCompletedPayload as ZPC } from '../../../../shared/domain/events/schemas'

function env<T>(event: { eventType: string; eventVersion: string; payload: T }, ctx: string, aggId: string, aggType: string, c: { tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null }): EventEnvelope<T> {
  return { eventId: uuidv4(), eventType: event.eventType, eventVersion: event.eventVersion, timestamp: new Date().toISOString(), correlationId: c.correlationId ?? uuidv4(), causationId: c.causationId ?? null, tenantId: c.tenantId, source: { context: ctx, aggregateId: aggId, aggregateType: aggType }, payload: event.payload, metadata: { userId: c.userId, agentId: c.agentId ?? null, channel: c.agentId ? 'agent' : 'api' } }
}

type Cmd = { tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null }

export class PublishConversationStartedUseCase {
  constructor(private readonly p: IEventPublisher) {}
  async execute(c: Cmd & { payload: ConversationStartedPayload }) { const v = ZCS.parse(c.payload); const e = env(new ConversationStartedEvent(v), 'telegram-commerce', v.chatId, 'Conversation', c); await this.p.publish(e); return e }
}
export class PublishOrderConfirmedViaChatUseCase {
  constructor(private readonly p: IEventPublisher) {}
  async execute(c: Cmd & { payload: OrderConfirmedViaChatPayload }) { const v = ZOC.parse(c.payload); const e = env(new OrderConfirmedViaChatEvent(v), 'telegram-commerce', v.chatOrderId, 'ChatOrder', c); await this.p.publish(e); return e }
}
export class PublishPaymentCompletedUseCase {
  constructor(private readonly p: IEventPublisher) {}
  async execute(c: Cmd & { payload: PaymentCompletedPayload }) { const v = ZPC.parse(c.payload); const e = env(new PaymentCompletedEvent(v), 'telegram-commerce', v.paymentId, 'Payment', c); await this.p.publish(e); return e }
}
