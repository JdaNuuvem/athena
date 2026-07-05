import { z } from 'zod'

export const ListingPublishedPayload = z.object({
  listingId: z.string().uuid(),
  channel: z.enum(['mercadolivre', 'shopee', 'amazon', 'magalu']),
  productId: z.string().uuid(),
  channelSku: z.string().min(1),
  channelListingId: z.string().optional(),
  channelUrl: z.string().url().optional(),
  publishedAt: z.string().datetime(),
  price: z.number().nonnegative(),
  stockQuantity: z.number().int().nonnegative(),
  status: z.enum(['active', 'paused', 'closed']),
})

export const SyncCompletedPayload = z.object({
  syncId: z.string().uuid(),
  channel: z.enum(['mercadolivre', 'shopee', 'amazon', 'magalu']),
  syncType: z.enum(['full', 'incremental', 'event_driven']),
  listingsSynced: z.number().int().nonnegative().optional(),
  listingsFailed: z.number().int().nonnegative().optional(),
  errors: z.array(z.string()).optional(),
  durationSeconds: z.number().optional(),
  completedAt: z.string().datetime(),
})

export const ChannelOrderReceivedPayload = z.object({
  channelOrderId: z.string().min(1),
  channel: z.enum(['mercadolivre', 'shopee', 'amazon', 'magalu']),
  channelAccountId: z.string().optional(),
  items: z.array(z.object({
    channelSku: z.string().min(1),
    internalSku: z.string().optional(),
    quantity: z.number().int().positive(),
    unitPrice: z.number().nonnegative(),
    total: z.number().nonnegative().optional(),
  })).min(1),
  customer: z.object({
    name: z.string().min(1),
    email: z.string().email().optional(),
    phone: z.string().optional(),
    shippingAddress: z.object({
      recipientName: z.string().optional(),
      street: z.string().optional(),
      number: z.string().optional(),
      neighborhood: z.string().optional(),
      city: z.string().min(1),
      state: z.string().min(1),
      zipCode: z.string().min(1),
    }),
  }),
  totals: z.object({
    subtotal: z.number().optional(),
    shipping: z.number().optional(),
    discount: z.number().optional(),
    grandTotal: z.number().nonnegative(),
    currency: z.string().default('BRL'),
  }),
  receivedAt: z.string().datetime(),
  estimatedShipDeadline: z.string().optional(),
})

export const CompetitorPriceChangedPayload = z.object({
  sku: z.string().min(1),
  channel: z.enum(['mercadolivre', 'shopee', 'amazon', 'magalu']),
  competitorId: z.string().min(1),
  competitorName: z.string().optional(),
  previousPrice: z.number().optional(),
  newPrice: z.number().nonnegative(),
  ourPrice: z.number().optional(),
  priceDifferencePercent: z.number().optional(),
  detectedAt: z.string().datetime(),
})

export const ChannelAccountHealthPayload = z.object({
  channelAccountId: z.string().min(1),
  channel: z.enum(['mercadolivre', 'shopee', 'amazon', 'magalu']),
  reputationLevel: z.string().optional(),
  reputationColor: z.enum(['green', 'yellow', 'orange', 'red']).optional(),
  cancellationRate: z.number().optional(),
  delayRate: z.number().optional(),
  responseTimeMinutes: z.number().optional(),
  healthScore: z.number().int().min(0).max(100).optional(),
  warnings: z.array(z.string()).optional(),
  checkedAt: z.string().datetime(),
})

export const PriceRepricedPayload = z.object({
  listingId: z.string().min(1),
  channel: z.enum(['mercadolivre', 'shopee', 'amazon', 'magalu']),
  sku: z.string().min(1),
  oldPrice: z.number().nonnegative(),
  newPrice: z.number().nonnegative(),
  reason: z.enum(['competitor_undercut', 'margin_protection', 'promotion', 'liquidation', 'manual']),
  marginPercent: z.number().optional(),
  repricedAt: z.string().datetime(),
  agentId: z.string().optional(),
})
