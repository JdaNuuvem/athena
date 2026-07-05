import { IEventConsumer } from '../../../application/ports/messaging'
import { EventEnvelope } from '../../../domain/events'

export interface KafkaConsumerConfig {
  brokers: string[]
  groupId: string
  clientId: string
  fromBeginning?: boolean
  sessionTimeout?: number
}

export abstract class BaseKafkaConsumer implements IEventConsumer {
  protected readonly config: KafkaConsumerConfig
  protected readonly handlers = new Map<string, (envelope: EventEnvelope) => Promise<void>>()

  constructor(config: KafkaConsumerConfig) {
    this.config = config
  }

  abstract connect(): Promise<void>
  abstract disconnect(): Promise<void>
  abstract subscribe<T>(
    eventType: string,
    handler: (envelope: EventEnvelope<T>) => Promise<void>,
  ): Promise<void>
  abstract unsubscribe(eventType: string): Promise<void>

  protected topicFor(context: string): string {
    return `athena.${context}.events`
  }
}
