import { describe, it, expect } from '@jest/globals'
import { Product, BOM } from '../../../src/contexts/product-engineering/domain/entities'
import { MaterialSpec, DimensionsVO, RevisionNumber } from '../../../src/contexts/product-engineering/domain/value-objects'
import { SpecificationChecker, BOMValidator } from '../../../src/contexts/product-engineering/domain/services'
import { StockItem } from '../../../src/contexts/inventory/domain/entities'
import { ReorderPoint } from '../../../src/contexts/inventory/domain/value-objects'
import { Order, Fulfillment } from '../../../src/contexts/order-management/domain/entities'

describe('Product Engineering Domain', () => {
  it('should create a product with materials', () => {
    const materials = [new MaterialSpec('M1', 'Polipropileno', 'termoplastico', 0.91, 12)]
    const dimensions = new DimensionsVO(120, 80, 15, 45)
    const product = new Product('PT-0001-A', 'Tampa Universal', 'utensilios', materials, dimensions)

    expect(product.sku).toBe('PT-0001-A')
    expect(product.id).toBeDefined()
    expect(product.status).toBe('draft')
    expect(product.materials.length).toBe(1)
  })

  it('should activate product and emit event', () => {
    const product = new Product('PT-0002', 'Test', 'cat', [new MaterialSpec('M1', 'ABS', 'termoplastico')])
    product.activate()

    expect(product.status).toBe('active')
    expect(product.pullDomainEvents().length).toBe(1)
    expect(product.pullDomainEvents()[0]!.eventType).toContain('product.designed')
  })

  it('should archive product', () => {
    const product = new Product('PT-0003', 'Old', 'cat', [new MaterialSpec('M1', 'PE', 'termoplastico')])
    product.activate()
    product.pullDomainEvents()
    product.archive('Obsoleto')

    expect(product.status).toBe('archived')
    expect(product.pullDomainEvents().length).toBe(1)
  })

  it('should validate BOM completeness', () => {
    const validator = new BOMValidator()
    const result = validator.validate([
      { componentId: 'C1', name: 'Body', quantity: 1, materialSpec: 'PP' },
      { componentId: 'C2', name: 'Seal', quantity: 1 },
    ])
    expect(result.valid).toBe(false)
    expect(result.issues.some(i => i.includes('MaterialSpec'))).toBe(true)
  })

  it('should detect BOM duplicates', () => {
    const validator = new BOMValidator()
    const result = validator.validate([
      { componentId: 'C1', name: 'A', quantity: 1, materialSpec: 'PP' },
      { componentId: 'C1', name: 'A dup', quantity: 1, materialSpec: 'PP' },
    ])
    expect(result.valid).toBe(false)
  })

  it('should check specification completeness', () => {
    const checker = new SpecificationChecker()
    const product = new Product('bad-sku', 'X', 'cat', [new MaterialSpec('M1', 'PP', 'termoplastico')])
    const result = checker.checkCompleteness(product)
    expect(result.passed).toBe(false)
    expect(result.issues.length).toBeGreaterThan(0)
  })

  it('should create BOM and validate', () => {
    const bom = new BOM('PROD-1', [
      { componentId: 'C1', name: 'Base', quantity: 1, materialSpec: 'PP Copolimero' },
    ])
    bom.validate('inspector-1')

    expect(bom.validated).toBe(true)
    expect(bom.validatedBy).toBe('inspector-1')
    expect(bom.pullDomainEvents().length).toBe(1)
  })

  it('RevisionNumber should increment correctly', () => {
    const rev = new RevisionNumber(2, 3)
    expect(rev.toString()).toBe('2.3')
    expect(rev.nextMajor().toString()).toBe('3.0')
    expect(rev.nextMinor().toString()).toBe('2.4')
  })
})

