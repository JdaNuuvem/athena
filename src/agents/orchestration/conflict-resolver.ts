export interface ConflictRecord {
  readonly involvedAgents: string[]
  readonly issue: string
  readonly resolution: 'agent-a-wins' | 'agent-b-wins' | 'merged' | 'human-review' | 'retry'
  readonly resolvedBy: string
  readonly timestamp: Date
}

export interface ConflictResolver {
  resolve(agents: string[], issue: string, proposals: Array<{ agentId: string; proposal: Record<string, unknown>; confidence: number }>): ConflictRecord
  history(): ConflictRecord[]
}

export class DefaultConflictResolver implements ConflictResolver {
  private records: ConflictRecord[] = []

  resolve(
    agents: string[],
    issue: string,
    proposals: Array<{ agentId: string; proposal: Record<string, unknown>; confidence: number }>,
  ): ConflictRecord {
    const sorted = [...proposals].sort((a, b) => b.confidence - a.confidence)
    const winner = sorted[0]
    if (!winner) {
      const record: ConflictRecord = { involvedAgents: agents, issue, resolution: 'human-review', resolvedBy: 'system', timestamp: new Date() }
      this.records.push(record)
      return record
    }

    const second = sorted[1]
    const margin = second ? winner.confidence - second.confidence : 1

    const record: ConflictRecord = {
      involvedAgents: agents,
      issue,
      resolution: margin > 0.2 ? 'agent-a-wins' : margin > 0.05 ? 'agent-a-wins' : 'human-review',
      resolvedBy: margin > 0.05 ? winner.agentId : 'system',
      timestamp: new Date(),
    }
    this.records.push(record)
    return record
  }

  history(): ConflictRecord[] {
    return [...this.records]
  }
}
