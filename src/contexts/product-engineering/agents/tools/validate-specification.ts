import { z } from 'zod'
import { ToolDefinition } from '@agents/tools/tool-registry'

export interface SpecificationInput {
  productId: string
  sku: string
  name: string
  category: string
  materials: Array<{ materialId: string; name: string; type: string }>
  dimensions?: { lengthMm: number; widthMm: number; heightMm: number; weightG: number }
}

const inputSchema = z.object({
  productId: z.string().min(1),
  sku: z.string().min(1),
  name: z.string().min(1),
  category: z.string().min(1),
  materials: z.array(z.object({
    materialId: z.string().min(1),
    name: z.string().min(1),
    type: z.string().min(1),
  })).min(1),
  dimensions: z.object({
    lengthMm: z.number().positive(),
    widthMm: z.number().positive(),
    heightMm: z.number().positive(),
    weightG: z.number().positive(),
  }).optional(),
})

const outputSchema = z.object({
  valid: z.boolean(),
  issues: z.array(z.object({ field: z.string(), severity: z.enum(['error', 'warning']), message: z.string() })),
  score: z.number().min(0).max(100),
})

type SpecificationOutput = z.infer<typeof outputSchema>

export const validateSpecificationTool: ToolDefinition<SpecificationInput, SpecificationOutput> = {
  name: 'validate-specification',
  description: 'Valida especificacao de produto: campos obrigatorios, materiais validos, dimensoes consistentes, nomeacao de SKU',
  inputSchema,
  outputSchema,
  timeout: 15000,
  retryCount: 2,
  handler: async (input: SpecificationInput) => {
    const issues: Array<{ field: string; severity: 'error' | 'warning'; message: string }> = []

    if (!input.name || input.name.length < 3) {
      issues.push({ field: 'name', severity: 'error', message: 'Nome do produto deve ter pelo menos 3 caracteres' })
    }

    if (!input.sku.match(/^[A-Z]{2,4}-\d{4,6}-[A-Z]{1,3}$/)) {
      issues.push({ field: 'sku', severity: 'warning', message: 'SKU fora do padrao recomendado (ex: PT-0001-A)' })
    }

    if (!input.materials.length) {
      issues.push({ field: 'materials', severity: 'error', message: 'Produto deve ter pelo menos 1 material' })
    }

    for (const mat of input.materials) {
      if (!mat.name || mat.name.length < 2) {
        issues.push({ field: 'materials', severity: 'error', message: `Material "${mat.materialId}" sem nome valido` })
      }
    }

    if (input.dimensions) {
      const d = input.dimensions
      if (d.lengthMm <= 0 || d.widthMm <= 0 || d.heightMm <= 0) {
        issues.push({ field: 'dimensions', severity: 'error', message: 'Dimensoes devem ser positivas' })
      }
      if (d.weightG <= 0) {
        issues.push({ field: 'dimensions', severity: 'warning', message: 'Peso deve ser maior que zero' })
      }
    } else {
      issues.push({ field: 'dimensions', severity: 'warning', message: 'Dimensoes nao informadas' })
    }

    if (!input.category) {
      issues.push({ field: 'category', severity: 'error', message: 'Categoria obrigatoria' })
    }

    const errors = issues.filter(i => i.severity === 'error').length
    const score = errors === 0 ? (issues.length === 0 ? 100 : 70) : errors > 2 ? 20 : 50

    return { valid: errors === 0, issues, score }
  },
}
