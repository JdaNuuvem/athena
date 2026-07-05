import { EventEmitter } from 'events'
import type { AgentId } from '../core/agent-types'

export interface SagaStep {
  readonly id: string
  readonly action: (input: Record<string, unknown>) => Promise<Record<string, unknown>>
  readonly compensation: (input: Record<string, unknown>) => Promise<void>
  readonly timeout?: number
}

export interface SagaDefinition {
  readonly name: string
  readonly steps: SagaStep[]
  readonly retryPolicy?: { maxRetries: number; backoffMs: number }
}

export interface SagaInstance {
  readonly sagaId: string
  readonly sagaName: string
  status: 'running' | 'completed' | 'compensating' | 'failed' | 'compensated'
  readonly startedAt: Date
  completedAt?: Date
  currentStep: number
  readonly results: Record<string, unknown>[]
  errors: string[]
}

export interface SagaCoordinator {
  execute(saga: SagaDefinition, input: Record<string, unknown>): Promise<SagaInstance>
  getInstance(sagaId: string): SagaInstance | undefined
  readonly events: EventEmitter
}

export class DefaultSagaCoordinator implements SagaCoordinator {
  private instances = new Map<string, SagaInstance>()
  public readonly events = new EventEmitter()

  async execute(saga: SagaDefinition, input: Record<string, unknown>): Promise<SagaInstance> {
    const sagaId = `${saga.name}-${Date.now()}`
    const instance: SagaInstance = {
      sagaId,
      sagaName: saga.name,
      status: 'running',
      startedAt: new Date(),
      currentStep: 0,
      results: [],
      errors: [],
    }
    this.instances.set(sagaId, instance)
    this.events.emit('saga-started', { sagaId, sagaName: saga.name })

    try {
      for (let i = 0; i < saga.steps.length; i++) {
        const step = saga.steps[i]!
        instance.currentStep = i
        this.events.emit('saga-step-started', { sagaId, stepId: step.id, stepIndex: i })

        try {
          const maxRetries = saga.retryPolicy?.maxRetries ?? 0
          let lastError: unknown
          for (let attempt = 0; attempt <= maxRetries; attempt++) {
            try {
              const result = await this.withTimeout(
                step.action({ ...input, ...this.mergeResults(instance.results) }),
                step.timeout ?? 30000,
              )
              instance.results.push(result)
              this.events.emit('saga-step-completed', { sagaId, stepId: step.id, stepIndex: i })
              break
            } catch (err) {
              lastError = err
              if (attempt < maxRetries && saga.retryPolicy) {
                await new Promise(r => setTimeout(r, saga.retryPolicy!.backoffMs))
              }
            }
          }
          if (instance.results.length <= i) {
            throw lastError
          }
        } catch (err) {
          instance.errors.push(String(err))
          this.events.emit('saga-step-failed', { sagaId, stepId: step.id, error: String(err) })
          await this.compensate(instance, saga, input, i)
          return instance
        }
      }

      instance.status = 'completed'
      instance.completedAt = new Date()
      this.events.emit('saga-completed', { sagaId })
      return instance
    } catch (err) {
      instance.status = 'failed'
      instance.errors.push(String(err))
      instance.completedAt = new Date()
      return instance
    }
  }

  getInstance(sagaId: string): SagaInstance | undefined {
    return this.instances.get(sagaId)
  }

  private async compensate(instance: SagaInstance, saga: SagaDefinition, input: Record<string, unknown>, failedStepIndex: number): Promise<void> {
    instance.status = 'compensating'
    this.events.emit('saga-compensating', { sagaId: instance.sagaId, failedStep: failedStepIndex })

    for (let i = failedStepIndex; i >= 0; i--) {
      const step = saga.steps[i]!
      try {
        await step.compensation(input)
      } catch (err) {
        instance.errors.push(`compensate-${step.id}: ${String(err)}`)
      }
    }

    instance.status = 'compensated'
    instance.completedAt = new Date()
    this.events.emit('saga-compensated', { sagaId: instance.sagaId })
  }

  private mergeResults(results: Record<string, unknown>[]): Record<string, unknown> {
    return results.reduce((acc, r) => ({ ...acc, ...r }), {})
  }

  private withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
    return Promise.race([
      promise,
      new Promise<T>((_, reject) => setTimeout(() => reject(new Error('Saga step timed out')), ms)),
    ])
  }
}
