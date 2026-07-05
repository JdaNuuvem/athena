import type { EventEnvelope } from '../../../../shared/domain/events'
import { productRepo, bomRepo, revisionRepo } from '../../infrastructure/persistence/product.repo'
import { Product } from '../../domain/entities/product.entity'

export const productEventHandlers: Record<string, (envelope: EventEnvelope) => Promise<void>> = {
  'product-engineering.v1.product.designed': async (env) => {
    const p = env.payload as Record<string, unknown>
    const product = new Product(String(p['productId']), String(p['sku']), String(p['name'] ?? ''), String(p['category'] ?? ''))
    product.status = 'draft'
    await productRepo.save(product, String(p['sku']))
  },

  'product-engineering.v1.product.archived': async (env) => {
    const p = env.payload as Record<string, unknown>
    const product = await productRepo.findById(String(p['productId'] ?? ''))
    if (product) { product.archive(); await productRepo.save(product, product.sku || '') }
  },

  'product-engineering.v1.bom.updated': async (env) => {
    const p = env.payload as Record<string, unknown>
    const components = (p['components'] as Array<Record<string, unknown>>) ?? []
    await bomRepo.save(String(p['productId'] ?? ''), components.map(c => ({ name: String(c['name'] ?? ''), quantity: Number(c['quantity'] ?? 1), materialSpec: String(c['materialSpec'] ?? '') })))
  },

  'product-engineering.v1.revision.approved': async (env) => {
    const p = env.payload as Record<string, unknown>
    await revisionRepo.approve(String(p['revisionId'] ?? ''), String(p['approvedBy'] ?? 'system'))
    const product = await productRepo.findById(String(p['productId'] ?? ''))
    if (product) {
      product.revision = String(p['newRevision'] ?? product.revision)
      await productRepo.save(product, product.sku || '')
    }
  },
}
