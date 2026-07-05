import type { Mold, MaintenanceRecord } from '../entities'
export interface IMoldRepository { save(m: Mold): Promise<void>; findById(id: string): Promise<Mold | null>; findByProductId(productId: string): Promise<Mold | null>; findActive(): Promise<Mold[]>; delete(id: string): Promise<void> }
export interface IMaintenanceRepository { save(m: MaintenanceRecord): Promise<void>; findByMoldId(moldId: string): Promise<MaintenanceRecord[]>; findById(id: string): Promise<MaintenanceRecord | null> }
