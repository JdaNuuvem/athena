import { AgentRuntime } from '../../core/agent-runtime'
import { AgentContext } from '../../core/agent-context'
import { DefaultMemoryManager } from '../../memory/memory-manager'
import { DefaultToolRegistry, type ToolDefinition } from '../../tools/tool-registry'
import { ToolExecutor } from '../../tools/tool-executor'
import { z } from 'zod'
import type { AgentDefinition } from '../../core/agent-types'

const DEFINITION: AgentDefinition = {
  id: 'ag-002', name: 'bom-validator', role: 'decision-maker', context: 'product-engineering',
  systemPrompt: `Você é o BOM Validator. Valida consistência da Bill of Materials, detecta componentes faltantes, conflitos de revisão e duplicatas.`,
  capabilities: [{ name: 'bom.validate', description: 'Validate BOM', inputSchema: {}, outputSchema: {} }],
  config: { modelProvider: 'openai', modelName: 'gpt-4o-mini', temperature: 0.2, maxTokens: 1024, retryPolicy: { maxRetries: 2, backoffMs: 500 }, timeout: 15000 },
}

const tools: ToolDefinition[] = [
  {
    name: 'bom.validate',
    description: 'Valida consistência de uma Bill of Materials',
    inputSchema: z.object({ bomId: z.string(), productId: z.string(), components: z.array(z.object({ componentId: z.string(), name: z.string(), quantity: z.number(), materialSpec: z.string().optional() })) }),
    outputSchema: z.object({ valid: z.boolean(), issues: z.array(z.string()), duplicateCount: z.number(), missingCount: z.number() }),
    handler: async (input: unknown) => {
      const data = input as { components: Array<{ componentId: string }> }
      const ids = data.components.map(c => c.componentId)
      const duplicates = ids.filter((id, i) => ids.indexOf(id) !== i)
      return { valid: duplicates.length === 0, issues: duplicates.length > 0 ? [`Componentes duplicados: ${duplicates.join(', ')}`] : [], duplicateCount: duplicates.length, missingCount: 0 }
    },
  },
  {
    name: 'bom.checkRevision',
    description: 'Verifica conflitos de revisão entre componentes',
    inputSchema: z.object({ bomId: z.string(), currentRevision: z.string(), componentRevisions: z.record(z.string()) }),
    outputSchema: z.object({ hasConflicts: z.boolean(), conflicts: z.array(z.object({ componentId: z.string(), expectedRevision: z.string(), actualRevision: z.string() })) }),
    handler: async (input: unknown) => {
      const data = input as { componentRevisions: Record<string, string> }
      const conflicts = Object.entries(data.componentRevisions).filter(([, rev]) => rev === 'deprecated').map(([id]) => ({ componentId: id, expectedRevision: 'latest', actualRevision: 'deprecated' }))
      return { hasConflicts: conflicts.length > 0, conflicts }
    },
  },
]

export class BOMValidatorAgent extends AgentRuntime {
  private executor: ToolExecutor
  constructor() {
    const memory = new DefaultMemoryManager()
    const registry = new DefaultToolRegistry()
    for (const t of tools) registry.register(t)
    super('ag-002', DEFINITION, new AgentContext('ag-002', memory, registry))
    this.executor = new ToolExecutor(registry)
  }
  override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> {
    await super.handleTask(task)
    if (task['type'] === 'validate_bom') {
      const result = await this.executor.execute('bom.validate', task)
      return { ...task, result }
    }
    return super.handleTask(task)
  }
}
