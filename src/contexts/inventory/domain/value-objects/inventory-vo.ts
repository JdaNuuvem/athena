import { ValueObject } from '@shared/domain/value-objects'

export class LocationVO extends ValueObject {
  constructor(
    public readonly warehouseId: string,
    public readonly binCode?: string,
  ) {
    super()
    if (!warehouseId) throw new Error('Location requires warehouseId')
  }

  equals(other: ValueObject): boolean {
    return other instanceof LocationVO
      && other.warehouseId === this.warehouseId
      && other.binCode === this.binCode
  }
}

export class BatchLot extends ValueObject {
  constructor(
    public readonly batchId: string,
    public readonly expiryDate?: Date,
  ) {
    super()
  }

  equals(other: ValueObject): boolean {
    return other instanceof BatchLot && other.batchId === this.batchId
  }
}

export class ReorderPoint extends ValueObject {
  constructor(
    public readonly quantity: number,
    public readonly leadTimeDays: number = 7,
  ) {
    super()
    if (quantity < 0) throw new Error('Reorder point must be non-negative')
  }

  isTriggered(currentQty: number, reservedQty: number = 0): boolean {
    return (currentQty - reservedQty) <= this.quantity
  }

  equals(other: ValueObject): boolean {
    return other instanceof ReorderPoint
      && other.quantity === this.quantity
      && other.leadTimeDays === this.leadTimeDays
  }
}
