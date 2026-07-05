import 'dotenv/config'
import { getConfig } from '../shared/infrastructure/config/app-config'
import { connectRedis, disconnectRedis } from '../shared/infrastructure/persistence/redis-client'
import { getPrisma, disconnectPrisma } from '../shared/infrastructure/persistence/prisma-client'
import { ensureCollection } from '../shared/infrastructure/persistence/qdrant-client'
import { metrics } from '../shared/infrastructure/observability/metrics'
import { setupWSBroadcast } from '../shared/infrastructure/websocket/ws-broadcast'
import { logger } from '../shared/infrastructure/observability/logger'
import { getRedisEventBus, disconnectRedisEventBus } from '../shared/infrastructure/messaging/redis-event-bus'
import { initSettingsTable, loadSettingsToEnv } from '../shared/infrastructure/persistence/settings-repository'
import { initShopeeTable, initShopeeOrdersTable, startShopeeSync, startShopeeOrderSync } from '../shared/infrastructure/integrations/shopee-stock-sync'
import type { EventEnvelope } from '../shared/domain/events'
import { DefaultAgentRegistry } from '../agents/registry/agent-registry'
import { DefaultCapabilityRegistry } from '../agents/registry/capability-registry'
import { DAGOrchestrationEngine } from '../agents/orchestration/orchestration-engine'
import { EventTaskBridge, createDefaultMappings } from '../agents/orchestration/event-task-bridge'
import { defineWorkflow } from '../agents/orchestration/workflow-definitions'
import { startDashboard } from '../api/rest/fastify-server'
import { athenaPubSub } from '../graphql/pubsub'
import type { AgentProcess } from '../agents/core/agent-runtime'
import { inventoryEventHandlers } from '../contexts/inventory/application/event-handlers/inventory.handlers'
import { orderEventHandlers } from '../contexts/order-management/application/event-handlers/order.handlers'
import { productEventHandlers } from '../contexts/product-engineering/application/event-handlers/product.handlers'
import { catalogEventHandlers, customerEventHandlers, shippingEventHandlers, pricingEventHandlers } from '../contexts/shared/catalog-customer-shipping-pricing.handlers'
import { manufacturingEventHandlers } from '../contexts/manufacturing/application/event-handlers/manufacturing.handlers'
import { marketplaceEventHandlers, retailEventHandlers, telegramEventHandlers, analyticsEventHandlers } from '../contexts/shared/marketplace-retail-telegram-analytics.handlers'
import { createStockLevelMonitor } from '../agents/instances/observers/stock-level-monitor'
import { createDefectDetector } from '../agents/instances/observers/defect-detector'
import { RevisionTrackerAgent } from '../agents/instances/observers/revision-tracker'
import { OrderRouterAgent } from '../agents/instances/decision-makers/order-router'
import { FraudDetectorAgent } from '../agents/instances/decision-makers/fraud-detector'
import { CarrierSelectorAgent } from '../agents/instances/decision-makers/carrier-selector'
import { BOMValidatorAgent } from '../agents/instances/decision-makers/bom-validator'
import { createMoldDesignReviewer, createMoldMaintenancePredictor, createFabricationTracker, createCNCScheduler, createToolWearMonitor, createNCProgramValidator } from '../agents/instances/production-agents'
import { createCycleOptimizer, createProductionForecaster, createQualityGatekeeper, createFormulationOptimizer, createCuringMonitor, createCoatingQC, createMoldMaterialMatcher, createSetupSheetGenerator } from '../agents/instances/production-agents-2'
import { createCatalogEnricher, createMediaOrganizer, createSEOOptimizer, createCompetitorMonitor, createChannelHealth, createRepricingAgent, createStoreInventoryAuditor, createSalesPatternAnalyzer, createOrderAssistant, createProductRecommender } from '../agents/instances/commercial-agents'
import { ConversationalSellerAgent } from '../agents/instances/executors/conversational-seller-real'
import { ListingSyncAgent } from '../agents/instances/executors/listing-sync-real'
import { ExecutiveDigestAgent } from '../agents/instances/executors/executive-digest-real'
import { createDemandForecaster, createInventoryOptimizer, createDeadStockDetector, createFulfillmentMonitor, createReturnAnalyzer, createCustomerSegmenter, createChurnPredictor, createLifetimeValueEstimator, createShippingCostOptimizer, createDeliveryTracker } from '../agents/instances/operations-agents'
import { createBusinessAnalyst, createAnomalyDetector, createTrendForecaster, createCrossContextCorrelator, createMarginWatchdog, createWorkflowOrchestrator, createSystemHealthMonitor } from '../agents/instances/intelligence-agents'
import { ProductDesignAssistantAgent } from '../agents/instances/observers/product-design-assistant'
import { TaskScheduler, createDefaultCronJobs } from '../agents/tasks/task-scheduler'

