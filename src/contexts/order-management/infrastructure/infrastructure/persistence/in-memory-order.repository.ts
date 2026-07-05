import { InMemoryRepository } from '../../../../shared/infrastructure/persistence/in-memory-repository'
import { Order } from '../../domain/entities/order'
import { IOrderRepository } from '../../domain/repositories/order.repository'

export class InMemoryOrderRepository extends InMemoryRepository<Order> implements IOrderRepository {
  async findByStatus(status: string): Promise<Order[]> {
    return this.findBy(item => item.status === status)
  }
}
