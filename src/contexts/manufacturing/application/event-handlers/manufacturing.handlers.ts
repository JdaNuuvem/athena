import type { EventEnvelope } from '../../../../shared/domain/events'
import { moldRepo, maintenanceRepo, cncJobRepo, productionRunRepo, qualityCheckRepo, plastisolRepo } from '../../infrastructure/persistence/manufacturing.repo'

export const manufacturingEventHandlers: Record<string, (envelope: EventEnvelope) => Promise<void>> = {
  'mold-making.v1.mold.designed': async (env) => {
    const p = env.payload as Record<string, unknown>
    await moldRepo.save({ id: String(p['moldId']), moldCode: String(p['moldCode']), productId: String(p['productId']), steelType: String(p['steelType'] ?? 'P20'), cycleLife: Number(p['cycleLife'] ?? 500000), cavities: Number(p['cavities'] ?? 1), status: 'design' })
  },

  'mold-making.v1.mold.ready': async (env) => {
    const p = env.payload as Record<string, unknown>
    await moldRepo.updateStatus(String(p['moldId']), 'ready')
  },

  'mold-making.v1.maintenance.scheduled': async (env) => {
    const p = env.payload as Record<string, unknown>
    await maintenanceRepo.record({ moldId: String(p['moldId']), type: String(p['maintenanceType'] ?? 'preventive'), description: String(p['description'] ?? ''), cost: Number(p['cost'] ?? 0) })
    await moldRepo.updateStatus(String(p['moldId']), 'maintenance')
  },

  'mold-making.v1.maintenance.completed': async (env) => {
    const p = env.payload as Record<string, unknown>
    await moldRepo.updateStatus(String(p['moldId']), 'ready')
  },

  'cnc-machining.v1.job.created': async (env) => {
    const p = env.payload as Record<string, unknown>
    await cncJobRepo.save({ id: String(p['jobId']), partNumber: String(p['partNumber']), estimatedHours: Number(p['estimatedHours'] ?? 1), priority: Number(p['priority'] ?? 1), status: 'scheduled' })
  },

  'cnc-machining.v1.job.started': async (env) => {
    const p = env.payload as Record<string, unknown>
    await cncJobRepo.assignToMachine(String(p['jobId']), String(p['machineId'] ?? ''), String(p['programId'] ?? ''))
  },

  'cnc-machining.v1.job.completed': async (env) => {
    const p = env.payload as Record<string, unknown>
    await cncJobRepo.save({ id: String(p['jobId']), partNumber: '', estimatedHours: 0, priority: 0, status: 'completed' })
  },

  'injection-molding.v1.run.started': async (env) => {
    const p = env.payload as Record<string, unknown>
    await productionRunRepo.save({ id: String(p['runId']), moldId: String(p['moldId']), machineId: String(p['machineId']), productSku: String(p['productSku']), targetQuantity: Number(p['targetQuantity'] ?? 0), status: 'running' })
  },

  'injection-molding.v1.run.completed': async (env) => {
    const p = env.payload as Record<string, unknown>
    await productionRunRepo.updateProgress(String(p['runId']), Number(p['producedQuantity'] ?? 0), Number(p['scrapQuantity'] ?? 0), Number(p['defectRate'] ?? 0))
    await productionRunRepo.save({ id: String(p['runId']), moldId: '', machineId: '', productSku: '', targetQuantity: 0, status: 'completed' })
  },

  'injection-molding.v1.quality.checked': async (env) => {
    const p = env.payload as Record<string, unknown>
    await qualityCheckRepo.record({
      id: String(p['checkId'] ?? `qc-${Date.now()}`), runId: String(p['runId']),
      passed: Boolean(p['passed']), defects: (p['defects'] as string[]) ?? [],
      parameters: (p['parameters'] as Record<string, unknown>) ?? {},
    })
  },

  'plastisol-processing.v1.formulation.mixed': async (env) => {
    const p = env.payload as Record<string, unknown>
    await plastisolRepo.saveFormulation({
      id: String(p['formulationId']), formulaCode: String(p['formulaCode']),
      components: (p['components'] as Record<string, unknown>) ?? {},
      viscosity: Number(p['viscosity'] ?? 0), gelTemperature: Number(p['gelTemperature'] ?? 0),
    })
  },

  'plastisol-processing.v1.curing.started': async (env) => {
    const p = env.payload as Record<string, unknown>
    await plastisolRepo.saveCuringCycle({
      id: String(p['curingId']), formulationId: String(p['formulationId']),
      lineId: String(p['lineId']), targetTemperature: Number(p['targetTemperature'] ?? 0),
      targetDuration: Number(p['targetDuration'] ?? 0), status: 'started',
    })
  },

  'plastisol-processing.v1.curing.completed': async (env) => {
    const p = env.payload as Record<string, unknown>
    await plastisolRepo.completeCuringCycle(String(p['curingId']), Number(p['actualTemperature'] ?? 0), Number(p['actualDuration'] ?? 0))
  },
}
