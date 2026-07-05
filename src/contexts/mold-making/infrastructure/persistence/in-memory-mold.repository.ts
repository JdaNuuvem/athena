import { InMemoryRepository } from '../../../../shared/infrastructure/persistence/in-memory-repository'
import { Mold, MoldMaintenance } from '../../domain/entities/mold-entities'

export class InMemoryMoldRepository extends InMemoryRepository<Mold> {
  readonly maintenances = new InMemoryRepository<MoldMaintenance>()
  findByProduct(productId: string): Mold | null { return this.findBy(m => m.productId === productId)[0] ?? null }
  getActive(): Mold[] { return this.findBy(m => m.status === 'installed') }
}
