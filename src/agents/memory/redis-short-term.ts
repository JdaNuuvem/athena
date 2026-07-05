import type { MemoryEntry, ShortTermMemory } from './memory-types'
import type { Redis } from 'ioredis'
import { getRedis } from '../../shared/infrastructure/persistence/redis-client'

export class RedisShortTerm implements ShortTermMemory {
  private redis: Redis
  private readonly maxSize: number
  private readonly prefix = 'athena:memory:st:'

  constructor(maxSize = 1000) {
    this.redis = getRedis()
    this.maxSize = maxSize
  }

  private makeKey(key: string, namespace = 'default'): string {
    return `${this.prefix}${namespace}:${key}`
  }

  recall(key: string, namespace = 'default'): MemoryEntry | null {
    return null
  }

  async recallAsync(key: string, namespace = 'default'): Promise<MemoryEntry | null> {
    const raw = await this.redis.get(this.makeKey(key, namespace))
    if (!raw) return null
    const entry = JSON.parse(raw) as MemoryEntry
    if (entry.ttl && Date.now() - new Date(entry.timestamp).getTime() > entry.ttl) {
      await this.redis.del(this.makeKey(key, namespace))
      return null
    }
    return entry
  }

  remember(entry: MemoryEntry): void {
    const fullKey = this.makeKey(entry.key, entry.namespace)
    const ttlSeconds = entry.ttl ? Math.floor(entry.ttl / 1000) : 86400
    this.redis
      .set(fullKey, JSON.stringify(entry), 'EX', ttlSeconds)
      .catch(err => console.error('[RedisShortTerm] set error:', err))
  }

  forget(key: string, namespace = 'default'): void {
    this.redis.del(this.makeKey(key, namespace)).catch(err => console.error('[RedisShortTerm] del error:', err))
  }

  async recent(limit = 20): Promise<MemoryEntry[]> {
    const keys = await this.redis.keys(`${this.prefix}*`)
    if (keys.length === 0) return []
    const raw = await this.redis.mget(...keys.slice(-limit))
    return raw.filter(Boolean).map(r => JSON.parse(r!) as MemoryEntry)
  }

  async clear(): Promise<void> {
    const keys = await this.redis.keys(`${this.prefix}*`)
    if (keys.length > 0) await this.redis.del(...keys)
  }
}
