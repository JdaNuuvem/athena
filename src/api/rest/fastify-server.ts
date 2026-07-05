import Fastify from 'fastify'
import cors from '@fastify/cors'
import websocket from '@fastify/websocket'
import mercurius from 'mercurius'
import fastifyStatic from '@fastify/static'
import fastifySwagger from '@fastify/swagger'
import fastifySwaggerUi from '@fastify/swagger-ui'
import path from 'path'
import { getConfig } from '../../shared/infrastructure/config/app-config'
import type { AgentRegistry } from '../../agents/registry/agent-registry'
import type { OrchestrationEngine } from '../../agents/orchestration/orchestration-engine'
import { registerBusinessRoutes } from './business-routes'
import { authMiddleware, type AuthRole } from '../../shared/infrastructure/auth/middleware'
import { checkRateLimit } from '../../shared/infrastructure/auth/rate-limiter'
import { authenticateUser, createToken } from '../../shared/infrastructure/auth'
import { metrics, getMetricsAsText } from '../../shared/infrastructure/observability/metrics'
import { logger } from '../../shared/infrastructure/observability/logger'
import { wsBus } from '../../shared/infrastructure/websocket/ws-bus'
import { getDetailedHealth } from '../../shared/infrastructure/observability/health-check'
import { getRateLimitStats } from '../../shared/infrastructure/auth/rate-limiter'
import type { TaskScheduler } from '../../agents/tasks/task-scheduler'
import { typeDefs } from '../../graphql/schema'
import { resolvers, createLoaders } from '../../graphql/resolvers'
import { athenaPubSub } from '../../graphql/pubsub'

