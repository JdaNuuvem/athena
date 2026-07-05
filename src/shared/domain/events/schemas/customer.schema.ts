import { z } from 'zod'

export const CustomerRegisteredPayload = z.object({
  customerId: z.string().min(1),
  name: z.string().min(1),
  email: z.string().email(),
  phone: z.string().optional(),
  document: z.string().optional(),
  channelOrigin: z.enum(['mercadolivre', 'shopee', 'amazon', 'magalu', 'retail', 'telegram', 'website', 'manual']),
  registeredAt: z.string().datetime(),
})

export const TierChangedPayload = z.object({
  customerId: z.string().min(1),
  previousTier: z.enum(['bronze', 'silver', 'gold', 'diamond']),
  newTier: z.enum(['bronze', 'silver', 'gold', 'diamond']),
  reason: z.string().optional(),
  lifetimeValue: z.number().optional(),
  totalOrders: z.number().int().nonnegative().optional(),
  changedAt: z.string().datetime(),
})

export const ChurnRiskDetectedPayload = z.object({
  customerId: z.string().min(1),
  riskScore: z.number().min(0).max(1),
  riskLevel: z.enum(['low', 'medium', 'high', 'critical']),
  factors: z.array(z.object({
    factor: z.string(),
    contribution: z.number(),
  })).optional(),
  daysSinceLastOrder: z.number().optional(),
  detectedAt: z.string().datetime(),
  recommendedAction: z.string().optional(),
})

export const CustomerSegmentedPayload = z.object({
  customerId: z.string().min(1),
  segment: z.string().min(1),
  rfmScore: z.object({
    recency: z.number().int(),
    frequency: z.number().int(),
    monetary: z.number().int(),
    total: z.number().int(),
  }).optional(),
  segmentedAt: z.string().datetime(),
  segmentChanged: z.boolean().optional(),
})
