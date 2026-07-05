import { z } from 'zod'
import type { ToolDefinition } from '../tools/tool-registry'
import { telegramBot } from '../../shared/infrastructure/integrations/telegram-bot'
import { mercadoLivreAdapter } from '../../shared/infrastructure/integrations/mercadolivre-adapter'
import { shopeeAdapter } from '../../shared/infrastructure/integrations/shopee-adapter'
import { emailSender } from '../../shared/infrastructure/integrations/email-sender'
import { publishEvent } from '../../shared/infrastructure/messaging/event-publisher'
import { stockRepository } from '../../shared/infrastructure/persistence/repositories'
import { randomUUID } from 'crypto'

export function createRealTelegramTools(): ToolDefinition[] {
  return [
    {
      name: 'telegram.sendProduct',
      description: 'Envia card de produto via Telegram (API real)',
      inputSchema: z.object({ chatId: z.string(), name: z.string(), description: z.string(), price: z.number(), sku: z.string(), imageUrl: z.string().optional() }),
      outputSchema: z.object({ sent: z.boolean() }),
      handler: async (input: unknown) => {
        const d = input as { chatId: string; name: string; description: string; price: number; sku: string; imageUrl?: string }
        if (!telegramBot.isConfigured) return { sent: false, reason: 'Telegram not configured' }
        await telegramBot.sendProductCard(d.chatId, { name: d.name, description: d.description, price: d.price, sku: d.sku, imageUrl: d.imageUrl })
        return { sent: true }
      },
    },
    {
      name: 'telegram.sendOrderStatus',
      description: 'Envia status de pedido via Telegram (API real)',
      inputSchema: z.object({ chatId: z.string(), orderId: z.string(), status: z.string(), tracking: z.string().optional() }),
      outputSchema: z.object({ sent: z.boolean() }),
      handler: async (input: unknown) => {
        const d = input as { chatId: string; orderId: string; status: string; tracking?: string }
        if (!telegramBot.isConfigured) return { sent: false }
        await telegramBot.sendOrderStatus(d.chatId, d.orderId, d.status, d.tracking)
        return { sent: true }
      },
    },
    {
      name: 'telegram.sendAlert',
      description: 'Envia alerta via Telegram (API real)',
      inputSchema: z.object({ chatId: z.string(), title: z.string(), message: z.string(), severity: z.enum(['info', 'warning', 'critical']) }),
      outputSchema: z.object({ sent: z.boolean() }),
      handler: async (input: unknown) => {
        const d = input as { chatId: string; title: string; message: string; severity: 'info' | 'warning' | 'critical' }
        if (!telegramBot.isConfigured) return { sent: false }
        await telegramBot.sendAlert(d.chatId, d.title, d.message, d.severity)
        return { sent: true }
      },
    },
  ]
}

