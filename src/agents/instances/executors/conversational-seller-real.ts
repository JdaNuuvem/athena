import { AgentRuntime } from '../../core/agent-runtime'
import { AgentContext } from '../../core/agent-context'
import { DefaultMemoryManager } from '../../memory/memory-manager'
import { DefaultToolRegistry, type ToolDefinition } from '../../tools/tool-registry'
import { ToolExecutor } from '../../tools/tool-executor'
import { createRealTelegramTools } from '../../tools/real-integration-tools'
import type { AgentDefinition } from '../../core/agent-types'

const DEFINITION: AgentDefinition = {
  id: 'ag-028', name: 'conversational-seller', role: 'executor', context: 'telegram-commerce',
  systemPrompt: 'Você é o Conversational Seller. Conduz vendas via Telegram enviando cards de produto e respondendo dúvidas.',
  capabilities: [{ name: 'telegram.sendProduct', description: 'Send product card', inputSchema: {}, outputSchema: {} }],
  config: { modelProvider: 'openai', modelName: 'gpt-4o-mini', temperature: 0.3, maxTokens: 1024, retryPolicy: { maxRetries: 2, backoffMs: 500 }, timeout: 15000 },
}

const tools: ToolDefinition[] = createRealTelegramTools()

export class ConversationalSellerAgent extends AgentRuntime {
  private exec: ToolExecutor
  constructor() {
    const memory = new DefaultMemoryManager(); const registry = new DefaultToolRegistry()
    for (const t of tools) registry.register(t)
    super('ag-028', DEFINITION, new AgentContext('ag-028', memory, registry))
    this.exec = new ToolExecutor(registry)
  }
  override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> {
    await super.handleTask(task)
    if (task['type'] === 'send_product_card') {
      const r = await this.exec.execute('telegram.sendProduct', task)
      return { ...task, result: r }
    }
    if (task['type'] === 'send_order_status') {
      const r = await this.exec.execute('telegram.sendOrderStatus', task)
      return { ...task, result: r }
    }
    return super.handleTask(task)
  }
}
