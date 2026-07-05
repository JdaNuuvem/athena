import { z } from 'zod'

export const TaskPrioritySchema = z.enum(['low', 'normal', 'high', 'critical'])
export type TaskPriority = z.infer<typeof TaskPrioritySchema>

export const TaskStatusSchema = z.enum(['pending', 'running', 'completed', 'failed', 'dead-letter'])
export type TaskStatus = z.infer<typeof TaskStatusSchema>

export interface TaskDefinition {
  readonly id: string
  readonly type: string
  readonly priority: TaskPriority
  readonly input: Record<string, unknown>
  readonly targetAgentId?: string
  readonly deadline?: Date
  readonly retryPolicy?: { maxRetries: number; backoffMs: number }
  readonly correlationId?: string
  status: TaskStatus
  readonly createdAt: Date
  startedAt?: Date
  completedAt?: Date
  error?: string
  result?: Record<string, unknown>
  retryCount: number
}

export type TaskHandler = (task: TaskDefinition) => Promise<Record<string, unknown>>
