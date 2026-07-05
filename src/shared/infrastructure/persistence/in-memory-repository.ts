export interface IRepository<T, TId = string> {
  findById(id: TId): Promise<T | null>
  save(entity: T): Promise<void>
  delete(id: TId): Promise<void>
}

export class InMemoryRepository<T extends { id: string }, TId = string> implements IRepository<T, TId> {
  protected store = new Map<string, T>()

  async findById(id: TId): Promise<T | null> {
    return this.store.get(String(id)) ?? null
  }

  async save(entity: T): Promise<void> {
    this.store.set(entity.id, { ...entity })
  }

  async delete(id: TId): Promise<void> {
    this.store.delete(String(id))
  }

  getAll(): T[] {
    return Array.from(this.store.values())
  }

  findBy(predicate: (item: T) => boolean): T[] {
    return this.getAll().filter(predicate)
  }

  clear(): void {
    this.store.clear()
  }
}
