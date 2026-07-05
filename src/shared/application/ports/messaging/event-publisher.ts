import { EventEnvelope } from '../../../domain/events'

export interface IEventPublisher {
  publish<T>(envelope: EventEnvelope<T>): Promise<void>
  publishBatch<T>(envelopes: EventEnvelope<T>[]): Promise<void>
}
