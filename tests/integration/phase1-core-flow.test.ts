import { InMemoryEventBus } from '../../src/shared/infrastructure/messaging/in-memory-event-bus'

import { InMemoryProductDesignRepository } from '../../src/contexts/product-engineering/infrastructure/persistence/in-memory-product-design.repository'
import { InMemoryCatalogEntryRepository } from '../../src/contexts/catalog/infrastructure/persistence/in-memory-catalog-entry.repository'
import { InMemoryOrderRepository } from '../../src/contexts/order-management/infrastructure/persistence/in-memory-order.repository'
import { InMemoryStockItemRepository } from '../../src/contexts/inventory/infrastructure/persistence/in-memory-stock-item.repository'

import { PublishProductDesignedUseCase } from '../../src/contexts/product-engineering/application/use-cases/publish-events.use-case'
import { PublishProductPublishedUseCase } from '../../src/contexts/catalog/application/use-cases/publish-events.use-case'
import { PublishOrderPlacedUseCase } from '../../src/contexts/order-management/application/use-cases/publish-events.use-case'
import { PublishOrderShippedUseCase } from '../../src/contexts/order-management/application/use-cases/publish-events.use-case'

import { OnProductDesignedHandler } from '../../src/contexts/catalog/application/event-handlers/on-product-designed.handler'
import { OnOrderPlacedHandler } from '../../src/contexts/inventory/application/event-handlers/on-order-placed.handler'
import { OnOrderShippedHandler } from '../../src/contexts/inventory/application/event-handlers/on-order-shipped.handler'
import { OnStockReservedHandler } from '../../src/contexts/order-management/application/event-handlers/on-stock-reserved.handler'
import { OnStockShippedHandler } from '../../src/contexts/order-management/application/event-handlers/on-stock-shipped.handler'

import { StockItem } from '../../src/contexts/inventory/domain/entities/stock-item'

function setupPhase1CoreFlow() {
  const eventBus = new InMemoryEventBus()

  const productRepo = new InMemoryProductDesignRepository()
  const catalogRepo = new InMemoryCatalogEntryRepository()
  const orderRepo = new InMemoryOrderRepository()
  const stockRepo = new InMemoryStockItemRepository()

  const publishProductDesigned = new PublishProductDesignedUseCase(eventBus)
  const publishProductPublished = new PublishProductPublishedUseCase(eventBus)
  const publishOrderPlaced = new PublishOrderPlacedUseCase(eventBus)
  const publishOrderShipped = new PublishOrderShippedUseCase(eventBus)

  eventBus.registerHandler('product-engineering.v1.product.designed', new OnProductDesignedHandler(catalogRepo))

  const { BaseEventHandler } = require('../../src/shared/domain/events/base-event-handler')
  eventBus.registerHandler('order-management.v1.order.placed', new (class extends BaseEventHandler {
    readonly eventType = 'order-management.v1.order.placed'
    protected async apply(env: any) {
      await orderRepo.save({
        id: env.payload.orderId,
        channel: env.payload.channel,
        customerId: env.payload.customerId,
        status: 'placed' as const,
        items: env.payload.items.map((i: any) => ({ sku: i.sku, quantity: i.quantity, unitPrice: i.unitPrice, total: i.total })),
        totals: env.payload.totals,
        shippingAddress: env.payload.shippingAddress || { recipientName: '', city: '', state: '', zipCode: '' },
        createdAt: env.timestamp,
        updatedAt: env.timestamp,
      })
    }
  })() as any)

  eventBus.registerHandler('order-management.v1.order.placed', new OnOrderPlacedHandler(stockRepo, eventBus))
  eventBus.registerHandler('order-management.v1.order.shipped', new OnOrderShippedHandler(stockRepo, eventBus))
  eventBus.registerHandler('inventory.v1.stock.reserved', new OnStockReservedHandler(orderRepo, eventBus))
  eventBus.registerHandler('inventory.v1.stock.shipped', new OnStockShippedHandler(orderRepo))

  return { eventBus, productRepo, catalogRepo, orderRepo, stockRepo, publishProductDesigned, publishProductPublished, publishOrderPlaced, publishOrderShipped }
}

async function seedStock(stockRepo: InMemoryStockItemRepository) {
  const item: StockItem = {
    id: 'stock-PROD-001-WH1',
    sku: 'PROD-001',
    warehouseId: 'warehouse-001',
    location: 'A-01-01',
    quantity: 100,
    reserved: 0,
    available: 100,
    reorderPoint: 20,
    safetyStock: 10,
    unitCost: 15.50,
    updatedAt: new Date().toISOString(),
  }
  await stockRepo.save(item)
}

