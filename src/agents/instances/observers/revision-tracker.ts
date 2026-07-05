import { AgentRuntime } from '../../core/agent-runtime'
import { AgentContext } from '../../core/agent-context'
import { DefaultMemoryManager } from '../../memory/memory-manager'
import { DefaultToolRegistry, type ToolDefinition } from '../../tools/tool-registry'
import { ToolExecutor } from '../../tools/tool-executor'
import { z } from 'zod'
import type { AgentDefinition } from '../../core/agent-types'

const DEFINITION: AgentDefinition = {
  id: 'ag-003', name: 'revision-tracker', role: 'observer', context: 'product-engineering',
  systemPrompt: `Você é o Revision Tracker. Monitora ciclo de revisões, alerta sobre revisões pendentes de aprovação há mais de X dias, mantém histórico de mudanças.`,
  capabilities: [{ name: 'revision.track', description: 'Track revisions', inputSchema: {}, outputSchema: {} }],
  config: { modelProvider: 'openai', modelName: 'gpt-4o-mini', temperature: 0.2, maxTokens: 1024, retryPolicy: { maxRetries: 1, backoffMs: 500 }, timeout: 15000 },
}

const tools: ToolDefinition[] = [
  {
    name: 'revision.track',
    description: 'Rastreia status de revisões de produto',
    inputSchema: z.object({ productId: z.string(), revisions: z.array(z.object({ revisionId: z.string(), number: z.string(), status: z.enum(['draft', 'pending', 'approved', 'rejected', 'archived']), createdAt: z.string(), author: z.string() })) }),
    outputSchema: z.object({ pendingCount: z.number(), overdueCount: z.number(), staleDays: z.number(), recommendations: z.array(z.string()) }),
    handler: async (input: unknown) => {
      const data = input as { revisions: Array<{ status: string; createdAt: string }> }
      const pending = data.revisions.filter(r => r.status === 'pending')
      const now = Date.now()
      const overdue = pending.filter(r => now - new Date(r.createdAt).getTime() > 7 * 86400000)
      return { pendingCount: pending.length, overdueCount: overdue.length, staleDays: overdue.length > 0 ? 7 : 0, recommendations: overdue.length > 0 ? [`${overdue.length} revisões pendentes há mais de 7 dias — requer atenção`] : [] }
    },
  },
  {
    name: 'revision.compare',
    description: 'Compara duas revisões e destaca diferenças',
    inputSchema: z.object({ productId: z.string(), fromRevision: z.string(), toRevision: z.string(), changes: z.record(z.string()) }),
    outputSchema: z.object({ changedFields: z.array(z.string()), summary: z.string() }),
    handler: async (input: unknown) => {
      const data = input as { changes: Record<string, string> }
      const fields = Object.keys(data.changes)
      return { changedFields: fields, summary: `${fields.length} campos alterados: ${fields.join(', ')}` }
    },
  },
]

export class RevisionTrackerAgent extends AgentRuntime {
  private executor: ToolExecutor
  constructor() {
    const memory = new DefaultMemoryManager()
    const registry = new DefaultToolRegistry()
    for (const t of tools) registry.register(t)
    super('ag-003', DEFINITION, new AgentContext('ag-003', memory, registry))
    this.executor = new ToolExecutor(registry)
  }
  override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> {
    await super.handleTask(task)
    if (task['type'] === 'track_revisions') {
      const result = await this.executor.execute('revision.track', task)
      return { ...task, result }
    }
    return super.handleTask(task)
  }
}
