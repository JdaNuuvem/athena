import { v4 as uuidv4 } from 'uuid'
import { IEventPublisher } from '../../../../shared/application/ports/messaging'
import { EventEnvelope } from '../../../../shared/domain/events'
import {
  OrderPlacedEvent, OrderPlacedPayload,
  OrderConfirmedEvent, OrderConfirmedPayload,
  OrderShippedEvent, OrderShippedPayload,
  OrderDeliveredEvent, OrderDeliveredPayload,
  FulfillmentCompletedEvent, FulfillmentCompletedPayload,
  FulfillmentRoutedEvent, FulfillmentRoutedPayload,
  ReturnRequestedEvent, ReturnRequestedPayload,
} from '../../domain/events'
import {
  OrderPlacedPayload as ZodOrderPlaced,
  OrderConfirmedPayload as ZodOrderConfirmed,
  OrderShippedPayload as ZodOrderShipped,
  OrderDeliveredPayload as ZodOrderDelivered,
  FulfillmentCompletedPayload as ZodFulfillmentCompleted,
  FulfillmentRoutedPayload as ZodFulfillmentRouted,
  ReturnRequestedPayload as ZodReturnRequested,
} from '../../../../shared/domain/events/schemas'

export class PublishOrderPlacedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}
  async execute(command: {
    payload: OrderPlacedPayload; tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null
  }): Promise<EventEnvelope<OrderPlacedPayload>> {
    const validated = ZodOrderPlaced.parse(command.payload)
    return this.publish(new OrderPlacedEvent(validated), 'Order', command)
  }
  private async publish<T>(event: { eventType: string; eventVersion: string; payload: T }, aggregateType: string, command: { tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null }): Promise<EventEnvelope<T>> {
    const env: EventEnvelope<T> = {
      eventId: uuidv4(),
      eventType: event.eventType,
      eventVersion: event.eventVersion,
      timestamp: new Date().toISOString(),
      correlationId: command.correlationId ?? uuidv4(),
      causationId: command.causationId ?? null,
      tenantId: command.tenantId,
      source: { context: 'order-management', aggregateId: (event.payload as Record<string, unknown>)['orderId'] as string ?? '', aggregateType },
      payload: event.payload,
      metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
    }
    await this.publisher.publish(env)
    return env
  }
}

export class PublishOrderConfirmedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}
  async execute(command: {
    payload: OrderConfirmedPayload; tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null
  }): Promise<EventEnvelope<OrderConfirmedPayload>> {
    const validated = ZodOrderConfirmed.parse(command.payload)
    const event = new OrderConfirmedEvent(validated)
    const env: EventEnvelope<OrderConfirmedPayload> = {
      eventId: uuidv4(), eventType: event.eventType, eventVersion: event.eventVersion,
      timestamp: new Date().toISOString(),
      correlationId: command.correlationId ?? uuidv4(),
      causationId: command.causationId ?? null,
      tenantId: command.tenantId,
      source: { context: 'order-management', aggregateId: validated.orderId, aggregateType: 'Order' },
      payload: validated,
      metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
    }
    await this.publisher.publish(env)
    return env
  }
}

export class PublishOrderShippedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}
  async execute(command: {
    payload: OrderShippedPayload; tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null
  }): Promise<EventEnvelope<OrderShippedPayload>> {
    const validated = ZodOrderShipped.parse(command.payload)
    const event = new OrderShippedEvent(validated)
    const env: EventEnvelope<OrderShippedPayload> = {
      eventId: uuidv4(), eventType: event.eventType, eventVersion: event.eventVersion,
      timestamp: new Date().toISOString(),
      correlationId: command.correlationId ?? uuidv4(), causationId: command.causationId ?? null,
      tenantId: command.tenantId,
      source: { context: 'order-management', aggregateId: validated.orderId, aggregateType: 'Order' },
      payload: validated,
      metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
    }
    await this.publisher.publish(env)
    return env
  }
}

export class PublishOrderDeliveredUseCase {
  constructor(private readonly publisher: IEventPublisher) {}
  async execute(command: {
    payload: OrderDeliveredPayload; tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null
  }): Promise<EventEnvelope<OrderDeliveredPayload>> {
    const validated = ZodOrderDelivered.parse(command.payload)
    const event = new OrderDeliveredEvent(validated)
    const env: EventEnvelope<OrderDeliveredPayload> = {
      eventId: uuidv4(), eventType: event.eventType, eventVersion: event.eventVersion,
      timestamp: new Date().toISOString(),
      correlationId: command.correlationId ?? uuidv4(), causationId: command.causationId ?? null,
      tenantId: command.tenantId,
      source: { context: 'order-management', aggregateId: validated.orderId, aggregateType: 'Order' },
      payload: validated,
      metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
    }
    await this.publisher.publish(env)
    return env
  }
}

export class PublishFulfillmentCompletedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}
  async execute(command: {
    payload: FulfillmentCompletedPayload; tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null
  }): Promise<EventEnvelope<FulfillmentCompletedPayload>> {
    const validated = ZodFulfillmentCompleted.parse(command.payload)
    const event = new FulfillmentCompletedEvent(validated)
    const env: EventEnvelope<FulfillmentCompletedPayload> = {
      eventId: uuidv4(), eventType: event.eventType, eventVersion: event.eventVersion,
      timestamp: new Date().toISOString(),
      correlationId: command.correlationId ?? uuidv4(), causationId: command.causationId ?? null,
      tenantId: command.tenantId,
      source: { context: 'order-management', aggregateId: validated.fulfillmentId, aggregateType: 'Fulfillment' },
      payload: validated,
      metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
    }
    await this.publisher.publish(env)
    return env
  }
}

export class PublishFulfillmentRoutedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}
  async execute(command: {
    payload: FulfillmentRoutedPayload; tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null
  }): Promise<EventEnvelope<FulfillmentRoutedPayload>> {
    const validated = ZodFulfillmentRouted.parse(command.payload)
    const event = new FulfillmentRoutedEvent(validated)
    const env: EventEnvelope<FulfillmentRoutedPayload> = {
      eventId: uuidv4(), eventType: event.eventType, eventVersion: event.eventVersion,
      timestamp: new Date().toISOString(),
      correlationId: command.correlationId ?? uuidv4(), causationId: command.causationId ?? null,
      tenantId: command.tenantId,
      source: { context: 'order-management', aggregateId: validated.orderId, aggregateType: 'Fulfillment' },
      payload: validated,
      metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
    }
    await this.publisher.publish(env)
    return env
  }
}

export class PublishReturnRequestedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}
  async execute(command: {
    payload: ReturnRequestedPayload; tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null
  }): Promise<EventEnvelope<ReturnRequestedPayload>> {
    const validated = ZodReturnRequested.parse(command.payload)
    const event = new ReturnRequestedEvent(validated)
    const env: EventEnvelope<ReturnRequestedPayload> = {
      eventId: uuidv4(), eventType: event.eventType, eventVersion: event.eventVersion,
      timestamp: new Date().toISOString(),
      correlationId: command.correlationId ?? uuidv4(), causationId: command.causationId ?? null,
      tenantId: command.tenantId,
      source: { context: 'order-management', aggregateId: validated.returnId, aggregateType: 'Return' },
      payload: validated,
      metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
    }
    await this.publisher.publish(env)
    return env
  }
}
