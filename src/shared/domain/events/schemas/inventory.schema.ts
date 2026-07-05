import { z } from 'zod'

export const StockReceivedPayload = z.object({
  movementId: z.string().uuid(),
  warehouseId: z.string().min(1),
  warehouseName: z.string().optional(),
  items: z.array(z.object({
    sku: z.string().min(1),
    quantity: z.number().int().positive(),
    batchLot: z.string().optional(),
    location: z.string().min(1),
    unitCost: z.number().nonnegative().optional(),
  })).min(1),
  receivedAt: z.string().datetime(),
  supplierId: z.string().optional(),
  purchaseOrderId: z.string().optional(),
  productionBatchId: z.string().optional(),
})

export const StockShippedPayload = z.object({
  movementId: z.string().uuid(),
  orderId: z.string().min(1),
  warehouseId: z.string().min(1),
  items: z.array(z.object({
    sku: z.string().min(1),
    quantity: z.number().int().positive(),
    batchLot: z.string().optional(),
    location: z.string().optional(),
  })).min(1),
  shippedAt: z.string().datetime(),
  carrierId: z.string().optional(),
})

export const StockReservedPayload = z.object({
  reservationId: z.string().uuid(),
  orderId: z.string().min(1),
  items: z.array(z.object({
    sku: z.string().min(1),
    quantity: z.number().int().positive(),
    warehouseId: z.string().min(1),
    location: z.string().optional(),
  })).min(1),
  reservedAt: z.string().datetime(),
  expiresAt: z.string().datetime().optional(),
})

export const LowStockAlertPayload = z.object({
  sku: z.string().min(1),
  productName: z.string().optional(),
  warehouseId: z.string().min(1),
  warehouseName: z.string().optional(),
  currentQuantity: z.number().int(),
  reorderPoint: z.number().int(),
  safetyStock: z.number().int().optional(),
  averageDailyDemand: z.number().nonnegative().optional(),
  daysUntilStockout: z.number().optional(),
  triggeredAt: z.string().datetime(),
  severity: z.enum(['warning', 'critical', 'stockout']),
})

export const StockAdjustedPayload = z.object({
  adjustmentId: z.string().uuid(),
  warehouseId: z.string().min(1),
  items: z.array(z.object({
    sku: z.string().min(1),
    previousQuantity: z.number().int(),
    newQuantity: z.number().int(),
    difference: z.number().int(),
    location: z.string().optional(),
  })).min(1),
  reason: z.enum(['cycle_count', 'damage', 'loss', 'correction', 'return', 'transfer']),
  adjustedAt: z.string().datetime(),
  adjustedBy: z.string().optional(),
})
