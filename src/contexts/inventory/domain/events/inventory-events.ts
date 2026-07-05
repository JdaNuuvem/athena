import { DomainEvent, EventEnvelope } from '@shared/domain/events'

export interface StockReceivedPayload {
  movementId: string
  warehouseId: string
  warehouseName?: string
  items: Array<{ sku: string; quantity: number; batchLot?: string; location: string; unitCost?: number }>
  receivedAt: string
  supplierId?: string
  purchaseOrderId?: string
  productionBatchId?: string
}

export class StockReceivedEvent implements DomainEvent<StockReceivedPayload> {
  readonly eventType = 'inventory.v1.stock.received'
  readonly eventVersion = '1.0'
  constructor(readonly payload: StockReceivedPayload) {}
  toEnvelope(props: Omit<EventEnvelope<StockReceivedPayload>, 'eventType' | 'eventVersion' | 'payload'>): EventEnvelope<StockReceivedPayload> {
    return { ...props, eventType: this.eventType, eventVersion: this.eventVersion, payload: this.payload }
  }
}

export interface StockShippedPayload {
  movementId: string
  orderId: string
  warehouseId: string
  items: Array<{ sku: string; quantity: number; batchLot?: string; location?: string }>
  shippedAt: string
  carrierId?: string
}

export class StockShippedEvent implements DomainEvent<StockShippedPayload> {
  readonly eventType = 'inventory.v1.stock.shipped'
  readonly eventVersion = '1.0'
  constructor(readonly payload: StockShippedPayload) {}
  toEnvelope(props: Omit<EventEnvelope<StockShippedPayload>, 'eventType' | 'eventVersion' | 'payload'>): EventEnvelope<StockShippedPayload> {
    return { ...props, eventType: this.eventType, eventVersion: this.eventVersion, payload: this.payload }
  }
}

export interface StockReservedPayload {
  reservationId: string
  orderId: string
  items: Array<{ sku: string; quantity: number; warehouseId: string; location?: string }>
  reservedAt: string
  expiresAt?: string
}

export class StockReservedEvent implements DomainEvent<StockReservedPayload> {
  readonly eventType = 'inventory.v1.stock.reserved'
  readonly eventVersion = '1.0'
  constructor(readonly payload: StockReservedPayload) {}
  toEnvelope(props: Omit<EventEnvelope<StockReservedPayload>, 'eventType' | 'eventVersion' | 'payload'>): EventEnvelope<StockReservedPayload> {
    return { ...props, eventType: this.eventType, eventVersion: this.eventVersion, payload: this.payload }
  }
}

export interface LowStockAlertPayload {
  sku: string
  productName?: string
  warehouseId: string
  warehouseName?: string
  currentQuantity: number
  reorderPoint: number
  safetyStock?: number
  averageDailyDemand?: number
  daysUntilStockout?: number
  triggeredAt: string
  severity: 'warning' | 'critical' | 'stockout'
}

export class LowStockAlertEvent implements DomainEvent<LowStockAlertPayload> {
  readonly eventType = 'inventory.v1.low.stock.alert'
  readonly eventVersion = '1.0'
  constructor(readonly payload: LowStockAlertPayload) {}
  toEnvelope(props: Omit<EventEnvelope<LowStockAlertPayload>, 'eventType' | 'eventVersion' | 'payload'>): EventEnvelope<LowStockAlertPayload> {
    return { ...props, eventType: this.eventType, eventVersion: this.eventVersion, payload: this.payload }
  }
}

export interface StockAdjustedPayload {
  adjustmentId: string
  warehouseId: string
  items: Array<{ sku: string; previousQuantity: number; newQuantity: number; difference: number; location?: string }>
  reason: 'cycle_count' | 'damage' | 'loss' | 'correction' | 'return' | 'transfer' | 'adjustment'
  adjustedAt: string
  adjustedBy?: string
}

export class StockAdjustedEvent implements DomainEvent<StockAdjustedPayload> {
  readonly eventType = 'inventory.v1.stock.adjusted'
  readonly eventVersion = '1.0'
  constructor(readonly payload: StockAdjustedPayload) {}
  toEnvelope(props: Omit<EventEnvelope<StockAdjustedPayload>, 'eventType' | 'eventVersion' | 'payload'>): EventEnvelope<StockAdjustedPayload> {
    return { ...props, eventType: this.eventType, eventVersion: this.eventVersion, payload: this.payload }
  }
}
