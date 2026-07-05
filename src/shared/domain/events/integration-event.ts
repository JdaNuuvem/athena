import { EventEnvelope } from './event-envelope'

export interface IntegrationEvent<T = Record<string, unknown>> {
  readonly eventType: string
  readonly eventVersion: string
  readonly payload: T
  readonly correlationId: string
  readonly causationId: string | null
  toEnvelope(props: Omit<EventEnvelope<T>, 'eventType' | 'eventVersion' | 'payload' | 'correlationId' | 'causationId'>): EventEnvelope<T>
}
