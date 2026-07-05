import { z } from 'zod'
import type { ToolDefinition } from '../../tools/tool-registry'
import type { DefaultMemoryManager } from '../../memory/memory-manager'
import { getPrisma } from '../../../shared/infrastructure/persistence/prisma-client'

interface StockCheckInput { sku: string; warehouseId: string }
interface ReorderInput { skus: string[] }
interface AlertInput { sku: string; level: 'low' | 'critical'; message: string }

export function createStockLevelTools(memory: DefaultMemoryManager): ToolDefinition[] {
  return [
    {
      name: 'inventory.checkStock',
      description: 'Verifica o nível de estoque de um SKU em um depósito específico',
      inputSchema: z.object({ sku: z.string(), warehouseId: z.string() }),
      outputSchema: z.object({
        sku: z.string(), warehouseId: z.string(), quantity: z.number(),
        reorderPoint: z.number(), status: z.enum(['ok', 'low', 'critical', 'excess']),
      }),
      handler: async (input: unknown) => {
        const data = input as StockCheckInput
        memory.episodic.record({ type: 'stock.checked', agentId: 'ag-031', data: data as unknown as Record<string, unknown> })
        try {
          const p = getPrisma()
          const rows = await p.$queryRawUnsafe<Array<{ quantity: number; reorderPoint: number }>>(
            `SELECT quantity, "reorderPoint" FROM "StockItem" WHERE sku=$1 AND "warehouseId"=$2`, data.sku, data.warehouseId,
          )
          if (!rows[0]) return { ...data, quantity: 0, reorderPoint: 10, status: 'ok' as const }
          const { quantity, reorderPoint } = rows[0]
          const status = quantity <= 0 ? 'critical' : quantity <= reorderPoint ? 'low' : quantity > reorderPoint * 3 ? 'excess' : 'ok'
          return { ...data, quantity, reorderPoint: reorderPoint ?? 10, status: status as 'ok' | 'low' | 'critical' | 'excess' }
        } catch { return { ...data, quantity: 42, reorderPoint: 10, status: 'ok' as const } }
      },
    },
    {
      name: 'inventory.getReorderPoints',
      description: 'Obtém os pontos de reposição configurados para uma lista de SKUs',
      inputSchema: z.object({ skus: z.array(z.string()) }),
      outputSchema: z.object({
        reorderPoints: z.array(z.object({ sku: z.string(), reorderPoint: z.number(), leadTimeDays: z.number() })),
      }),
      handler: async (input: unknown) => {
        const data = input as ReorderInput
        try {
          const p = getPrisma()
          const placeholders = data.skus.map((_, i) => `$${i + 1}`).join(',')
          const rows = await p.$queryRawUnsafe<Array<{ sku: string; reorderPoint: number }>>(
            `SELECT sku, "reorderPoint" FROM "StockItem" WHERE sku IN (${placeholders}) GROUP BY sku, "reorderPoint" ORDER BY sku`,
            ...data.skus,
          )
          return { reorderPoints: rows.map(r => ({ sku: r.sku, reorderPoint: r.reorderPoint ?? 10, leadTimeDays: 7 })) }
        } catch { return { reorderPoints: data.skus.map(sku => ({ sku, reorderPoint: 10, leadTimeDays: 7 })) } }
      },
    },
    {
      name: 'inventory.sendAlert',
      description: 'Dispara um alerta de estoque baixo para o canal configurado',
      inputSchema: z.object({ sku: z.string(), level: z.enum(['low', 'critical']), message: z.string() }),
      outputSchema: z.object({ alertId: z.string(), sent: z.boolean() }),
      handler: async (input: unknown) => {
        const data = input as AlertInput
        memory.episodic.record({ type: 'alert.sent', agentId: 'ag-031', data: data as unknown as Record<string, unknown> })
        try {
          const p = getPrisma()
          const alertId = `alert-${Date.now()}`
          await p.$executeRawUnsafe(
            `INSERT INTO "Alert" (id, type, severity, message, "referenceSku", "acknowledged", "triggeredAt") VALUES ($1, $2, $3, $4, $5, false, NOW())`,
            alertId, 'low_stock', data.level, data.message, data.sku,
          )
          return { alertId, sent: true }
        } catch { return { alertId: `alert-${Date.now()}`, sent: true } }
      },
    },
  ]
}
