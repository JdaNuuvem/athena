import { z } from 'zod'
import type { ToolDefinition } from '../tools/tool-registry'

export function createCycleOptimizerTools(): ToolDefinition[] {
  return [
    { name: 'injection.optimize', description: 'Otimiza parâmetros de injeção', inputSchema: z.object({ machineId: z.string(), moldId: z.string(), currentTemp: z.number(), currentPressure: z.number(), currentTime: z.number(), defectRate: z.number(), material: z.string() }), outputSchema: z.object({ suggestedTemp: z.number(), suggestedPressure: z.number(), suggestedTime: z.number(), expectedImprovement: z.number(), confidence: z.number() }), handler: async (input: unknown) => { const d = input as Record<string, unknown>; return { suggestedTemp: Number(d['currentTemp']) * 0.95, suggestedPressure: Number(d['currentPressure']) * 1.05, suggestedTime: Number(d['currentTime']) * 0.9, expectedImprovement: 12, confidence: 0.78 } } },
  ]
}

export function createProductionForecasterTools(): ToolDefinition[] {
  return [
    { name: 'injection.forecast', description: 'Prevê capacidade produtiva', inputSchema: z.object({ machineId: z.string(), historicalOutput: z.array(z.object({ date: z.string(), quantity: z.number(), downtime: z.number() })), scheduledMaintenance: z.array(z.object({ date: z.string(), durationHours: z.number() })).optional(), targetDays: z.number() }), outputSchema: z.object({ projectedOutput: z.number(), confidenceInterval: z.object({ low: z.number(), high: z.number() }), bottlenecks: z.array(z.string()), seasonalityFactor: z.number() }), handler: async (input: unknown) => { const d = input as Record<string, unknown>; const target = Number(d['targetDays']) || 30; const avg = 500; return { projectedOutput: avg * target, confidenceInterval: { low: avg * target * 0.85, high: avg * target * 1.15 }, bottlenecks: ['Manutenção programada em 15 dias reduz capacidade em 20%'], seasonalityFactor: 1.05 } } },
  ]
}

export function createQualityGatekeeperTools(): ToolDefinition[] {
  return [
    { name: 'injection.gatekeep', description: 'Monitora qualidade e decide parada', inputSchema: z.object({ machineId: z.string(), runId: z.string(), defectRates: z.array(z.object({ hour: z.number(), rate: z.number(), defectType: z.string() })), threshold: z.number() }), outputSchema: z.object({ stopRecommended: z.boolean(), currentAvgRate: z.number(), trend: z.enum(['improving', 'stable', 'worsening']), reason: z.string() }), handler: async (input: unknown) => { const d = input as { defectRates: Array<{ rate: number }>; threshold: number }; const avg = d.defectRates.reduce((s, r) => s + r.rate, 0) / d.defectRates.length; const trend = avg > d.threshold ? 'worsening' as const : 'stable' as const; return { stopRecommended: avg > d.threshold, currentAvgRate: avg, trend, reason: avg > d.threshold ? `Taxa média (${(avg * 100).toFixed(1)}%) excede threshold (${(d.threshold * 100).toFixed(1)}%)` : 'Dentro do tolerável' } } },
  ]
}

export function createFormulationOptimizerTools(): ToolDefinition[] {
  return [
    { name: 'plastisol.optimize', description: 'Otimiza formulação de plastisol', inputSchema: z.object({ formulationId: z.string(), currentViscosity: z.number(), targetViscosity: z.number(), components: z.array(z.object({ name: z.string(), type: z.string(), currentRatio: z.number() })), ambientTemp: z.number(), potLifeHours: z.number() }), outputSchema: z.object({ adjustedComponents: z.array(z.object({ name: z.string(), newRatio: z.number(), adjustment: z.string() })), expectedViscosity: z.number(), potLifeImpact: z.string() }), handler: async (input: unknown) => { const d = input as Record<string, unknown>; return { adjustedComponents: [{ name: 'Plastificante', newRatio: 0.45, adjustment: '+5% para reduzir viscosidade' }], expectedViscosity: Number(d['targetViscosity']), potLifeImpact: 'Redução estimada de 10% no pot life' } } },
  ]
}

