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
import { registerBIRoutes } from './bi-routes'
import { registerRbacRoutes } from './rbac-routes'
import { registerDocumentosRoutes } from './documentos-routes'
import { authMiddleware, requirePermission } from '../../shared/infrastructure/auth'
import { checkRateLimit } from '../../shared/infrastructure/auth/rate-limiter'
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

  server.get('/api/settings', { preHandler: [authMiddleware(null), requirePermission('settings:view')] }, async () => {
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

  server.put<{ Body: { settings: Array<{ key: string; value: string }> } }>('/api/settings', { preHandler: [authMiddleware(null), requirePermission('settings:manage')] }, async (req) => {
    const { setSettingsBatch } = await import('../../shared/infrastructure/persistence/settings-repository')
    await setSettingsBatch(req.body.settings)
    return { status: 'saved', count: req.body.settings.length }
  })

  server.post('/api/shopee/sync', { preHandler: [authMiddleware(null), requirePermission('integrations:manage')] }, async () => {
    const { syncShopeeProducts } = await import('../../shared/infrastructure/integrations/shopee-stock-sync')
    const result = await syncShopeeProducts()
    return result
  })

  server.post('/api/shopee/orders/sync', { preHandler: [authMiddleware(null), requirePermission('integrations:manage')] }, async () => {
    const { syncShopeeOrders } = await import('../../shared/infrastructure/integrations/shopee-stock-sync')
    const result = await syncShopeeOrders()
    return result
  })

  server.post<{ Body: { orderId: string; items: Array<{ sku: string; quantity: number }> } }>('/api/stock/decrement', { preHandler: [authMiddleware(null), requirePermission('inventory:edit')] }, async (req, reply) => {
    const { decrementAndPushStock } = await import('../../shared/infrastructure/integrations/shopee-stock-sync')
    const check = await decrementAndPushStock(req.body.orderId, req.body.items)
    if (!check.success) {
      return reply.status(409).send({ status: 'validation_failed', errors: check.errors })
    }
    return { status: 'decremented', items: req.body.items.length }
  })

  server.get('/api/shopee/oauth/callback', async (req, reply) => {
    const { code, shop_id } = req.query as { code?: string; shop_id?: string }
    if (!code || !shop_id) return reply.status(400).send({ error: 'code and shop_id required' })
    try {
      const { createHmac } = await import('crypto')
      const partnerId = process.env['SHOPEE_PARTNER_ID'] ?? ''
      const partnerKey = process.env['SHOPEE_PARTNER_KEY'] ?? ''

      // Exchange code for access_token (Shopee API v2 sign: partner_id + path + timestamp + partner_key, NO access_token/shop_id)
      const path = '/api/v2/auth/token/get'
      const timestamp = Math.floor(Date.now() / 1000)
      const signStr = `${partnerId}${path}${timestamp}${partnerKey}`
      const sign = createHmac('sha256', partnerKey).update(signStr).digest('hex')

      const baseApi = process.env['SHOPEE_SANDBOX'] !== 'false'
        ? 'https://openplatform.sandbox.test-stable.shopee.sg'
        : (process.env['SHOPEE_REGION'] === 'br' ? 'https://partner.shopeemobile.com.br' : 'https://partner.shopeemobile.com')

      const tokenResp = await fetch(`${baseApi}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, partner_id: Number(partnerId), shop_id: Number(shop_id), sign, timestamp }),
      })
      const tokenData: any = await tokenResp.json()
      console.log(`[Shopee] OAuth token exchange:`, { shop_id, error: tokenData?.error })

      if (tokenData?.access_token) {
        const { setSettingsBatch } = await import('../../shared/infrastructure/persistence/settings-repository')
        await setSettingsBatch([
          { key: 'shopee_shop_id', value: shop_id },
          { key: 'shopee_access_token', value: tokenData.access_token },
          { key: 'shopee_refresh_token', value: tokenData.refresh_token ?? '' },
        ])
        process.env['SHOPEE_SHOP_ID'] = shop_id
        process.env['SHOPEE_ACCESS_TOKEN'] = tokenData.access_token
        console.log(`[Shopee] OAuth complete: shop_id=${shop_id}`)
        return reply.redirect('/products?shopee=ok')
      }

      return reply.send({ success: false, error: tokenData?.error ?? 'token_exchange_failed', detail: tokenData })
    } catch (e) {
      return reply.status(500).send({ error: 'OAuth failed', detail: String(e) })
    }
  })

  server.post('/api/hermes/chat', async (req, reply) => {
    const { user_id, mensagem, nome } = req.body as { user_id?: string; mensagem?: string; nome?: string }
    if (!user_id || !mensagem) return reply.status(400).send({ error: 'user_id and mensagem required' })
    const envio = { user_id, mensagem, nome: nome ?? '' }

    // Try direct Hermes API (within Docker network via Coolify proxy)
    for (const base of [
      'http://hermes:5000',
      'http://localhost:5000',
      'http://hermeswebui-w9hn3qezdgivens9g1o7r3of.177.7.45.242.sslip.io',
    ]) {
      try {
        const resp = await fetch(`${base}/api/agent/ag_06_telegram/processar`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(envio),
          signal: AbortSignal.timeout(3000),
        })
        if (resp.ok) return await resp.json()
      } catch { /* try next */ }
    }

    // Fallback: answer using Athena's own agent data
    try {
      const health = registry.list()
      const stats = { total: health.length, running: health.filter(a => a.status === 'running').length }
      const msg = mensagem.toLowerCase()
      let resposta = ''
      if (msg.includes('agente') || msg.includes('agente')) {
        resposta = `Tenho ${stats.total} agentes no total, ${stats.running} rodando.`
      } else if (msg.includes('pedido') || msg.includes('venda')) {
        resposta = 'Consulte a página Pedidos para detalhes completos.'
      } else if (msg.includes('estoque') || msg.includes('estoque')) {
        resposta = 'Consulte a página Estoque para ver o nível atual.'
      } else if (msg.includes('producao') || msg.includes('produção')) {
        resposta = 'Consulte a página Produção para ver o status da fábrica.'
      } else if (msg.includes('molde') || msg.includes('cnc')) {
        resposta = 'Consulte a página Moldes & CNC para ver o status.'
      } else {
        resposta = `Sou o assistente do Athena OS. Tenho ${stats.total} agentes de inteligência empresarial. Como posso ajudar?`
      }
      return { resposta, fonte: 'athena-local' }
    } catch {
      return { resposta: 'Erro ao processar mensagem.' }
    }
  })

  // Shopee Product Management
  server.get('/api/shopee/products', { preHandler: [authMiddleware(null), requirePermission('products:view')] }, async (req, reply) => {
    const { ShopeeAdapter } = await import('../../shared/infrastructure/integrations/shopee-adapter')
    const { status, offset, limit } = req.query as { status?: string; offset?: string; limit?: string }
    const adapter = new ShopeeAdapter()
    if (!adapter.isConfigured) return reply.status(503).send({ error: 'Shopee not configured. Authorize via Settings.' })
    const result = await adapter.getItems(status ?? 'NORMAL', Number(offset ?? 0), Number(limit ?? 50))
    return result
  })

  server.get<{ Params: { id: string } }>('/api/shopee/products/:id', { preHandler: [authMiddleware(null), requirePermission('products:view')] }, async (req, reply) => {
    const { ShopeeAdapter } = await import('../../shared/infrastructure/integrations/shopee-adapter')
    const adapter = new ShopeeAdapter()
    if (!adapter.isConfigured) return reply.status(503).send({ error: 'Shopee not configured' })
    const items = await adapter.getItemBaseInfo([Number(req.params.id)])
    const item = items[0]
    if (!item) return reply.status(404).send({ error: 'Product not found' })
    let models: any[] = []
    if (item.has_model) models = await adapter.getModelList(Number(req.params.id))
    return { ...item, models }
  })

  server.post<{ Body: { item_name: string; description: string; price: number; stock: number; category_id: number; weight: number; images: string[] } }>('/api/shopee/products', { preHandler: [authMiddleware(null), requirePermission('products:create')] }, async (req, reply) => {
    const { ShopeeAdapter } = await import('../../shared/infrastructure/integrations/shopee-adapter')
    const adapter = new ShopeeAdapter()
    if (!adapter.isConfigured) return reply.status(503).send({ error: 'Shopee not configured' })
    const result = await adapter.publishProduct(req.body as any)
    if (!result) return reply.status(502).send({ error: 'Failed to publish product' })
    return { status: 'published', item_id: result.item_id }
  })

  server.put<{ Params: { id: string }; Body: { stock: number; model_id?: number } }>('/api/shopee/products/:id/stock', { preHandler: [authMiddleware(null), requirePermission('inventory:edit')] }, async (req, reply) => {
    const { ShopeeAdapter } = await import('../../shared/infrastructure/integrations/shopee-adapter')
    const adapter = new ShopeeAdapter()
    if (!adapter.isConfigured) return reply.status(503).send({ error: 'Shopee not configured' })
    const result = await adapter.updateStock({
      item_id: Number(req.params.id),
      stock_list: [{ model_id: req.body.model_id ? Number(req.body.model_id) : undefined, seller_stock: [{ stock: Number(req.body.stock) }] }],
    })
    return result
  })

  server.put<{ Params: { id: string }; Body: { price: number } }>('/api/shopee/products/:id/price', { preHandler: [authMiddleware(null), requirePermission('products:edit')] }, async (req, reply) => {
    const { ShopeeAdapter } = await import('../../shared/infrastructure/integrations/shopee-adapter')
    const adapter = new ShopeeAdapter()
    if (!adapter.isConfigured) return reply.status(503).send({ error: 'Shopee not configured' })
    const ok = await adapter.updatePrice(Number(req.params.id), req.body.price)
    return { success: ok }
  })

  registerBusinessRoutes(server, registry, orchestrator)
  registerBIRoutes(server)
  registerRbacRoutes(server)
  registerDocumentosRoutes(server)

  await server.register(mercurius, {
    schema: typeDefs,
    resolvers,
    graphiql: true,
    subscription: true,
    context: (req) => {
      const user = (req as unknown as { user?: { sub: string; role: string; permissions: string[] } }).user
      return { user, registry, orchestrator, pubsub: athenaPubSub, loaders: createLoaders() }
    },
  })

  server.addHook('preHandler', async (req, reply) => {
    if (req.url === '/graphql' || req.url.startsWith('/graphql?')) {
      await new Promise<void>((resolve, reject) => {
        authMiddleware(null)(req, reply).then(() => resolve()).catch(reject)
      })
    }
  })

  await server.listen({ port: config.PORT, host: config.HOST })
  return { server, url: `http://${config.HOST}:${config.PORT}` }
}
