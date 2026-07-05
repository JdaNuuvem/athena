import { AgentRuntime } from '../../core/agent-runtime'
import { AgentContext } from '../../core/agent-context'
import { DefaultMemoryManager } from '../../memory/memory-manager'
import { DefaultToolRegistry, type ToolDefinition } from '../../tools/tool-registry'
import { ToolExecutor } from '../../tools/tool-executor'
import { z } from 'zod'
import type { AgentDefinition } from '../../core/agent-types'

const DEFINITION: AgentDefinition = {
  id: 'ag-001', name: 'product-design-assistant', role: 'observer', context: 'product-engineering',
  systemPrompt: `Você é o Product Design Assistant. Auxilia designers plásticos com:
- Validação de especificações técnicas
- Sugestão de materiais alternativos
- Verificação de manufaturabilidade do design
- Recomendações de ângulos de saída e espessura de parede`,
  capabilities: [{ name: 'spec.validate', description: 'Validate product spec', inputSchema: {}, outputSchema: {} }],
  config: { modelProvider: 'openai', modelName: 'gpt-4o-mini', temperature: 0.3, maxTokens: 2048, retryPolicy: { maxRetries: 2, backoffMs: 1000 }, timeout: 30000 },
}

const tools: ToolDefinition[] = [
  {
    name: 'spec.validate',
    description: 'Valida especificação de produto plástico',
    inputSchema: z.object({ productId: z.string(), sku: z.string(), name: z.string(), category: z.string(), material: z.string(), draftAngle: z.number(), wallThickness: z.number(), maxTemp: z.number().optional() }),
    outputSchema: z.object({ valid: z.boolean(), issues: z.array(z.object({ field: z.string(), severity: z.enum(['error', 'warning']), message: z.string() })), score: z.number() }),
    handler: async (input: unknown) => {
      const d = input as { name: string; draftAngle: number; wallThickness: number; maxTemp?: number }
      const issues: Array<{ field: string; severity: 'error' | 'warning'; message: string }> = []
      if (!d.name || d.name.length < 3) issues.push({ field: 'name', severity: 'error', message: 'Nome do produto muito curto (mín 3 caracteres)' })
      if (d.draftAngle < 1) issues.push({ field: 'draftAngle', severity: 'error', message: 'Ângulo de saída insuficiente (mín 1° para desmolde)' })
      if (d.wallThickness < 1.5) issues.push({ field: 'wallThickness', severity: 'warning', message: 'Espessura abaixo de 1.5mm — risco de fragilidade' })
      if (d.wallThickness > 4) issues.push({ field: 'wallThickness', severity: 'warning', message: 'Espessura acima de 4mm — risco de rechupo' })
      if (d.maxTemp && d.maxTemp > 120) issues.push({ field: 'maxTemp', severity: 'warning', message: 'Temperatura de uso elevada — considerar PPS ou PEEK' })
      return { valid: issues.filter(i => i.severity === 'error').length === 0, issues, score: issues.length === 0 ? 95 : Math.max(40, 95 - issues.length * 15) }
    },
  },
  {
    name: 'spec.suggestMaterial',
    description: 'Sugere materiais para o produto',
    inputSchema: z.object({ productType: z.string(), requirements: z.object({ strength: z.enum(['low', 'medium', 'high']), flexibility: z.enum(['low', 'medium', 'high']), heatResistance: z.enum(['low', 'medium', 'high']), foodContact: z.boolean().optional(), uvResistant: z.boolean().optional() }) }),
    outputSchema: z.object({ suggestions: z.array(z.object({ material: z.string(), density: z.number(), meltTemp: z.string(), moldShrinkage: z.string(), cost: z.enum(['low', 'medium', 'high']), compatibility: z.number() })) }),
    handler: async (input: unknown) => {
      const d = input as { requirements: { strength: string; heatResistance: string; foodContact?: boolean; uvResistant?: boolean } }
      const suggestions: Array<{ material: string; density: number; meltTemp: string; moldShrinkage: string; cost: 'low' | 'medium' | 'high'; compatibility: number }> = []
      if (d.requirements.strength === 'low' && d.requirements.heatResistance === 'low') {
        suggestions.push({ material: 'Polipropileno (PP)', density: 0.91, meltTemp: '160-170°C', moldShrinkage: '1.5-2.0%', cost: 'low', compatibility: 0.95 })
      }
      if (d.requirements.strength === 'medium') {
        suggestions.push({ material: 'ABS', density: 1.05, meltTemp: '200-240°C', moldShrinkage: '0.4-0.7%', cost: 'medium', compatibility: 0.85 })
      }
      if (d.requirements.heatResistance === 'high') {
        suggestions.push({ material: 'Policarbonato (PC)', density: 1.20, meltTemp: '260-300°C', moldShrinkage: '0.5-0.7%', cost: 'high', compatibility: 0.90 })
      }
      if (d.requirements.strength === 'high') {
        suggestions.push({ material: 'Nylon 6/6 (PA66)', density: 1.14, meltTemp: '250-270°C', moldShrinkage: '1.5-2.0%', cost: 'medium', compatibility: 0.80 })
      }
      if (d.requirements.foodContact) {
        suggestions.push({ material: 'Tritan (PCT)', density: 1.18, meltTemp: '260-280°C', moldShrinkage: '0.5-0.7%', cost: 'high', compatibility: 0.92 })
      }
      if (d.requirements.uvResistant) {
        suggestions.push({ material: 'ASA', density: 1.07, meltTemp: '220-250°C', moldShrinkage: '0.4-0.7%', cost: 'medium', compatibility: 0.88 })
      }
      return { suggestions: suggestions.length > 0 ? suggestions : [{ material: 'Polipropileno (PP)', density: 0.91, meltTemp: '160-170°C', moldShrinkage: '1.5-2.0%', cost: 'low', compatibility: 0.75 }] }
    },
  },
  {
    name: 'spec.checkManufacturability',
    description: 'Verifica manufaturabilidade do design para injeção',
    inputSchema: z.object({ productId: z.string(), geometry: z.object({ hasUndercuts: z.boolean(), hasSharpCorners: z.boolean(), uniformWallThickness: z.boolean(), maxDrawDepth: z.number(), ribThicknessRatio: z.number().optional() }) }),
    outputSchema: z.object({ manufacturable: z.boolean(), issues: z.array(z.string()), estimatedCycleTime: z.number(), toolingComplexity: z.enum(['simple', 'moderate', 'complex']) }),
    handler: async (input: unknown) => {
      const d = input as { geometry: { hasUndercuts: boolean; hasSharpCorners: boolean; uniformWallThickness: boolean; maxDrawDepth: number; ribThicknessRatio?: number } }
      const issues: string[] = []
      if (d.geometry.hasUndercuts) issues.push('Undercuts detectados — requer slides ou lifters no molde')
      if (d.geometry.hasSharpCorners) issues.push('Cantos vivos — adicionar raio mínimo de 0.5mm')
      if (!d.geometry.uniformWallThickness) issues.push('Espessura não uniforme — risco de empenamento')
      if (d.geometry.maxDrawDepth > 100) issues.push('Profundidade de extração > 100mm — verificar curso da máquina')
      if (d.geometry.ribThicknessRatio && d.geometry.ribThicknessRatio > 0.7) issues.push('Nervuras muito espessas — risco de rechupo (manter ≤ 0.6x espessura)')
      const complexity = issues.length >= 3 ? 'complex' as const : issues.length >= 1 ? 'moderate' as const : 'simple' as const
      return { manufacturable: complexity !== 'complex', issues, estimatedCycleTime: complexity === 'simple' ? 18 : complexity === 'moderate' ? 25 : 35, toolingComplexity: complexity }
    },
  },
]

export class ProductDesignAssistantAgent extends AgentRuntime {
  private exec: ToolExecutor
  constructor() {
    const memory = new DefaultMemoryManager()
    const registry = new DefaultToolRegistry()
    for (const t of tools) registry.register(t)
    super('ag-001', DEFINITION, new AgentContext('ag-001', memory, registry))
    this.exec = new ToolExecutor(registry)
  }
  override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> {
    await super.handleTask(task)
    if (task['type'] === 'validate_spec') {
      const r = await this.exec.execute('spec.validate', task)
      return { ...task, result: r }
    }
    if (task['type'] === 'suggest_material') {
      const r = await this.exec.execute('spec.suggestMaterial', task)
      return { ...task, result: r }
    }
    if (task['type'] === 'check_manufacturability') {
      const r = await this.exec.execute('spec.checkManufacturability', task)
      return { ...task, result: r }
    }
    return super.handleTask(task)
  }
}