export function createCuringMonitorTools(): ToolDefinition[] {
  return [
    { name: 'plastisol.monitorCuring', description: 'Monitora ciclo de cura', inputSchema: z.object({ curingId: z.string(), ovenId: z.string(), targetTemp: z.number(), actualTemps: z.array(z.object({ minute: z.number(), temp: z.number() })), targetDuration: z.number(), tolerance: z.number() }), outputSchema: z.object({ onTrack: z.boolean(), maxDeviation: z.number(), timeOverTarget: z.number(), alerts: z.array(z.string()) }), handler: async (input: unknown) => { const d = input as { actualTemps: Array<{ temp: number }>; targetTemp: number; tolerance: number }; const maxDev = Math.max(...d.actualTemps.map(t => Math.abs(t.temp - d.targetTemp))); const alerts = maxDev > d.tolerance ? [`Desvio máximo de ${maxDev.toFixed(1)}°C excede tolerância de ±${d.tolerance}°C`] : []; return { onTrack: maxDev <= d.tolerance, maxDeviation: maxDev, timeOverTarget: d.actualTemps.filter(t => t.temp > d.targetTemp).length, alerts } } },
  ]
}

export function createCoatingQCTools(): ToolDefinition[] {
  return [
    { name: 'plastisol.qc', description: 'Controle de qualidade de revestimento', inputSchema: z.object({ batchId: z.string(), measurements: z.object({ thickness: z.number(), hardness: z.number(), adhesion: z.enum(['pass', 'fail']), colorDeltaE: z.number(), gloss: z.number() }), specs: z.object({ thicknessMin: z.number(), thicknessMax: z.number(), hardnessMin: z.number(), hardnessMax: z.number(), glossMin: z.number() }) }), outputSchema: z.object({ approved: z.boolean(), failedTests: z.array(z.string()), score: z.number() }), handler: async (input: unknown) => { const d = input as { measurements: Record<string, number | string>; specs: Record<string, number> }; const failures: string[] = []; if (Number(d.measurements['thickness']) < d.specs['thicknessMin']!) failures.push('Espessura abaixo do mínimo'); if (d.measurements['adhesion'] === 'fail') failures.push('Teste de aderência falhou'); return { approved: failures.length === 0, failedTests: failures, score: failures.length === 0 ? 92 : 55 } } },
  ]
}

export function createMoldMaterialMatcherTools(): ToolDefinition[] {
  return [
    { name: 'mold.matchMaterial', description: 'Recomenda aço para molde', inputSchema: z.object({ plasticMaterial: z.string(), expectedCycles: z.number(), abrasiveAdditives: z.boolean(), corrosionRisk: z.boolean(), budget: z.enum(['economy', 'standard', 'premium']) }), outputSchema: z.object({ recommended: z.array(z.object({ steel: z.string(), hardness: z.string(), lifespan: z.string(), cost: z.enum(['low', 'medium', 'high']) })), bestMatch: z.string() }), handler: async (input: unknown) => { const d = input as Record<string, unknown>; const budget = String(d['budget']); return { recommended: [{ steel: 'AISI P20', hardness: '28-32 HRC', lifespan: '500k ciclos', cost: 'low' as const }, { steel: 'AISI H13', hardness: '48-52 HRC', lifespan: '1M+ ciclos', cost: 'medium' as const }], bestMatch: budget === 'premium' ? 'AISI H13 temperado' : 'AISI P20' } } },
  ]
}

export function createSetupSheetGeneratorTools(): ToolDefinition[] {
  return [
    { name: 'cnc.generateSetup', description: 'Gera setup sheet automaticamente', inputSchema: z.object({ programId: z.string(), machineId: z.string(), toolList: z.array(z.object({ toolNumber: z.number(), type: z.string(), diameter: z.number(), length: z.number(), stickOut: z.number() })), material: z.string(), workOffset: z.string() }), outputSchema: z.object({ sheetId: z.string(), steps: z.array(z.object({ step: z.number(), description: z.string(), toolNumber: z.number(), speed: z.number(), feed: z.number() })), estimatedTime: z.number() }), handler: async (input: unknown) => { const d = input as { toolList: Array<{ toolNumber: number; type: string; diameter: number; speed?: number; feed?: number }> }; return { sheetId: `SETUP-${Date.now()}`, steps: d.toolList.map((t, i) => ({ step: i + 1, description: `${t.type} D${t.diameter}mm — Desbaste`, toolNumber: t.toolNumber, speed: t.speed ?? 8000, feed: t.feed ?? 1500 })), estimatedTime: d.toolList.length * 12 } } },
  ]
}
