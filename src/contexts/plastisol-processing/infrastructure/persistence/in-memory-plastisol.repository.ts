import { InMemoryRepository } from '../../../../shared/infrastructure/persistence/in-memory-repository'
import { PlastisolFormulation, CoatingBatch } from '../../domain/entities/plastisol-entities'

export class InMemoryPlastisolRepository {
  readonly formulations = new InMemoryRepository<PlastisolFormulation>()
  readonly batches = new InMemoryRepository<CoatingBatch>()
}