export function createRealMarketplaceTools(): ToolDefinition[] {
  return [
    {
      name: 'marketplace.publishML',
      description: 'Publica produto no Mercado Livre (API real)',
      inputSchema: z.object({ title: z.string(), categoryId: z.string(), price: z.number(), quantity: z.number(), description: z.string(), pictures: z.array(z.string()) }),
      outputSchema: z.object({ mlId: z.string().optional(), published: z.boolean(), error: z.string().optional() }),
      handler: async (input: unknown) => {
        const d = input as { title: string; categoryId: string; price: number; quantity: number; description: string; pictures: string[] }
        if (!mercadoLivreAdapter.isConfigured) return { published: false, error: 'Mercado Livre not configured' }
        const result = await mercadoLivreAdapter.publishProduct({
          title: d.title, category_id: d.categoryId, price: d.price,
          available_quantity: d.quantity, description: d.description,
          pictures: d.pictures.map(source => ({ source })),
          attributes: [], shipping: { mode: 'me2', free_shipping: false },
        })
        if (result) {
          await publishEvent({
            eventId: randomUUID(), eventType: 'marketplace.v1.listing.published',
            eventVersion: '1.0', timestamp: new Date().toISOString(),
            correlationId: randomUUID(), causationId: null, tenantId: 'default',
            source: { context: 'marketplace-integration', aggregateId: result.id, aggregateType: 'Listing' },
            payload: { mlId: result.id, title: d.title } as Record<string, unknown>,
            metadata: { userId: 'system', agentId: 'ag-022', channel: 'agent' },
          })
          return { published: true, mlId: result.id }
        }
        return { published: false, error: 'Failed to publish' }
      },
    },
    {
      name: 'marketplace.syncStock',
      description: 'Sincroniza estoque no Mercado Livre (API real)',
      inputSchema: z.object({ mlId: z.string(), quantity: z.number() }),
      outputSchema: z.object({ synced: z.boolean() }),
      handler: async (input: unknown) => {
        const d = input as { mlId: string; quantity: number }
        if (!mercadoLivreAdapter.isConfigured) return { synced: false }
        const ok = await mercadoLivreAdapter.updateStock(d.mlId, d.quantity)
        return { synced: ok }
      },
    },
    {
      name: 'marketplace.syncPrice',
      description: 'Atualiza preço no Mercado Livre (API real)',
      inputSchema: z.object({ mlId: z.string(), price: z.number() }),
      outputSchema: z.object({ synced: z.boolean() }),
      handler: async (input: unknown) => {
        const d = input as { mlId: string; price: number }
        if (!mercadoLivreAdapter.isConfigured) return { synced: false }
        const ok = await mercadoLivreAdapter.updatePrice(d.mlId, d.price)
        return { synced: ok }
      },
    },
    {
      name: 'marketplace.getOrders',
      description: 'Busca pedidos do Mercado Livre (API real)',
      inputSchema: z.object({ status: z.string().optional(), limit: z.number().optional() }),
      outputSchema: z.object({ orders: z.array(z.object({ id: z.number(), status: z.string(), total: z.number(), buyer: z.string() })), count: z.number() }),
      handler: async (input: unknown) => {
        const d = input as { status?: string; limit?: number }
        if (!mercadoLivreAdapter.isConfigured) return { orders: [], count: 0 }
        const orders = await mercadoLivreAdapter.getOrders({ status: d.status, limit: d.limit })
        return {
          orders: orders.map(o => ({ id: o.id, status: o.status, total: o.total_amount, buyer: o.buyer.nickname })),
          count: orders.length,
        }
      },
    },
    {
      name: 'marketplace.publishShopee',
      description: 'Publica produto na Shopee (API real)',
      inputSchema: z.object({ name: z.string(), description: z.string(), price: z.number(), stock: z.number(), categoryId: z.number(), weight: z.number(), images: z.array(z.string()) }),
      outputSchema: z.object({ itemId: z.number().optional(), published: z.boolean(), error: z.string().optional() }),
      handler: async (input: unknown) => {
        const d = input as { name: string; description: string; price: number; stock: number; categoryId: number; weight: number; images: string[] }
        if (!shopeeAdapter.isConfigured) return { published: false, error: 'Shopee not configured' }
        const result = await shopeeAdapter.publishProduct({
          item_name: d.name, description: d.description, price: d.price,
          stock: d.stock, category_id: d.categoryId, weight: d.weight,
          images: d.images.map(url => ({ url })),
        })
        if (result) return { published: true, itemId: result.item_id }
        return { published: false, error: 'Failed to publish' }
      },
    },
  ]
}

