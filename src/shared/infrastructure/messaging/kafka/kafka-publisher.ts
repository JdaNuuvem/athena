import { IEventPublisher } from '../../../application/ports/messaging'
import { EventEnvelope } from '../../../domain/events'

export interface KafkaPublisherConfig {
  brokers: string[]
  clientId: string
  retries?: number
  acks?: -1 | 0 | 1
}

export abstract class BaseKafkaPublisher implements IEventPublisher {
  protected readonly config: KafkaPublisherConfig
  protected abstract readonly defaultTopic: string

  constructor(config: KafkaPublisherConfig) {
    this.config = config
  }

  abstract connect(): Promise<void>
  abstract disconnect(): Promise<void>
  abstract publish<T>(envelope: EventEnvelope<T>): Promise<void>
  abstract publishBatch<T>(envelopes: EventEnvelope<T>[]): Promise<void>

  protected topicFor(context: string): string {
    return `athena.${context}.events`
  }

  // ponytail: EventEnvelope payload type is irrelevant for key generation — source.aggregateId is all we need
  protected keyFor(envelope: { source: { aggregateId: string } }): string {
    return envelope.source.aggregateId
  }
}