const ALL_EVENT_TYPES = [
  'inventory.v1.stock.adjusted', 'inventory.v1.low.stock.alert', 'inventory.v1.stock.reserved', 'inventory.v1.stock.received', 'inventory.v1.stock.shipped',
  'order-management.v1.order.placed', 'order-management.v1.order.confirmed', 'order-management.v1.order.shipped', 'order-management.v1.order.delivered',
  'order-management.v1.return.requested', 'order-management.v1.fulfillment.routed', 'order-management.v1.fulfillment.completed',
  'product-engineering.v1.product.designed', 'product-engineering.v1.bom.updated', 'product-engineering.v1.revision.approved', 'product-engineering.v1.product.archived',
  'mold-making.v1.mold.designed', 'mold-making.v1.mold.ready', 'mold-making.v1.maintenance.scheduled', 'mold-making.v1.maintenance.completed',
  'cnc-machining.v1.job.created', 'cnc-machining.v1.job.started', 'cnc-machining.v1.job.completed',
  'injection-molding.v1.run.started', 'injection-molding.v1.run.completed', 'injection-molding.v1.quality.checked',
  'plastisol-processing.v1.formulation.mixed', 'plastisol-processing.v1.curing.started', 'plastisol-processing.v1.curing.completed',
  'catalog.v1.product.published', 'catalog.v1.product.updated', 'catalog.v1.variant.created',
  'customer.v1.registered', 'customer.v1.tier.changed',
  'shipping.v1.carrier.selected', 'shipping.v1.delivery.tracked',
  'pricing.v1.updated',
  'marketplace.v1.listing.published', 'marketplace.v1.listing.updated', 'marketplace.v1.order.synced', 'marketplace.v1.health.alert',
  'retail.v1.sale.completed', 'retail.v1.inventory.audited', 'retail.v1.shift.closed',
  'telegram.v1.order.created', 'telegram.v1.session.started', 'telegram.v1.message.received',
  'analytics.v1.report.generated', 'analytics.v1.metric.recorded', 'analytics.v1.insight.found',
]


async function initInfrastructure(): Promise<void> {
  const config = getConfig()
  console.log(`\n[ATHENA] ${config.NODE_ENV} mode — starting...`)
  try { await connectRedis(); console.log('  Redis    connected') } catch { console.warn('  Redis    offline') }
  try { getPrisma(); console.log('  Prisma   ready') } catch { console.warn('  Prisma   offline') }
  try { await ensureCollection('agent_long_term_memory'); console.log('  Qdrant   ready') } catch { console.warn('  Qdrant   offline') }
  try { getRedisEventBus(); console.log('  Redis    Pub/Sub ready') } catch { console.warn('  Redis    Pub/Sub offline') }
  try { await initSettingsTable(); console.log('  Settings ready') } catch { console.warn('  Settings  offline') }
  try { await loadSettingsToEnv(); console.log('  Env      loaded from DB') } catch { console.warn('  Env      failed to load') }
  try { await initShopeeTable(); console.log('  Shopee   table ready') } catch { console.warn('  Shopee   table offline') }
  try { await initShopeeOrdersTable(); console.log('  Orders   table ready') } catch { console.warn('  Orders   table offline') }
  try { startShopeeSync(300000); console.log('  Shopee   sync started (5min)') } catch { console.warn('  Shopee   sync skipped') }
  try { startShopeeOrderSync(60000); console.log('  Orders   sync started (1min)') } catch { console.warn('  Orders   sync skipped') }
}

