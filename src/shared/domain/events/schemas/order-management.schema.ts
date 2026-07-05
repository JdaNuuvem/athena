import { z } from 'zod'

export const OrderPlacedPayload = z.object({
  orderId: z.string().min(1),
  channel: z.enum(['mercadolivre', 'shopee', 'amazon', 'magalu', 'retail', 'telegram', 'manual']),
  sourceId: z.string().optional(),
  items: z.array(z.object({
    sku: z.string().min(1),
    quantity: z.number().int().positive(),
    unitPrice: z.number().nonnegative(),
    total: z.number().nonnegative(),
  })).min(1),
  customerId: z.string().min(1),
  shippingAddress: z.object({
    recipientName: z.string().min(1),
    street: z.string().optional(),
    number: z.string().optional(),
    complement: z.string().optional(),
    neighborhood: z.string().optional(),
    city: z.string().min(1),
    state: z.string().min(1),
    zipCode: z.string().min(1),
  }),
  totals: z.object({
    subtotal: z.number().nonnegative(),
    shipping: z.number().nonnegative().optional(),
    discount: z.number().nonnegative().optional(),
    grandTotal: z.number().nonnegative(),
    currency: z.string().default('BRL'),
  }),
  paymentMethod: z.string().optional(),
  installments: z.number().int().positive().optional(),
})

export const OrderConfirmedPayload = z.object({
  orderId: z.string().min(1),
  fraudCheckResult: z.enum(['approved', 'manual_review', 'rejected']).optional(),
  confirmedAt: z.string().datetime(),
  confirmedBy: z.string().optional(),
  estimatedShipDate: z.string().optional(),
})

export const OrderShippedPayload = z.object({
  orderId: z.string().min(1),
  carrierId: z.string().min(1),
  carrierName: z.string().optional(),
  trackingCode: z.string().min(1),
  trackingUrl: z.string().url().optional(),
  shippedAt: z.string().datetime(),
  estimatedDeliveryDate: z.string().optional(),
  packages: z.array(z.object({
    packageId: z.string().min(1),
    weightG: z.number().positive().optional(),
    items: z.array(z.object({
      sku: z.string().min(1),
      quantity: z.number().int().positive(),
    })).optional(),
  })).optional(),
})

export const OrderDeliveredPayload = z.object({
  orderId: z.string().min(1),
  deliveredAt: z.string().datetime(),
  receivedBy: z.string().optional(),
  deliveryNotes: z.string().optional(),
  onTime: z.boolean().optional(),
  deliveryAttempts: z.number().int().nonnegative().optional(),
})

export const FulfillmentCompletedPayload = z.object({
  fulfillmentId: z.string().uuid(),
  orderId: z.string().min(1),
  warehouseId: z.string().min(1),
  items: z.array(z.object({
    sku: z.string().min(1),
    quantityPicked: z.number().int().nonnegative(),
    quantityOrdered: z.number().int().nonnegative(),
  })).optional(),
  completedAt: z.string().datetime(),
  completedBy: z.string().optional(),
  durationSeconds: z.number().nonnegative().optional(),
})

export const FulfillmentRoutedPayload = z.object({
  orderId: z.string().min(1),
  warehouseId: z.string().min(1),
  warehouseName: z.string().optional(),
  routedAt: z.string().datetime(),
  routingStrategy: z.string().optional(),
  estimatedPickTimeMinutes: z.number().nonnegative().optional(),
  distanceKm: z.number().nonnegative().optional(),
})

export const ReturnRequestedPayload = z.object({
  returnId: z.string().uuid(),
  orderId: z.string().min(1),
  reason: z.string().min(1),
  reasonDetail: z.string().optional(),
  items: z.array(z.object({
    sku: z.string().min(1),
    quantity: z.number().int().positive(),
    returnReason: z.string().optional(),
  })).optional(),
  requestedAt: z.string().datetime(),
  refundExpected: z.boolean().optional(),
  returnLabelGenerated: z.boolean().optional(),
})
