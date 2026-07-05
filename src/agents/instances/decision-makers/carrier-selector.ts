import { AgentRuntime } from '../../core/agent-runtime'
import { AgentContext } from '../../core/agent-context'
import { DefaultMemoryManager } from '../../memory/memory-manager'
import { DefaultToolRegistry } from '../../tools/tool-registry'
import { ToolExecutor } from '../../tools/tool-executor'
import { z } from 'zod'
import type { AgentDefinition } from '../../core/agent-types'

const CARRIER_SELECTOR_DEFINITION: AgentDefinition = {
  id: 'ag-042',
  name: 'carrier-selector',
  role: 'decision-maker',
  context: 'shipping',
  systemPrompt: `Você é o Carrier Selector, agente decisor do contexto de Shipping.
Seleciona a transportadora ótima por pedido baseado em:
- Menor custo de frete
- Prazo de entrega
- Confiabilidade da transportadora
- Cobertura geográfica`,
  capabilities: [
    { name: 'shipping.selectCarrier', description: 'Select optimal carrier for shipment', inputSchema: {}, outputSchema: {} },
  ],
  config: {
    modelProvider: 'openai', modelName: 'gpt-4o-mini',
    temperature: 0.2, maxTokens: 1024,
    retryPolicy: { maxRetries: 2, backoffMs: 1000 }, timeout: 15000,
  },
}

export class CarrierSelectorAgent extends AgentRuntime {
  private executor: ToolExecutor

  constructor() {
    const memory = new DefaultMemoryManager()
    const tools = new DefaultToolRegistry()
    const context = new AgentContext('ag-042', memory, tools)

    tools.register({
      name: 'shipping.selectCarrier',
      description: 'Seleciona transportadora ótima',
      inputSchema: z.object({ orderId: z.string(), destination: z.string(), weight: z.number() }),
      outputSchema: z.object({
        orderId: z.string(),
        carrier: z.string(),
        service: z.string(),
        cost: z.number(),
        estimatedDays: z.number(),
        score: z.number(),
      }),
      handler: async (input: unknown) => {
        const data = input as { orderId: string; destination: string; weight: number }
        const carriers = [
          { name: 'Correios', service: 'SEDEX', baseCost: 25 },
          { name: 'Jadlog', service: 'Express', baseCost: 18 },
          { name: 'Loggi', service: 'SameDay', baseCost: 22 },
        ]
        const chosen = carriers[0] ?? { name: 'Correios', service: 'SEDEX', baseCost: 25 }
        const cost = chosen.baseCost + Math.floor(data.weight * 2)
        return {
          orderId: data.orderId,
          carrier: chosen.name,
          service: chosen.service,
          cost,
          estimatedDays: 1 + Math.floor(Math.random() * 5),
          score: 85 + Math.floor(Math.random() * 15),
        }
      },
    })

    tools.register({
      name: 'shipping.getTracking',
      description: 'Consulta rastreamento de envio',
      inputSchema: z.object({ trackingCode: z.string() }),
      outputSchema: z.object({ trackingCode: z.string(), status: z.string(), lastUpdate: z.string(), location: z.string() }),
      handler: async (input: unknown) => {
        const data = input as { trackingCode: string }
        return { trackingCode: data.trackingCode, status: 'in_transit', lastUpdate: new Date().toISOString(), location: 'Centro de Distribuição' }
      },
    })

    super('ag-042', CARRIER_SELECTOR_DEFINITION, context)
    this.executor = new ToolExecutor(tools)
  }

  override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> {
    await super.handleTask(task)
    if (task['type'] === 'select_carrier') {
      const result = await this.executor.execute('shipping.selectCarrier', task)
      this.context.memory.episodic.record({
        type: 'carrier.selected', agentId: this.id,
        data: { orderId: task['orderId'] as string, result },
      })
      return { ...task, result }
    }
    return super.handleTask(task)
  }
}
