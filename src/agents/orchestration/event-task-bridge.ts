import type { AgentRegistry } from '../registry/agent-registry'

export interface EventTaskMapping {
  readonly eventType: string
  readonly agentId: string
  readonly taskType: string
  readonly mapPayload: (payload: Record<string, unknown>) => Record<string, unknown>
  readonly priority?: number
}

export class EventTaskBridge {
  private mappings: EventTaskMapping[] = []

  constructor(private registry: AgentRegistry) {}

  registerMapping(mapping: EventTaskMapping): void {
    this.mappings.push(mapping)
  }

  async handleEvent(eventType: string, payload: Record<string, unknown>): Promise<void> {
    const matching = this.mappings.filter(m => eventType.includes(m.eventType) || eventType === m.eventType)
    if (matching.length === 0) return

    for (const mapping of matching) {
      const agent = this.registry.get(mapping.agentId)
      if (!agent || agent.status !== 'running') continue

      const task = { type: mapping.taskType, eventType, ...mapping.mapPayload(payload) }
      try {
        await agent.handleTask(task)
      } catch (err) {
        console.error(`[EventTaskBridge] ${mapping.agentId}.${mapping.taskType}:`, err)
      }
    }
  }
}

export function createDefaultMappings(): EventTaskMapping[] {
  return [
    { eventType: 'product.designed', agentId: 'AG-001', taskType: 'validate-specification', mapPayload: p => ({ productId: p['productId'], sku: p['sku'], name: p['name'], category: p['category'], materials: p['materials'] }), priority: 10 },
    { eventType: 'bom.updated', agentId: 'ag-002', taskType: 'validate_bom', mapPayload: p => ({ bomId: p['bomId'], productId: p['productId'], components: p['components'] }), priority: 10 },
    { eventType: 'revision.approved', agentId: 'ag-003', taskType: 'track_revision', mapPayload: p => ({ revisionId: p['revisionId'], productId: p['productId'] }), priority: 8 },
    { eventType: 'mold.designed', agentId: 'ag-004', taskType: 'review_design', mapPayload: p => ({ moldId: p['moldId'], cavities: p['cavities'], material: p['material'] }), priority: 9 },
    { eventType: 'cycle.completed', agentId: 'ag-005', taskType: 'predict_maintenance', mapPayload: p => ({ moldId: p['moldId'], cycleCount: p['cycleCount'] }), priority: 6 },
    { eventType: 'mold.fabrication', agentId: 'ag-006', taskType: 'track_fabrication', mapPayload: p => ({ moldId: p['moldId'], currentPhase: p['currentPhase'] }), priority: 7 },
    { eventType: 'cnc.schedule', agentId: 'ag-007', taskType: 'schedule', mapPayload: p => ({ jobs: p['jobs'], machines: p['machines'] }), priority: 8 },
    { eventType: 'cnc.tool', agentId: 'ag-008', taskType: 'monitor_tool_wear', mapPayload: p => ({ toolId: p['toolId'], hoursUsed: p['hoursUsed'] }), priority: 6 },
    { eventType: 'nc.program', agentId: 'ag-009', taskType: 'validate_program', mapPayload: p => ({ programId: p['programId'], toolpaths: p['toolpaths'] }), priority: 9 },
    { eventType: 'cycle.completed', agentId: 'ag-010', taskType: 'optimize_cycle', mapPayload: p => ({ cycleId: p['cycleId'], parameters: p['parameters'] }), priority: 5 },
    { eventType: 'cycle.completed', agentId: 'ag-011', taskType: 'analyze_cycle', mapPayload: p => ({ cycleId: p['cycleId'], machineId: p['machineId'], parameters: p['parameters'] }), priority: 6 },
    { eventType: 'production.forecast', agentId: 'ag-012', taskType: 'forecast', mapPayload: p => ({ sku: p['sku'], historicalData: p['historicalData'] }), priority: 4 },
    { eventType: 'quality.check', agentId: 'ag-013', taskType: 'gatekeep', mapPayload: p => ({ batchId: p['batchId'], defectRate: p['defectRate'] }), priority: 8 },
    { eventType: 'formulation', agentId: 'ag-014', taskType: 'optimize', mapPayload: p => ({ formulationId: p['formulationId'], components: p['components'] }), priority: 5 },
    { eventType: 'curing.cycle', agentId: 'ag-015', taskType: 'monitor_curing', mapPayload: p => ({ cycleId: p['cycleId'], temperature: p['temperature'] }), priority: 7 },
    { eventType: 'coating.qc', agentId: 'ag-016', taskType: 'check_quality', mapPayload: p => ({ batchId: p['batchId'], thickness: p['thickness'] }), priority: 8 },
    { eventType: 'mold.designed', agentId: 'ag-017', taskType: 'match_material', mapPayload: p => ({ moldId: p['moldId'], plasticType: p['plasticType'], volume: p['volume'] }), priority: 7 },
    { eventType: 'nc.program', agentId: 'ag-018', taskType: 'generate_sheet', mapPayload: p => ({ programId: p['programId'], machineId: p['machineId'] }), priority: 4 },
    { eventType: 'product.published', agentId: 'ag-019', taskType: 'enrich', mapPayload: p => ({ productId: p['productId'], name: p['name'] }), priority: 5 },
    { eventType: 'product.published', agentId: 'ag-020', taskType: 'organize_media', mapPayload: p => ({ productId: p['productId'], media: p['media'] }), priority: 4 },
    { eventType: 'product.published', agentId: 'ag-021', taskType: 'optimize_seo', mapPayload: p => ({ productId: p['productId'], title: p['title'], description: p['description'] }), priority: 4 },
    { eventType: 'product.published', agentId: 'ag-022', taskType: 'sync_listing', mapPayload: p => ({ productId: p['productId'], channels: p['channels'] }), priority: 6 },
    { eventType: 'listing.updated', agentId: 'ag-023', taskType: 'monitor_competitors', mapPayload: p => ({ sku: p['sku'], marketplacePrice: p['marketplacePrice'] }), priority: 3 },
    { eventType: 'channel.health', agentId: 'ag-024', taskType: 'check_health', mapPayload: p => ({ channelId: p['channelId'], metrics: p['metrics'] }), priority: 3 },
    { eventType: 'competitor.price', agentId: 'ag-025', taskType: 'repricing', mapPayload: p => ({ sku: p['sku'], currentPrice: p['currentPrice'], competitorPrice: p['competitorPrice'] }), priority: 7 },
    { eventType: 'inventory.count', agentId: 'ag-026', taskType: 'audit', mapPayload: p => ({ storeId: p['storeId'], sku: p['sku'], physicalCount: p['physicalCount'] }), priority: 4 },
    { eventType: 'sale.completed', agentId: 'ag-027', taskType: 'analyze_patterns', mapPayload: p => ({ storeId: p['storeId'], date: p['date'] }), priority: 4 },
    { eventType: 'conversation.started', agentId: 'ag-028', taskType: 'sell', mapPayload: p => ({ chatId: p['chatId'], userId: p['userId'] }), priority: 5 },
    { eventType: 'order.status', agentId: 'ag-029', taskType: 'assist', mapPayload: p => ({ orderId: p['orderId'], chatId: p['chatId'] }), priority: 5 },
    { eventType: 'conversation.started', agentId: 'ag-030', taskType: 'recommend', mapPayload: p => ({ chatId: p['chatId'], userId: p['userId'], history: p['history'] }), priority: 5 },
    { eventType: 'stock.adjusted', agentId: 'ag-031', taskType: 'check_stock', mapPayload: p => ({ sku: p['sku'], warehouseId: p['warehouseId'] }), priority: 5 },
    { eventType: 'stock.adjusted', agentId: 'ag-032', taskType: 'forecast_demand', mapPayload: p => ({ sku: p['sku'], channel: p['channel'] }), priority: 4 },
    { eventType: 'stock.adjusted', agentId: 'ag-033', taskType: 'optimize_inventory', mapPayload: p => ({ warehouseId: p['warehouseId'], skus: p['skus'] }), priority: 4 },
    { eventType: 'inventory.report', agentId: 'ag-034', taskType: 'detect_dead', mapPayload: p => ({ warehouseId: p['warehouseId'], daysWithoutMovement: p['daysWithoutMovement'] }), priority: 3 },
    { eventType: 'order.placed', agentId: 'ag-035', taskType: 'route_order', mapPayload: p => ({ orderId: p['orderId'], skus: p['skus'], customerId: p['customerId'] }), priority: 10 },
    { eventType: 'order.placed', agentId: 'ag-036', taskType: 'check_fraud', mapPayload: p => ({ orderId: p['orderId'], amount: p['amount'], customerId: p['customerId'] }), priority: 9 },
    { eventType: 'order.confirmed', agentId: 'ag-037', taskType: 'monitor_fulfillment', mapPayload: p => ({ orderId: p['orderId'], sla: p['sla'] }), priority: 7 },
    { eventType: 'return.requested', agentId: 'ag-038', taskType: 'analyze_returns', mapPayload: p => ({ orderId: p['orderId'], reason: p['reason'], sku: p['sku'] }), priority: 5 },
    { eventType: 'customer.registered', agentId: 'ag-039', taskType: 'segment', mapPayload: p => ({ customerId: p['customerId'], attributes: p['attributes'] }), priority: 3 },
    { eventType: 'customer.activity', agentId: 'ag-040', taskType: 'predict_churn', mapPayload: p => ({ customerId: p['customerId'], lastActivity: p['lastActivity'] }), priority: 4 },
    { eventType: 'customer.purchase', agentId: 'ag-041', taskType: 'estimate_ltv', mapPayload: p => ({ customerId: p['customerId'], purchaseAmount: p['purchaseAmount'] }), priority: 4 },
    { eventType: 'order.confirmed', agentId: 'ag-042', taskType: 'select_carrier', mapPayload: p => ({ orderId: p['orderId'], destination: p['destination'], weight: p['weight'] }), priority: 8 },
    { eventType: 'order.confirmed', agentId: 'ag-043', taskType: 'optimize_shipping', mapPayload: p => ({ orderId: p['orderId'], items: p['items'] }), priority: 6 },
    { eventType: 'order.shipped', agentId: 'ag-044', taskType: 'track_delivery', mapPayload: p => ({ trackingCode: p['trackingCode'], orderId: p['orderId'] }), priority: 6 },
    { eventType: 'analytics.report', agentId: 'ag-045', taskType: 'generate_report', mapPayload: p => ({ reportType: p['reportType'], period: p['period'] }), priority: 3 },
    { eventType: 'analytics.metrics', agentId: 'ag-046', taskType: 'detect_anomaly', mapPayload: p => ({ metricName: p['metricName'], value: p['value'] }), priority: 4 },
    { eventType: 'analytics.report', agentId: 'ag-047', taskType: 'forecast_trends', mapPayload: p => ({ category: p['category'], period: p['period'] }), priority: 3 },
    { eventType: 'analytics.schedule', agentId: 'ag-048', taskType: 'send_digest', mapPayload: p => ({ channel: p['channel'], recipients: p['recipients'] }), priority: 2 },
    { eventType: 'analytics.alert', agentId: 'ag-049', taskType: 'correlate', mapPayload: p => ({ eventA: p['eventA'], eventB: p['eventB'] }), priority: 3 },
    { eventType: 'pricing.updated', agentId: 'ag-050', taskType: 'watch_margin', mapPayload: p => ({ productId: p['productId'], cost: p['cost'], price: p['price'] }), priority: 4 },
    { eventType: 'workflow.trigger', agentId: 'ag-051', taskType: 'orchestrate', mapPayload: p => ({ workflowName: p['workflowName'], input: p['input'] }), priority: 1 },
    { eventType: 'agent.heartbeat', agentId: 'ag-052', taskType: 'health_check', mapPayload: p => ({ agentId: p['agentId'] }), priority: 1 },
  ]
}
