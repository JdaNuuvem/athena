import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'
import { Order } from '../../domain/entities/order.entity'

// ponytail: raw SQL because Prisma 7 generated types don't match schema fields 1:1
export const orderRepo = {
  async save(order: Order): Promise<void> {
    const p = getPrisma()
    try {
      await p.$executeRawUnsafe(
        `INSERT INTO "Order" (id, "customerId", channel, status, "totalAmount", "createdAt", "updatedAt") VALUES ($1, $2, $3, $4, $5, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET status=$4, "totalAmount"=$5, "updatedAt"=NOW()`,
        order.id, order.customerId, order.channel, order.status, order.totalAmount,
      )
    } catch { /* Prisma offline */ }
  },

  async findById(id: string): Promise<Order | null> {
    const p = getPrisma()
    try {
      const rows = await p.$queryRawUnsafe<Array<Record<string, unknown>>>(
        `SELECT id, "customerId", channel, status, "totalAmount" FROM "Order" WHERE id=$1`, id,
      )
      if (rows.length === 0) return null
      const r = rows[0]!
      const order = new Order(String(r['id']), String(r['customerId']), String(r['channel']))
      order.status = String(r['status']); order.totalAmount = Number(r['totalAmount'])
      return order
    } catch { return null }
  },

  async findByCustomer(customerId: string): Promise<Order[]> {
    const p = getPrisma()
    try {
      const rows = await p.$queryRawUnsafe<Array<Record<string, unknown>>>(
        `SELECT id, "customerId", channel, status, "totalAmount" FROM "Order" WHERE "customerId"=$1 ORDER BY "createdAt" DESC LIMIT 50`, customerId,
      )
      return rows.map(r => { const o = new Order(String(r['id']), String(r['customerId']), String(r['channel'])); o.status = String(r['status']); return o })
    } catch { return [] }
  },
}

export const orderLineRepo = {
  async saveLines(orderId: string, lines: Array<{ sku: string; name: string; quantity: number; unitPrice: number }>): Promise<void> {
    const p = getPrisma()
    try {
      await p.$executeRawUnsafe(`DELETE FROM "OrderLine" WHERE "orderId"=$1`, orderId)
      for (const l of lines) {
        await p.$executeRawUnsafe(
          `INSERT INTO "OrderLine" (id, "orderId", sku, name, quantity, "unitPrice") VALUES (gen_random_uuid(), $1, $2, $3, $4, $5)`,
          orderId, l.sku, l.name, l.quantity, l.unitPrice,
        )
      }
    } catch { /* Prisma offline */ }
  },
}

export const fulfillmentRepo = {
  async save(params: { orderId: string; centerId?: string; estimatedDays?: number }): Promise<void> {
    const p = getPrisma()
    try {
      await p.$executeRawUnsafe(
        `INSERT INTO "Fulfillment" (id, "orderId", "centerId", "estimatedDays", status) VALUES ($1, $2, $3, $4, 'pending') ON CONFLICT ("orderId") DO UPDATE SET "centerId"=$3, "estimatedDays"=$4`,
        `ful-${params.orderId}`, params.orderId, params.centerId ?? null, params.estimatedDays ?? 3,
      )
    } catch { /* offline */ }
  },

  async markShipped(orderId: string, trackingCode: string, carrierId: string): Promise<void> {
    const p = getPrisma()
    try {
      await p.$executeRawUnsafe(
        `UPDATE "Fulfillment" SET status='shipped', "trackingCode"=$1, "carrierId"=$2, "shippedAt"=NOW() WHERE "orderId"=$3`,
        trackingCode, carrierId, orderId,
      )
    } catch { /* offline */ }
  },
}
