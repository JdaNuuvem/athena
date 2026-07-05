import { IEventPublisher } from '../../application/ports/messaging'
import { IEventHandler } from '../../application/ports/messaging'
import { EventEnvelope } from '../../domain/events'

export class InMemoryEventBus implements IEventPublisher {
  private handlers = new Map<string, Array<(envelope: EventEnvelope) => Promise<void>>>()
  private published: EventEnvelope[] = []

  registerHandler(eventType: string, handler: IEventHandler<any>): void {
    if (!this.handlers.has(eventType)) this.handlers.set(eventType, [])
    this.handlers.get(eventType)!.push(async (env) => handler.handle(env))
  }

  async publish<T>(envelope: EventEnvelope<T>): Promise<void> {
    this.published.push(envelope as EventEnvelope)
    const handlers = this.handlers.get(envelope.eventType)
    if (handlers) {
      for (const h of handlers) {
        await h(envelope as EventEnvelope)
      }
    }
  }

  async publishBatch<T>(envelopes: EventEnvelope<T>[]): Promise<void> {
    for (const env of envelopes) await this.publish(env)
  }

  getPublished(): EventEnvelope[] {
    return [...this.published]
  }

  clear(): void {
    this.published = []
  }
}
