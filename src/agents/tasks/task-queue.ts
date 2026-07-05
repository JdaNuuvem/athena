import { TaskDefinition, TaskStatus, TaskPriority } from './task-definition'

const priorityWeight: Record<TaskPriority, number> = { critical: 4, high: 3, normal: 2, low: 1 }

export interface TaskQueue {
  enqueue(task: TaskDefinition): void
  dequeue(agentId?: string): TaskDefinition | undefined
  peek(agentId?: string): TaskDefinition | undefined
  size(agentId?: string): number
  list(agentId?: string): TaskDefinition[]
  mark(id: string, status: TaskStatus, result?: Record<string, unknown>, error?: string): void
  get(id: string): TaskDefinition | undefined
}

export class InMemoryTaskQueue implements TaskQueue {
  private tasks = new Map<string, TaskDefinition>()

  enqueue(task: TaskDefinition): void {
    this.tasks.set(task.id, task)
  }

  dequeue(agentId?: string): TaskDefinition | undefined {
    const pending = this.listPending(agentId)
    if (!pending.length) return undefined
    pending.sort((a, b) => priorityWeight[b.priority] - priorityWeight[a.priority] || a.createdAt.getTime() - b.createdAt.getTime())
    return pending[0]
  }

  peek(agentId?: string): TaskDefinition | undefined {
    return this.dequeue(agentId)
  }

  size(agentId?: string): number {
    return this.listPending(agentId).length
  }

  list(agentId?: string): TaskDefinition[] {
    return agentId
      ? [...this.tasks.values()].filter(t => !t.targetAgentId || t.targetAgentId === agentId)
      : [...this.tasks.values()]
  }

  mark(id: string, status: TaskStatus, result?: Record<string, unknown>, error?: string): void {
    const task = this.tasks.get(id)
    if (!task) return
    task.status = status
    if (status === 'completed') { task.completedAt = new Date(); task.result = result }
    if (status === 'failed') { task.error = error; task.retryCount++ }
  }

  get(id: string): TaskDefinition | undefined {
    return this.tasks.get(id)
  }

  private listPending(agentId?: string): TaskDefinition[] {
    return this.list(agentId).filter(t => t.status === 'pending')
  }
}