export function createRealEmailTools(): ToolDefinition[] {
  return [
    {
      name: 'email.sendAlert',
      description: 'Envia email de alerta (SMTP real)',
      inputSchema: z.object({ to: z.string(), title: z.string(), body: z.string(), severity: z.enum(['info', 'warning', 'critical', 'success']) }),
      outputSchema: z.object({ sent: z.boolean(), messageId: z.string().optional() }),
      handler: async (input: unknown) => {
        const d = input as { to: string; title: string; body: string; severity: 'info' | 'warning' | 'critical' | 'success' }
        if (!emailSender.isConfigured) return { sent: false }
        await emailSender.sendAlert(d.to, d.title, d.body, d.severity)
        return { sent: true }
      },
    },
    {
      name: 'email.sendDigest',
      description: 'Envia resumo diário por email (SMTP real)',
      inputSchema: z.object({ to: z.string(), metrics: z.array(z.object({ label: z.string(), value: z.string(), change: z.string(), trend: z.enum(['up', 'down', 'stable']) })) }),
      outputSchema: z.object({ sent: z.boolean() }),
      handler: async (input: unknown) => {
        const d = input as { to: string; metrics: Array<{ label: string; value: string; change: string; trend: 'up' | 'down' | 'stable' }> }
        if (!emailSender.isConfigured) return { sent: false }
        await emailSender.sendDailyDigest(d.to, d.metrics)
        return { sent: true }
      },
    },
    {
      name: 'email.sendReport',
      description: 'Envia relatório por email com anexo (SMTP real)',
      inputSchema: z.object({ to: z.string(), subject: z.string(), html: z.string(), attachmentName: z.string().optional(), attachmentContent: z.string().optional() }),
      outputSchema: z.object({ sent: z.boolean(), messageId: z.string().optional() }),
      handler: async (input: unknown) => {
        const d = input as { to: string; subject: string; html: string; attachmentName?: string; attachmentContent?: string }
        if (!emailSender.isConfigured) return { sent: false }
        const attachments = d.attachmentName && d.attachmentContent
          ? [{ filename: d.attachmentName, content: d.attachmentContent, contentType: 'application/json' }]
          : undefined
        const result = await emailSender.send({ to: d.to, subject: d.subject, html: d.html, attachments })
        return { sent: result !== null, messageId: result?.messageId }
      },
    },
  ]
}

export function createRealStockTools(): ToolDefinition[] {
  return [
    {
      name: 'inventory.checkReal',
      description: 'Verifica estoque real no banco de dados',
      inputSchema: z.object({ sku: z.string(), warehouseId: z.string() }),
      outputSchema: z.object({ sku: z.string(), warehouseId: z.string(), quantity: z.number(), reorderPoint: z.number(), status: z.string(), source: z.literal('database') }),
      handler: async (input: unknown) => {
        const d = input as { sku: string; warehouseId: string }
        const row = await stockRepository.findBySku(d.sku, d.warehouseId)
        if (!row) return { sku: d.sku, warehouseId: d.warehouseId, quantity: 0, reorderPoint: 0, status: 'not_found', source: 'database' as const }
        const qty = Number(row['quantity'] ?? 0)
        const reserved = Number(row['reservedQuantity'] ?? 0)
        const reorder = Number(row['reorderPoint'] ?? 0)
        const available = qty - reserved
        const status = available <= 0 ? 'critical' : available <= reorder ? 'low' : 'ok'
        return { sku: d.sku, warehouseId: d.warehouseId, quantity: available, reorderPoint: reorder, status, source: 'database' as const }
      },
    },
    {
      name: 'inventory.findLowStock',
      description: 'Busca itens com estoque baixo no banco de dados',
      inputSchema: z.object({ threshold: z.number().optional() }),
      outputSchema: z.object({ items: z.array(z.object({ sku: z.string(), quantity: z.number(), reorderPoint: z.number() })), count: z.number() }),
      handler: async (input: unknown) => {
        const d = input as { threshold?: number }
        const items = await stockRepository.findLowStock(d.threshold ?? 1)
        return {
          items: items.map(r => ({ sku: String(r['sku']), quantity: Number(r['quantity']), reorderPoint: Number(r['reorderPoint']) })),
          count: items.length,
        }
      },
    },
  ]
}
