import type { AgentId } from '../core/agent-types'
import type { TaskDefinition } from '../tasks/task-definition'
import type { TaskQueue } from '../tasks/task-queue'
import type { AgentRegistry } from '../registry/agent-registry'
import type { CapabilityRegistry } from '../registry/capability-registry'

export interface TaskDispatcher {
  dispatch(task: Omit<TaskDefinition, 'id' | 'status' | 'createdAt' | 'retryCount'>): TaskDefinition
  dispatchToBest(task: Omit<TaskDefinition, 'id' | 'status' | 'createdAt' | 'retryCount' | 'targetAgentId'>): TaskDefinition
  route(task: TaskDefinition): void
}

export class CapabilityTaskDispatcher implements TaskDispatcher {
  constructor(
    private taskQueue: TaskQueue,
    private agentRegistry: AgentRegistry,
    private capabilityRegistry: CapabilityRegistry,
  ) {}

  dispatch(task: Omit<TaskDefinition, 'id' | 'status' | 'createdAt' | 'retryCount'>): TaskDefinition {
    const full: TaskDefinition = {
      ...task, id: `task-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      status: 'pending', createdAt: new Date(), retryCount: 0,
    }
    this.taskQueue.enqueue(full)
    return full
  }

  dispatchToBest(task: Omit<TaskDefinition, 'id' | 'status' | 'createdAt' | 'retryCount' | 'targetAgentId'>): TaskDefinition {
    const capName = task.type.replace(/_/g, '-')
    const candidates = this.capabilityRegistry.findAgentsFor(capName)
    let best: AgentId | undefined
    if (candidates.length > 0) {
      const running = candidates
        .map(id => this.agentRegistry.get(id))
        .filter((a): a is NonNullable<typeof a> => a !== undefined && a.status === 'running')
      if (running.length > 0) best = running[0]!.id
    }
    if (!best) { const all = this.agentRegistry.list({ status: 'running' }); if (all.length > 0) best = all[0]!.id }
    return this.dispatch({ ...task, targetAgentId: best })
  }

  route(task: TaskDefinition): void {
    const agentId = task.targetAgentId
    if (!agentId) return
    const agent = this.agentRegistry.get(agentId)
    if (!agent || agent.status !== 'running') { this.taskQueue.mark(task.id, 'failed', undefined, 'Agent not available'); return }
    this.taskQueue.mark(task.id, 'running')
    agent.handleTask(task as Record<string, unknown>)
      .then((r: Record<string, unknown>) => this.taskQueue.mark(task.id, 'completed', r))
      .catch((e: unknown) => this.taskQueue.mark(task.id, 'failed', undefined, String(e)))
  }
}
