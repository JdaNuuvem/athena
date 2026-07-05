import type { MemorySearchResult } from './memory-types'
import type { ShortTermMemory, LongTermMemory, EpisodicMemory } from './memory-types'
import { RedisShortTerm } from './redis-short-term'
import { QdrantLongTerm } from './qdrant-long-term'
import { PostgresEpisodic } from './postgres-episodic'
import { InMemoryShortTerm } from './short-term'
import { InMemoryLongTerm } from './long-term'
import { InMemoryEpisodic } from './episodic'

export interface MemoryManager {
  readonly shortTerm: ShortTermMemory
  readonly longTerm: LongTermMemory
  readonly episodic: EpisodicMemory
  hybridSearch(query: string, options?: { namespace?: string; limit?: number }): Promise<MemorySearchResult[]>
}

export class RealMemoryManager implements MemoryManager {
  public readonly shortTerm: ShortTermMemory
  public readonly longTerm: LongTermMemory
  public readonly episodic: EpisodicMemory

  constructor(options?: { stMaxSize?: number }) {
    try {
      this.shortTerm = new RedisShortTerm(options?.stMaxSize)
      this.longTerm = new QdrantLongTerm()
      this.episodic = new PostgresEpisodic()
    } catch {
      this.shortTerm = new InMemoryShortTerm(options?.stMaxSize)
      this.longTerm = new InMemoryLongTerm()
      this.episodic = new InMemoryEpisodic()
    }
  }

  async hybridSearch(query: string, options?: { namespace?: string; limit?: number }): Promise<MemorySearchResult[]> {
    return this.longTerm.search(query, options)
  }
}

export class DefaultMemoryManager extends RealMemoryManager {}
