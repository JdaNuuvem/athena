export const PHASE_1_TOPICS = {
  'product-engineering': 'athena.product-engineering.events',
  catalog: 'athena.catalog.events',
  'order-management': 'athena.order-management.events',
  inventory: 'athena.inventory.events',
  'marketplace-integration': 'athena.marketplace-integration.events',
  'retail-operations': 'athena.retail-operations.events',
  'telegram-commerce': 'athena.telegram-commerce.events',
  customer: 'athena.customer.events',
  'mold-making': 'athena.mold-making.events',
  'cnc-machining': 'athena.cnc-machining.events',
  'injection-molding': 'athena.injection-molding.events',
  'plastisol-processing': 'athena.plastisol-processing.events',
  pricing: 'athena.pricing.events',
  shipping: 'athena.shipping.events',
  analytics: 'athena.analytics.events',
} as const

export const TOPIC_CONFIG = {
  defaultPartitions: 6,
  defaultReplicationFactor: 3,
  retentionMs: 7 * 24 * 60 * 60 * 1000,
  cleanupPolicy: 'delete' as const,
}

export type Phase1Context = keyof typeof PHASE_1_TOPICS

export function topicFor(context: Phase1Context): string {
  return PHASE_1_TOPICS[context]
}

export function contextFromTopic(topic: string): Phase1Context | null {
  for (const [ctx, t] of Object.entries(PHASE_1_TOPICS)) {
    if (t === topic) return ctx as Phase1Context
  }
  return null
}
