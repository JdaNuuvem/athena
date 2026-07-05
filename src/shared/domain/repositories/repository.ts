export interface IRepository<T, TId = string> {
  findById(id: TId): Promise<T | null>
  save(entity: T): Promise<void>
  delete(id: TId): Promise<void>
}
