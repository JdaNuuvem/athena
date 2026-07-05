import Redis from 'ioredis'
import { getConfig } from '../config/app-config'

let redis: Redis | null = null

export function getRedis(): Redis {
  if (redis) return redis
  const config = getConfig()
  redis = new Redis(config.REDIS_URL, {
    maxRetriesPerRequest: 3,
    retryStrategy(times) {
      if (times > 5) return null
      return Math.min(times * 100, 2000)
    },
    lazyConnect: true,
  })
  return redis
}

export async function connectRedis(): Promise<void> {
  const r = getRedis()
  if (r.status === 'wait') await r.connect()
}

export async function disconnectRedis(): Promise<void> {
  if (redis) {
    await redis.quit()
    redis = null
  }
}
