import { EventEmitter } from 'events'
import type { AgentId, AgentRole, AgentDefinition, AgentStatus } from '../core/agent-types'
import type { AgentProcess } from '../core/agent-runtime'

export interface AgentRegistration {
  readonly id: AgentId
  readonly definition: AgentDefinition
  readonly process: AgentProcess
  readonly registeredAt: Date
  status: AgentStatus
  lastHeartbeat: Date
  taskCount: number
  errorCount: number
  metadata: Record<string, string>
}

export interface AgentRegistry {
  register(process: AgentProcess): void
  unregister(id: AgentId): void
  get(id: AgentId): AgentProcess | undefined
  list(filter?: { role?: AgentRole; context?: string; status?: AgentStatus }): AgentProcess[]
  findByCapability(capabilityName: string): AgentProcess[]
  updateStatus(id: AgentId, status: AgentStatus): void
  heartbeat(id: AgentId): void
  healthCheck(): Array<{ agentId: AgentId; healthy: boolean; status: AgentStatus; uptime: number }>
  readonly events: EventEmitter
}

export class DefaultAgentRegistry implements AgentRegistry {
  private agents = new Map<AgentId, AgentRegistration>()
  public readonly events = new EventEmitter()
  private missedHeartbeats = new Map<AgentId, number>()

  register(process: AgentProcess): void {
    const reg: AgentRegistration = {
      id: process.id,
      definition: process.definition,
      process,
      registeredAt: new Date(),
      status: process.status,
      lastHeartbeat: new Date(),
      taskCount: 0,
      errorCount: 0,
      metadata: {},
    }
    this.agents.set(process.id, reg)
    this.missedHeartbeats.set(process.id, 0)

    process.events.on('task-completed', () => { reg.taskCount++; reg.lastHeartbeat = new Date() })
    process.events.on('task-failed', () => { reg.errorCount++; reg.lastHeartbeat = new Date() })
    process.events.on('started', () => { reg.status = 'running'; reg.lastHeartbeat = new Date() })

    this.events.emit('agent-registered', { id: process.id, role: process.definition.role })
  }

  unregister(id: AgentId): void {
    if (this.agents.has(id)) {
      this.agents.delete(id)
      this.missedHeartbeats.delete(id)
      this.events.emit('agent-unregistered', { id })
    }
  }

  get(id: AgentId): AgentProcess | undefined {
    return this.agents.get(id)?.process
  }

  list(filter?: { role?: AgentRole; context?: string; status?: AgentStatus }): AgentProcess[] {
    let results = [...this.agents.values()]
    if (filter?.role) results = results.filter(a => a.definition.role === filter.role)
    if (filter?.context) results = results.filter(a => a.definition.context === filter.context)
    if (filter?.status) results = results.filter(a => a.status === filter.status)
    return results.map(a => a.process)
  }

  findByCapability(capabilityName: string): AgentProcess[] {
    return [...this.agents.values()]
      .filter(a => a.definition.capabilities.some(c => c.name === capabilityName))
      .map(a => a.process)
  }

  updateStatus(id: AgentId, status: AgentStatus): void {
    const agent = this.agents.get(id)
    if (!agent) return
    const previous = agent.status
    agent.status = status
    agent.process.status = status
    this.events.emit('agent-status-changed', { id, previous, current: status })
  }

  heartbeat(id: AgentId): void {
    const agent = this.agents.get(id)
    if (agent) {
      agent.lastHeartbeat = new Date()
      this.missedHeartbeats.set(id, 0)
    }
  }

  healthCheck(): Array<{ agentId: AgentId; healthy: boolean; status: AgentStatus; uptime: number }> {
    const now = Date.now()
    return [...this.agents.values()].map(a => {
      const elapsed = now - a.lastHeartbeat.getTime()
      const missed = this.missedHeartbeats.get(a.id) ?? 0
      return {
        agentId: a.id,
        healthy: elapsed < 30000 && missed < 3,
        status: a.status,
        uptime: a.registeredAt ? now - a.registeredAt.getTime() : 0,
      }
    })
  }
}
