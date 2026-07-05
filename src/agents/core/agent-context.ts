import type { AgentId } from './agent-types'
import type { MemoryManager } from '../memory/memory-manager'
import type { ToolRegistry } from '../tools/tool-registry'

export interface AgentContextData {
  readonly agentId: AgentId
  readonly memory: MemoryManager
  readonly tools: ToolRegistry
  readonly state: Map<string, unknown>
  readonly conversationHistory: Array<{ role: string; content: string }>
  startedAt: Date
  taskCount: number
}

export class AgentContext implements AgentContextData {
  public readonly memory: MemoryManager
  public readonly tools: ToolRegistry
  public readonly state = new Map<string, unknown>()
  public readonly conversationHistory: Array<{ role: string; content: string }> = []
  public startedAt: Date
  public taskCount = 0

  constructor(
    public readonly agentId: AgentId,
    memory: MemoryManager,
    tools: ToolRegistry,
  ) {
    this.memory = memory
    this.tools = tools
    this.startedAt = new Date()
  }
}
