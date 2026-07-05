import { z } from 'zod'
import { ToolDefinition } from '@agents/tools/tool-registry'

export interface BOMCheckInput {
  bomId: string
  productId: string
  components: Array<{ componentId: string; name: string; quantity: number; materialSpec?: string; notes?: string }>
}

const inputSchema = z.object({
  bomId: z.string().min(1),
  productId: z.string().min(1),
  components: z.array(z.object({
    componentId: z.string().min(1),
    name: z.string().min(1),
    quantity: z.number().int().positive(),
    materialSpec: z.string().optional(),
    notes: z.string().optional(),
  })).min(1),
})

const outputSchema = z.object({
  complete: z.boolean(),
  issues: z.array(z.object({ component: z.string(), field: z.string(), message: z.string() })),
  missingFields: z.array(z.string()),
  duplicateCount: z.number(),
  componentCount: z.number(),
})

type BOMCheckOutput = z.infer<typeof outputSchema>

export const checkBOMCompletenessTool: ToolDefinition<BOMCheckInput, BOMCheckOutput> = {
  name: 'check-bom-completeness',
  description: 'Verifica completude da BOM: componentes duplicados, campos obrigatorios faltantes, quantidades zeradas, especificacoes de material ausentes',
  inputSchema,
  outputSchema,
  timeout: 15000,
  retryCount: 2,
  handler: async (input: BOMCheckInput) => {
    const issues: Array<{ component: string; field: string; message: string }> = []
    const missingFields: string[] = []
    const seen = new Set<string>()
    let duplicateCount = 0

    for (const comp of input.components) {
      if (seen.has(comp.componentId)) {
        duplicateCount++
        issues.push({ component: comp.componentId, field: 'componentId', message: 'Componente duplicado na BOM' })
      }
      seen.add(comp.componentId)

      if (!comp.name || comp.name.length < 2) {
        issues.push({ component: comp.componentId, field: 'name', message: 'Nome do componente ausente ou muito curto' })
        missingFields.push(`${comp.componentId}.name`)
      }

      if (!comp.quantity || comp.quantity <= 0) {
        issues.push({ component: comp.componentId, field: 'quantity', message: 'Quantidade invalida (deve ser > 0)' })
        missingFields.push(`${comp.componentId}.quantity`)
      }

      if (!comp.materialSpec) {
        issues.push({ component: comp.componentId, field: 'materialSpec', message: 'Especificacao de material ausente' })
        missingFields.push(`${comp.componentId}.materialSpec`)
      }
    }

    return {
      complete: issues.length === 0,
      issues,
      missingFields,
      duplicateCount,
      componentCount: input.components.length,
    }
  },
}
