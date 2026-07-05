import { AggregateRoot } from '@shared/domain/entities'
import { StockReceivedEvent, StockReservedEvent, StockShippedEvent, LowStockAlertEvent, StockAdjustedEvent } from '../events/inventory-events'
import { ReorderPoint } from '../value-objects'
import type { StockReceivedPayload, StockReservedPayload, StockShippedPayload, StockAdjustedPayload } from '../events/inventory-events'

export class StockItem extends AggregateRoot {
  public reorderPoint: ReorderPoint = new ReorderPoint(10)
  public reservedQty = 0

  constructor(
    public readonly sku: string,
    public readonly warehouseId: string,
    public quantity: number,
    id?: string,
  ) {
    super(id)
    if (!sku) throw new Error('StockItem requires SKU')
    if (quantity < 0) throw new Error('Quantity cannot be negative')
  }

  receive(amount: number, referenceId?: string): void {
    if (amount <= 0) throw new Error('Receive amount must be positive')
    this.quantity += amount
    this.addDomainEvent(new StockReceivedEvent({
      movementId: `rec-${Date.now()}`,
      warehouseId: this.warehouseId,
      items: [{ sku: this.sku, quantity: amount, location: '' }],
      receivedAt: new Date().toISOString(),
      purchaseOrderId: referenceId,
    }))
  }

  reserve(amount: number, orderId: string): void {
    if (amount <= 0) throw new Error('Reserve amount must be positive')
    if (amount > this.availableQty) throw new Error(`Insufficient stock: available ${this.availableQty}, requested ${amount}`)
    this.reservedQty += amount
    this.addDomainEvent(new StockReservedEvent({
      reservationId: `res-${orderId}-${Date.now()}`, orderId,
      items: [{ sku: this.sku, quantity: amount, warehouseId: this.warehouseId }],
      reservedAt: new Date().toISOString(),
    }))
  }

  ship(amount: number, orderId: string): void {
    if (amount <= 0) throw new Error('Ship amount must be positive')
    if (amount > this.quantity) throw new Error(`Insufficient stock: ${this.quantity}, requested ${amount}`)
    this.quantity -= amount
    this.reservedQty = Math.max(0, this.reservedQty - amount)
    this.addDomainEvent(new StockShippedEvent({
      movementId: `mov-${Date.now()}`, orderId, warehouseId: this.warehouseId,
      items: [{ sku: this.sku, quantity: amount }],
      shippedAt: new Date().toISOString(),
    }))
    this.checkLowStock()
  }

  adjust(newQuantity: number, reason: string): void {
    const previous = this.quantity
    this.quantity = newQuantity
    this.addDomainEvent(new StockAdjustedEvent({
      adjustmentId: `adj-${Date.now()}`,
      warehouseId: this.warehouseId,
      items: [{ sku: this.sku, previousQuantity: previous, newQuantity, difference: newQuantity - previous }],
      reason: reason as StockAdjustedPayload['reason'],
      adjustedAt: new Date().toISOString(),
    }))
    this.checkLowStock()
  }

  setReorderPoint(quantity: number, leadTimeDays?: number): void {
    this.reorderPoint = new ReorderPoint(quantity, leadTimeDays)
  }

  get availableQty(): number {
    return Math.max(0, this.quantity - this.reservedQty)
  }

  private checkLowStock(): void {
    if (this.reorderPoint.isTriggered(this.quantity, this.reservedQty)) {
      if (this.availableQty <= 0) {
        this.addDomainEvent(new LowStockAlertEvent({
          sku: this.sku, warehouseId: this.warehouseId,
          currentQuantity: this.quantity, reorderPoint: this.reorderPoint.quantity,
          severity: 'stockout', triggeredAt: new Date().toISOString(),
        }))
      } else if (this.quantity <= this.reorderPoint.quantity) {
        this.addDomainEvent(new LowStockAlertEvent({
          sku: this.sku, warehouseId: this.warehouseId,
          currentQuantity: this.quantity, reorderPoint: this.reorderPoint.quantity,
          severity: 'warning', triggeredAt: new Date().toISOString(),
        }))
      }
    }
  }
}

export interface StockMovement {
  id: string
  sku: string
  warehouseId?: string
  type: string
  quantity: number
  reference?: string
  reason?: string
  timestamp?: string
}
