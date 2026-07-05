import { Kafka, Consumer, EachMessagePayload, KafkaMessage } from 'kafkajs'
import { BaseKafkaConsumer, KafkaConsumerConfig } from './kafka-consumer'
import { EventEnvelope } from '../../../domain/events'
import { topicFor, Phase1Context } from './topic-config'
import { validateEvent } from '../../../domain/events/schemas'

export class KafkaConsumer extends BaseKafkaConsumer {
  private kafka!: Kafka
  private consumer!: Consumer
  private connected = false

  constructor(config: KafkaConsumerConfig) {
    super(config)
  }

  async connect(): Promise<void> {
    this.kafka = new Kafka({
      clientId: this.config.clientId,
      brokers: this.config.brokers,
      retry: { retries: 5 },
    })
    this.consumer = this.kafka.consumer({
      groupId: this.config.groupId,
      sessionTimeout: this.config.sessionTimeout ?? 30000,
      heartbeatInterval: 3000,
      maxBytesPerPartition: 1048576,
    })
    await this.consumer.connect()
    this.connected = true
  }

  async disconnect(): Promise<void> {
    if (this.consumer) await this.consumer.disconnect()
    this.connected = false
  }

  async subscribe<T>(
    eventType: string,
    handler: (envelope: EventEnvelope<T>) => Promise<void>,
  ): Promise<void> {
    this.ensureConnected()
    this.handlers.set(eventType, handler as (envelope: EventEnvelope) => Promise<void>)

    const context = eventType.split('.')[0] as Phase1Context
    const topic = topicFor(context)

    await this.consumer.subscribe({ topic, fromBeginning: this.config.fromBeginning ?? false })

    await this.consumer.run({
      eachMessage: async (payload: EachMessagePayload) => {
        await this.handleMessage(payload.message)
      },
    })
  }

  async unsubscribe(eventType: string): Promise<void> {
    this.handlers.delete(eventType)
    if (this.handlers.size === 0 && this.consumer) {
      await this.consumer.stop()
    }
  }

  private async handleMessage(message: KafkaMessage): Promise<void> {
    if (!message.value) return

    let raw: unknown
    try {
      raw = JSON.parse(message.value.toString())
    } catch {
      return
    }

    const eventType = (raw as Record<string, unknown>)?.['eventType']
    if (typeof eventType !== 'string') return

    const result = validateEvent(raw)
    if (!result.success) return

    const handler = this.handlers.get(eventType)
    if (!handler) return

    try {
      await handler(result.data as EventEnvelope)
    } catch (error) {
      throw error
    }
  }

  isConnected(): boolean {
    return this.connected
  }

  private ensureConnected(): void {
    if (!this.connected) throw new Error('KafkaConsumer not connected. Call connect() first.')
  }
}
