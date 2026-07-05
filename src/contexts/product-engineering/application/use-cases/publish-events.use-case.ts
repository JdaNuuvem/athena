import { v4 as uuidv4 } from 'uuid'
import { IEventPublisher } from '../../../../shared/application/ports/messaging'
import { EventEnvelope } from '../../../../shared/domain/events'
import {
  ProductDesignedEvent, ProductDesignedPayload,
  BOMUpdatedEvent, BOMUpdatedPayload,
  RevisionApprovedEvent, RevisionApprovedPayload,
  ProductArchivedEvent, ProductArchivedPayload,
} from '../../domain/events'
import {
  ProductDesignedPayload as ZodProductDesigned,
  BOMUpdatedPayload as ZodBOMUpdated,
  RevisionApprovedPayload as ZodRevisionApproved,
  ProductArchivedPayload as ZodProductArchived,
} from '../../../../shared/domain/events/schemas'

export class PublishProductDesignedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}

  async execute(command: {
    payload: ProductDesignedPayload
    tenantId: string
    userId: string
    agentId?: string | null
    correlationId?: string
    causationId?: string | null
  }): Promise<EventEnvelope<ProductDesignedPayload>> {
    const validated = ZodProductDesigned.parse(command.payload)
    const event = new ProductDesignedEvent(validated)
    const envelope: EventEnvelope<ProductDesignedPayload> = {
      eventId: uuidv4(),
      eventType: event.eventType,
      eventVersion: event.eventVersion,
      timestamp: new Date().toISOString(),
      correlationId: command.correlationId ?? uuidv4(),
      causationId: command.causationId ?? null,
      tenantId: command.tenantId,
      source: { context: 'product-engineering', aggregateId: validated.productId, aggregateType: 'Product' },
      payload: validated,
      metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
    }
    await this.publisher.publish(envelope)
    return envelope
  }
}

export class PublishBOMUpdatedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}

  async execute(command: {
    payload: BOMUpdatedPayload
    tenantId: string
    userId: string
    agentId?: string | null
    correlationId?: string
    causationId?: string | null
  }): Promise<EventEnvelope<BOMUpdatedPayload>> {
    const validated = ZodBOMUpdated.parse(command.payload)
    const event = new BOMUpdatedEvent(validated)
    const envelope: EventEnvelope<BOMUpdatedPayload> = {
      eventId: uuidv4(),
      eventType: event.eventType,
      eventVersion: event.eventVersion,
      timestamp: new Date().toISOString(),
      correlationId: command.correlationId ?? uuidv4(),
      causationId: command.causationId ?? null,
      tenantId: command.tenantId,
      source: { context: 'product-engineering', aggregateId: validated.productId, aggregateType: 'BOM' },
      payload: validated,
      metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
    }
    await this.publisher.publish(envelope)
    return envelope
  }
}

export class PublishRevisionApprovedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}

  async execute(command: {
    payload: RevisionApprovedPayload
    tenantId: string
    userId: string
    agentId?: string | null
    correlationId?: string
    causationId?: string | null
  }): Promise<EventEnvelope<RevisionApprovedPayload>> {
    const validated = ZodRevisionApproved.parse(command.payload)
    const event = new RevisionApprovedEvent(validated)
    const envelope: EventEnvelope<RevisionApprovedPayload> = {
      eventId: uuidv4(),
      eventType: event.eventType,
      eventVersion: event.eventVersion,
      timestamp: new Date().toISOString(),
      correlationId: command.correlationId ?? uuidv4(),
      causationId: command.causationId ?? null,
      tenantId: command.tenantId,
      source: { context: 'product-engineering', aggregateId: validated.productId, aggregateType: 'Revision' },
      payload: validated,
      metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
    }
    await this.publisher.publish(envelope)
    return envelope
  }
}

export class PublishProductArchivedUseCase {
  constructor(private readonly publisher: IEventPublisher) {}

  async execute(command: {
    payload: ProductArchivedPayload
    tenantId: string
    userId: string
    agentId?: string | null
    correlationId?: string
    causationId?: string | null
  }): Promise<EventEnvelope<ProductArchivedPayload>> {
    const validated = ZodProductArchived.parse(command.payload)
    const event = new ProductArchivedEvent(validated)
    const envelope: EventEnvelope<ProductArchivedPayload> = {
      eventId: uuidv4(),
      eventType: event.eventType,
      eventVersion: event.eventVersion,
      timestamp: new Date().toISOString(),
      correlationId: command.correlationId ?? uuidv4(),
      causationId: command.causationId ?? null,
      tenantId: command.tenantId,
      source: { context: 'product-engineering', aggregateId: validated.productId, aggregateType: 'Product' },
      payload: validated,
      metadata: { userId: command.userId, agentId: command.agentId ?? null, channel: command.agentId ? 'agent' : 'api' },
    }
    await this.publisher.publish(envelope)
    return envelope
  }
}
