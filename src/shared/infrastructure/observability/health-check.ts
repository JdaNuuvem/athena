import { getConfig } from '../config/app-config'

export interface DetailedHealth {
  status: 'healthy' | 'degraded' | 'unhealthy'
  version: string
  uptime: number
  timestamp: string
  agents: { total: number; running: number; errored: number }
  infrastructure: {
    kafka: { status: string; connected: boolean }
    redis: { status: string; connected: boolean }
    qdrant: { status: string; connected: boolean }
    postgres: { status: string; connected: boolean }
  }
  memory: { heapUsedMB: number; heapTotalMB: number }
}

export async function getDetailedHealth(agentStats: { total: number; running: number; errored: number }): Promise<DetailedHealth> {
  const config = getConfig()
  const mem = process.memoryUsage()

  const infraChecks = await Promise.allSettled([
    checkKafka(config.KAFKA_BROKERS),
    checkRedis(config.REDIS_URL),
    checkQdrant(config.QDRANT_URL),
    checkPostgres(config.DATABASE_URL),
  ])

  const [kafkaOk, redisOk, qdrantOk, postgresOk] = infraChecks.map(r => r.status === 'fulfilled' && r.value)

  const allUp = kafkaOk && redisOk && qdrantOk && postgresOk
  const anyDown = !kafkaOk || !redisOk || !qdrantOk || !postgresOk

  return {
    status: allUp ? 'healthy' : anyDown ? 'degraded' : 'unhealthy',
    version: '0.1.0',
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
    agents: agentStats,
    infrastructure: {
      kafka: { status: kafkaOk ? 'connected' : 'disconnected', connected: kafkaOk as boolean },
      redis: { status: redisOk ? 'connected' : 'disconnected', connected: redisOk as boolean },
      qdrant: { status: qdrantOk ? 'connected' : 'disconnected', connected: qdrantOk as boolean },
      postgres: { status: postgresOk ? 'connected' : 'disconnected', connected: postgresOk as boolean },
    },
    memory: { heapUsedMB: Math.round(mem.heapUsed / 1024 / 1024), heapTotalMB: Math.round(mem.heapTotal / 1024 / 1024) },
  }
}

async function checkKafka(brokers: string): Promise<boolean> {
  try {
    const { KafkaConnectionManager } = await import('../messaging/kafka/connection-manager')
    const mgr = new KafkaConnectionManager()
    await mgr.connectPublisher({ clientId: `health-${Date.now()}`, brokers: brokers.split(','), acks: 0 })
    await mgr.disconnectAll()
    return true
  } catch { return false }
}

async function checkRedis(url: string): Promise<boolean> {
  try {
    const Redis = (await import('ioredis')).default
    const r = new Redis(url, { lazyConnect: true, connectTimeout: 2000 })
    await r.connect()
    await r.ping()
    await r.quit()
    return true
  } catch { return false }
}

async function checkQdrant(url: string): Promise<boolean> {
  try {
    const { QdrantClient } = await import('@qdrant/js-client-rest')
    const c = new QdrantClient({ url })
    await c.getCollections()
    return true
  } catch { return false }
}

async function checkPostgres(_url: string): Promise<boolean> {
  try {
    const { getPrisma } = await import('../persistence/prisma-client')
    const p = getPrisma()
    await p.$queryRawUnsafe(`SELECT 1`)
    return true
  } catch { return false }
}
