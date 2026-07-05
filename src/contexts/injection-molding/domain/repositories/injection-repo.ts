import type { ProductionRun, QualityCheck } from '../entities'
export interface IProductionRunRepository { save(r: ProductionRun): Promise<void>; findById(id: string): Promise<ProductionRun | null>; findByMoldId(moldId: string): Promise<ProductionRun[]>; findActive(): Promise<ProductionRun[]>; delete(id: string): Promise<void> }
export interface IQualityCheckRepository { save(q: QualityCheck): Promise<void>; findByRunId(runId: string): Promise<QualityCheck[]> }
