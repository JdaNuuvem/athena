import { BaseEntity } from './base-entity'
import type { DomainEvent } from '../events/domain-event'

export abstract class AggregateRoot extends BaseEntity {
  private _domainEvents: DomainEvent[] = []

  get domainEvents(): ReadonlyArray<DomainEvent> {
    return this._domainEvents
  }

  protected addDomainEvent(event: DomainEvent<any>): void {
    this._domainEvents.push(event)
    this.touch()
  }

  public pullDomainEvents(): DomainEvent[] {
    const events = [...this._domainEvents]
    this._domainEvents = []
    return events
  }

  public clearDomainEvents(): void {
    this._domainEvents = []
  }
}
