import { InMemoryEventBus } from '../../src/shared/infrastructure/messaging/in-memory-event-bus'
import { InMemoryMoldRepository } from '../../src/contexts/mold-making/infrastructure/persistence/in-memory-mold.repository'
import { InMemoryCNCRepository } from '../../src/contexts/cnc-machining/infrastructure/persistence/in-memory-cnc.repository'
import { InMemoryInjectionRepository } from '../../src/contexts/injection-molding/infrastructure/persistence/in-memory-injection.repository'
import { InMemoryPlastisolRepository } from '../../src/contexts/plastisol-processing/infrastructure/persistence/in-memory-plastisol.repository'
import { InMemoryStockItemRepository } from '../../src/contexts/inventory/infrastructure/persistence/in-memory-stock-item.repository'

import { OnMoldDesignedHandler, OnMoldFabricationCompletedHandler, OnMoldInstalledHandler, OnMaintenancePerformedHandler } from '../../src/contexts/mold-making/application/event-handlers/mold-handlers'
import { OnCNCJobScheduledHandler, OnCNCMachiningCompletedHandler } from '../../src/contexts/cnc-machining/application/event-handlers/cnc-handlers'
import { OnRunStartedHandler, OnBatchCompletedHandler, OnRunCompletedHandler } from '../../src/contexts/injection-molding/application/event-handlers/injection-handlers'
import { OnFormulationMixedHandler, OnPlastisolBatchCompletedHandler } from '../../src/contexts/plastisol-processing/application/event-handlers/plastisol-handlers'

import { PublishMoldDesigned, PublishMoldFabricationCompleted, PublishMoldInstalled } from '../../src/contexts/mold-making/application/use-cases/publish-events.use-case'
import { PublishJobScheduled, PublishMachiningCompleted } from '../../src/contexts/cnc-machining/application/use-cases/publish-events.use-case'
import { PublishRunStarted, PublishBatchCompleted, PublishRunCompleted } from '../../src/contexts/injection-molding/application/use-cases/publish-events.use-case'
import { PublishBatchCompleted as PublishPlastisolBatch } from '../../src/contexts/plastisol-processing/application/use-cases/publish-events.use-case'

import { v4 as uuidv4 } from 'uuid'

function setupManufacturing() {
  const eventBus = new InMemoryEventBus()
  const moldRepo = new InMemoryMoldRepository()
  const cncRepo = new InMemoryCNCRepository()
  const injectionRepo = new InMemoryInjectionRepository()
  const plastisolRepo = new InMemoryPlastisolRepository()
  const stockRepo = new InMemoryStockItemRepository()

  eventBus.registerHandler('mold-making.v1.mold.designed', new OnMoldDesignedHandler(moldRepo))
  eventBus.registerHandler('mold-making.v1.mold.fabrication.completed', new OnMoldFabricationCompletedHandler(moldRepo))
  eventBus.registerHandler('mold-making.v1.mold.installed', new OnMoldInstalledHandler(moldRepo))
  eventBus.registerHandler('mold-making.v1.maintenance.performed', new OnMaintenancePerformedHandler(moldRepo))
  eventBus.registerHandler('cnc-machining.v1.job.scheduled', new OnCNCJobScheduledHandler(cncRepo))
  eventBus.registerHandler('cnc-machining.v1.machining.completed', new OnCNCMachiningCompletedHandler(cncRepo))
  eventBus.registerHandler('injection-molding.v1.run.started', new OnRunStartedHandler(injectionRepo))
  eventBus.registerHandler('injection-molding.v1.batch.completed', new OnBatchCompletedHandler(injectionRepo))
  eventBus.registerHandler('injection-molding.v1.run.completed', new OnRunCompletedHandler(injectionRepo))
  eventBus.registerHandler('plastisol-processing.v1.formulation.mixed', new OnFormulationMixedHandler(plastisolRepo))
  eventBus.registerHandler('plastisol-processing.v1.batch.completed', new OnPlastisolBatchCompletedHandler(plastisolRepo))

  return {
    eventBus, moldRepo, cncRepo, injectionRepo, plastisolRepo, stockRepo,
    pubMold: new PublishMoldDesigned(eventBus),
    pubMoldFab: new PublishMoldFabricationCompleted(eventBus),
    pubMoldInstalled: new PublishMoldInstalled(eventBus),
    pubJob: new PublishJobScheduled(eventBus),
    pubMachiningDone: new PublishMachiningCompleted(eventBus),
    pubRunStart: new PublishRunStarted(eventBus),
    pubBatchDone: new PublishBatchCompleted(eventBus),
    pubRunDone: new PublishRunCompleted(eventBus),
    pubPlastisolBatch: new PublishPlastisolBatch(eventBus),
  }
}

