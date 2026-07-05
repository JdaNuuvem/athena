import type { EpisodicMemory } from './memory-types'

// ponytail: append-only array, O(n) replay scan. Swap for EventStoreDB when >100k events.
export class InMemoryEpisodic implements EpisodicMemory {
  private events: Array<{
    type: string
    agentId: string
    data: Record<string, unknown>
    timestamp: Date
  }> = []

  record(event: { type: string; agentId: string; data: Record<string, unknown> }): void {
    this.events.push({ ...event, timestamp: new Date() })
  }

  history(agentId: string, limit = 50): Array<{ type: string; data: Record<string, unknown>; timestamp: Date }> {
    return this.events.filter(e => e.agentId === agentId).slice(-limit)
  }

  replay(agentId: string, since?: Date): Array<{ type: string; data: Record<string, unknown>; timestamp: Date }> {
    return this.events.filter(e => e.agentId === agentId && (!since || e.timestamp >= since))
  }
}
