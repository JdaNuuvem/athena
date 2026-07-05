import { EventEnvelope } from './event-envelope'

export interface DomainEvent<T = Record<string, unknown>> {
  readonly eventType: string
  readonly eventVersion: string
  readonly payload: T
  toEnvelope(props: Omit<EventEnvelope<T>, 'eventType' | 'eventVersion' | 'payload'>): EventEnvelope<T>
}
