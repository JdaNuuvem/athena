import { InMemoryEventBus } from '../../src/shared/infrastructure/messaging/in-memory-event-bus'
import { InMemoryStockItemRepository } from '../../src/contexts/inventory/infrastructure/persistence/in-memory-stock-item.repository'
import { InMemoryOrderRepository } from '../../src/contexts/order-management/infrastructure/persistence/in-memory-order.repository'
import { InMemoryCustomerRepository } from '../../src/contexts/customer/infrastructure/persistence/in-memory-customer.repository'

import { OnChannelOrderReceivedHandler } from '../../src/contexts/order-management/application/event-handlers/on-channel-order-received.handler'
import { OnRetailSaleCompletedHandler } from '../../src/contexts/order-management/application/event-handlers/on-retail-sale-completed.handler'
import { OnTelegramOrderConfirmedHandler } from '../../src/contexts/order-management/application/event-handlers/on-telegram-order-confirmed.handler'
import { OnOrderPlacedHandler } from '../../src/contexts/inventory/application/event-handlers/on-order-placed.handler'
import { OnStockReservedHandler } from '../../src/contexts/order-management/application/event-handlers/on-stock-reserved.handler'
import { OnCompetitorPriceChangedHandler } from '../../src/contexts/pricing/application/event-handlers/on-competitor-price-changed.handler'
import { OnOrderConfirmedShipmentHandler } from '../../src/contexts/shipping/application/event-handlers/on-order-confirmed-shipment.handler'

import { PublishChannelOrderReceivedUseCase } from '../../src/contexts/marketplace-integration/application/use-cases/publish-events.use-case'

import { StockItem } from '../../src/contexts/inventory/domain/entities/stock-item'

function setupOmnichannel() {
  const eventBus = new InMemoryEventBus()
  const orderRepo = new InMemoryOrderRepository()
  const stockRepo = new InMemoryStockItemRepository()
  const customerRepo = new InMemoryCustomerRepository()

  const { BaseEventHandler } = require('../../src/shared/domain/events/base-event-handler')

  eventBus.registerHandler('order-management.v1.order.placed', new (class extends BaseEventHandler {
    readonly eventType = 'order-management.v1.order.placed'
    protected async apply(env: any) {
      await orderRepo.save({ id: env.payload.orderId, channel: env.payload.channel, customerId: env.payload.customerId, status: 'placed', items: env.payload.items, totals: env.payload.totals, shippingAddress: env.payload.shippingAddress || { recipientName: '', city: '', state: '', zipCode: '' }, createdAt: env.timestamp, updatedAt: env.timestamp })
    }
  })() as any)

  eventBus.registerHandler('order-management.v1.order.placed', new OnOrderPlacedHandler(stockRepo, eventBus))
  eventBus.registerHandler('inventory.v1.stock.reserved', new OnStockReservedHandler(orderRepo, eventBus))
  eventBus.registerHandler('marketplace-integration.v1.channel.order.received', new OnChannelOrderReceivedHandler(orderRepo, eventBus))
  eventBus.registerHandler('retail-operations.v1.sale.completed', new OnRetailSaleCompletedHandler(orderRepo, eventBus))
  eventBus.registerHandler('telegram-commerce.v1.order.confirmed', new OnTelegramOrderConfirmedHandler(orderRepo, eventBus))
  eventBus.registerHandler('marketplace-integration.v1.competitor.price.changed', new OnCompetitorPriceChangedHandler(eventBus))
  eventBus.registerHandler('order-management.v1.order.confirmed', new OnOrderConfirmedShipmentHandler(eventBus))

  const publishChannelOrder = new PublishChannelOrderReceivedUseCase(eventBus)

  return { eventBus, orderRepo, stockRepo, customerRepo, publishChannelOrder }
}

async function seedStock(stockRepo: InMemoryStockItemRepository, sku: string) {
  const item: StockItem = { id: `stock-${sku}-WH1`, sku, warehouseId: 'warehouse-001', location: 'A-01-01', quantity: 100, reserved: 0, available: 100, reorderPoint: 20, safetyStock: 10, unitCost: 15.50, updatedAt: new Date().toISOString() }
  await stockRepo.save(item)
}

describe('Phase 2 — Omnichannel Order Flow', () => {
  it('should process marketplace order → reserve stock → confirm → create shipment', async () => {
    const ctx = setupOmnichannel()
    await seedStock(ctx.stockRepo, 'ML-001')

    const corrId = 'corr-ml-001'

    await ctx.publishChannelOrder.execute({
      payload: {
        channelOrderId: 'ml-order-123', channel: 'mercadolivre',
        items: [{ channelSku: 'ML-001', internalSku: 'ML-001', quantity: 3, unitPrice: 49.90 }],
        customer: { name: 'Maria Silva', email: 'maria@email.com', shippingAddress: { recipientName: 'Maria Silva', city: 'São Paulo', state: 'SP', zipCode: '01001-000' } },
        totals: { grandTotal: 149.70, currency: 'BRL' },
        receivedAt: new Date().toISOString(),
      },
      tenantId: 't1', userId: 'u1', correlationId: corrId,
    })

    const order = await ctx.orderRepo.findById('ml-order-123')
    expect(order).not.toBeNull()
    expect(order!.status).toBe('confirmed')
    expect(order!.channel).toBe('mercadolivre')

    const stock = await ctx.stockRepo.findBySkuAndWarehouse('ML-001', 'warehouse-001')
    expect(stock!.reserved).toBe(3)
    expect(stock!.available).toBe(97)

    const events = ctx.eventBus.getPublished()
    const shipmentCreated = events.find(e => e.eventType === 'shipping.v1.shipment.created')
    expect(shipmentCreated).toBeDefined()
    expect(shipmentCreated!.causationId).toBe(events.find(e => e.eventType === 'order-management.v1.order.confirmed')!.eventId)
  })

  it('should trigger margin alert when competitor undercuts significantly', async () => {
    const ctx = setupOmnichannel()

    const eventBus = ctx.eventBus

    await eventBus.publish({
      eventId: 'evt-001', eventType: 'marketplace-integration.v1.competitor.price.changed', eventVersion: '1.0',
      timestamp: new Date().toISOString(), correlationId: 'corr-comp-001', causationId: null,
      tenantId: 't1',
      source: { context: 'marketplace-integration', aggregateId: 'comp-001', aggregateType: 'Competitor' },
      payload: { sku: 'PROD-X', channel: 'mercadolivre', competitorId: 'comp-001', competitorName: 'Concorrente X', newPrice: 29.90, ourPrice: 49.90, detectedAt: new Date().toISOString() },
      metadata: { userId: 'system', agentId: 'AG-023', channel: 'agent' },
    })

    const events = ctx.eventBus.getPublished()
    const marginAlert = events.find(e => e.eventType === 'pricing.v1.margin.alert')
    expect(marginAlert).toBeDefined()
    expect(marginAlert!.payload['currentMarginPercent']).toBeCloseTo(40.08, 0)
  })
})
