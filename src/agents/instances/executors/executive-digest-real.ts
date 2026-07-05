import { AgentRuntime } from '../../core/agent-runtime'
import { AgentContext } from '../../core/agent-context'
import { DefaultMemoryManager } from '../../memory/memory-manager'
import { DefaultToolRegistry, type ToolDefinition } from '../../tools/tool-registry'
import { ToolExecutor } from '../../tools/tool-executor'
import { createRealEmailTools } from '../../tools/real-integration-tools'
import type { AgentDefinition } from '../../core/agent-types'

const DEFINITION: AgentDefinition = {
  id: 'ag-048', name: 'executive-digest', role: 'executor', context: 'analytics',
  systemPrompt: 'Você é o Executive Digest. Gera e envia relatórios executivos por email.',
  capabilities: [{ name: 'email.sendDigest', description: 'Send daily digest', inputSchema: {}, outputSchema: {} }],
  config: { modelProvider: 'openai', modelName: 'gpt-4o-mini', temperature: 0.2, maxTokens: 2048, retryPolicy: { maxRetries: 2, backoffMs: 1000 }, timeout: 30000 },
}

const tools: ToolDefinition[] = createRealEmailTools()

export class ExecutiveDigestAgent extends AgentRuntime {
  private exec: ToolExecutor
  constructor() {
    const memory = new DefaultMemoryManager(); const registry = new DefaultToolRegistry()
    for (const t of tools) registry.register(t)
    super('ag-048', DEFINITION, new AgentContext('ag-048', memory, registry))
    this.exec = new ToolExecutor(registry)
  }
  override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> {
    await super.handleTask(task)
    if (task['type'] === 'send_digest') {
      const r = await this.exec.execute('email.sendDigest', task)
      return { ...task, result: r }
    }
    if (task['type'] === 'send_alert') {
      const r = await this.exec.execute('email.sendAlert', task)
      return { ...task, result: r }
    }
    return super.handleTask(task)
  }
}
