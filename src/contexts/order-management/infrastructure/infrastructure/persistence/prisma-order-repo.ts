import { getPrisma } from '@shared/infrastructure/persistence/prisma-client'
import type { IOrderRepository } from '../../domain/repositories'
import { Order, OrderLine } from '../../domain/entities'

export class PrismaOrderRepository implements IOrderRepository {
  async save(order: Order): Promise<void> {
    const prisma = getPrisma()
    await prisma.order.upsert({
      where: { id: order.id },
      create: {
        id: order.id, customerId: order.customerId, channel: order.channel,
        status: order.status, totalAmount: order.totalAmount,
        shippingAddress: order.shippingAddress ?? null,
        correlationId: order.correlationId ?? null,
      },
      update: { status: order.status, totalAmount: order.totalAmount, shippingAddress: order.shippingAddress ?? null },
    })

    await prisma.orderLine.deleteMany({ where: { orderId: order.id } })
    for (const line of order.lines) {
      await prisma.orderLine.create({
        data: { orderId: order.id, sku: line.sku, name: line.name, quantity: line.quantity, unitPrice: line.unitPrice },
      })
    }
  }

  async findById(id: string): Promise<Order | null> {
    const prisma = getPrisma()
    const row = await prisma.order.findUnique({ where: { id }, include: { lines: true } })
    if (!row) return null
    return this.toDomain(row, row.lines)
  }

  async findByCustomer(customerId: string): Promise<Order[]> {
    const prisma = getPrisma()
    const rows = await prisma.order.findMany({ where: { customerId }, include: { lines: true } })
    return rows.map(r => this.toDomain(r, r.lines))
  }

  async findByStatus(status: string): Promise<Order[]> {
    const prisma = getPrisma()
    const rows = await prisma.order.findMany({ where: { status }, include: { lines: true } })
    return rows.map(r => this.toDomain(r, r.lines))
  }

  async delete(id: string): Promise<void> {
    const prisma = getPrisma()
    await prisma.order.delete({ where: { id } })
  }

  private toDomain(row: { id: string; customerId: string; channel: string; status: string; totalAmount: number; shippingAddress: unknown }, lines: Array<{ sku: string; name: string; quantity: number; unitPrice: number }>): Order {
    const orderLines: OrderLine[] = lines.map(l => ({ sku: l.sku, name: l.name, quantity: l.quantity, unitPrice: l.unitPrice }))
    const order = new Order(row.customerId, row.channel, orderLines, row.totalAmount, (row.shippingAddress as Record<string, unknown>) ?? undefined, row.id)
    order.status = row.status as Order['status']
    return order
  }
}

import type { IFulfillmentRepository } from '../../domain/repositories'
import { Fulfillment } from '../../domain/entities'

export class PrismaFulfillmentRepository implements IFulfillmentRepository {
  async save(fulfillment: Fulfillment): Promise<void> {
    const prisma = getPrisma()
    await prisma.fulfillment.upsert({
      where: { id: fulfillment.id },
      create: {
        id: fulfillment.id, orderId: fulfillment.orderId, type: fulfillment.type,
        status: fulfillment.status, centerId: fulfillment.centerId ?? null,
        estimatedDays: fulfillment.estimatedDays, trackingCode: fulfillment.trackingCode ?? null,
        carrierId: fulfillment.carrierId ?? null, shippedAt: fulfillment.shippedAt ?? null,
        deliveredAt: fulfillment.deliveredAt ?? null,
      },
      update: { status: fulfillment.status, centerId: fulfillment.centerId ?? null, trackingCode: fulfillment.trackingCode ?? null, carrierId: fulfillment.carrierId ?? null, shippedAt: fulfillment.shippedAt ?? null, deliveredAt: fulfillment.deliveredAt ?? null },
    })
  }

  async findByOrderId(orderId: string): Promise<Fulfillment | null> {
    const prisma = getPrisma()
    const row = await prisma.fulfillment.findUnique({ where: { orderId } })
    if (!row) return null
    return this.toDomain(row)
  }

  async findById(id: string): Promise<Fulfillment | null> {
    const prisma = getPrisma()
    const row = await prisma.fulfillment.findUnique({ where: { id } })
    if (!row) return null
    return this.toDomain(row)
  }

  private toDomain(row: { id: string; orderId: string; type: string; status: string; centerId: string | null; estimatedDays: number; trackingCode: string | null; carrierId: string | null; shippedAt: Date | null; deliveredAt: Date | null }): Fulfillment {
    const f = new Fulfillment(row.orderId, row.type, row.estimatedDays, row.id)
    f.status = row.status as Fulfillment['status']
    f.centerId = row.centerId ?? undefined
    f.trackingCode = row.trackingCode ?? undefined
    f.carrierId = row.carrierId ?? undefined
    f.shippedAt = row.shippedAt ?? undefined
    f.deliveredAt = row.deliveredAt ?? undefined
    return f
  }
}
