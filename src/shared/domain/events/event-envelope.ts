export interface EventSource {
  readonly context: string
  readonly aggregateId: string
  readonly aggregateType: string
}

export interface EventMetadata {
  readonly userId: string
  readonly agentId: string | null
  readonly channel: 'api' | 'agent' | 'scheduler' | 'system'
}

export interface EventEnvelope<T = Record<string, unknown>> {
  readonly eventId: string
  readonly eventType: string
  readonly eventVersion: string
  readonly timestamp: string
  readonly correlationId: string
  readonly causationId: string | null
  readonly tenantId: string
  readonly source: EventSource
  readonly payload: T
  readonly metadata: EventMetadata
}
