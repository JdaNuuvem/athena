import type { EventEnvelope } from '../../domain/events'
import { getRedisEventBus } from './redis-event-bus'

export async function publishEvent<T = Record<string, unknown>>(envelope: EventEnvelope<T>): Promise<void> {
  try {
    await getRedisEventBus().publish(envelope)
  } catch (err) {
    console.error('[EventPublisher] Failed to publish event:', envelope.eventType, err)
  }
}

export async function publishBatch<T = Record<string, unknown>>(envelopes: EventEnvelope<T>[]): Promise<void> {
  try {
    await getRedisEventBus().publishBatch(envelopes)
  } catch (err) {
    console.error('[EventPublisher] Failed to publish batch:', err)
  }
}

export function getPublisher(): import('./redis-event-bus').RedisEventBus {
  return getRedisEventBus()
}
