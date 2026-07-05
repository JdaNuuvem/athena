import { randomUUID } from 'crypto'

export abstract class BaseEntity {
  public readonly id: string
  public readonly createdAt: Date
  public updatedAt: Date

  constructor(id?: string) {
    this.id = id ?? randomUUID()
    this.createdAt = new Date()
    this.updatedAt = new Date()
  }

  protected touch(): void {
    this.updatedAt = new Date()
  }
}