function createAllAgents(): AgentProcess[] {
  return [
    new ProductDesignAssistantAgent(),
    createStockLevelMonitor(), createDefectDetector(), new RevisionTrackerAgent(),
    new OrderRouterAgent(), new FraudDetectorAgent(), new CarrierSelectorAgent(), new BOMValidatorAgent(),
    createMoldDesignReviewer(), createMoldMaintenancePredictor(), createFabricationTracker(),
    createCNCScheduler(), createToolWearMonitor(), createNCProgramValidator(),
    createCycleOptimizer(), createProductionForecaster(), createQualityGatekeeper(),
    createFormulationOptimizer(), createCuringMonitor(), createCoatingQC(),
    createMoldMaterialMatcher(), createSetupSheetGenerator(),
    createCatalogEnricher(), createMediaOrganizer(), createSEOOptimizer(),
    new ListingSyncAgent(), createCompetitorMonitor(), createChannelHealth(), createRepricingAgent(),
    createStoreInventoryAuditor(), createSalesPatternAnalyzer(),
    new ConversationalSellerAgent(), createOrderAssistant(), createProductRecommender(),
    createDemandForecaster(), createInventoryOptimizer(), createDeadStockDetector(),
    createFulfillmentMonitor(), createReturnAnalyzer(),
    createCustomerSegmenter(), createChurnPredictor(), createLifetimeValueEstimator(),
    createShippingCostOptimizer(), createDeliveryTracker(),
    createBusinessAnalyst(), createAnomalyDetector(), createTrendForecaster(),
    new ExecutiveDigestAgent(), createCrossContextCorrelator(), createMarginWatchdog(),
    createWorkflowOrchestrator(), createSystemHealthMonitor(),
  ]
}

function deployAllWorkflows(orchestrator: DAGOrchestrationEngine): void {
  const wf = defineWorkflow
  const workflows = [
    wf({ name: 'order-processing', description: 'Route → Fraud → Carrier', trigger: { event: 'order-management.v1.order.placed' }, onFailure: 'alert', steps: [{ id: 'route', label: 'Route', targetAgentId: 'ag-035', config: {} }, { id: 'fraud', label: 'Fraud', targetAgentId: 'ag-036', config: {} }, { id: 'carrier', label: 'Carrier', targetAgentId: 'ag-042', dependsOn: ['route', 'fraud'], config: {} }] }),
    wf({ name: 'injection-quality-flow', description: 'Optimize → Detect → Gatekeep', trigger: { event: 'injection-molding.v1.cycle.completed' }, onFailure: 'alert', steps: [{ id: 'optimize', label: 'Optimize', targetAgentId: 'ag-010', config: {} }, { id: 'detect', label: 'Detect', targetAgentId: 'ag-011', dependsOn: ['optimize'], config: {} }, { id: 'gatekeep', label: 'Gatekeep', targetAgentId: 'ag-013', dependsOn: ['detect'], config: {} }] }),
    wf({ name: 'inventory-management-flow', description: 'Check → Forecast → Optimize → Dead', trigger: { event: 'inventory.v1.stock.adjusted' }, onFailure: 'alert', steps: [{ id: 'check', label: 'Check', targetAgentId: 'ag-031', config: {} }, { id: 'forecast', label: 'Forecast', targetAgentId: 'ag-032', dependsOn: ['check'], config: {} }, { id: 'optimize', label: 'Optimize', targetAgentId: 'ag-033', dependsOn: ['forecast'], config: {} }, { id: 'dead', label: 'Dead Stock', targetAgentId: 'ag-034', dependsOn: ['optimize'], config: {} }] }),
    wf({ name: 'customer-intelligence-flow', description: 'Segment → Churn → LTV', trigger: { event: 'customer.v1.registered' }, onFailure: 'alert', steps: [{ id: 'segment', label: 'Segment', targetAgentId: 'ag-039', config: {} }, { id: 'churn', label: 'Churn', targetAgentId: 'ag-040', dependsOn: ['segment'], config: {} }, { id: 'ltv', label: 'LTV', targetAgentId: 'ag-041', dependsOn: ['churn'], config: {} }] }),
  ]
  for (const w of workflows) orchestrator.deploy(w)
  console.log(`  Workflows ${workflows.length} deployed`)
}

