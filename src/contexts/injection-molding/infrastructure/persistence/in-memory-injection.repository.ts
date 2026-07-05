import { InMemoryRepository } from '../../../../shared/infrastructure/persistence/in-memory-repository'
import { ProductionRun, ProductionBatch, DefectRecord } from '../../domain/entities/injection-entities'

export class InMemoryInjectionRepository {
  readonly runs = new InMemoryRepository<ProductionRun>()
  readonly batches = new InMemoryRepository<ProductionBatch>()
  readonly defects = new InMemoryRepository<DefectRecord>()
  getActiveRuns(): ProductionRun[] { return this.runs.findBy(r => r.status === 'running') }
}