describe('Phase 3 — Manufacturing Chain', () => {
  it('should track mold lifecycle: designed → fabricated → installed', async () => {
    const ctx = setupManufacturing()
    const moldId = uuidv4()
    const productId = uuidv4()
    const machineId = 'machine-001'

    await ctx.pubMold.execute({ payload: { moldId, productId, cavityCount: 4, steelType: 'P20', designedAt: new Date().toISOString(), moldCode: 'MD-001' }, tenantId: 't1', userId: 'u1' })
    let mold = await ctx.moldRepo.findById(moldId)
    expect(mold!.status).toBe('designed')

    await ctx.pubMoldFab.execute({ payload: { moldId, completedAt: new Date().toISOString() }, tenantId: 't1', userId: 'u1' })
    mold = await ctx.moldRepo.findById(moldId)
    expect(mold!.status).toBe('fabricated')

    await ctx.pubMoldInstalled.execute({ payload: { moldId, machineId, installedAt: new Date().toISOString() }, tenantId: 't1', userId: 'u1' })
    mold = await ctx.moldRepo.findById(moldId)
    expect(mold!.status).toBe('installed')
    expect(mold!.installedMachineId).toBe(machineId)
  })

  it('should track injection molding: run → batch → run completion with OEE', async () => {
    const ctx = setupManufacturing()
    const runId = uuidv4()
    const batchId = uuidv4()
    const moldId = uuidv4()
    const productId = uuidv4()
    const machineId = 'inj-machine-01'

    await ctx.moldRepo.save({ id: moldId, moldCode: 'MD-TEST', productId, cavityCount: 8, steelType: 'H13', cycleLife: 100000, currentCycles: 0, status: 'installed', installedMachineId: machineId, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() })

    await ctx.pubRunStart.execute({ payload: { runId, machineId, moldId, productId, startedAt: new Date().toISOString(), materialLot: 'LOT-001', targetCycles: 1000 }, tenantId: 't1', userId: 'u1' })
    let run = await ctx.injectionRepo.runs.findById(runId)
    expect(run!.status).toBe('running')

    await ctx.pubBatchDone.execute({ payload: { batchId, runId, productId, totalCycles: 500, totalPartsProduced: 3950, defectiveParts: 50, scrapRatePercent: 1.25, completedAt: new Date().toISOString(), qualityStatus: 'approved' }, tenantId: 't1', userId: 'u1' })
    run = await ctx.injectionRepo.runs.findById(runId)
    expect(run!.totalCycles).toBe(500)
    expect(run!.totalPartsProduced).toBe(3950)

    const batch = await ctx.injectionRepo.batches.findById(batchId)
    expect(batch!.qualityStatus).toBe('approved')

    await ctx.pubRunDone.execute({ payload: { runId, machineId, moldId, totalBatches: 2, totalCycles: 1000, totalPartsProduced: 7960, totalDefectives: 40, totalMaterialKg: 120, durationHours: 8, avgOEE: 92.5, completedAt: new Date().toISOString(), moldCycleCountAtEnd: 1000 }, tenantId: 't1', userId: 'u1' })
    run = await ctx.injectionRepo.runs.findById(runId)
    expect(run!.status).toBe('completed')
    expect(run!.oee).toBe(92.5)
    expect(run!.totalMaterialKg).toBe(120)
  })

  it('should track maintenance history on molds', async () => {
    const ctx = setupManufacturing()
    const moldId = uuidv4()
    const maintId = uuidv4()

    await ctx.moldRepo.save({ id: moldId, moldCode: 'MD-MAINT', productId: uuidv4(), cavityCount: 2, steelType: 'P20', cycleLife: 100000, currentCycles: 50000, status: 'installed', createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() })

    // Publish maintenance performed directly via event bus
    await ctx.eventBus.publish({
      eventId: uuidv4(), eventType: 'mold-making.v1.maintenance.performed', eventVersion: '1.0',
      timestamp: new Date().toISOString(), correlationId: 'corr-maint', causationId: null, tenantId: 't1',
      source: { context: 'mold-making', aggregateId: moldId, aggregateType: 'Mold' },
      payload: { maintenanceId: maintId, moldId, type: 'preventive', findings: 'Minor wear on ejector pins', partsReplaced: ['ejector-pin-3', 'ejector-pin-4'], downtimeHours: 2.5, performedAt: new Date().toISOString(), nextMaintenanceCycles: 75000 },
      metadata: { userId: 'tech-1', agentId: null, channel: 'api' },
    })

    const maint = await ctx.moldRepo.maintenances.findById(maintId)
    expect(maint).not.toBeNull()
    expect(maint!.type).toBe('preventive')
    expect(maint!.partsReplaced).toHaveLength(2)
    expect(maint!.downtimeHours).toBe(2.5)

    const maintenances = ctx.moldRepo.maintenances.findBy(m => m.moldId === moldId)
    expect(maintenances).toHaveLength(1)
  })
})
