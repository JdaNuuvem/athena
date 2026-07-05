import { EventEmitter } from 'events'
import type { AgentId } from '../core/agent-types'
import type { WorkflowDefinition, WorkflowStep, WorkflowStatus, WorkflowInstance } from './workflow-definitions'

export interface OrchestrationEngine {
  deploy(workflow: WorkflowDefinition): void
  trigger(workflowName: string, input: Record<string, unknown>): Promise<WorkflowInstance>
  getInstance(instanceId: string): WorkflowInstance | undefined
  getWorkflowStatus(instanceId: string): { status: WorkflowStatus } | undefined
  status(instanceId: string): WorkflowStatus | null
  cancel(instanceId: string): void
  readonly events: EventEmitter
}

interface StepState {
  step: WorkflowStep
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  result?: Record<string, unknown>
  error?: string
  startedAt?: Date
  completedAt?: Date
}

interface InstanceState extends WorkflowInstance {
  steps: StepState[]
}

export class DAGOrchestrationEngine implements OrchestrationEngine {
  private workflows = new Map<string, WorkflowDefinition>()
  private instances = new Map<string, InstanceState>()
  public readonly events = new EventEmitter()

  private agents = new Map<AgentId, { handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> }>()

  registerAgent(agentId: AgentId, handler: { handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> }): void {
    this.agents.set(agentId, handler)
  }

  deploy(workflow: WorkflowDefinition): void {
    this.workflows.set(workflow.name, workflow)
    this.events.emit('workflow-deployed', { name: workflow.name, version: workflow.version })
  }

  async trigger(workflowName: string, input: Record<string, unknown>): Promise<WorkflowInstance> {
    const workflow = this.workflows.get(workflowName)
    if (!workflow) throw new Error(`Workflow "${workflowName}" not found`)

    const instanceId = `${workflowName}-${Date.now()}`
    const steps = this.buildStepStates(workflow)
    const instance: InstanceState = {
      instanceId,
      workflowName,
      status: 'running',
      input,
      startedAt: new Date(),
      steps,
    }
    this.instances.set(instanceId, instance)
    this.events.emit('workflow-started', { instanceId, workflowName })

    await this.executeReadySteps(instance, input)

    return instance
  }

  getInstance(instanceId: string): WorkflowInstance | undefined {
    return this.instances.get(instanceId)
  }

  getWorkflowStatus(instanceId: string): { status: WorkflowStatus } | undefined {
    const instance = this.instances.get(instanceId)
    if (!instance) return undefined
    return { status: instance.status }
  }

  status(instanceId: string): WorkflowStatus | null {
    return this.instances.get(instanceId)?.status ?? null
  }

  cancel(instanceId: string): void {
    const instance = this.instances.get(instanceId)
    if (!instance) return
    instance.status = 'cancelled'
    this.events.emit('workflow-cancelled', { instanceId, workflowName: instance.workflowName })
  }

  private buildStepStates(workflow: WorkflowDefinition): StepState[] {
    return workflow.steps.map(step => ({ step, status: 'pending' }))
  }

  private async executeReadySteps(instance: InstanceState, input: Record<string, unknown>): Promise<void> {
    const ready = this.getReadySteps(instance)
    if (ready.length === 0) {
      const allDone = instance.steps.every(s => s.status === 'completed' || s.status === 'skipped')
      const anyFailed = instance.steps.some(s => s.status === 'failed')
      instance.status = anyFailed ? 'failed' : allDone ? 'completed' : 'failed'
      instance.completedAt = new Date()
      this.events.emit('workflow-completed', { instanceId: instance.instanceId, status: instance.status })
      return
    }

    const results = await Promise.allSettled(
      ready.map(stepState => this.executeStep(stepState, input, instance)),
    )

    const context: Record<string, unknown> = { ...input }
    for (const [i, result] of results.entries()) {
      if (result.status === 'fulfilled' && result.value) {
        context[ready[i]!.step.id] = result.value
      }
    }

    await this.executeReadySteps(instance, context)
  }

  private async executeStep(stepState: StepState, _context: Record<string, unknown>, instance: InstanceState): Promise<Record<string, unknown> | undefined> {
    stepState.status = 'running'
    stepState.startedAt = new Date()
    this.events.emit('step-started', { instanceId: instance.instanceId, stepId: stepState.step.id })

    try {
      const agent = stepState.step.targetAgentId ? this.agents.get(stepState.step.targetAgentId) : undefined
      const result = agent
        ? await agent.handleTask({ workflowStep: stepState.step.id, ...stepState.step.config })
        : { status: 'ok', step: stepState.step.id }

      stepState.result = result
      stepState.status = 'completed'
      stepState.completedAt = new Date()
      this.events.emit('step-completed', { instanceId: instance.instanceId, stepId: stepState.step.id })
      return result
    } catch (err) {
      stepState.error = String(err)
      stepState.status = 'failed'
      stepState.completedAt = new Date()
      this.events.emit('step-failed', { instanceId: instance.instanceId, stepId: stepState.step.id, error: String(err) })
      throw err
    }
  }

  private getReadySteps(instance: InstanceState): StepState[] {
    const pending = instance.steps.filter(s => s.status === 'pending')
    const completed = new Set(instance.steps.filter(s => s.status === 'completed').map(s => s.step.id))
    const failed = new Set(instance.steps.filter(s => s.status === 'failed').map(s => s.step.id))
    const skipped = new Set(instance.steps.filter(s => s.status === 'skipped').map(s => s.step.id))

    return pending.filter(stepState => {
      const deps = stepState.step.dependsOn ?? []
      if (deps.length === 0) return true
      return deps.every(depId => {
        if (completed.has(depId)) return true
        if (skipped.has(depId)) return true
        if (failed.has(depId) && stepState.step.onDepFailure === 'skip') {
          stepState.status = 'skipped'
          return false
        }
        return false
      })
    })
  }
}
