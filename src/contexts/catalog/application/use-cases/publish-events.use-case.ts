import { v4 as uuidv4 } from 'uuid'
import { IEventPublisher } from '../../../../shared/application/ports/messaging'
import { EventEnvelope } from '../../../../shared/domain/events'
import {
  ProductPublishedEvent, ProductPublishedPayload,
  ProductUpdatedEvent, ProductUpdatedPayload,
  VariantCreatedEvent, VariantCreatedPayload,
  MediaAddedEvent, MediaAddedPayload,
} from '../../domain/events'
import {
  ProductPublishedPayload as ZodProductPublished,
  ProductUpdatedPayload as ZodProductUpdated,
  VariantCreatedPayload as ZodVariantCreated,
  MediaAddedPayload as ZodMediaAdded,
} from '../../../../shared/domain/events/schemas'

export class PublishProductPublishedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}

  async execute(command: {
    payload: ProductPublishedPayload
    tenantId: string
    userId: string
    agentId?: string | null
    correlationId?: string
    causationId?: string | null
  }): Promise<EventEnvelope<ProductPublishedPayload>> {
    const validated = ZodProductPublished.parse(command.payload)
    const event = new ProductPublishedEvent(validated)
    const envelope: EventEnvelope<ProductPublishedPayload> = {
      eventId: uuidv4(),
      eventType: event.eventType,
      eventVersion: event.eventVersion,
      timestamp: new Date().toISOString(),
      correlationId: command.correlationId ?? uuidv4(),
      causationId: command.causationId ?? null,
      tenantId: command.tenantId,
      source: { context: 'catalog', aggregateId: validated.productId, aggregateType: 'ProductCard' },
      payload: validated,
      metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
    }
    await this.publisher.publish(envelope)
    return envelope
  }
}

export class PublishProductUpdatedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}

  async execute(command: {
    payload: ProductUpdatedPayload
    tenantId: string
    userId: string
    agentId?: string | null
    correlationId?: string
    causationId?: string | null
  }): Promise<EventEnvelope<ProductUpdatedPayload>> {
    const validated = ZodProductUpdated.parse(command.payload)
    const event = new ProductUpdatedEvent(validated)
    const envelope: EventEnvelope<ProductUpdatedPayload> = {
      eventId: uuidv4(),
      eventType: event.eventType,
      eventVersion: event.eventVersion,
      timestamp: new Date().toISOString(),
      correlationId: command.correlationId ?? uuidv4(),
      causationId: command.causationId ?? null,
      tenantId: command.tenantId,
      source: { context: 'catalog', aggregateId: validated.productId, aggregateType: 'ProductCard' },
      payload: validated,
      metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
    }
    await this.publisher.publish(envelope)
    return envelope
  }
}

export class PublishVariantCreatedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}

  async execute(command: {
    payload: VariantCreatedPayload
    tenantId: string
    userId: string
    agentId?: string | null
    correlationId?: string
    causationId?: string | null
  }): Promise<EventEnvelope<VariantCreatedPayload>> {
    const validated = ZodVariantCreated.parse(command.payload)
    const event = new VariantCreatedEvent(validated)
    const envelope: EventEnvelope<VariantCreatedPayload> = {
      eventId: uuidv4(),
      eventType: event.eventType,
      eventVersion: event.eventVersion,
      timestamp: new Date().toISOString(),
      correlationId: command.correlationId ?? uuidv4(),
      causationId: command.causationId ?? null,
      tenantId: command.tenantId,
      source: { context: 'catalog', aggregateId: validated.variantId, aggregateType: 'Variant' },
      payload: validated,
      metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
    }
    await this.publisher.publish(envelope)
    return envelope
  }
}

export class PublishMediaAddedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}

  async execute(command: {
    payload: MediaAddedPayload
    tenantId: string
    userId: string
    agentId?: string | null
    correlationId?: string
    causationId?: string | null
  }): Promise<EventEnvelope<MediaAddedPayload>> {
    const validated = ZodMediaAdded.parse(command.payload)
    const event = new MediaAddedEvent(validated)
    const envelope: EventEnvelope<MediaAddedPayload> = {
      eventId: uuidv4(),
      eventType: event.eventType,
      eventVersion: event.eventVersion,
      timestamp: new Date().toISOString(),
      correlationId: command.correlationId ?? uuidv4(),
      causationId: command.causationId ?? null,
      tenantId: command.tenantId,
      source: { context: 'catalog', aggregateId: validated.mediaId, aggregateType: 'Media' },
      payload: validated,
      metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
    }
    await this.publisher.publish(envelope)
    return envelope
  }
}
