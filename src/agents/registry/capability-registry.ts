import type { AgentId, AgentCapability } from '../core/agent-types'
import type { AgentRegistry } from './agent-registry'

export interface CapabilityEntry {
  readonly capability: AgentCapability
  agents: AgentId[]
}

export interface CapabilityRegistry {
  registerCapability(agentId: AgentId, capability: AgentCapability): void
  unregisterAgent(agentId: AgentId): void
  findByCapability(name: string): CapabilityEntry | undefined
  findAgentsFor(capabilityName: string): AgentId[]
  searchCapabilities(query: string): CapabilityEntry[]
  list(): CapabilityEntry[]
}

export class DefaultCapabilityRegistry implements CapabilityRegistry {
  private capabilities = new Map<string, CapabilityEntry>()

  constructor(private agentRegistry: AgentRegistry) {}

  registerCapability(agentId: AgentId, capability: AgentCapability): void {
    const existing = this.capabilities.get(capability.name)
    if (existing) {
      if (!existing.agents.includes(agentId)) {
        existing.agents.push(agentId)
      }
    } else {
      this.capabilities.set(capability.name, { capability, agents: [agentId] })
    }
  }

  unregisterAgent(agentId: AgentId): void {
    for (const [name, entry] of this.capabilities) {
      entry.agents = entry.agents.filter(id => id !== agentId)
      if (entry.agents.length === 0) this.capabilities.delete(name)
    }
  }

  findByCapability(name: string): CapabilityEntry | undefined {
    return this.capabilities.get(name)
  }

  findAgentsFor(capabilityName: string): AgentId[] {
    return this.capabilities.get(capabilityName)?.agents ?? []
  }

  searchCapabilities(query: string): CapabilityEntry[] {
    const q = query.toLowerCase()
    return [...this.capabilities.values()].filter(
      c => c.capability.name.toLowerCase().includes(q) || c.capability.description.toLowerCase().includes(q),
    )
  }

  list(): CapabilityEntry[] {
    return [...this.capabilities.values()]
  }
}
