import type { MemoryEntry, LongTermMemory, MemorySearchResult } from './memory-types'

export class InMemoryLongTerm implements LongTermMemory {
  private entries = new Map<string, MemoryEntry>()

  private makeKey(key: string, namespace = 'default'): string {
    return `${namespace}:${key}`
  }

  async store(entry: MemoryEntry): Promise<void> {
    this.entries.set(this.makeKey(entry.key, entry.namespace), entry)
  }

  async search(
    query: string,
    options: { namespace?: string; limit?: number; threshold?: number } = {},
  ): Promise<MemorySearchResult[]> {
    const results: MemorySearchResult[] = []
    for (const [, entry] of this.entries) {
      if (options.namespace && entry.namespace !== options.namespace) continue
      if (!entry.tags.some(t => query.toLowerCase().includes(t.toLowerCase()))) continue
      results.push({ entry, score: 0.5 })
    }
    return results.slice(0, options.limit ?? 10)
  }

  async retrieve(key: string, namespace = 'default'): Promise<MemoryEntry | null> {
    return this.entries.get(this.makeKey(key, namespace)) ?? null
  }

  async delete(key: string, namespace = 'default'): Promise<void> {
    this.entries.delete(this.makeKey(key, namespace))
  }
}
