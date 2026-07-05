import { Redis } from 'ioredis'
import { getRedis } from '../persistence/redis-client'
import type { EventEnvelope } from '../../domain/events'
import type { IEventPublisher, IEventConsumer } from '../../application/ports/messaging'

const CHANNEL_PREFIX = 'athena:events:'

let subscriberClient: Redis | null = null

function getSubscriber(): Redis {
  if (!subscriberClient) {
    subscriberClient = getRedis().duplicate()
  }
  return subscriberClient
}

function channelFor(eventType: string): string {
  return `${CHANNEL_PREFIX}${eventType}`
}

export class RedisEventBus implements IEventPublisher, IEventConsumer {
  private activeSubscriptions = new Map<string, boolean>()

  async publish<T>(envelope: EventEnvelope<T>): Promise<void> {
    const channel = channelFor(envelope.eventType)
    try {
      await getRedis().publish(channel, JSON.stringify(envelope))
    } catch (err) {
      console.error(`[RedisEventBus] Publish failed for ${envelope.eventType}:`, err)
    }
  }

  async publishBatch<T>(envelopes: EventEnvelope<T>[]): Promise<void> {
    const pipeline = getRedis().pipeline()
    for (const env of envelopes) {
      pipeline.publish(channelFor(env.eventType), JSON.stringify(env))
    }
    try {
      await pipeline.exec()
    } catch (err) {
      console.error('[RedisEventBus] Batch publish failed:', err)
    }
  }

  async subscribe<T>(eventType: string, handler: (envelope: EventEnvelope<T>) => Promise<void>): Promise<void> {
    if (this.activeSubscriptions.has(eventType)) return
    this.activeSubscriptions.set(eventType, true)

    const sub = getSubscriber()
    const channel = channelFor(eventType)
    await sub.subscribe(channel)

    sub.on('message', async (msgChannel: string, message: string) => {
      if (msgChannel !== channel) return
      try {
        const envelope = JSON.parse(message) as EventEnvelope<T>
        await handler(envelope)
      } catch (err) {
        console.error(`[RedisEventBus] Handler error for ${eventType}:`, err)
      }
    })
  }

  async unsubscribe(eventType: string): Promise<void> {
    this.activeSubscriptions.delete(eventType)
    await getSubscriber().unsubscribe(channelFor(eventType))
  }

  async disconnect(): Promise<void> {
    const sub = subscriberClient
    if (sub && sub.status === 'ready') {
      try { await sub.unsubscribe() } catch { /* ignore */ }
      try { await sub.quit() } catch { /* ignore */ }
    }
    subscriberClient = null
    this.activeSubscriptions.clear()
  }

  isConnected(): boolean {
    return getRedis().status === 'ready'
  }
}

let _bus: RedisEventBus | null = null

export function getRedisEventBus(): RedisEventBus {
  if (!_bus) _bus = new RedisEventBus()
  return _bus
}

export async function disconnectRedisEventBus(): Promise<void> {
  if (_bus) {
    await _bus.disconnect()
    _bus = null
  }
}
