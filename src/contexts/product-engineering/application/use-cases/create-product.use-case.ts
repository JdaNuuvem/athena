import type { IProductRepository } from '../../domain/repositories'
import { Product } from '../../domain/entities'
import { MaterialSpec, DimensionsVO } from '../../domain/value-objects'
import { SpecificationChecker } from '../../domain/services'
import type { IEventBus } from '@shared/domain/events'

export class CreateProductUseCase {
  constructor(
    private productRepo: IProductRepository,
    private eventBus: IEventBus,
  ) {}

  async execute(input: CreateProductInput): Promise<Product> {
    const existing = await this.productRepo.findBySku(input.sku)
    if (existing) throw new Error(`SKU ${input.sku} already exists`)

    const materials = input.materials.map(m => new MaterialSpec(m.materialId, m.name, m.type, m.density, m.mfi))
    const dimensions = input.dimensions
      ? new DimensionsVO(input.dimensions.lengthMm, input.dimensions.widthMm, input.dimensions.heightMm, input.dimensions.weightG)
      : undefined

    const product = new Product(input.sku, input.name, input.category, materials, dimensions)
    new SpecificationChecker().checkCompleteness(product)

    await this.productRepo.save(product)

    for (const event of product.pullDomainEvents()) {
      await this.eventBus.publish(event)
    }

    return product
  }
}

export interface CreateProductInput {
  sku: string
  name: string
  category: string
  materials: Array<{ materialId: string; name: string; type: string; density?: number; mfi?: number }>
  dimensions?: { lengthMm: number; widthMm: number; heightMm: number; weightG: number }
  description?: string
}

export class ApproveRevisionUseCase {
  constructor(
    private productRepo: IProductRepository,
    private eventBus: IEventBus,
  ) {}

  async execute(productId: string, revisionNumber: string, approvedBy: string): Promise<void> {
    const product = await this.productRepo.findById(productId)
    if (!product) throw new Error('Product not found')

    product.approveRevision(revisionNumber, approvedBy)
    await this.productRepo.save(product)

    for (const event of product.pullDomainEvents()) {
      await this.eventBus.publish(event)
    }
  }
}

export class ArchiveProductUseCase {
  constructor(
    private productRepo: IProductRepository,
    private eventBus: IEventBus,
  ) {}

  async execute(productId: string, reason: string): Promise<void> {
    const product = await this.productRepo.findById(productId)
    if (!product) throw new Error('Product not found')

    product.archive(reason)
    await this.productRepo.save(product)

    for (const event of product.pullDomainEvents()) {
      await this.eventBus.publish(event)
    }
  }
}
