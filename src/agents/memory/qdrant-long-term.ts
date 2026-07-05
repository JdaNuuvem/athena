import type { MemoryEntry, LongTermMemory, MemorySearchResult } from './memory-types'
import { getQdrant, ensureCollection } from '../../shared/infrastructure/persistence/qdrant-client'

const COLLECTION = 'agent_long_term_memory'

export class QdrantLongTerm implements LongTermMemory {
  private initialized = false

  private async init(): Promise<void> {
    if (this.initialized) return
    await ensureCollection(COLLECTION, 1536)
    this.initialized = true
  }

  async store(entry: MemoryEntry): Promise<void> {
    await this.init()
    const client = getQdrant()
    const vector = entry.embedding ?? new Array(1536).fill(0) as number[]
    const pointId = `${entry.namespace}:${entry.key}`
    await client.upsert(COLLECTION, {
      wait: true,
      points: [{
        id: pointId,
        vector,
        payload: {
          key: entry.key,
          namespace: entry.namespace,
          value: JSON.stringify(entry.value),
          tags: entry.tags,
          timestamp: entry.timestamp.toISOString(),
        },
      }],
    })
  }

  async search(query: string, options: { namespace?: string; limit?: number; threshold?: number } = {}): Promise<MemorySearchResult[]> {
    await this.init()
    const client = getQdrant()
    const searchResult = await client.search(COLLECTION, {
      vector: new Array(1536).fill(0) as number[],
      limit: options.limit ?? 10,
      score_threshold: options.threshold ?? 0.7,
      filter: options.namespace
        ? { must: [{ key: 'namespace', match: { value: options.namespace } }] }
        : undefined,
    })

    return searchResult.map(r => {
      const p = r.payload as Record<string, unknown> | null
      return {
        entry: {
          key: String(p?.['key'] ?? ''),
          value: JSON.parse(String(p?.['value'] ?? '{}')),
          namespace: String(p?.['namespace'] ?? 'default'),
          tags: (p?.['tags'] as string[]) ?? [],
          timestamp: new Date(String(p?.['timestamp'] ?? Date.now())),
        },
        score: r.score,
      }
    })
  }

  async retrieve(key: string, namespace = 'default'): Promise<MemoryEntry | null> {
    await this.init()
    const client = getQdrant()
    const pointId = `${namespace}:${key}`
    try {
      const result = await client.retrieve(COLLECTION, { ids: [pointId] })
      const point = result[0]
      if (!point?.payload) return null
      const p = point.payload as Record<string, unknown>
      return {
        key: String(p['key'] ?? ''),
        value: JSON.parse(String(p['value'] ?? '{}')),
        namespace: String(p['namespace'] ?? 'default'),
        tags: (p['tags'] as string[]) ?? [],
        timestamp: new Date(String(p['timestamp'] ?? Date.now())),
      }
    } catch {
      return null
    }
  }

  async delete(key: string, namespace = 'default'): Promise<void> {
    const client = getQdrant()
    const pointId = `${namespace}:${key}`
    await client.delete(COLLECTION, { points: [pointId] })
  }
}
