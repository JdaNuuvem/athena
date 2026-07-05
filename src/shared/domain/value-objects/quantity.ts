import { ValueObject } from './value-object'

export class Quantity extends ValueObject {
  constructor(
    public readonly value: number,
    public readonly unit: string = 'units',
  ) {
    super()
    if (value < 0) throw new Error('Quantity must be non-negative')
  }

  add(other: Quantity): Quantity {
    if (this.unit !== other.unit) throw new Error('Cannot add quantities with different units')
    return new Quantity(this.value + other.value, this.unit)
  }

  subtract(other: Quantity): Quantity {
    if (this.unit !== other.unit) throw new Error('Cannot subtract quantities with different units')
    return new Quantity(Math.max(0, this.value - other.value), this.unit)
  }

  equals(other: ValueObject): boolean {
    if (!(other instanceof Quantity)) return false
    return this.value === other.value && this.unit === other.unit
  }
}
