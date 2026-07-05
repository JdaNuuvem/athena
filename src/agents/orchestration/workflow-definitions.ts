import type { AgentId } from '../core/agent-types'

export type WorkflowStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface WorkflowStep {
  readonly id: string
  readonly label: string
  readonly targetAgentId?: AgentId
  readonly dependsOn?: string[]
  readonly onDepFailure?: 'skip' | 'fail'
  readonly config: Record<string, unknown>
  readonly timeout?: number
  readonly retry?: { maxRetries: number; backoffMs: number }
}

export interface WorkflowDefinition {
  readonly name: string
  readonly version: string
  readonly description: string
  readonly trigger: { event: string } | { cron: string } | { manual: true }
  readonly steps: WorkflowStep[]
  readonly timeout?: number
  readonly onFailure?: 'rollback' | 'compensate' | 'alert'
}

export interface WorkflowInstance {
  readonly instanceId: string
  readonly workflowName: string
  status: WorkflowStatus
  readonly input: Record<string, unknown>
  readonly startedAt: Date
  completedAt?: Date
  readonly steps: Array<{
    step: WorkflowStep
    status: string
    result?: Record<string, unknown>
    error?: string
    startedAt?: Date
    completedAt?: Date
  }>
}

export function defineWorkflow(def: Omit<WorkflowDefinition, 'version'> & { version?: string }): WorkflowDefinition {
  return { ...def, version: def.version ?? '1.0' }
}

export const sampleProductDesignWorkflow = defineWorkflow({
  name: 'product-design-review',
  description: 'Workflow completo de revisao de design de produto',
  trigger: { event: 'product-engineering.v1.product.designed' },
  onFailure: 'alert',
  steps: [
    {
      id: 'validate-spec',
      label: 'Validar Especificacao',
      targetAgentId: 'AG-001',
      config: { tool: 'validate-specification' },
      timeout: 30000,
    },
    {
      id: 'check-bom',
      label: 'Verificar BOM',
      targetAgentId: 'AG-001',
      dependsOn: ['validate-spec'],
      config: { tool: 'check-bom-completeness' },
      timeout: 30000,
    },
    {
      id: 'quality-review',
      label: 'Revisao de Qualidade',
      dependsOn: ['validate-spec', 'check-bom'],
      config: {},
      onDepFailure: 'skip',
    },
  ],
})
