import { describe, it, expect } from '@jest/globals'
import { EventEnvelope, EventSource, EventMetadata } from '../../../src/shared/domain/events'

describe('EventEnvelope', () => {
  const source: EventSource = { context: 'inventory', aggregateId: '550e8400-e29b-41d4-a716-446655440000', aggregateType: 'StockItem' }
  const metadata: EventMetadata = { userId: 'user-1', agentId: null, channel: 'api' }

  const envelope: EventEnvelope<{ sku: string; qty: number }> = {
    eventId: '550e8400-e29b-41d4-a716-446655440001',
    eventType: 'inventory.v1.stock.received',
    eventVersion: '1.0',
    timestamp: '2026-07-02T23:00:00Z',
    correlationId: '550e8400-e29b-41d4-a716-446655440002',
    causationId: null,
    tenantId: 'tenant-001',
    source,
    payload: { sku: 'PROD-001', qty: 100 },
    metadata,
  }

  it('should have required envelope fields', () => {
    expect(envelope.eventId).toBeDefined()
    expect(envelope.eventType).toBe('inventory.v1.stock.received')
    expect(envelope.eventVersion).toBe('1.0')
    expect(envelope.correlationId).toBeDefined()
    expect(envelope.tenantId).toBe('tenant-001')
    expect(envelope.source.context).toBe('inventory')
    expect(envelope.source.aggregateId).toBeDefined()
    expect(envelope.metadata.channel).toBe('api')
    expect(envelope.payload.sku).toBe('PROD-001')
    expect(envelope.payload.qty).toBe(100)
  })

  it('should allow null causationId for root events', () => {
    expect(envelope.causationId).toBeNull()
  })

  it('should support generic payload typing', () => {
    const typed: EventEnvelope<{ orderId: string }> = {
      eventId: 'id', eventType: 'order-management.v1.order.placed', eventVersion: '1.0',
      timestamp: '2026-07-02T23:00:00Z', correlationId: 'cid', causationId: null,
      tenantId: 't1', source, metadata,
      payload: { orderId: 'ord_123' },
    }
    expect(typed.payload.orderId).toBe('ord_123')
  })
})