async function initEventConsumers(registry: DefaultAgentRegistry, orchestrator: DAGOrchestrationEngine): Promise<EventTaskBridge> {
  const bridge = new EventTaskBridge(registry)
  for (const m of createDefaultMappings()) bridge.registerMapping(m)

  const handlers: Record<string, (e: EventEnvelope) => Promise<void>> = {
    ...inventoryEventHandlers, ...orderEventHandlers, ...productEventHandlers,
    ...catalogEventHandlers, ...customerEventHandlers, ...shippingEventHandlers,
    ...pricingEventHandlers,
    ...manufacturingEventHandlers,
    ...marketplaceEventHandlers,
    ...retailEventHandlers,
    ...telegramEventHandlers,
    ...analyticsEventHandlers,
  }

  const publishToSubscriptions = (envelope: EventEnvelope<Record<string, unknown>>) => {
    const topic = mapEventToTopic(envelope.eventType)
    if (topic) athenaPubSub.publish(topic, envelope.payload as Record<string, unknown>)
  }

  try {
    const bus = getRedisEventBus()
    for (const eventType of ALL_EVENT_TYPES) {
      await bus.subscribe(eventType, async (envelope: EventEnvelope<Record<string, unknown>>) => {
        metrics.kafkaMessagesConsumed.inc({ event_type: envelope.eventType })
        const h = handlers[envelope.eventType]
        if (h) { try { await h(envelope as EventEnvelope<Record<string, unknown>>) } catch { /* handler error */ } }
        await bridge.handleEvent(envelope.eventType, envelope.payload as Record<string, unknown>)
        publishToSubscriptions(envelope)
        try { await orchestrator.trigger('order-processing', envelope.payload as Record<string, unknown>) } catch { /* no match */ }
      })
    }
    console.log(`  Redis    listening on ${ALL_EVENT_TYPES.length} event types + ${Object.keys(handlers).length} domain handlers`)
  } catch { console.warn('  Redis    initial connection failed — retrying in background') }

  return bridge
}

function mapEventToTopic(eventType: string): string | null {
  if (eventType.startsWith('order-management') || eventType.startsWith('order')) {
    if (eventType.includes('.placed') || eventType.includes('.created')) return 'order.placed'
    return 'order.updated'
  }
  if (eventType.startsWith('inventory') || eventType.startsWith('stock')) return 'inventory.changed'
  if (eventType.startsWith('injection-molding') || eventType.startsWith('cnc-machining') || eventType.includes('run.')) return 'production.progress'
  if (eventType.startsWith('mold-making')) return 'mold.changed'
  if (eventType.startsWith('shipping')) return 'shipment.changed'
  if (eventType.startsWith('analytics')) return 'kpi.snapshot'
  return null
}

async function start(): Promise<void> {
  await initInfrastructure()

  const registry = new DefaultAgentRegistry()
  const orchestrator = new DAGOrchestrationEngine()
  const agents = createAllAgents()

  for (const agent of agents) {
    try {
      await agent.start()
      registry.register(agent)
      orchestrator.registerAgent(agent.id, agent)
    } catch { /* agent fail */ }
  }

  metrics.agentsRunning.set(registry.list().filter(a => a.status === 'running').length)
  metrics.agentsErrored.set(registry.list().filter(a => a.status === 'error').length)
  setupWSBroadcast(registry)

  const scheduler = new TaskScheduler(registry)
  for (const job of createDefaultCronJobs()) scheduler.register(job)
  scheduler.start()
  console.log(`  Scheduler ${scheduler.list().length} cron jobs active`)

  deployAllWorkflows(orchestrator)
  await initEventConsumers(registry, orchestrator)

  const { url } = await startDashboard(registry, orchestrator, scheduler)
  console.log(`\n  Dashboard → ${url}\n`)

  const shutdown = async () => {
    console.log('\n[ATHENA] Shutting down...')
    scheduler.stop()
    for (const a of agents) await a.stop()
    await disconnectRedisEventBus()
    await disconnectRedis()
    await disconnectPrisma()
    process.exit(0)
  }
  process.on('SIGINT', shutdown)
  process.on('SIGTERM', shutdown)
}

if (require.main === module) {
  start().catch(err => { console.error('[ATHENA] Fatal:', err); process.exit(1) })
}

export { start }
