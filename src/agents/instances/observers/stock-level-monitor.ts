import { AgentRuntime } from '../../core/agent-runtime'
import { AgentContext } from '../../core/agent-context'
import { DefaultMemoryManager } from '../../memory/memory-manager'
import { DefaultToolRegistry } from '../../tools/tool-registry'
import { ToolExecutor } from '../../tools/tool-executor'
import { createStockLevelTools } from './stock-level-tools'
import { createRealStockTools } from '../../tools/real-integration-tools'
import type { AgentDefinition } from '../../core/agent-types'

const STOCK_MONITOR_DEFINITION: AgentDefinition = {
  id: 'ag-031',
  name: 'stock-level-monitor',
  role: 'observer',
  context: 'inventory',
  systemPrompt: `Você é o Stock Level Monitor, agente observador do contexto de Inventory.
Sua responsabilidade é monitorar níveis de estoque, disparar alertas de ponto de reposição,
detectar ruptura ou excesso de estoque. Você NÃO toma decisões, apenas observa e alerta.`,
  capabilities: [
    { name: 'inventory.checkStock', description: 'Check stock level for SKU', inputSchema: {}, outputSchema: {} },
    { name: 'inventory.sendAlert', description: 'Send low stock alert', inputSchema: {}, outputSchema: {} },
  ],
  config: {
    modelProvider: 'openai',
    modelName: 'gpt-4o-mini',
    temperature: 0.3,
    maxTokens: 1024,
    retryPolicy: { maxRetries: 2, backoffMs: 1000 },
    timeout: 30000,
  },
}

export class StockLevelMonitorAgent extends AgentRuntime {
  private executor: ToolExecutor

  constructor() {
    const memory = new DefaultMemoryManager({ stMaxSize: 500 })
    const tools = new DefaultToolRegistry()
    const context = new AgentContext('ag-031', memory, tools)

    for (const tool of createRealStockTools()) tools.register(tool)

    super('ag-031', STOCK_MONITOR_DEFINITION, context)

    this.executor = new ToolExecutor(tools)
  }

  override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> {
    await super.handleTask(task)

    if (task['type'] === 'check_stock') {
      const result = await this.executor.execute('inventory.checkReal', task)
      if (result.success && result.data) {
        const data = result.data as Record<string, unknown>
        if (data['status'] === 'low' || data['status'] === 'critical') {
          await this.executor.execute('inventory.sendAlert', {
            sku: data['sku'],
            level: data['status'],
            message: `ALERTA: ${String(data['sku'])} está ${String(data['status'])} (qtd: ${String(data['quantity'])})`,
          })
        }
      }
      return { ...task, result }
    }

    return super.handleTask(task)
  }
}

export function createStockLevelMonitor(): StockLevelMonitorAgent {
  return new StockLevelMonitorAgent()
}
