import type { EventEnvelope } from '../../../../shared/domain/events'
import { orderRepo, orderLineRepo, fulfillmentRepo } from '../../infrastructure/persistence/order.repo'
import { Order } from '../../domain/entities/order.entity'

export const orderEventHandlers: Record<string, (envelope: EventEnvelope) => Promise<void>> = {
  'order-management.v1.order.placed': async (env) => {
    const p = env.payload as Record<string, unknown>
    const order = new Order(String(p['orderId'] ?? ''), String(p['customerId'] ?? ''), String(p['channel'] ?? 'manual'))
    order.place()
    order.totalAmount = Number(p['amount'] ?? 0)
    await orderRepo.save(order)
    const lines = (p['lines'] as Array<Record<string, unknown>>) ?? []
    if (lines.length > 0) await orderLineRepo.saveLines(order.id, lines.map(l => ({ sku: String(l['sku']), name: String(l['name'] ?? ''), quantity: Number(l['quantity']), unitPrice: Number(l['unitPrice']) })))
  },

  'order-management.v1.order.confirmed': async (env) => {
    const p = env.payload as Record<string, unknown>
    const order = await orderRepo.findById(String(p['orderId'] ?? ''))
    if (order) { order.confirm(); await orderRepo.save(order) }
  },

  'order-management.v1.order.shipped': async (env) => {
    const p = env.payload as Record<string, unknown>
    const orderId = String(p['orderId'] ?? '')
    const order = await orderRepo.findById(orderId)
    if (order) { order.ship(); await orderRepo.save(order) }
  },

  'order-management.v1.order.delivered': async (env) => {
    const p = env.payload as Record<string, unknown>
    const order = await orderRepo.findById(String(p['orderId'] ?? ''))
    if (order) { order.deliver(); await orderRepo.save(order) }
  },

  'order-management.v1.return.requested': async (env) => {
    const p = env.payload as Record<string, unknown>
    const order = await orderRepo.findById(String(p['orderId'] ?? ''))
    if (order) { order.return(); await orderRepo.save(order) }
    const prisma = (await import('../../../../shared/infrastructure/persistence/prisma-client')).getPrisma()
    try { await prisma.$executeRawUnsafe(`INSERT INTO "Return" (id, "orderId", reason, items) VALUES ($1, $2, $3, $4)`, `ret-${String(p['returnId'])}`, String(p['orderId']), String(p['reason'] ?? ''), JSON.stringify(p['items'] ?? {})) } catch { /* offline */ }
  },

  'order-management.v1.fulfillment.routed': async (env) => {
    const p = env.payload as Record<string, unknown>
    await fulfillmentRepo.save({ orderId: String(p['orderId'] ?? ''), centerId: String(p['centerId'] ?? ''), estimatedDays: Number(p['estimatedDays'] ?? 3) })
  },

  'order-management.v1.fulfillment.completed': async (env) => {
    const p = env.payload as Record<string, unknown>
    const order = await orderRepo.findById(String(p['orderId'] ?? ''))
    if (order) { order.fulfill(); await orderRepo.save(order) }
  },
}
