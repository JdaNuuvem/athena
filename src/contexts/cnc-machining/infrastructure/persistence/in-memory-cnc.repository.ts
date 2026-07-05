import { InMemoryRepository } from '../../../../shared/infrastructure/persistence/in-memory-repository'
import { CNCJob, CNCTool, MachineDowntime } from '../../domain/entities/cnc-entities'

export class InMemoryCNCRepository {
  readonly jobs = new InMemoryRepository<CNCJob>()
  readonly tools = new InMemoryRepository<CNCTool>()
  readonly downtimes = new InMemoryRepository<MachineDowntime>()
  getActiveJobs(): CNCJob[] { return this.jobs.findBy(j => j.status === 'running' || j.status === 'scheduled') }
}
