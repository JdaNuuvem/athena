import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'

export const moldRepo = {
  async save(mold: { id: string; moldCode: string; productId: string; steelType: string; cycleLife: number; cavities: number; status: string }): Promise<void> {
    const p = getPrisma()
    try {
      await p.$executeRawUnsafe(
        `INSERT INTO "Mold" (id, "moldCode", "productId", "steelType", "cycleLife", cavities, status) VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (id) DO UPDATE SET status=$7, "updatedAt"=NOW()`,
        mold.id, mold.moldCode, mold.productId, mold.steelType, mold.cycleLife, mold.cavities, mold.status,
      )
    } catch { /* offline */ }
  },

  async findById(id: string): Promise<Record<string, unknown> | null> {
    const p = getPrisma()
    try {
      const rows = await p.$queryRawUnsafe<Array<Record<string, unknown>>>(`SELECT * FROM "Mold" WHERE id=$1`, id)
      return rows[0] ?? null
    } catch { return null }
  },

  async findByProductId(productId: string): Promise<Array<Record<string, unknown>>> {
    const p = getPrisma()
    try {
      return p.$queryRawUnsafe<Array<Record<string, unknown>>>(`SELECT * FROM "Mold" WHERE "productId"=$1`, productId)
    } catch { return [] }
  },

  async updateStatus(id: string, status: string): Promise<void> {
    const p = getPrisma()
    try { await p.$executeRawUnsafe(`UPDATE "Mold" SET status=$1, "updatedAt"=NOW() WHERE id=$2`, status, id) } catch { /* offline */ }
  },
}

export const maintenanceRepo = {
  async record(params: { moldId: string; type: string; description: string; cost: number }): Promise<void> {
    const p = getPrisma()
    try {
      await p.$executeRawUnsafe(
        `INSERT INTO "MaintenanceRecord" (id, "moldId", type, description, cost, "performedAt") VALUES (gen_random_uuid(), $1, $2, $3, $4, NOW())`,
        params.moldId, params.type, params.description, params.cost,
      )
    } catch { /* offline */ }
  },

  async getHistory(moldId: string): Promise<Array<Record<string, unknown>>> {
    const p = getPrisma()
    try {
      return p.$queryRawUnsafe<Array<Record<string, unknown>>>(`SELECT * FROM "MaintenanceRecord" WHERE "moldId"=$1 ORDER BY "performedAt" DESC`, moldId)
    } catch { return [] }
  },
}
