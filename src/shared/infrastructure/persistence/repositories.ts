import { getPrisma } from './prisma-client'

export const stockRepository = {
  async findBySku(sku: string, warehouseId: string): Promise<Record<string, unknown> | null> {
    const prisma = getPrisma()
    const rows = await prisma.$queryRawUnsafe<Array<Record<string, unknown>>>(
      `SELECT * FROM "StockItem" WHERE sku=$1 AND "warehouseId"=$2 LIMIT 1`, sku, warehouseId,
    )
    return rows[0] ?? null
  },

  async findLowStock(reorderThreshold: number): Promise<Array<Record<string, unknown>>> {
    const prisma = getPrisma()
    return prisma.$queryRawUnsafe<Array<Record<string, unknown>>>(
      `SELECT * FROM "StockItem" WHERE quantity - "reservedQuantity" <= "reorderPoint" * $1`, reorderThreshold,
    )
  },
}

export const orderRepository = {
  async findByStatus(status: string, limit = 50): Promise<Array<Record<string, unknown>>> {
    const prisma = getPrisma()
    return prisma.$queryRawUnsafe<Array<Record<string, unknown>>>(
      `SELECT * FROM "Order" WHERE status=$1 LIMIT $2`, status, limit,
    )
  },
}

export const agentRepository = {
  async save(id: string, name: string, role: string, context: string): Promise<void> {
    const prisma = getPrisma()
    await prisma.$executeRawUnsafe(
      `INSERT INTO "Agent" (id, name, role, context, status, "systemPrompt", "createdAt", "updatedAt")
       VALUES ($1, $2, $3, $4, 'running', '', NOW(), NOW())
       ON CONFLICT (id) DO UPDATE SET status='running', "updatedAt"=NOW()`,
      id, name, role, context,
    )
  },

  async updateStatus(id: string, status: string): Promise<void> {
    const prisma = getPrisma()
    await prisma.$executeRawUnsafe(
      `UPDATE "Agent" SET status=$1, "updatedAt"=NOW() WHERE id=$2`, status, id,
    )
  },
}
