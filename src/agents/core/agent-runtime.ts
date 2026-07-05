import { EventEmitter } from 'events'
import type { AgentId, AgentStatus, AgentDefinition } from './agent-types'
import type { AgentContext } from './agent-context'
import { createLLMProvider, type LLMProvider, type LLMMessage } from './llm-provider'
import { metrics } from '../../shared/infrastructure/observability/metrics'
import { startAgentSpan, endSpan } from '../../shared/infrastructure/observability/tracing'
import { logAgentEvent } from '../../shared/infrastructure/observability/logger'
import { broadcastAgentTask } from '../../shared/infrastructure/websocket/ws-broadcast'

export interface AgentProcess {
  readonly id: AgentId
  readonly definition: AgentDefinition
  readonly context: AgentContext
  status: AgentStatus
  readonly startedAt: Date | null
  readonly events: EventEmitter
  start(): Promise<void>
  pause(): Promise<void>
  resume(): Promise<void>
  stop(): Promise<void>
  handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>>
}

export class AgentRuntime implements AgentProcess {
  public readonly id: AgentId
  public readonly definition: AgentDefinition
  public readonly context: AgentContext
  public status: AgentStatus = 'idle'
  public startedAt: Date | null = null
  public readonly events = new EventEmitter()
  protected llm: LLMProvider

  constructor(id: AgentId, definition: AgentDefinition, context: AgentContext) {
    this.id = id
    this.definition = definition
    this.context = context
    this.llm = createLLMProvider(definition.config)
  }

  async start(): Promise<void> {
    this.status = 'running'
    this.startedAt = new Date()
    this.events.emit('started', { agentId: this.id, at: this.startedAt })
  }

  async pause(): Promise<void> {
    if (this.status !== 'running') return
    this.status = 'paused'
    this.events.emit('paused', { agentId: this.id })
  }

  async resume(): Promise<void> {
    if (this.status !== 'paused') return
    this.status = 'running'
    this.events.emit('resumed', { agentId: this.id })
  }

  async stop(): Promise<void> {
    this.status = 'stopped'
    this.events.emit('stopped', { agentId: this.id })
  }

  async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> {
    if (this.status !== 'running') throw new Error(`Agent ${this.id} is not running`)
    this.events.emit('task-started', { agentId: this.id, task })
    this.context.taskCount++
    const taskType = task['type'] as string ?? 'unknown'
    const span = startAgentSpan(this.id, taskType)
    const startedAt = performance.now()
    logAgentEvent(this.id, `task_started:${taskType}`, { taskType })
    broadcastAgentTask(this.id, 'started', { taskType })

    const taskPrompt = `Task: ${JSON.stringify(task, null, 2)}\n\nAnalyze this task and provide a structured response.`
    const messages: LLMMessage[] = [
      { role: 'system', content: this.definition.systemPrompt },
    ]

    let recent: Array<{ key: string; value: unknown }> = []
    try { const r = await Promise.resolve(this.context.memory.shortTerm.recent(10)); recent = r } catch { /* memory offline */ }
    if (recent.length > 0) {
      messages.push({ role: 'system', content: `Recent context: ${JSON.stringify(recent.map((r: { key: string; value: unknown }) => ({ key: r.key, value: r.value })))}` })
    }

    messages.push({ role: 'user', content: taskPrompt })

    try {
      let llmResponse
      try {
        llmResponse = await this.llm.complete(messages, {
          temperature: this.definition.config.temperature,
          maxTokens: this.definition.config.maxTokens,
        })
      } catch {
        llmResponse = { content: '[LLM offline — using rule-based response]', model: 'fallback', usage: undefined, finishReason: 'fallback' }
      }

      const result = {
        agentId: this.id,
        task,
        status: 'completed',
        response: llmResponse.content,
        model: llmResponse.model,
        usage: llmResponse.usage,
        timestamp: new Date().toISOString(),
      }

      try { this.context.memory.shortTerm.remember({
        key: `task-${this.context.taskCount}`,
        value: result,
        namespace: this.id,
        timestamp: new Date(),
        tags: ['task', task['type'] as string ?? 'unknown'],
      }) } catch { /* memory offline */ }

      try { this.context.memory.episodic.record({
        type: 'task_completed',
        agentId: this.id,
        data: { taskType: task['type'], result: 'success' },
      }) } catch { /* memory offline */ }

      this.events.emit('task-completed', { agentId: this.id, result })
      metrics.agentTasksTotal.inc({ agent_id: this.id, status: 'completed' })
      metrics.agentTaskDuration.observe({ agent_id: this.id }, (performance.now() - startedAt) / 1000)
      endSpan(span)
      logAgentEvent(this.id, `task_completed:${taskType}`, { duration: (performance.now() - startedAt) / 1000 })
      broadcastAgentTask(this.id, 'completed', { taskType, duration: performance.now() - startedAt })
      return result
    } catch (err) {
      const errorResult = {
        agentId: this.id,
        task,
        status: 'error',
        error: String(err),
        timestamp: new Date().toISOString(),
      }

      try { this.context.memory.episodic.record({
        type: 'task_failed',
        agentId: this.id,
        data: { taskType: task['type'], error: String(err) },
      }) } catch { /* memory offline */ }

      this.events.emit('task-failed', { agentId: this.id, error: err })
      metrics.agentTasksTotal.inc({ agent_id: this.id, status: 'error' })
      endSpan(span, err as Error)
      broadcastAgentTask(this.id, 'failed', { taskType, error: String(err) })
      return errorResult
    }
  }
}
