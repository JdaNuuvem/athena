import { ValueObject } from './value-object'

export type Currency = 'BRL' | 'USD' | 'EUR'

export class Money extends ValueObject {
  constructor(
    public readonly amount: number,
    public readonly currency: Currency = 'BRL',
  ) {
    super()
    if (amount < 0) throw new Error('Money amount must be non-negative')
  }

  add(other: Money): Money {
    if (this.currency !== other.currency) throw new Error('Cannot add different currencies')
    return new Money(this.amount + other.amount, this.currency)
  }

  subtract(other: Money): Money {
    if (this.currency !== other.currency) throw new Error('Cannot subtract different currencies')
    return new Money(Math.max(0, this.amount - other.amount), this.currency)
  }

  multiply(factor: number): Money {
    return new Money(this.amount * factor, this.currency)
  }

  equals(other: ValueObject): boolean {
    if (!(other instanceof Money)) return false
    return this.amount === other.amount && this.currency === other.currency
  }
}
