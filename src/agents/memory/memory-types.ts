export interface MemoryEntry {
  readonly key: string
  readonly value: unknown
  readonly namespace: string
  readonly timestamp: Date
  readonly ttl?: number
  readonly tags: string[]
  readonly embedding?: number[]
}

export interface MemorySearchResult {
  readonly entry: MemoryEntry
  readonly score: number
}

export interface ShortTermMemory {
  recall(key: string, namespace?: string): MemoryEntry | null
  remember(entry: MemoryEntry): void
  forget(key: string, namespace?: string): void
  recent(limit?: number): MemoryEntry[] | Promise<MemoryEntry[]>
  clear(): void
}

export interface LongTermMemory {
  store(entry: MemoryEntry): Promise<void>
  search(query: string, options?: { namespace?: string; limit?: number; threshold?: number }): Promise<MemorySearchResult[]>
  retrieve(key: string, namespace?: string): Promise<MemoryEntry | null>
  delete(key: string, namespace?: string): Promise<void>
}

export interface EpisodicMemory {
  record(event: { type: string; agentId: string; data: Record<string, unknown> }): void
  history(agentId: string, limit?: number): Array<{ type: string; data: Record<string, unknown>; timestamp: Date }> | Promise<Array<{ type: string; data: Record<string, unknown>; timestamp: Date }>>
  replay(agentId: string, since?: Date): Array<{ type: string; data: Record<string, unknown>; timestamp: Date }> | Promise<Array<{ type: string; data: Record<string, unknown>; timestamp: Date }>>
}
