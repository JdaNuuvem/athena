import type { MemoryEntry, ShortTermMemory } from './memory-types'

export class InMemoryShortTerm implements ShortTermMemory {
  private store = new Map<string, MemoryEntry>()
  private order: string[] = []
  private readonly maxSize: number

  constructor(maxSize = 1000) {
    this.maxSize = maxSize
  }

  private makeKey(key: string, namespace = 'default'): string {
    return `${namespace}:${key}`
  }

  recall(key: string, namespace = 'default'): MemoryEntry | null {
    const entry = this.store.get(this.makeKey(key, namespace))
    if (entry?.ttl && Date.now() - entry.timestamp.getTime() > entry.ttl) {
      this.store.delete(this.makeKey(key, namespace))
      return null
    }
    return entry ?? null
  }

  remember(entry: MemoryEntry): void {
    const fullKey = this.makeKey(entry.key, entry.namespace)
    if (!this.store.has(fullKey) && this.order.length >= this.maxSize) {
      const oldest = this.order.shift()
      if (oldest) this.store.delete(oldest)
    }
    if (!this.store.has(fullKey)) this.order.push(fullKey)
    this.store.set(fullKey, entry)
  }

  forget(key: string, namespace = 'default'): void {
    const fullKey = this.makeKey(key, namespace)
    this.store.delete(fullKey)
    this.order = this.order.filter(k => k !== fullKey)
  }

  recent(limit = 20): MemoryEntry[] {
    return this.order.slice(-limit).map(k => this.store.get(k)!).filter(Boolean)
  }

  clear(): void {
    this.store.clear()
    this.order = []
  }
}