describe('Phase 1 Core Flow — End-to-End', () => {
  it('should execute the full product → catalog → order → inventory flow', async () => {
    const ctx = setupPhase1CoreFlow()

    await seedStock(ctx.stockRepo)

    // 1. Product Designed → triggers OnProductDesignedHandler → creates catalog entry
    await ctx.publishProductDesigned.execute({
      payload: {
        productId: '550e8400-e29b-41d4-a716-446655440001', sku: 'PROD-001', name: 'Copo Térmico 300ml', category: 'copos',
        materials: [{ materialId: 'mat-pp', name: 'Polipropileno', type: 'polipropileno' }],
        dimensions: { lengthMm: 80, widthMm: 80, heightMm: 120, weightG: 45 },
      },
      tenantId: 'tenant-001', userId: 'user-001',
    })

    const catalogEntry = await ctx.catalogRepo.findByProductId('550e8400-e29b-41d4-a716-446655440001')
    expect(catalogEntry).not.toBeNull()
    expect(catalogEntry!.title).toBe('Copo Térmico 300ml')
    expect(catalogEntry!.status).toBe('draft')
    expect(catalogEntry!.materials).toContain('Polipropileno')

    // 2. Catalog Product Published
    await ctx.publishProductPublished.execute({
      payload: {
        productId: '550e8400-e29b-41d4-a716-446655440001', sku: 'PROD-001', title: 'Copo Térmico 300ml',
        description: 'Copo térmico premium', categoryId: 'cat-01',
        status: 'published', publishedAt: new Date().toISOString(),
      },
      tenantId: 'tenant-001', userId: 'user-001',
    })

    // 3. Order Placed → Inventory handler reserves stock → StockReserved → Order handler confirms
    await ctx.publishOrderPlaced.execute({
      payload: {
        orderId: 'ord-001', channel: 'mercadolivre', sourceId: 'ml-001',
        items: [{ sku: 'PROD-001', quantity: 2, unitPrice: 49.90, total: 99.80 }],
        customerId: 'cus-001',
        shippingAddress: { recipientName: 'João Silva', city: 'São Paulo', state: 'SP', zipCode: '01001-000' },
        totals: { subtotal: 99.80, shipping: 15.00, grandTotal: 114.80, currency: 'BRL' },
      },
      tenantId: 'tenant-001', userId: 'user-001',
    })

    // Verify stock was reserved
    const stockAfterReserve = await ctx.stockRepo.findBySkuAndWarehouse('PROD-001', 'warehouse-001')
    expect(stockAfterReserve).not.toBeNull()
    expect(stockAfterReserve!.reserved).toBe(2)
    expect(stockAfterReserve!.available).toBe(98)
    expect(stockAfterReserve!.quantity).toBe(100)

    // Verify order was confirmed
    const order = await ctx.orderRepo.findById('ord-001')
    expect(order).not.toBeNull()
    expect(order!.status).toBe('confirmed')

    // Verify stock movement was recorded
    const movements = ctx.stockRepo.getMovements()
    expect(movements.length).toBe(1)
    expect(movements[0]!.type).toBe('reserve')
    expect(movements[0]!.quantity).toBe(2)

    // 4. Order Shipped → Inventory handler deducts stock → StockShipped → Order handler updates status
    await ctx.publishOrderShipped.execute({
      payload: {
        orderId: 'ord-001', carrierId: 'correios', carrierName: 'Correios',
        trackingCode: 'BR123456789', shippedAt: new Date().toISOString(),
        packages: [{ packageId: 'pkg-001', items: [{ sku: 'PROD-001', quantity: 2 }] }],
      },
      tenantId: 'tenant-001', userId: 'user-001',
    })

    // Verify stock was deducted
    const stockAfterShip = await ctx.stockRepo.findBySkuAndWarehouse('PROD-001', 'warehouse-001')
    expect(stockAfterShip).not.toBeNull()
    expect(stockAfterShip!.quantity).toBe(98)
    expect(stockAfterShip!.reserved).toBe(0)
    expect(stockAfterShip!.available).toBe(98)

    // Verify order is now shipped
    const orderAfterShip = await ctx.orderRepo.findById('ord-001')
    expect(orderAfterShip!.status).toBe('shipped')

    // Verify all stock movements
    const allMovements = ctx.stockRepo.getMovements()
    expect(allMovements.length).toBe(2)
    expect(allMovements[0]!.type).toBe('reserve')
    expect(allMovements[1]!.type).toBe('out')
  })

  it('should maintain correlationId chain across the event flow', async () => {
    const ctx = setupPhase1CoreFlow()
    await seedStock(ctx.stockRepo)
    await ctx.stockRepo.save({
      id: 'stock-CHAIN-WH1', sku: 'CHAIN-001', warehouseId: 'warehouse-001',
      location: 'A-01-02', quantity: 50, reserved: 0, available: 50,
      reorderPoint: 5, safetyStock: 5, unitCost: 5.00, updatedAt: new Date().toISOString(),
    })

    const correlationId = 'corr-chain-001'

    await ctx.publishProductDesigned.execute({
      payload: {
        productId: '550e8400-e29b-41d4-a716-446655440002', sku: 'CHAIN-001', name: 'Test Chain', category: 'test',
        materials: [{ materialId: 'm1', name: 'Test', type: 'test' }],
      },
      tenantId: 't1', userId: 'u1', correlationId,
    })

    await ctx.publishOrderPlaced.execute({
      payload: {
        orderId: 'ord-chain', channel: 'mercadolivre',
        items: [{ sku: 'CHAIN-001', quantity: 1, unitPrice: 10, total: 10 }],
        customerId: 'c1', totals: { subtotal: 10, grandTotal: 10, currency: 'BRL' },
        shippingAddress: { recipientName: 'T', city: 'T', state: 'T', zipCode: '00000-000' },
      },
      tenantId: 't1', userId: 'u1', correlationId,
    })

    const allEvents = ctx.eventBus.getPublished()
    const placedEvent = allEvents.find(e => e.eventType === 'order-management.v1.order.placed')
    const reservedEvent = allEvents.find(e => e.eventType === 'inventory.v1.stock.reserved')
    const confirmedEvent = allEvents.find(e => e.eventType === 'order-management.v1.order.confirmed')

    expect(placedEvent).toBeDefined()
    expect(placedEvent!.correlationId).toBe(correlationId)
    expect(reservedEvent).toBeDefined()
    expect(reservedEvent!.correlationId).toBe(correlationId)
    expect(reservedEvent!.causationId).toBe(placedEvent!.eventId)
    expect(confirmedEvent).toBeDefined()
    expect(confirmedEvent!.correlationId).toBe(correlationId)
    expect(confirmedEvent!.causationId).toBe(reservedEvent!.eventId)
  })
})