export async function startDashboard(registry: AgentRegistry, orchestrator: OrchestrationEngine, scheduler?: TaskScheduler): Promise<{ server: ReturnType<typeof Fastify>; url: string }> {
  const config = getConfig()
  const server = Fastify({ logger: true })
  await server.register(cors, { origin: true })
  await server.register(websocket)
  await server.register(fastifyStatic, { root: path.join(__dirname, 'public'), prefix: '/', wildcard: false })

  server.setNotFoundHandler((_req, reply) => {
    reply.header('Content-Type', 'text/html')
    reply.sendFile('index.html')
  })

  await server.register(fastifySwagger, {
    openapi: {
      info: { title: 'ATHENA OS API', version: '0.1.0', description: 'Multi-agent enterprise intelligence OS for plastic transformation industry' },
      servers: [{ url: `http://localhost:${config.PORT}` }],
      components: {
        securitySchemes: { bearerAuth: { type: 'http', scheme: 'bearer', bearerFormat: 'JWT' } },
      },
    },
  })
  await server.register(fastifySwaggerUi, { routePrefix: '/docs' })

  server.get('/ws', { websocket: true }, (socket) => {
    wsBus.addClient(socket)
  })

  server.addHook('onRequest', async (req, reply) => {
    const r = checkRateLimit(req.ip ?? 'unknown', req.url)
    if (!r.allowed) return reply.status(429).send({ error: 'Too many requests', retryAfter: r.retryAfter })
  })

  server.addHook('onResponse', async (req, reply) => {
    const route = req.routeOptions?.url ?? req.url
    metrics.httpRequestsTotal.inc({ method: req.method, route, status_code: String(reply.statusCode) })
    metrics.httpRequestDuration.observe({ method: req.method, route }, reply.elapsedTime / 1000)
  })

  server.get('/metrics', async (_, reply) => {
    reply.header('Content-Type', 'text/plain')
    return getMetricsAsText()
  })

  server.get('/api/admin/scheduler', { preHandler: [authMiddleware('operator')] }, async () => {
    return scheduler ? { jobs: scheduler.list(), stats: scheduler.getStats() } : { error: 'Scheduler not initialized' }
  })

  server.get('/api/admin/rate-limits', { preHandler: [authMiddleware('operator')] }, async () => {
    return { rateLimits: getRateLimitStats() }
  })

  server.get('/api/health', async () => {
    const agents = registry.list()
    const stats = { total: agents.length, running: agents.filter(a => a.status === 'running').length, errored: agents.filter(a => a.status === 'error').length }
    return getDetailedHealth(stats)
  })

  server.get('/api/agents', { preHandler: [authMiddleware('viewer')] }, async () => ({
    agents: registry.list().map(a => ({ id: a.id, name: a.definition.name, role: a.definition.role, status: a.status, context: a.definition.context, startedAt: a.startedAt?.toISOString() ?? null, taskCount: a.context.taskCount })),
  }))

  server.get<{ Params: { id: string } }>('/api/agents/:id', { preHandler: [authMiddleware('viewer')] }, async (req) => {
    const agent = registry.get(req.params.id)
    if (!agent) return { error: 'Agent not found' }
    return { id: agent.id, name: agent.definition.name, role: agent.definition.role, status: agent.status, context: agent.definition.context, startedAt: agent.startedAt, taskCount: agent.context.taskCount, config: agent.definition.config, capabilities: agent.definition.capabilities }
  })

  server.get<{ Params: { id: string } }>('/api/agents/:id/memory', { preHandler: [authMiddleware('operator')] }, async (req) => {
    const agent = registry.get(req.params.id)
    if (!agent) return { error: 'Agent not found' }
    let r: unknown = []; let e: unknown = []
    try { r = await Promise.resolve(agent.context.memory.shortTerm.recent(20)) } catch { /* memory offline */ }
    try { e = await Promise.resolve(agent.context.memory.episodic.history(req.params.id, 20)) } catch { /* memory offline */ }
    return { shortTerm: r, episodic: e }
  })

  server.get<{ Params: { id: string } }>('/api/workflows/:id', { preHandler: [authMiddleware('viewer')] }, async (req) => {
    const instance = orchestrator.getInstance(req.params.id)
    return instance ?? { error: 'Workflow not found' }
  })

  server.post<{ Body: { workflowName: string; input: Record<string, unknown> } }>('/api/workflows/trigger', { preHandler: [authMiddleware('operator')] }, async (req) => {
    const { workflowName, input } = req.body
    const instance = await orchestrator.trigger(workflowName, input)
    return { instanceId: instance.instanceId, status: instance.status }
  })

  server.post('/api/whatsapp/webhook', async (req, reply) => {
    const body = req.body as Record<string, unknown>
    const data = body['data'] as Record<string, unknown> | undefined
    if (!data) return reply.status(400).send({ error: 'Invalid webhook payload' })

    const fromMe = data['fromMe']
    if (fromMe) return { status: 'ignored', reason: 'own_message' }

    const remoteJid = data['remoteJid'] as string
    const pushName = data['pushName'] as string
    const messageType = data['messageType'] as string

    let text = ''
    if (messageType === 'conversation') {
      text = (data['message'] as any)?.conversation ?? (data['text'] as any)?.message ?? ''
    } else if (messageType === 'extendedTextMessage') {
      text = (data['message'] as any)?.extendedTextMessage?.text ?? ''
    } else if (messageType === 'buttonsResponseMessage') {
      text = (data['buttonResponse'] as any)?.selectedButtonId ?? (data['message'] as any)?.buttonsResponseMessage?.selectedButtonId ?? ''
    }

    const phone = remoteJid?.replace(/@s\.whatsapp\.net$/g, '') ?? ''
    if (!phone) return reply.status(400).send({ error: 'No phone number' })

    const agent = registry.get('ag-052')
    if (agent) {
      try {
        const result = await agent.handleTask({
          type: 'handle_message',
          phone,
          phoneRaw: remoteJid,
          senderName: pushName,
          text,
          messageType,
          timestamp: data['date_time'] ?? new Date().toISOString(),
        })
        return { status: 'processed', agent: 'ag-052', result }
      } catch (err) {
        console.error('[WhatsApp Webhook] Agent error:', err)
        return { status: 'error', message: 'Agent processing failed' }
      }
    }

    return { status: 'ignored', reason: 'agent not running' }
  })

  server.post('/api/whatsapp/remarketing/trigger', { preHandler: [authMiddleware('operator')] }, async (req) => {
    const body = req.body as { type?: string; phone?: string; customerName?: string; productName?: string; total?: number; couponCode?: string; title?: string; message?: string }
    const agent = registry.get('ag-052')
    if (!agent) return { error: 'WhatsApp agent not running' }

    const taskType = body.type === 'abandoned_cart' ? 'abandoned_cart'
      : body.type === 'promotion' ? 'send_promotion'
      : body.type === 'reengagement' ? 'send_promotion'
      : 'send_promotion'

    try {
      const result = await agent.handleTask({
        type: taskType,
        phone: body.phone,
        customerName: body.customerName,
        productName: body.productName,
        total: body.total,
        title: body.title ?? body.message,
        body: body.message,
        couponCode: body.couponCode,
      })
      return { status: 'sent', result }
    } catch (err) {
      return { error: 'Failed to trigger remarketing', detail: String(err) }
    }
  })

  server.get('/api/settings', { preHandler: [authMiddleware('operator')] }, async () => {
    const { getAllSettings } = await import('../../shared/infrastructure/persistence/settings-repository')
    const rows = await getAllSettings()
    const groups: Record<string, Array<{ key: string; value: string; secure: boolean; updatedAt: string }>> = {}
    for (const r of rows) {
      const g = r.group as string
      if (!groups[g]) groups[g] = []
      groups[g].push({ key: r.key, value: r.secure ? '••••••••' : r.value, secure: !!r.secure, updatedAt: r.updatedAt })
    }
    return groups
  })

  server.put<{ Body: { settings: Array<{ key: string; value: string }> } }>('/api/settings', { preHandler: [authMiddleware('operator')] }, async (req) => {
    const { setSettingsBatch } = await import('../../shared/infrastructure/persistence/settings-repository')
    await setSettingsBatch(req.body.settings)
    return { status: 'saved', count: req.body.settings.length }
  })

  await server.register(mercurius, {
    schema: typeDefs,
    resolvers,
    graphiql: true,
    subscription: true,
    context: () => ({ registry, orchestrator, pubsub: athenaPubSub, loaders: createLoaders() }),
  })

  await server.listen({ port: config.PORT, host: config.HOST })
  return { server, url: `http://${config.HOST}:${config.PORT}` }
}
