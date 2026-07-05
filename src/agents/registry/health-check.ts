import type { AgentId, AgentStatus } from '../core/agent-types'
import type { AgentRegistry } from './agent-registry'

export interface HealthStatus {
  readonly agentId: AgentId
  readonly healthy: boolean
  readonly status: AgentStatus
  readonly uptime: number
}

export interface HealthCheckConfig {
  heartbeatIntervalMs: number
  heartbeatTimeoutMs: number
  maxMissedHeartbeats: number
  autoRestart: boolean
}

export interface HealthCheck {
  start(): void
  stop(): void
  check(agentId: AgentId): HealthStatus | null
  checkAll(): HealthStatus[]
  readonly config: HealthCheckConfig
}

export class DefaultHealthCheck implements HealthCheck {
  private heartbeatTimers = new Map<AgentId, ReturnType<typeof setInterval>>()
  private lastSeen = new Map<AgentId, Date>()
  private missedHeartbeats = new Map<AgentId, number>()
  private running = false

  constructor(
    private agentRegistry: AgentRegistry,
    public readonly config: HealthCheckConfig = {
      heartbeatIntervalMs: 5000,
      heartbeatTimeoutMs: 15000,
      maxMissedHeartbeats: 3,
      autoRestart: true,
    },
  ) {}

  start(): void {
    if (this.running) return
    this.running = true
    const allAgents = this.agentRegistry.list()
    for (const agent of allAgents) {
      this.lastSeen.set(agent.id, new Date())
      this.startWatchdog(agent.id)
    }
    this.agentRegistry.events.on('agent-registered', ({ id }: { id: AgentId }) => {
      this.lastSeen.set(id, new Date())
      this.startWatchdog(id)
    })
  }

  stop(): void {
    this.running = false
    for (const [, timer] of this.heartbeatTimers) clearInterval(timer)
    this.heartbeatTimers.clear()
    this.missedHeartbeats.clear()
  }

  check(agentId: AgentId): HealthStatus | null {
    const agent = this.agentRegistry.get(agentId)
    if (!agent) return null

    const lastSeen = this.lastSeen.get(agentId)
    const now = Date.now()
    const timeSinceHeartbeat = lastSeen ? now - lastSeen.getTime() : Infinity
    const missed = this.missedHeartbeats.get(agentId) ?? 0
    const healthy = timeSinceHeartbeat < this.config.heartbeatTimeoutMs && missed < this.config.maxMissedHeartbeats
    const uptime = agent.startedAt ? now - agent.startedAt.getTime() : 0

    return {
      agentId,
      healthy,
      status: agent.status,
      uptime,
    }
  }

  checkAll(): HealthStatus[] {
    return this.agentRegistry.list()
      .map(a => this.check(a.id))
      .filter((s): s is HealthStatus => s !== null)
  }

  private startWatchdog(agentId: AgentId): void {
    if (this.heartbeatTimers.has(agentId)) return
    this.missedHeartbeats.set(agentId, 0)
    const timer = setInterval(() => {
      const agent = this.agentRegistry.get(agentId)
      if (!agent) {
        clearInterval(timer)
        this.heartbeatTimers.delete(agentId)
        return
      }
      this.agentRegistry.heartbeat(agentId)
      this.lastSeen.set(agentId, new Date())
      const elapsed = this.lastSeen.get(agentId)
        ? Date.now() - (this.lastSeen.get(agentId)?.getTime() ?? Date.now())
        : 0
      if (elapsed > this.config.heartbeatTimeoutMs) {
        const missed = (this.missedHeartbeats.get(agentId) ?? 0) + 1
        this.missedHeartbeats.set(agentId, missed)
        if (missed >= this.config.maxMissedHeartbeats) {
          this.agentRegistry.updateStatus(agentId, 'error')
          if (this.config.autoRestart) {
            this.agentRegistry.updateStatus(agentId, 'stopped')
          }
        }
      } else {
        this.missedHeartbeats.set(agentId, 0)
      }
    }, this.config.heartbeatIntervalMs)
    this.heartbeatTimers.set(agentId, timer)
  }
}
