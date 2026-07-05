import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'

export const moldRepo = {
  async save(mold: { id: string; moldCode: string; productId: string; steelType: string; cycleLife: number; cavities: number; status: string }): Promise<void> {
    const p = getPrisma(); try { await p.$executeRawUnsafe(`INSERT INTO "Mold" (id, "moldCode", "productId", "steelType", "cycleLife", cavities, status) VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (id) DO UPDATE SET status=$7`, mold.id, mold.moldCode, mold.productId, mold.steelType, mold.cycleLife, mold.cavities, mold.status) } catch { /* offline */ }
  },
  async updateStatus(id: string, status: string): Promise<void> { const p = getPrisma(); try { await p.$executeRawUnsafe(`UPDATE "Mold" SET status=$1 WHERE id=$2`, status, id) } catch { /* offline */ } },
}

export const maintenanceRepo = {
  async record(params: { moldId: string; type: string; description: string; cost: number }): Promise<void> {
    const p = getPrisma(); try { await p.$executeRawUnsafe(`INSERT INTO "MaintenanceRecord" (id, "moldId", type, description, cost, "performedAt") VALUES (gen_random_uuid(),$1,$2,$3,$4,NOW())`, params.moldId, params.type, params.description, params.cost) } catch { /* offline */ }
  },
}

export const cncJobRepo = {
  async save(job: { id: string; partNumber: string; estimatedHours: number; priority: number; status: string }): Promise<void> {
    const p = getPrisma(); try { await p.$executeRawUnsafe(`INSERT INTO "CNCJob" (id, "partNumber", "estimatedHours", priority, status) VALUES ($1,$2,$3,$4,$5) ON CONFLICT (id) DO UPDATE SET status=$5`, job.id, job.partNumber, job.estimatedHours, job.priority, job.status) } catch { /* offline */ }
  },
  async assignToMachine(id: string, machineId: string, programId: string): Promise<void> {
    const p = getPrisma(); try { await p.$executeRawUnsafe(`UPDATE "CNCJob" SET "machineId"=$1, "programId"=$2, status='running' WHERE id=$3`, machineId, programId, id) } catch { /* offline */ }
  },
}

export const productionRunRepo = {
  async save(run: { id: string; moldId: string; machineId: string; productSku: string; targetQuantity: number; status: string }): Promise<void> {
    const p = getPrisma(); try { await p.$executeRawUnsafe(`INSERT INTO "ProductionRun" (id,"moldId","machineId","productSku","targetQuantity",status) VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (id) DO UPDATE SET status=$6`, run.id, run.moldId, run.machineId, run.productSku, run.targetQuantity, run.status) } catch { /* offline */ }
  },
  async updateProgress(id: string, produced: number, scrap: number, defectRate: number): Promise<void> {
    const p = getPrisma(); try { await p.$executeRawUnsafe(`UPDATE "ProductionRun" SET "producedQuantity"=$1, "scrapQuantity"=$2, "defectRate"=$3 WHERE id=$4`, produced, scrap, defectRate, id) } catch { /* offline */ }
  },
}

export const qualityCheckRepo = {
  async record(params: { id: string; runId: string; passed: boolean; defects: string[]; parameters: Record<string, unknown> }): Promise<void> {
    const p = getPrisma(); try { await p.$executeRawUnsafe(`INSERT INTO "QualityCheck" (id,"runId",passed,defects,parameters) VALUES ($1,$2,$3,$4,$5)`, params.id, params.runId, params.passed, params.defects, JSON.stringify(params.parameters)) } catch { /* offline */ }
  },
}

export const plastisolRepo = {
  async saveFormulation(formula: { id: string; formulaCode: string; components: Record<string, unknown>; viscosity: number; gelTemperature: number }): Promise<void> {
    const p = getPrisma(); try { await p.$executeRawUnsafe(`INSERT INTO "PlastisolFormulation" (id,"formulaCode",components,viscosity,"gelTemperature") VALUES ($1,$2,$3,$4,$5) ON CONFLICT ("formulaCode") DO UPDATE SET components=$3`, formula.id, formula.formulaCode, JSON.stringify(formula.components), formula.viscosity, formula.gelTemperature) } catch { /* offline */ }
  },
  async saveCuringCycle(cycle: { id: string; formulationId: string; lineId: string; targetTemperature: number; targetDuration: number; status: string }): Promise<void> {
    const p = getPrisma(); try { await p.$executeRawUnsafe(`INSERT INTO "CuringCycle" (id,"formulationId","lineId","targetTemperature","targetDuration",status) VALUES ($1,$2,$3,$4,$5,$6)`, cycle.id, cycle.formulationId, cycle.lineId, cycle.targetTemperature, cycle.targetDuration, cycle.status) } catch { /* offline */ }
  },
  async completeCuringCycle(id: string, actualTemp: number, actualDuration: number): Promise<void> {
    const p = getPrisma(); try { await p.$executeRawUnsafe(`UPDATE "CuringCycle" SET status='completed',"actualTemperature"=$1,"actualDuration"=$2 WHERE id=$3`, actualTemp, actualDuration, id) } catch { /* offline */ }
  },
}