describe('Inventory Domain', () => {
  it('should create stock item', () => {
    const item = new StockItem('SKU-001', 'WH-01', 100)
    expect(item.quantity).toBe(100)
    expect(item.availableQty).toBe(100)
  })

  it('should receive stock', () => {
    const item = new StockItem('SKU-002', 'WH-01', 50)
    item.receive(30, 'PO-001')
    expect(item.quantity).toBe(80)
    expect(item.pullDomainEvents().length).toBe(1)
  })

  it('should reserve and ship stock', () => {
    const item = new StockItem('SKU-003', 'WH-01', 100)
    item.reserve(30, 'ORD-001')
    expect(item.reservedQty).toBe(30)
    expect(item.availableQty).toBe(70)

    item.ship(30, 'ORD-001')
    expect(item.quantity).toBe(70)
    expect(item.availableQty).toBe(70)
  })

  it('should throw on insufficient stock reserve', () => {
    const item = new StockItem('SKU-004', 'WH-01', 10)
    expect(() => item.reserve(20, 'ORD-002')).toThrow('Insufficient stock')
  })

  it('should adjust stock and emit event', () => {
    const item = new StockItem('SKU-005', 'WH-01', 100)
    item.adjust(90, 'Inventory count correction')
    expect(item.quantity).toBe(90)
    expect(item.pullDomainEvents().length).toBe(1)
  })

  it('should emit low stock alert', () => {
    const item = new StockItem('SKU-006', 'WH-01', 5)
    item.setReorderPoint(10)
    item.pullDomainEvents()
    item.ship(3, 'ORD-003')
    const events = item.pullDomainEvents()
    const alert = events.find(e => e.eventType.includes('low.stock'))
    expect(alert).toBeDefined()
  })

  it('should emit out of stock alert', () => {
    const item = new StockItem('SKU-007', 'WH-01', 5)
    item.setReorderPoint(10)
    item.pullDomainEvents()
    item.ship(5, 'ORD-004')
    const events = item.pullDomainEvents()
    const alert = events.find(e => e.eventType.includes('low.stock'))
    expect(alert).toBeDefined()
    const payload = (alert as { payload: Record<string, string> }).payload
    expect(payload['alertType']).toBe('out_of_stock')
  })
})

describe('Order Management Domain', () => {
  it('should create and place an order', () => {
    const order = new Order('CUST-001', 'shopee', [
      { sku: 'SKU-A', name: 'Produto A', quantity: 2, unitPrice: 25 },
    ])
    expect(order.totalAmount).toBe(50)

    order.place()
    expect(order.status).toBe('placed')
    expect(order.pullDomainEvents().length).toBe(1)
  })

  it('should transition through lifecycle', () => {
    const order = new Order('CUST-002', 'manual', [
      { sku: 'SKU-B', name: 'Produto B', quantity: 1, unitPrice: 100 },
    ])
    order.place()
    order.confirm()
    expect(order.status).toBe('confirmed')

    order.ship('BR123456789', 'CORREIOS')
    expect(order.status).toBe('shipped')

    order.deliver()
    expect(order.status).toBe('delivered')

    expect(order.pullDomainEvents().length).toBe(4)
  })

  it('should not place already placed order', () => {
    const order = new Order('CUST-003', 'manual', [{ sku: 'X', name: 'X', quantity: 1, unitPrice: 10 }])
    order.place()
    expect(() => order.place()).toThrow('Cannot place order')
  })

  it('should add line to order', () => {
    const order = new Order('CUST-004', 'manual', [{ sku: 'A', name: 'A', quantity: 1, unitPrice: 50 }])
    order.addLine({ sku: 'B', name: 'B', quantity: 2, unitPrice: 25 })
    expect(order.lines.length).toBe(2)
    expect(order.totalAmount).toBe(100)
  })

  it('should route fulfillment', () => {
    const fulfillment = new Fulfillment('ORD-001')
    fulfillment.route('FUL-SP-01')

    expect(fulfillment.status).toBe('routed')
    expect(fulfillment.centerId).toBe('FUL-SP-01')
    expect(fulfillment.pullDomainEvents().length).toBe(1)
  })

  it('should complete fulfillment', () => {
    const fulfillment = new Fulfillment('ORD-002')
    fulfillment.route('FUL-RJ-01')
    fulfillment.pullDomainEvents()
    fulfillment.complete('BR987654321', 'JADLOG')

    expect(fulfillment.status).toBe('completed')
    expect(fulfillment.trackingCode).toBe('BR987654321')
  })

  it('should request return', () => {
    const order = new Order('CUST-005', 'retail', [{ sku: 'Z', name: 'Z', quantity: 1, unitPrice: 200 }])
    order.place()
    order.confirm()
    order.pullDomainEvents()
    order.requestReturn('Produto com defeito', [{ sku: 'Z', quantity: 1 }])

    expect(order.status).toBe('returned')
    expect(order.pullDomainEvents().length).toBe(1)
  })
})
