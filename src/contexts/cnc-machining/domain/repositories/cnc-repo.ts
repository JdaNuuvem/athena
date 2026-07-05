import type { CNCJob } from '../entities'
export interface ICNCJobRepository { save(j: CNCJob): Promise<void>; findById(id: string): Promise<CNCJob | null>; findByStatus(status: string): Promise<CNCJob[]>; findPending(): Promise<CNCJob[]>; delete(id: string): Promise<void> }
