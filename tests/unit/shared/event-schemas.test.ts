import { describe, it, expect } from '@jest/globals'
import { validateEvent, eventEnvelopeSchema } from '../../../src/shared/domain/events/schemas'
import { ProductDesignedPayload } from '../../../src/shared/domain/events/schemas/product-engineering.schema'
import { OrderPlacedPayload } from '../../../src/shared/domain/events/schemas/order-management.schema'

function baseEnvelope(eventType: string, payload: Record<string, unknown>) {
  return {
    eventId: '550e8400-e29b-41d4-a716-446655440000',
    eventType,
    eventVersion: '1.0',
    timestamp: '2026-07-02T23:00:00.000Z',
    correlationId: '550e8400-e29b-41d4-a716-446655440001',
    causationId: null,
    tenantId: 'tenant-001',
    source: { context: 'product-engineering', aggregateId: '550e8400-e29b-41d4-a716-446655440002', aggregateType: 'Product' },
    payload,
    metadata: { userId: 'user-1', agentId: null, channel: 'api' as const },
  }
}

describe('eventEnvelopeSchema validation', () => {
  it('should validate a valid ProductDesigned envelope', () => {
    const schema = eventEnvelopeSchema(ProductDesignedPayload)
    const result = schema.safeParse(baseEnvelope('product-engineering.v1.product.designed', {
      productId: '550e8400-e29b-41d4-a716-446655440003',
      sku: 'PROD-001',
      name: 'Copo 300ml',
      category: 'copos',
      materials: [{ materialId: 'mat-1', name: 'PP', type: 'polipropileno' }],
    }))
    expect(result.success).toBe(true)
  })

  it('should reject envelope with missing required payload fields', () => {
    const schema = eventEnvelopeSchema(ProductDesignedPayload)
    const result = schema.safeParse(baseEnvelope('product-engineering.v1.product.designed', {
      productId: '550e8400-e29b-41d4-a716-446655440003',
    }))
    expect(result.success).toBe(false)
  })

  it('should validate a valid OrderPlaced envelope', () => {
    const schema = eventEnvelopeSchema(OrderPlacedPayload)
    const result = schema.safeParse(baseEnvelope('order-management.v1.order.placed', {
      orderId: 'ord_123',
      channel: 'mercadolivre',
      items: [{ sku: 'PROD-001', quantity: 2, unitPrice: 49.90, total: 99.80 }],
      customerId: 'cus_789',
      shippingAddress: { recipientName: 'Joao', city: 'Sao Paulo', state: 'SP', zipCode: '01001-000' },
      totals: { subtotal: 99.80, grandTotal: 114.80, currency: 'BRL' },
    }))
    expect(result.success).toBe(true)
  })

  it('should reject orders with no items', () => {
    const schema = eventEnvelopeSchema(OrderPlacedPayload)
    const result = schema.safeParse(baseEnvelope('order-management.v1.order.placed', {
      orderId: 'ord_123',
      channel: 'mercadolivre',
      items: [],
      customerId: 'cus_789',
      shippingAddress: { recipientName: 'Joao', city: 'Sao Paulo', state: 'SP', zipCode: '01001-000' },
      totals: { subtotal: 99.80, grandTotal: 114.80, currency: 'BRL' },
    }))
    expect(result.success).toBe(false)
  })
})

describe('validateEvent registry', () => {
  it('should validate a known event type', () => {
    const result = validateEvent(baseEnvelope('product-engineering.v1.product.designed', {
      productId: '550e8400-e29b-41d4-a716-446655440003',
      sku: 'PROD-001',
      name: 'Copo 300ml',
      category: 'copos',
      materials: [{ materialId: 'mat-1', name: 'PP', type: 'polipropileno' }],
    }))
    expect(result.success).toBe(true)
  })

  it('should reject unknown event type', () => {
    const result = validateEvent(baseEnvelope('unknown.context.v1.event', {}))
    expect(result.success).toBe(false)
  })

  it('should reject non-object input', () => {
    const result = validateEvent('not-an-object')
    expect(result.success).toBe(false)
  })

  it('should reject null input', () => {
    const result = validateEvent(null)
    expect(result.success).toBe(false)
  })
})
