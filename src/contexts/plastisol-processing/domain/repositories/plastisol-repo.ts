import type { PlastisolFormulation, CuringCycle } from '../entities'
export interface IFormulationRepository { save(f: PlastisolFormulation): Promise<void>; findById(id: string): Promise<PlastisolFormulation | null>; findByCode(code: string): Promise<PlastisolFormulation | null>; delete(id: string): Promise<void> }
export interface ICuringCycleRepository { save(c: CuringCycle): Promise<void>; findById(id: string): Promise<CuringCycle | null>; findByFormulationId(fid: string): Promise<CuringCycle[]> }
