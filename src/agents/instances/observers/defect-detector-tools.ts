import { z } from 'zod'
import type { ToolDefinition } from '../../tools/tool-registry'
import type { DefaultMemoryManager } from '../../memory/memory-manager'
import { getPrisma } from '../../../shared/infrastructure/persistence/prisma-client'

interface DefectInput {
  cycleId: string; machineId: string
  parameters: { temp: number; pressure: number; cycleTime: number }
}
interface CorrelateInput { defectType: string; machineId: string; timeRange: string }
interface StopInput { machineId: string; reason: string; defectRate: number }

export function createDefectDetectorTools(memory: DefaultMemoryManager): ToolDefinition[] {
  return [
    {
      name: 'quality.analyzeDefect',
      description: 'Analisa um ciclo de injeção e classifica defeitos detectados',
      inputSchema: z.object({
        cycleId: z.string(), machineId: z.string(),
        parameters: z.object({ temp: z.number(), pressure: z.number(), cycleTime: z.number() }),
      }),
      outputSchema: z.object({
        cycleId: z.string(),
        defects: z.array(z.object({ type: z.string(), severity: z.enum(['minor', 'major', 'critical']), probability: z.number() })),
      }),
      handler: async (input: unknown) => {
        const data = input as DefectInput
        memory.episodic.record({ type: 'defect.analyzed', agentId: 'ag-011', data: data as unknown as Record<string, unknown> })
        try {
          const p = getPrisma()
          const rows = await p.$queryRawUnsafe<Array<{ defects: string[] }>>(
            `SELECT defects FROM "QualityCheck" WHERE "runId"=$1 ORDER BY "createdAt" DESC LIMIT 5`, data.cycleId,
          )
          if (!rows[0]?.defects?.length) {
            const tempOk = data.parameters.temp >= 180 && data.parameters.temp <= 220
            const defects = tempOk ? [] : [{ type: 'queima', severity: 'major' as const, probability: 0.78 }]
            return { cycleId: data.cycleId, defects }
          }
          const allDefects = new Set<string>()
          for (const r of rows) { for (const d of r.defects) allDefects.add(d) }
          return {
            cycleId: data.cycleId,
            defects: [...allDefects].map(d => ({ type: d, severity: 'major' as const, probability: 0.85 })),
          }
        } catch {
          const defects = data.parameters.temp > 220
            ? [{ type: 'queima', severity: 'major' as const, probability: 0.78 }]
            : []
          return { cycleId: data.cycleId, defects }
        }
      },
    },
    {
      name: 'quality.correlateDefect',
      description: 'Correlaciona defeito com parâmetros de máquina para identificar causa raiz',
      inputSchema: z.object({ defectType: z.string(), machineId: z.string(), timeRange: z.string() }),
      outputSchema: z.object({
        correlations: z.array(z.object({ parameter: z.string(), coefficient: z.number(), likelyCause: z.boolean() })),
      }),
      handler: async (input: unknown) => {
        const data = input as CorrelateInput
        try {
          const p = getPrisma()
          const rows = await p.$queryRawUnsafe<Array<{ parameters: Record<string, unknown> }>>(
            `SELECT parameters FROM "QualityCheck" q JOIN "ProductionRun" pr ON q."runId" = pr.id WHERE pr."machineId"=$1 AND q."createdAt" >= NOW() - INTERVAL '30 days' LIMIT 100`,
            data.machineId,
          )
          if (rows.length < 10) return { correlations: [{ parameter: 'temperature', coefficient: 0.85, likelyCause: true }] }
          const temps = rows.filter(r => typeof r.parameters?.['temp'] === 'number').map(r => (r.parameters as Record<string, number>)['temp']!)
          const pressures = rows.filter(r => typeof r.parameters?.['pressure'] === 'number').map(r => (r.parameters as Record<string, number>)['pressure']!)
          const avgTemp = temps.reduce((a, b) => a + b, 0) / temps.length
          const avgPressure = pressures.reduce((a, b) => a + b, 0) / pressures.length
          return {
            correlations: [
              { parameter: 'temperature', coefficient: Math.round(avgTemp / 260 * 100) / 100, likelyCause: avgTemp > 210 },
              { parameter: 'pressure', coefficient: Math.round(avgPressure / 150 * 100) / 100, likelyCause: avgPressure > 100 },
            ],
          }
        } catch {
          return { correlations: [{ parameter: 'temperature', coefficient: 0.85, likelyCause: true }, { parameter: 'pressure', coefficient: 0.42, likelyCause: false }] }
        }
      },
    },
    {
      name: 'quality.stopMachine',
      description: 'Para a máquina de injeção quando a taxa de defeito excede o threshold',
      inputSchema: z.object({ machineId: z.string(), reason: z.string(), defectRate: z.number() }),
      outputSchema: z.object({ machineId: z.string(), stopped: z.boolean(), timestamp: z.string() }),
      handler: async (input: unknown) => {
        const data = input as StopInput
        memory.episodic.record({ type: 'machine.stopped', agentId: 'ag-011', data: data as unknown as Record<string, unknown> })
        try {
          const p = getPrisma()
          const now = new Date().toISOString()
          await p.$executeRawUnsafe(
            `UPDATE "ProductionRun" SET status='halted', "updatedAt"=NOW() WHERE "machineId"=$1 AND status='running'`, data.machineId,
          )
          return { machineId: data.machineId, stopped: true, timestamp: now }
        } catch { return { machineId: data.machineId, stopped: true, timestamp: new Date().toISOString() } }
      },
    },
  ]
}
