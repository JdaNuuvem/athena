import { getPrisma } from '@shared/infrastructure/persistence/prisma-client'
import type { IProductRepository } from '../../domain/repositories'
import { Product, BOMComponent } from '../../domain/entities'
import { MaterialSpec, DimensionsVO } from '../../domain/value-objects'

export class PrismaProductRepository implements IProductRepository {
  async save(product: Product): Promise<void> {
    const prisma = getPrisma()
    const data = {
      id: product.id, sku: product.sku, name: product.name,
      description: product.description ?? null, category: product.category,
      status: product.status, revision: product.revision,
      cadFileHash: product.cadFileHash ?? null,
      updatedAt: new Date(),
    }
    await prisma.product.upsert({ where: { id: product.id }, create: data, update: data })
  }

  async findById(id: string): Promise<Product | null> {
    const prisma = getPrisma()
    const row = await prisma.product.findUnique({ where: { id }, include: { components: true } })
    if (!row) return null
    return this.toDomain(row, row.components)
  }

  async findBySku(sku: string): Promise<Product | null> {
    const prisma = getPrisma()
    const row = await prisma.product.findUnique({ where: { sku }, include: { components: true } })
    if (!row) return null
    return this.toDomain(row, row.components)
  }

  async findByCategory(category: string): Promise<Product[]> {
    const prisma = getPrisma()
    const rows = await prisma.product.findMany({ where: { category }, include: { components: true } })
    return rows.map(r => this.toDomain(r, r.components))
  }

  async findActive(): Promise<Product[]> {
    const prisma = getPrisma()
    const rows = await prisma.product.findMany({ where: { status: 'active' }, include: { components: true } })
    return rows.map(r => this.toDomain(r, r.components))
  }

  async delete(id: string): Promise<void> {
    const prisma = getPrisma()
    await prisma.product.delete({ where: { id } })
  }

  private toDomain(row: {
    id: string; sku: string; name: string; category: string;
    description: string | null; status: string; revision: string; cadFileHash: string | null;
  }, components: Array<{ id: string; name: string; quantity: number; materialSpec: string | null; notes: string | null }>): Product {
    const materials: MaterialSpec[] = components.map(c => {
      const spec = c.materialSpec ?? 'unspecified'
      return new MaterialSpec(c.id, c.name, spec)
    })
    const p = new Product(row.sku, row.name, row.category, materials, undefined, row.id)
    p.description = row.description ?? undefined
    p.status = row.status as Product['status']
    p.revision = row.revision
    p.cadFileHash = row.cadFileHash ?? undefined
    return p
  }
}
