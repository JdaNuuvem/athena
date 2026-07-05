import { getPrisma } from '../../shared/infrastructure/persistence/prisma-client'
import type { EventEnvelope } from '../../shared/domain/events'

export const catalogEventHandlers: Record<string, (envelope: EventEnvelope) => Promise<void>> = {
  'catalog.v1.product.published': async (env) => {
    const p = env.payload as Record<string, unknown>
    const prisma = getPrisma()
    try {
      await prisma.productCard.upsert({
        where: { productId: String(p['productId']) },
        create: { id: `card-${p['productId']}`, productId: String(p['productId']), name: String(p['name'] ?? ''), categoryId: String(p['category'] ?? ''), status: 'published' },
        update: { status: 'published' },
      })
    } catch { /* offline */ }
  },

  'catalog.v1.product.updated': async (env) => {
    const p = env.payload as Record<string, unknown>
    const prisma = getPrisma()
    try {
      await prisma.productCard.updateMany({
        where: { productId: String(p['productId'] ?? '') },
        data: { name: String(p['name'] ?? undefined), description: String(p['description'] ?? undefined) },
      })
    } catch { /* offline */ }
  },

  'catalog.v1.variant.created': async (env) => {
    const p = env.payload as Record<string, unknown>
    const prisma = getPrisma()
    try {
      const card = await prisma.productCard.findUnique({ where: { productId: String(p['productId']) } })
      if (card) {
        const existing = (card.variants as Array<Record<string, unknown>>) ?? []
        existing.push({ sku: String(p['sku']), price: Number(p['price']), stock: Number(p['stock']) })
        await prisma.productCard.update({ where: { productId: String(p['productId']) }, data: { variants: existing as unknown as object } })
      }
    } catch { /* offline */ }
  },
}

export const customerEventHandlers: Record<string, (envelope: EventEnvelope) => Promise<void>> = {
  'customer.v1.registered': async (env) => {
    const p = env.payload as Record<string, unknown>
    const prisma = getPrisma()
    try {
      await prisma.customer.upsert({
        where: { email: String(p['email'] ?? '') },
        create: { id: String(p['customerId'] ?? ''), name: String(p['name'] ?? ''), email: String(p['email'] ?? ''), phone: String(p['phone'] ?? ''), document: String(p['document'] ?? ''), tier: String(p['tier'] ?? 'bronze') },
        update: { name: String(p['name'] ?? ''), phone: String(p['phone'] ?? '') },
      })
    } catch { /* offline */ }
  },

  'customer.v1.tier.changed': async (env) => {
    const p = env.payload as Record<string, unknown>
    const prisma = getPrisma()
    try {
      await prisma.customer.updateMany({ where: { id: String(p['customerId'] ?? '') }, data: { tier: String(p['newTier'] ?? 'bronze') } })
    } catch { /* offline */ }
  },
}

export const shippingEventHandlers: Record<string, (envelope: EventEnvelope) => Promise<void>> = {
  'shipping.v1.carrier.selected': async (env) => {
    const p = env.payload as Record<string, unknown>
    const prisma = getPrisma()
    try {
      await prisma.shipment.upsert({
        where: { orderId: String(p['orderId'] ?? '') },
        create: { id: `ship-${p['orderId']}`, orderId: String(p['orderId']), carrierId: String(p['carrier'] ?? ''), trackingCode: '', cost: Number(p['cost'] ?? 0), estimatedDays: Number(p['estimatedDays'] ?? 3), status: 'label_created' },
        update: { carrierId: String(p['carrier'] ?? ''), cost: Number(p['cost'] ?? 0) },
      })
    } catch { /* offline */ }
  },

  'shipping.v1.delivery.tracked': async (env) => {
    const p = env.payload as Record<string, unknown>
    const prisma = getPrisma()
    try {
      await prisma.shipment.updateMany({
        where: { trackingCode: String(p['trackingCode'] ?? '') },
        data: { status: String(p['status'] ?? 'in_transit') },
      })
    } catch { /* offline */ }
  },
}

export const pricingEventHandlers: Record<string, (envelope: EventEnvelope) => Promise<void>> = {
  'pricing.v1.updated': async (env) => {
    const p = env.payload as Record<string, unknown>
    const prisma = getPrisma()
    try {
      await prisma.priceListItem.upsert({
        where: { productId: String(p['productId'] ?? '') },
        create: { id: `price-${p['productId']}`, productId: String(p['productId']), price: Number(p['price'] ?? 0), cost: Number(p['cost'] ?? 0) },
        update: { price: Number(p['price'] ?? 0), cost: Number(p['cost'] ?? 0) },
      })
    } catch { /* offline */ }
  },
}
