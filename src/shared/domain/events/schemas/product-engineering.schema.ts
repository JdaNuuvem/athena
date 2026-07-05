import { z } from 'zod'

export const ProductDesignedPayload = z.object({
  productId: z.string().uuid(),
  sku: z.string().min(1),
  name: z.string().min(1),
  description: z.string().optional(),
  category: z.string().min(1),
  materials: z.array(z.object({
    materialId: z.string().min(1),
    name: z.string().min(1),
    type: z.string().min(1),
  })).min(1),
  dimensions: z.object({
    lengthMm: z.number().positive(),
    widthMm: z.number().positive(),
    heightMm: z.number().positive(),
    weightG: z.number().positive(),
  }).optional(),
  bomId: z.string().uuid().optional(),
})

export const BOMUpdatedPayload = z.object({
  bomId: z.string().uuid(),
  productId: z.string().uuid(),
  revisionNumber: z.string().optional(),
  components: z.array(z.object({
    componentId: z.string().min(1),
    name: z.string().min(1),
    quantity: z.number().int().positive(),
    materialSpec: z.string().optional(),
    notes: z.string().optional(),
  })).min(1),
  totalComponents: z.number().int().positive().optional(),
})

export const RevisionApprovedPayload = z.object({
  revisionId: z.string().uuid(),
  productId: z.string().uuid(),
  revisionNumber: z.string().min(1),
  changesDescription: z.string().optional(),
  approvedBy: z.string().min(1),
  approvedAt: z.string().datetime(),
  cadFileHash: z.string().optional(),
})

export const ProductArchivedPayload = z.object({
  productId: z.string().uuid(),
  sku: z.string().optional(),
  reason: z.string().min(1),
  archivedBy: z.string().optional(),
  previousStatus: z.enum(['draft', 'active', 'deprecated']).optional(),
})
