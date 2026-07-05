import type { EventEnvelope } from './event-envelope'
import type { IEventHandler } from '../../application/ports/messaging/event-handler'

export interface IEventBus {
  publish(event: { eventType: string; payload: Record<string, unknown> }): Promise<void>
  publishBatch(events: Array<{ eventType: string; payload: Record<string, unknown> }>): Promise<void>
  subscribe(eventType: string, handler: IEventHandler<Record<string, unknown>>): void
  unsubscribe(eventType: string, handler: IEventHandler<Record<string, unknown>>): void
}

export class InMemoryEventBus implements IEventBus {
  private handlers = new Map<string, Set<IEventHandler<Record<string, unknown>>>>()

  async publish(event: { eventType: string; payload: Record<string, unknown> }): Promise<void> {
    const handlers = this.handlers.get(event.eventType)
    if (!handlers) return
    const envelope: EventEnvelope<Record<string, unknown>> = {
      eventId: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      eventType: event.eventType,
      eventVersion: '1.0',
      timestamp: new Date().toISOString(),
      correlationId: '',
      causationId: null,
      tenantId: 'default',
      source: { context: 'system', aggregateId: '', aggregateType: '' },
      metadata: { userId: 'system', agentId: null, channel: 'system' },
      payload: event.payload,
    }
    for (const handler of handlers) {
      try { await handler.handle(envelope) } catch (e) { console.error(`[EventBus] Handler error for ${event.eventType}:`, e) }
    }
  }

  async publishBatch(events: Array<{ eventType: string; payload: Record<string, unknown> }>): Promise<void> {
    for (const event of events) await this.publish(event)
  }

  subscribe(eventType: string, handler: IEventHandler<Record<string, unknown>>): void {
    if (!this.handlers.has(eventType)) this.handlers.set(eventType, new Set())
    this.handlers.get(eventType)!.add(handler)
  }

  unsubscribe(eventType: string, handler: IEventHandler<Record<string, unknown>>): void {
    this.handlers.get(eventType)?.delete(handler)
  }
}
