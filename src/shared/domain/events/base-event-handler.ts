import { IEventHandler } from '../../application/ports/messaging'
import { EventEnvelope } from './event-envelope'

export abstract class BaseEventHandler<T = Record<string, unknown>>
  implements IEventHandler<T>
{
  abstract readonly eventType: string

  private readonly processedEventIds = new Set<string>()
  private readonly maxProcessedIds = 100_000

  async handle(envelope: EventEnvelope<T>): Promise<void> {
    if (this.processedEventIds.has(envelope.eventId)) return
    try {
      await this.apply(envelope)
      this.processedEventIds.add(envelope.eventId)
      if (this.processedEventIds.size > this.maxProcessedIds) {
        const iter = this.processedEventIds.values()
        for (let i = 0; i < this.maxProcessedIds / 2; i++) {
          const next = iter.next()
          if (next.done) break
          this.processedEventIds.delete(next.value)
        }
      }
    } catch (error) {
      throw error
    }
  }

  protected abstract apply(envelope: EventEnvelope<T>): Promise<void>
}
