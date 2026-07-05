import { v4 as uuid } from 'uuid'

export type LogLevel = 'debug' | 'info' | 'warn' | 'error'

export interface AgentLogEntry {
  readonly agentId: string
  readonly correlationId: string
  readonly level: LogLevel
  readonly message: string
  readonly data?: Record<string, unknown>
  readonly timestamp: Date
}

export interface AgentLogger {
  debug(agentId: string, message: string, data?: Record<string, unknown>): void
  info(agentId: string, message: string, data?: Record<string, unknown>): void
  warn(agentId: string, message: string, data?: Record<string, unknown>): void
  error(agentId: string, message: string, data?: Record<string, unknown>): void
  getLogs(agentId: string, limit?: number): AgentLogEntry[]
}

export class InMemoryAgentLogger implements AgentLogger {
  private logs: AgentLogEntry[] = []

  debug(agentId: string, message: string, data?: Record<string, unknown>): void {
    this.write(agentId, 'debug', message, data)
  }

  info(agentId: string, message: string, data?: Record<string, unknown>): void {
    this.write(agentId, 'info', message, data)
  }

  warn(agentId: string, message: string, data?: Record<string, unknown>): void {
    this.write(agentId, 'warn', message, data)
  }

  error(agentId: string, message: string, data?: Record<string, unknown>): void {
    this.write(agentId, 'error', message, data)
  }

  getLogs(agentId: string, limit = 100): AgentLogEntry[] {
    return this.logs.filter(l => l.agentId === agentId).slice(-limit)
  }

  private write(agentId: string, level: LogLevel, message: string, data?: Record<string, unknown>): void {
    const entry: AgentLogEntry = {
      agentId,
      correlationId: uuid(),
      level,
      message,
      data,
      timestamp: new Date(),
    }
    this.logs.push(entry)
  }
}

export interface AuditEntry {
  readonly agentId: string
  readonly correlationId: string
  readonly action: string
  readonly decision: string
  readonly rationale: string
  readonly input?: Record<string, unknown>
  readonly output?: Record<string, unknown>
  readonly timestamp: Date
}

export class AuditTrail {
  private entries: AuditEntry[] = []

  record(entry: Omit<AuditEntry, 'correlationId' | 'timestamp'>): AuditEntry {
    const full: AuditEntry = {
      ...entry,
      correlationId: uuid(),
      timestamp: new Date(),
    }
    this.entries.push(full)
    return full
  }

  getByAgent(agentId: string, limit = 50): AuditEntry[] {
    return this.entries.filter(e => e.agentId === agentId).slice(-limit)
  }

  replay(agentId: string, since?: Date): AuditEntry[] {
    const filtered = this.entries.filter(e => e.agentId === agentId)
    return since ? filtered.filter(e => e.timestamp >= since) : filtered
  }
}
