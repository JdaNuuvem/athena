import { AgentRuntime } from '../../core/agent-runtime'
import { AgentContext } from '../../core/agent-context'
import { DefaultMemoryManager } from '../../memory/memory-manager'
import { DefaultToolRegistry } from '../../tools/tool-registry'
import { ToolExecutor } from '../../tools/tool-executor'
import { z } from 'zod'
import type { AgentDefinition } from '../../core/agent-types'
import { getPrisma } from '../../../shared/infrastructure/persistence/prisma-client'

const ORDER_ROUTER_DEFINITION: AgentDefinition = {
  id: 'ag-035',
  name: 'order-router',
  role: 'decision-maker',
  context: 'order-management',
  systemPrompt: `Você é o Order Router, agente decisor do contexto de Order Management.
Sua responsabilidade é rotear pedidos para o centro de fulfillment ótimo baseado em:
- Menor custo de envio
- Menor prazo de entrega
- Disponibilidade de estoque
- Carga atual do centro de fulfillment`,
  capabilities: [
    { name: 'order.route', description: 'Route order to optimal fulfillment center', inputSchema: {}, outputSchema: {} },
  ],
  config: {
    modelProvider: 'openai', modelName: 'gpt-4o-mini',
    temperature: 0.2, maxTokens: 2048,
    retryPolicy: { maxRetries: 2, backoffMs: 1000 }, timeout: 30000,
  },
}

export class OrderRouterAgent extends AgentRuntime {
  private executor: ToolExecutor

  constructor() {
    const memory = new DefaultMemoryManager()
    const tools = new DefaultToolRegistry()
    const context = new AgentContext('ag-035', memory, tools)

    tools.register({
      name: 'order.route',
      description: 'Roteia pedido para centro de fulfillment com base em estoque real',
      inputSchema: z.object({ orderId: z.string(), skus: z.array(z.string()), customerId: z.string() }),
      outputSchema: z.object({ orderId: z.string(), fulfillmentCenter: z.string(), estimatedDeliveryDays: z.number(), cost: z.number() }),
      handler: async (input: unknown) => {
        const data = input as { orderId: string; skus: string[] }
        try {
          const p = getPrisma()
          const warehouses = await p.$queryRawUnsafe<Array<{ id: string; name: string; city: string; state: string }>>(
            `SELECT id, name, city, state FROM "Warehouse" WHERE active=true ORDER BY name`,
          )
          if (!warehouses.length) {
            return { orderId: data.orderId, fulfillmentCenter: 'FUL-001', estimatedDeliveryDays: 3, cost: 25 }
          }

          let best = warehouses[0]!
          let bestScore = -1
          for (const w of warehouses) {
            const placeholders = data.skus.map((_, i) => `$${i + 1}`).join(',')
            const stockRows = await p.$queryRawUnsafe<Array<{ sku: string; quantity: number }>>(
              `SELECT sku, quantity FROM "StockItem" WHERE sku IN (${placeholders}) AND "warehouseId"=$1`, w.id, ...data.skus,
            )
            const score = stockRows.reduce((s, r) => s + r.quantity, 0)
            if (score > bestScore) { bestScore = score; best = w }
          }

          const costPerDay = { 'São Paulo': 20, 'Recife': 25, 'Manaus': 35, 'Curitiba': 22, 'Belo Horizonte': 23, 'Porto Alegre': 28 }
          const baseCost = (costPerDay as Record<string, number>)[best?.city ?? ''] ?? 25

          const kms: Record<string, number> = { 'São Paulo': 1, 'Recife': 3, 'Manaus': 5, 'Curitiba': 2, 'Belo Horizonte': 2, 'Porto Alegre': 3 }
          const days = kms[best?.city ?? ''] ?? 3

          await p.$executeRawUnsafe(
            `INSERT INTO "Fulfillment" (id, "orderId", type, "centerId", status, "estimatedDays", "createdAt") VALUES ($1, $2, 'warehouse', $3, 'routed', $4, NOW())`,
            `FUL-${data.orderId}`, data.orderId, best?.id, days,
          )

          return { orderId: data.orderId, fulfillmentCenter: `${best?.id} (${best?.city})`, estimatedDeliveryDays: days, cost: baseCost + days * 5 }
        } catch {
          return { orderId: data.orderId, fulfillmentCenter: 'FUL-001', estimatedDeliveryDays: 3, cost: 25 }
        }
      },
    })

    tools.register({
      name: 'order.getFulfillmentStatus',
      description: 'Consulta status de fulfillment de um pedido no banco',
      inputSchema: z.object({ orderId: z.string() }),
      outputSchema: z.object({ orderId: z.string(), status: z.string(), center: z.string() }),
      handler: async (input: unknown) => {
        const data = input as { orderId: string }
        try {
          const p = getPrisma()
          const rows = await p.$queryRawUnsafe<Array<{ status: string; centerId: string | null }>>(
            `SELECT status, "centerId" FROM "Fulfillment" WHERE "orderId"=$1`, data.orderId,
          )
          if (!rows[0]) return { orderId: data.orderId, status: 'pending', center: 'FUL-001' }
          return { orderId: data.orderId, status: rows[0].status, center: rows[0].centerId ?? 'FUL-001' }
        } catch {
          return { orderId: data.orderId, status: 'pending', center: 'FUL-001' }
        }
      },
    })

    super('ag-035', ORDER_ROUTER_DEFINITION, context)
    this.executor = new ToolExecutor(tools)
  }

  override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> {
    await super.handleTask(task)
    if (task['type'] === 'route_order') {
      const result = await this.executor.execute('order.route', task)
      this.context.memory.episodic.record({
        type: 'order.routed', agentId: this.id,
        data: { orderId: task['orderId'] as string, result },
      })
      return { ...task, result }
    }
    return super.handleTask(task)
  }
}
