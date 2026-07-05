import { AgentRuntime } from '../../core/agent-runtime'
import { AgentContext } from '../../core/agent-context'
import { DefaultMemoryManager } from '../../memory/memory-manager'
import { DefaultToolRegistry, type ToolDefinition } from '../../tools/tool-registry'
import { ToolExecutor } from '../../tools/tool-executor'
import { createRealMarketplaceTools } from '../../tools/real-integration-tools'
import type { AgentDefinition } from '../../core/agent-types'

const DEFINITION: AgentDefinition = {
  id: 'ag-022', name: 'listing-synchronizer', role: 'executor', context: 'marketplace-integration',
  systemPrompt: 'Você é o Listing Synchronizer. Publica e mantém produtos nos marketplaces via API real.',
  capabilities: [{ name: 'marketplace.publishML', description: 'Publish to ML', inputSchema: {}, outputSchema: {} }],
  config: { modelProvider: 'openai', modelName: 'gpt-4o-mini', temperature: 0.2, maxTokens: 1024, retryPolicy: { maxRetries: 3, backoffMs: 2000 }, timeout: 30000 },
}

const tools: ToolDefinition[] = createRealMarketplaceTools()

export class ListingSyncAgent extends AgentRuntime {
  private exec: ToolExecutor
  constructor() {
    const memory = new DefaultMemoryManager(); const registry = new DefaultToolRegistry()
    for (const t of tools) registry.register(t)
    super('ag-022', DEFINITION, new AgentContext('ag-022', memory, registry))
    this.exec = new ToolExecutor(registry)
  }
  override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> {
    await super.handleTask(task)
    if (task['type'] === 'publish_listing') {
      const r = await this.exec.execute('marketplace.publishML', task)
      return { ...task, result: r }
    }
    if (task['type'] === 'sync_stock') {
      const r = await this.exec.execute('marketplace.syncStock', task)
      return { ...task, result: r }
    }
    return super.handleTask(task)
  }
}
