import { Kafka, Producer, RecordMetadata, CompressionTypes } from 'kafkajs'
import { BaseKafkaPublisher, KafkaPublisherConfig } from './kafka-publisher'
import { EventEnvelope } from '../../../domain/events'
import { topicFor, Phase1Context } from './topic-config'

export class KafkaPublisher extends BaseKafkaPublisher {
  private kafka!: Kafka
  private producer!: Producer
  private connected = false
  protected readonly defaultTopic = 'athena.events'

  constructor(config: KafkaPublisherConfig) {
    super(config)
  }

  async connect(): Promise<void> {
    this.kafka = new Kafka({
      clientId: this.config.clientId,
      brokers: this.config.brokers,
      retry: { retries: this.config.retries ?? 5 },
    })
    this.producer = this.kafka.producer({
      allowAutoTopicCreation: false,
      idempotent: true,
      maxInFlightRequests: 1,
    })
    await this.producer.connect()
    this.connected = true
  }

  async disconnect(): Promise<void> {
    if (this.producer) await this.producer.disconnect()
    this.connected = false
  }

  async publish<T>(envelope: EventEnvelope<T>): Promise<void> {
    this.ensureConnected()
    const context = envelope.source.context as Phase1Context
    const topic = topicFor(context)
    const key = this.keyFor(envelope)
    const value = JSON.stringify(envelope)

    await this.producer.send({
      topic,
      compression: CompressionTypes.GZIP,
      messages: [{ key, value, headers: { eventType: envelope.eventType, eventVersion: envelope.eventVersion } }],
    })
  }

  async publishBatch<T>(envelopes: EventEnvelope<T>[]): Promise<void> {
    this.ensureConnected()
    const messagesByTopic = new Map<string, Array<{ key: string; value: string; headers: Record<string, string> }>>()

    for (const env of envelopes) {
      const topic = topicFor(env.source.context as Phase1Context)
      if (!messagesByTopic.has(topic)) messagesByTopic.set(topic, [])
      messagesByTopic.get(topic)!.push({
        key: this.keyFor(env),
        value: JSON.stringify(env),
        headers: { eventType: env.eventType, eventVersion: env.eventVersion },
      })
    }

    const sends: Promise<RecordMetadata[]>[] = []
    for (const [topic, messages] of messagesByTopic) {
      sends.push(this.producer.send({ topic, compression: CompressionTypes.GZIP, messages }))
    }
    await Promise.all(sends)
  }

  isConnected(): boolean {
    return this.connected
  }

  private ensureConnected(): void {
    if (!this.connected) throw new Error('KafkaPublisher not connected. Call connect() first.')
  }
}
