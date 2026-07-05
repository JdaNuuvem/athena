import { v4 as uuidv4 } from 'uuid'
import { IEventPublisher } from '../../../../shared/application/ports/messaging'
import { EventEnvelope } from '../../../../shared/domain/events'
import {
  StockReceivedEvent, StockReceivedPayload,
  StockShippedEvent, StockShippedPayload,
  StockReservedEvent, StockReservedPayload,
  LowStockAlertEvent, LowStockAlertPayload,
  StockAdjustedEvent, StockAdjustedPayload,
} from '../../domain/events'
import {
  StockReceivedPayload as ZodStockReceived,
  StockShippedPayload as ZodStockShipped,
  StockReservedPayload as ZodStockReserved,
  LowStockAlertPayload as ZodLowStockAlert,
  StockAdjustedPayload as ZodStockAdjusted,
} from '../../../../shared/domain/events/schemas'

function buildEnvelope<T>(event: { eventType: string; eventVersion: string; payload: T }, context: string, aggregateId: string, aggregateType: string, command: {
  tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null
}): EventEnvelope<T> {
  return {
    eventId: uuidv4(), eventType: event.eventType, eventVersion: event.eventVersion,
    timestamp: new Date().toISOString(),
    correlationId: command.correlationId ?? uuidv4(),
    causationId: command.causationId ?? null,
    tenantId: command.tenantId,
    source: { context, aggregateId, aggregateType },
    payload: event.payload,
    metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
  }
}

export class PublishStockReceivedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}
  async execute(command: {
    payload: StockReceivedPayload; tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null
  }): Promise<EventEnvelope<StockReceivedPayload>> {
    const v = ZodStockReceived.parse(command.payload)
    const env = buildEnvelope(new StockReceivedEvent(v), 'inventory', v.movementId, 'StockMovement', command)
    await this.publisher.publish(env)
    return env
  }
}

export class PublishStockShippedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}
  async execute(command: {
    payload: StockShippedPayload; tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null
  }): Promise<EventEnvelope<StockShippedPayload>> {
    const v = ZodStockShipped.parse(command.payload)
    const env = buildEnvelope(new StockShippedEvent(v), 'inventory', v.movementId, 'StockMovement', command)
    await this.publisher.publish(env)
    return env
  }
}

export class PublishStockReservedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}
  async execute(command: {
    payload: StockReservedPayload; tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null
  }): Promise<EventEnvelope<StockReservedPayload>> {
    const v = ZodStockReserved.parse(command.payload)
    const env = buildEnvelope(new StockReservedEvent(v), 'inventory', v.reservationId, 'Reservation', command)
    await this.publisher.publish(env)
    return env
  }
}

export class PublishLowStockAlertUseCase {
  constructor(private readonly publisher: IEventPublisher) {}
  async execute(command: {
    payload: LowStockAlertPayload; tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null
  }): Promise<EventEnvelope<LowStockAlertPayload>> {
    const v = ZodLowStockAlert.parse(command.payload)
    const env = buildEnvelope(new LowStockAlertEvent(v), 'inventory', v.sku, 'StockAlert', command)
    await this.publisher.publish(env)
    return env
  }
}

export class PublishStockAdjustedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}
  async execute(command: {
    payload: StockAdjustedPayload; tenantId: string; userId: string; agentId?: string | null; correlationId?: string; causationId?: string | null
  }): Promise<EventEnvelope<StockAdjustedPayload>> {
    const v = ZodStockAdjusted.parse(command.payload)
    const env = buildEnvelope(new StockAdjustedEvent(v), 'inventory', v.adjustmentId, 'StockAdjustment', command)
    await this.publisher.publish(env)
    return env
  }
}
