import type { IBOMRepository } from '../../domain/repositories'
import type { IProductRepository } from '../../domain/repositories'
import { BOM, BOMComponent } from '../../domain/entities'
import { BOMValidator } from '../../domain/services'
import type { IEventBus } from '@shared/domain/events'

export class CreateBOMUseCase {
  constructor(
    private bomRepo: IBOMRepository,
    private productRepo: IProductRepository,
    private eventBus: IEventBus,
  ) {}

  async execute(input: CreateBOMInput): Promise<BOM> {
    const product = await this.productRepo.findById(input.productId)
    if (!product) throw new Error('Product not found')

    const existing = await this.bomRepo.findByProductId(input.productId)
    if (existing) throw new Error('BOM already exists for this product')

    const components: BOMComponent[] = input.components.map(c => ({
      componentId: c.componentId, name: c.name, quantity: c.quantity,
      materialSpec: c.materialSpec, notes: c.notes,
    }))

    const validation = new BOMValidator().validate(components)
    if (!validation.valid) throw new Error(`BOM validation failed: ${validation.issues.join(', ')}`)

    const bom = new BOM(input.productId, components)
    await this.bomRepo.save(bom)

    for (const event of bom.pullDomainEvents()) {
      await this.eventBus.publish(event)
    }

    return bom
  }
}

export interface CreateBOMInput {
  productId: string
  components: Array<{ componentId: string; name: string; quantity: number; materialSpec?: string; notes?: string }>
}

export class UpdateBOMUseCase {
  constructor(
    private bomRepo: IBOMRepository,
    private eventBus: IEventBus,
  ) {}

  async execute(bomId: string, components: BOMComponent[], updatedBy: string): Promise<BOM> {
    const bom = await this.bomRepo.findById(bomId)
    if (!bom) throw new Error('BOM not found')

    bom.components = components
    bom.validate(updatedBy)
    await this.bomRepo.save(bom)

    for (const event of bom.pullDomainEvents()) {
      await this.eventBus.publish(event)
    }

    return bom
  }
}
