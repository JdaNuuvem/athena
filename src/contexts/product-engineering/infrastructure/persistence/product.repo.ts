import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'
import { Product } from '../../domain/entities/product.entity'

export const productRepo = {
  async save(product: Product, sku: string): Promise<void> {
    const p = getPrisma()
    try {
      await p.$executeRawUnsafe(
        `INSERT INTO "Product" (id, sku, name, category, status, revision) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (id) DO UPDATE SET name=$3, status=$5, revision=$6`,
        product.id, sku, product.name, product.category, product.status, product.revision,
      )
    } catch { /* offline */ }
  },

  async findById(id: string): Promise<Product | null> {
    const p = getPrisma()
    try {
      const rows = await p.$queryRawUnsafe<Array<Record<string, unknown>>>(
        `SELECT id, sku, name, category, status, revision, description FROM "Product" WHERE id=$1`, id,
      )
      if (rows.length === 0) return null
      const r = rows[0]!
      const prod = new Product(String(r['id']), String(r['sku']), String(r['name']), String(r['category']))
      prod.status = String(r['status']); prod.revision = String(r['revision']); prod.description = String(r['description'] ?? '')
      return prod
    } catch { return null }
  },

  async findBySku(sku: string): Promise<Product | null> {
    const p = getPrisma()
    try {
      const rows = await p.$queryRawUnsafe<Array<Record<string, unknown>>>(
        `SELECT id, sku, name, category, status FROM "Product" WHERE sku=$1`, sku,
      )
      if (rows.length === 0) return null
      const r = rows[0]!
      const prod = new Product(String(r['id']), String(r['sku']), String(r['name']), String(r['category']))
      prod.status = String(r['status'])
      return prod
    } catch { return null }
  },
}

export const bomRepo = {
  async save(productId: string, components: Array<{ name: string; quantity: number; materialSpec?: string }>): Promise<void> {
    const p = getPrisma()
    try {
      await p.$executeRawUnsafe(
        `INSERT INTO "BOM" (id, "productId", components) VALUES ($1, $2, $3) ON CONFLICT ("productId") DO UPDATE SET components=$3`,
        `bom-${productId}`, productId, JSON.stringify(components),
      )
      await p.$executeRawUnsafe(`DELETE FROM "Component" WHERE "productId"=$1`, productId)
      for (const c of components) {
        await p.$executeRawUnsafe(
          `INSERT INTO "Component" (id, "productId", name, quantity, "materialSpec") VALUES ($1, $2, $3, $4, $5)`,
          `cmp-${productId}-${c.name}`, productId, c.name, c.quantity, c.materialSpec ?? null,
        )
      }
    } catch { /* offline */ }
  },

  async findByProductId(productId: string): Promise<Array<{ name: string; quantity: number; materialSpec: string | null }>> {
    const p = getPrisma()
    try {
      const rows = await p.$queryRawUnsafe<Array<Record<string, unknown>>>(
        `SELECT name, quantity, "materialSpec" FROM "Component" WHERE "productId"=$1`, productId,
      )
      return rows.map(r => ({ name: String(r['name']), quantity: Number(r['quantity']), materialSpec: r['materialSpec'] ? String(r['materialSpec']) : null }))
    } catch { return [] }
  },
}

export const revisionRepo = {
  async create(productId: string, revisionNumber: string, changes: string): Promise<void> {
    const p = getPrisma()
    try {
      await p.$executeRawUnsafe(
        `INSERT INTO "Revision" (id, "productId", "revisionNumber", changes) VALUES ($1, $2, $3, $4)`,
        `rev-${productId}-${revisionNumber}`, productId, revisionNumber, changes,
      )
    } catch { /* offline */ }
  },

  async approve(revisionId: string, approvedBy: string): Promise<void> {
    const p = getPrisma()
    try {
      await p.$executeRawUnsafe(
        `UPDATE "Revision" SET status='approved', "approvedBy"=$1, "approvedAt"=NOW() WHERE id=$2`,
        approvedBy, revisionId,
      )
    } catch { /* offline */ }
  },
}
