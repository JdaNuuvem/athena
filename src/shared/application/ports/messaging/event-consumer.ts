import { EventEnvelope } from '../../../domain/events'

export interface IEventConsumer {
  subscribe<T>(
    eventType: string,
    handler: (envelope: EventEnvelope<T>) => Promise<void>,
  ): Promise<void>
  unsubscribe(eventType: string): Promise<void>
}
