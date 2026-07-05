import { z } from 'zod'

export const SaleCompletedPayload = z.object({
  saleId: z.string().min(1),
  storeId: z.string().min(1),
  registerId: z.string().optional(),
  sellerId: z.string().optional(),
  items: z.array(z.object({
    sku: z.string().min(1),
    quantity: z.number().int().positive(),
    unitPrice: z.number().nonnegative(),
    total: z.number().nonnegative().optional(),
    discount: z.number().optional(),
  })).min(1),
  totals: z.object({
    subtotal: z.number().nonnegative(),
    discount: z.number().optional(),
    grandTotal: z.number().nonnegative(),
    currency: z.string().default('BRL'),
  }),
  paymentMethod: z.string().optional(),
  completedAt: z.string().datetime(),
})

export const RegisterClosedPayload = z.object({
  registerId: z.string().min(1),
  storeId: z.string().min(1),
  openingBalance: z.number().optional(),
  closingBalance: z.number(),
  expectedBalance: z.number().optional(),
  difference: z.number().optional(),
  totalSales: z.number().optional(),
  saleCount: z.number().int().nonnegative().optional(),
  closedAt: z.string().datetime(),
  closedBy: z.string().optional(),
})

export const InventoryCountedPayload = z.object({
  countId: z.string().uuid(),
  storeId: z.string().min(1),
  items: z.array(z.object({
    sku: z.string().min(1),
    systemQuantity: z.number().int(),
    physicalQuantity: z.number().int(),
    difference: z.number().int(),
  })).optional(),
  countedAt: z.string().datetime(),
  countedBy: z.string().optional(),
  status: z.enum(['in_progress', 'completed', 'requires_recount']).optional(),
})
