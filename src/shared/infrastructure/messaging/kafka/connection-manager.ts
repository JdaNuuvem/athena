import { KafkaPublisher } from './kafka-publisher-impl'
import { KafkaConsumer } from './kafka-consumer-impl'
import { KafkaPublisherConfig, KafkaConsumerConfig } from '.'

export interface KafkaConnectionState {
  publisher: { connected: boolean; clientId: string }
  consumer: { connected: boolean; clientId: string; groupId: string }
}

export class KafkaConnectionManager {
  private publisher_: KafkaPublisher | null = null
  private consumer_: KafkaConsumer | null = null

  get publisher(): KafkaPublisher { return this.publisher_! }
  get consumer(): KafkaConsumer { return this.consumer_! }

  async connectPublisher(config: KafkaPublisherConfig): Promise<KafkaPublisher> {
    this.publisher_ = new KafkaPublisher(config)
    await this.publisher_.connect()
    return this.publisher_
  }

  async connectConsumer(config: KafkaConsumerConfig): Promise<KafkaConsumer> {
    this.consumer_ = new KafkaConsumer(config)
    await this.consumer_.connect()
    return this.consumer_
  }

  healthCheck(): KafkaConnectionState {
    return {
      publisher: {
        connected: this.publisher_?.isConnected() ?? false,
        clientId: this.publisher_?.['config']?.clientId ?? 'not-initialized',
      },
      consumer: {
        connected: this.consumer_?.isConnected() ?? false,
        clientId: this.consumer_?.['config']?.clientId ?? 'not-initialized',
        groupId: this.consumer_?.['config']?.groupId ?? 'not-initialized',
      },
    }
  }

  async disconnectAll(): Promise<void> {
    if (this.publisher_) await this.publisher_.disconnect()
    if (this.consumer_) await this.consumer_.disconnect()
    this.publisher_ = null
    this.consumer_ = null
  }
}

export const kafkaConnectionManager = new KafkaConnectionManager()
