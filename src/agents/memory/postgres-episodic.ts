import { getPrisma } from '../../shared/infrastructure/persistence/prisma-client'
import type { EpisodicMemory } from './memory-types'

export class PostgresEpisodic implements EpisodicMemory {
  record(event: { type: string; agentId: string; data: Record<string, unknown> }): void {
    const prisma = getPrisma()
    prisma.episodicEvent
      .create({ data: { type: event.type, agentId: event.agentId, data: event.data as object } })
      .catch(err => console.error('[PostgresEpisodic] record error:', err))
  }

  async history(agentId: string, limit = 50): Promise<Array<{ type: string; data: Record<string, unknown>; timestamp: Date }>> {
    const prisma = getPrisma()
    const events = await prisma.episodicEvent.findMany({
      where: { agentId },
      orderBy: { timestamp: 'desc' },
      take: limit,
    })
    return events.map(e => ({
      type: e.type,
      data: e.data as Record<string, unknown>,
      timestamp: e.timestamp,
    }))
  }

  async replay(agentId: string, since?: Date): Promise<Array<{ type: string; data: Record<string, unknown>; timestamp: Date }>> {
    const prisma = getPrisma()
    const events = await prisma.episodicEvent.findMany({
      where: { agentId, ...(since ? { timestamp: { gte: since } } : {}) },
      orderBy: { timestamp: 'asc' },
    })
    return events.map(e => ({
      type: e.type,
      data: e.data as Record<string, unknown>,
      timestamp: e.timestamp,
    }))
  }
}
