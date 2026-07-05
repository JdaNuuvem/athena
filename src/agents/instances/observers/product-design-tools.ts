import { z } from 'zod'
import type { ToolDefinition } from '../../tools/tool-registry'
import type { DefaultMemoryManager } from '../../memory/memory-manager'

export interface SpecificationInput {
  productId: string; sku: string; name: string; category: string
  materials: Array<{ materialId: string; name: string; type: string }>
  dimensions?: { lengthMm: number; widthMm: number; heightMm: number; weightG: number }
}

export interface BOMCheckInput {
  bomId: string; productId: string
  components: Array<{ componentId: string; name: string; quantity: number; materialSpec?: string; notes?: string }>
}

export function createProductDesignTools(memory: DefaultMemoryManager): ToolDefinition[] {
  return [
    {
      name: 'validate-specification',
      description: 'Valida especificacao de produto: campos obrigatorios, materiais, dimensoes, nomeacao de SKU',
      inputSchema: z.object({
        productId: z.string().min(1), sku: z.string().min(1), name: z.string().min(1),
        category: z.string().min(1),
        materials: z.array(z.object({
          materialId: z.string().min(1), name: z.string().min(1), type: z.string().min(1),
        })).min(1),
        dimensions: z.object({
          lengthMm: z.number().positive(), widthMm: z.number().positive(),
          heightMm: z.number().positive(), weightG: z.number().positive(),
        }).optional(),
      }),
      outputSchema: z.object({
        valid: z.boolean(), score: z.number().min(0).max(100),
        issues: z.array(z.object({
          field: z.string(), severity: z.enum(['error', 'warning']), message: z.string(),
        })),
      }),
      handler: async (input: unknown) => {
        const data = input as SpecificationInput
        const issues: Array<{ field: string; severity: 'error' | 'warning'; message: string }> = []

        if (!data.name || data.name.length < 3) {
          issues.push({ field: 'name', severity: 'error', message: 'Nome deve ter pelo menos 3 caracteres' })
        }
        if (!data.sku.match(/^[A-Z]{2,4}-\d{4,6}-[A-Z]{1,3}$/)) {
          issues.push({ field: 'sku', severity: 'warning', message: 'SKU fora do padrao (ex: PT-0001-A)' })
        }
        if (!data.materials.length) {
          issues.push({ field: 'materials', severity: 'error', message: 'Necessario pelo menos 1 material' })
        }
        for (const mat of data.materials) {
          if (!mat.name || mat.name.length < 2) {
            issues.push({ field: 'materials', severity: 'error', message: `Material "${mat.materialId}" sem nome` })
          }
        }
        if (data.dimensions) {
          const d = data.dimensions
          if (d.lengthMm <= 0 || d.widthMm <= 0 || d.heightMm <= 0) {
            issues.push({ field: 'dimensions', severity: 'error', message: 'Dimensoes devem ser positivas' })
          }
          if (d.weightG <= 0) {
            issues.push({ field: 'dimensions', severity: 'warning', message: 'Peso deve ser > 0' })
          }
        } else {
          issues.push({ field: 'dimensions', severity: 'warning', message: 'Dimensoes nao informadas' })
        }
        if (!data.category) {
          issues.push({ field: 'category', severity: 'error', message: 'Categoria obrigatoria' })
        }

        const errors = issues.filter(i => i.severity === 'error').length
        const score = errors === 0 ? (issues.length === 0 ? 100 : 70) : errors > 2 ? 20 : 50

        memory.episodic.record({
          type: 'specification.validated', agentId: 'AG-001',
          data: { productId: data.productId, valid: errors === 0, score },
        })

        return { valid: errors === 0, issues, score }
      },
    },
    {
      name: 'check-bom-completeness',
      description: 'Verifica BOM: duplicados, campos faltantes, quantidades',
      inputSchema: z.object({
        bomId: z.string().min(1), productId: z.string().min(1),
        components: z.array(z.object({
          componentId: z.string().min(1), name: z.string().min(1),
          quantity: z.number().int().positive(),
          materialSpec: z.string().optional(), notes: z.string().optional(),
        })).min(1),
      }),
      outputSchema: z.object({
        complete: z.boolean(), componentCount: z.number(), duplicateCount: z.number(),
        issues: z.array(z.object({ component: z.string(), field: z.string(), message: z.string() })),
        missingFields: z.array(z.string()),
      }),
      handler: async (input: unknown) => {
        const data = input as BOMCheckInput
        const issues: Array<{ component: string; field: string; message: string }> = []
        const missingFields: string[] = []
        const seen = new Set<string>()
        let dupes = 0

        for (const comp of data.components) {
          if (seen.has(comp.componentId)) {
            dupes++
            issues.push({ component: comp.componentId, field: 'componentId', message: 'Componente duplicado' })
          }
          seen.add(comp.componentId)
          if (!comp.name || comp.name.length < 2) {
            issues.push({ component: comp.componentId, field: 'name', message: 'Nome ausente' })
            missingFields.push(`${comp.componentId}.name`)
          }
          if (!comp.quantity || comp.quantity <= 0) {
            issues.push({ component: comp.componentId, field: 'quantity', message: 'Quantidade invalida' })
            missingFields.push(`${comp.componentId}.quantity`)
          }
          if (!comp.materialSpec) {
            issues.push({ component: comp.componentId, field: 'materialSpec', message: 'MaterialSpec ausente' })
            missingFields.push(`${comp.componentId}.materialSpec`)
          }
        }

        memory.episodic.record({
          type: 'bom.checked', agentId: 'AG-001',
          data: { bomId: data.bomId, productId: data.productId, complete: issues.length === 0 },
        })

        return { complete: issues.length === 0, issues, missingFields, duplicateCount: dupes, componentCount: data.components.length }
      },
    },
  ]
}
