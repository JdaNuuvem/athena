import { EventEnvelope } from '../../../domain/events'

export interface IEventHandler<T = Record<string, unknown>> {
  readonly eventType: string
  handle(envelope: EventEnvelope<T>): Promise<void>
}
