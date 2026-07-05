import { z } from 'zod'

export const SpecificationValidatedPayload = z.object({
  specId: z.string().uuid(),
  productId: z.string().uuid(),
  validationResult: z.enum(['passed', 'failed', 'requires_revision']).optional(),
  issues: z.array(z.string()).optional(),
  validatedAt: z.string().datetime(),
  validatedBy: z.string().optional(),
})

export const RevisionCreatedPayload = z.object({
  revisionId: z.string().uuid(),
  productId: z.string().uuid(),
  revisionNumber: z.string().min(1),
  changeDescription: z.string().optional(),
  cadFileHash: z.string().optional(),
  previousRevision: z.string().optional(),
  createdAt: z.string().datetime(),
  createdBy: z.string().optional(),
})

export const SpecificationApprovedPayload = z.object({
  specId: z.string().uuid(),
  productId: z.string().uuid(),
  approvalScope: z.enum(['draft', 'final', 'production']).optional(),
  approvedAt: z.string().datetime(),
  approvedBy: z.string().optional(),
})
