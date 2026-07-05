import type { FastifyInstance } from 'fastify'
import type { AgentRegistry } from '../../agents/registry/agent-registry'
import type { OrchestrationEngine } from '../../agents/orchestration/orchestration-engine'
import { authMiddleware } from '../../shared/infrastructure/auth/middleware'

export function registerBusinessRoutes(server: FastifyInstance, registry: AgentRegistry, orchestrator: OrchestrationEngine): void {

  server.get('/api/business/health', async () => ({
    status: 'operational',
    contexts: { inventory: 'online', 'order-management': 'online', catalog: 'online', shipping: 'online' },
    agents: registry.healthCheck(),
  }))

  server.get('/api/business/inventory/:sku', { preHandler: [authMiddleware('viewer')] }, async (req) => {
    const { sku } = req.params as { sku: string }
    const agent = registry.get('ag-031')
    if (!agent) return { error: 'Stock monitor agent offline' }
    return agent.handleTask({ type: 'check_stock', sku, warehouseId: 'default' })
  })

  server.post('/api/business/orders', { preHandler: [authMiddleware('operator')] }, async (req, reply) => {
    const body = req.body as { orderId?: string; customerId?: string; skus?: Array<{ sku: string; quantity: number }>; amount?: number }

    // ponytail: validate stock before creating order
    if (body.skus && body.skus.length > 0) {
      const { decrementAndPushStock } = await import('../../shared/infrastructure/integrations/shopee-stock-sync')
      const orderId = body.orderId || `ORD-${Date.now()}`
      const check = await decrementAndPushStock(orderId, body.skus.map(s => ({ sku: s.sku, quantity: s.quantity })))
      if (!check.success) {
        return reply.status(409).send({ error: 'insufficient_stock', details: check.errors })
      }
    }

    const orderId = body.orderId || `ORD-${Date.now()}`
    const input = { orderId, customerId: body.customerId || 'unknown', skus: body.skus || [], amount: body.amount || 0 }
    const instance = await orchestrator.trigger('order-processing', input)
    return { orderId, workflowInstance: instance.instanceId, status: instance.status }
  })

  server.get('/api/business/orders/:id/status', { preHandler: [authMiddleware('viewer')] }, async (req) => {
    const { id } = req.params as { id: string }
    const instance = orchestrator.getInstance(id)
    if (!instance) return { error: 'Workflow instance not found', instanceId: id }
    return { instanceId: instance.instanceId, workflowName: instance.workflowName, status: instance.status, startedAt: instance.startedAt, steps: instance.steps.map(s => ({ id: s.step.id, label: s.step.label, status: s.status })) }
  })

  server.post('/api/business/quality/analyze-cycle', { preHandler: [authMiddleware('operator')] }, async (req) => {
    const body = req.body as { cycleId: string; machineId: string; temp: number; pressure: number; cycleTime: number }
    const agent = registry.get('ag-011')
    if (!agent) return { error: 'Defect detector offline' }
    return agent.handleTask({ type: 'analyze_cycle', cycleId: body.cycleId, machineId: body.machineId, parameters: { temp: body.temp, pressure: body.pressure, cycleTime: body.cycleTime } })
  })
}
