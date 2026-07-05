import { getPrisma } from '../../shared/infrastructure/persistence/prisma-client'
import type { EventEnvelope } from '../../shared/domain/events'

export const marketplaceEventHandlers: Record<string, (envelope: EventEnvelope) => Promise<void>> = {
  'marketplace.v1.listing.published': async (env) => {
    const p = getPrisma(); const d = env.payload as Record<string, unknown>
    try { await p.$executeRawUnsafe(`INSERT INTO "ChannelListing" (id, "productId", channel, "mlItemId", price, stock, status, "syncedAt") VALUES ($1,$2,$3,$4,$5,$6,'active',NOW()) ON CONFLICT ("productId",channel) DO UPDATE SET "mlItemId"=$4, price=$5, stock=$6, "syncedAt"=NOW()`, `list-${d['mlId']}`, String(d['productId'] || ''), 'mercadolivre', String(d['mlId'] || ''), Number(d['price'] || 0), Number(d['quantity'] || 0)) } catch { /* offline */ }
  },
  'marketplace.v1.listing.updated': async (env) => {
    const p = getPrisma(); const d = env.payload as Record<string, unknown>
    try { await p.$executeRawUnsafe(`UPDATE "ChannelListing" SET price=$1, stock=$2, "syncedAt"=NOW() WHERE "mlItemId"=$3`, Number(d['price'] || 0), Number(d['stock'] || 0), String(d['mlItemId'] || '')) } catch { /* offline */ }
  },
  'marketplace.v1.order.synced': async (env) => {
    const p = getPrisma(); const d = env.payload as Record<string, unknown>
    try { await p.$executeRawUnsafe(`INSERT INTO "Order" (id, "customerId", channel, status, "totalAmount") VALUES ($1,$2,'marketplace','placed',$3) ON CONFLICT (id) DO NOTHING`, String(d['orderId'] || ''), String(d['buyerId'] || ''), Number(d['total'] || 0)) } catch { /* offline */ }
  },
  'marketplace.v1.health.alert': async (env) => {
    const d = env.payload as Record<string, unknown>
    console.warn(`[Marketplace] Health alert: ${String(d['message'])}`)
  },
}

export const retailEventHandlers: Record<string, (envelope: EventEnvelope) => Promise<void>> = {
  'retail.v1.sale.completed': async (env) => {
    const p = getPrisma(); const d = env.payload as Record<string, unknown>
    try { await p.$executeRawUnsafe(`INSERT INTO "SaleTransaction" (id, "storeId", total, "paymentMethod", items) VALUES ($1,$2,$3,$4,$5)`, String(d['saleId'] || ''), String(d['storeId'] || ''), Number(d['total'] || 0), String(d['paymentMethod'] || 'credit'), JSON.stringify(d['items'] || [])) } catch { /* offline */ }
  },
  'retail.v1.inventory.audited': async (env) => {
    const p = getPrisma(); const d = env.payload as Record<string, unknown>
    try { const items = (d['items'] as Array<Record<string, unknown>>) || []; for (const item of items) { await p.$executeRawUnsafe(`UPDATE "StockItem" SET quantity=$1, "updatedAt"=NOW() WHERE sku=$2 AND "warehouseId"=$3`, Number(item['physical'] || 0), String(item['sku']), String(d['storeId'] || '')) } } catch { /* offline */ }
  },
  'retail.v1.shift.closed': async (env) => {
    const d = env.payload as Record<string, unknown>
    console.log(`[Retail] Store ${String(d['storeId'])} shift closed: sales=${d['totalSales']}`)
  },
}

export const telegramEventHandlers: Record<string, (envelope: EventEnvelope) => Promise<void>> = {
  'telegram.v1.order.created': async (env) => {
    const p = getPrisma(); const d = env.payload as Record<string, unknown>
    try { await p.$executeRawUnsafe(`INSERT INTO "ChatOrder" (id, "chatId", "customerId", status, items, total) VALUES ($1,$2,$3,'open',$4,$5)`, String(d['orderId'] || ''), String(d['chatId'] || ''), String(d['customerId'] || ''), JSON.stringify(d['items'] || []), Number(d['total'] || 0)) } catch { /* offline */ }
  },
  'telegram.v1.session.started': async (env) => {
    const p = getPrisma(); const d = env.payload as Record<string, unknown>
    try { await p.$executeRawUnsafe(`INSERT INTO "ChatSession" (id, "chatId", "customerId", status) VALUES ($1,$2,$3,'active') ON CONFLICT ("chatId") DO UPDATE SET "lastActivity"=NOW()`, `sess-${String(d['chatId'])}`, String(d['chatId']), String(d['customerId'] || '')) } catch { /* offline */ }
  },
  'telegram.v1.message.received': async (env) => {
    const p = getPrisma(); const d = env.payload as Record<string, unknown>
    try { await p.$executeRawUnsafe(`UPDATE "ChatSession" SET messages = messages || $1::jsonb, "lastActivity"=NOW() WHERE "chatId"=$2`, JSON.stringify([{ role: 'user', content: d['text'], at: new Date().toISOString() }]), String(d['chatId'] || '')) } catch { /* offline */ }
  },
}

export const analyticsEventHandlers: Record<string, (envelope: EventEnvelope) => Promise<void>> = {
  'analytics.v1.report.generated': async (env) => {
    const p = getPrisma(); const d = env.payload as Record<string, unknown>
    try { await p.$executeRawUnsafe(`INSERT INTO "Report" (id, title, "metricType", data, period) VALUES ($1,$2,$3,$4,$5)`, String(d['reportId'] || ''), String(d['title'] || ''), String(d['metricType'] || ''), JSON.stringify(d['data'] || {}), String(d['period'] || 'daily')) } catch { /* offline */ }
  },
  'analytics.v1.metric.recorded': async (env) => {
    const p = getPrisma(); const d = env.payload as Record<string, unknown>
    try { await p.$executeRawUnsafe(`INSERT INTO "Metric" (id, name, value, tags) VALUES ($1,$2,$3,$4)`, `met-${Date.now()}`, String(d['name'] || ''), Number(d['value'] || 0), JSON.stringify(d['tags'] || {})) } catch { /* offline */ }
  },
  'analytics.v1.insight.found': async (env) => {
    const p = getPrisma(); const d = env.payload as Record<string, unknown>
    try { await p.$executeRawUnsafe(`INSERT INTO "Insight" (id, title, description, "confidenceScore", "sourceEvents") VALUES ($1,$2,$3,$4,$5)`, String(d['insightId'] || ''), String(d['title'] || ''), String(d['description'] || ''), Number(d['confidence'] || 0), JSON.stringify(d['events'] || [])) } catch { /* offline */ }
  },
}
