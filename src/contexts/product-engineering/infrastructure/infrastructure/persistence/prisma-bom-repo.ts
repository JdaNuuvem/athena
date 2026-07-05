import { getPrisma } from '@shared/infrastructure/persistence/prisma-client'
import type { IBOMRepository } from '../../domain/repositories'
import { BOM, BOMComponent } from '../../domain/entities'

export class PrismaBOMRepository implements IBOMRepository {
  async save(bom: BOM): Promise<void> {
    const prisma = getPrisma()
    await prisma.bOM.upsert({
      where: { id: bom.id },
      create: {
        id: bom.id, productId: bom.productId, revision: bom.revision,
        components: bom.components, validated: bom.validated,
        validatedAt: bom.validatedAt ?? null, validatedBy: bom.validatedBy ?? null,
      },
      update: {
        revision: bom.revision, components: bom.components,
        validated: bom.validated, validatedAt: bom.validatedAt ?? null,
        validatedBy: bom.validatedBy ?? null,
      },
    })
  }

  async findById(id: string): Promise<BOM | null> {
    const prisma = getPrisma()
    const row = await prisma.bOM.findUnique({ where: { id } })
    if (!row) return null
    const components = row.components as unknown as BOMComponent[]
    const bom = new BOM(row.productId, components, row.revision, row.id)
    bom.validated = row.validated
    bom.validatedAt = row.validatedAt ?? undefined
    bom.validatedBy = row.validatedBy ?? undefined
    return bom
  }

  async findByProductId(productId: string): Promise<BOM | null> {
    const prisma = getPrisma()
    const row = await prisma.bOM.findUnique({ where: { productId } })
    if (!row) return null
    const components = row.components as unknown as BOMComponent[]
    const bom = new BOM(row.productId, components, row.revision, row.id)
    bom.validated = row.validated
    bom.validatedAt = row.validatedAt ?? undefined
    bom.validatedBy = row.validatedBy ?? undefined
    return bom
  }

  async delete(id: string): Promise<void> {
    const prisma = getPrisma()
    await prisma.bOM.delete({ where: { id } })
  }
}
