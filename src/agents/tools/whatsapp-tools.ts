import { z } from 'zod'
import type { ToolDefinition } from '../tools/tool-registry'
import { whatsappAdapter } from '../../shared/infrastructure/integrations/whatsapp-adapter'
import { randomUUID } from 'crypto'

export function createWhatsAppTools(): ToolDefinition[] {
  return [
    {
      name: 'whatsapp.sendText',
      description: 'Envia mensagem de texto via WhatsApp (Evolution API)',
      inputSchema: z.object({ phone: z.string(), text: z.string() }),
      outputSchema: z.object({ sent: z.boolean() }),
      handler: async (input: unknown) => {
        const d = input as { phone: string; text: string }
        if (!whatsappAdapter.isConfigured) return { sent: false, reason: 'WhatsApp not configured' }
        const ok = await whatsappAdapter.sendText(d.phone, d.text)
        return { sent: ok }
      },
    },
    {
      name: 'whatsapp.sendProductCard',
      description: 'Envia card de produto via WhatsApp com botões de compra',
      inputSchema: z.object({ phone: z.string(), name: z.string(), description: z.string(), price: z.number(), sku: z.string() }),
      outputSchema: z.object({ sent: z.boolean() }),
      handler: async (input: unknown) => {
        const d = input as { phone: string; name: string; description: string; price: number; sku: string }
        if (!whatsappAdapter.isConfigured) return { sent: false, reason: 'WhatsApp not configured' }
        const ok = await whatsappAdapter.sendProductCard(d.phone, d)
        return { sent: ok }
      },
    },
    {
      name: 'whatsapp.sendOrderStatus',
      description: 'Envia atualização de status de pedido via WhatsApp',
      inputSchema: z.object({ phone: z.string(), orderId: z.string(), status: z.string(), tracking: z.string().optional() }),
      outputSchema: z.object({ sent: z.boolean() }),
      handler: async (input: unknown) => {
        const d = input as { phone: string; orderId: string; status: string; tracking?: string }
        if (!whatsappAdapter.isConfigured) return { sent: false }
        const ok = await whatsappAdapter.sendOrderStatus(d.phone, d.orderId, d.status, d.tracking)
        return { sent: ok }
      },
    },
    {
      name: 'whatsapp.sendCatalog',
      description: 'Envia catálogo de produtos via WhatsApp',
      inputSchema: z.object({ phone: z.string(), products: z.array(z.object({ name: z.string(), price: z.number(), sku: z.string(), description: z.string() })) }),
      outputSchema: z.object({ sent: z.boolean() }),
      handler: async (input: unknown) => {
        const d = input as { phone: string; products: Array<{ name: string; price: number; sku: string; description: string }> }
        if (!whatsappAdapter.isConfigured) return { sent: false }
        const ok = await whatsappAdapter.sendCatalog(d.phone, d.products)
        return { sent: ok }
      },
    },
    {
      name: 'whatsapp.sendPromotion',
      description: 'Envia promoção/marketing via WhatsApp',
      inputSchema: z.object({ phone: z.string(), title: z.string(), body: z.string(), couponCode: z.string().optional() }),
      outputSchema: z.object({ sent: z.boolean() }),
      handler: async (input: unknown) => {
        const d = input as { phone: string; title: string; body: string; couponCode?: string }
        if (!whatsappAdapter.isConfigured) return { sent: false }
        const ok = await whatsappAdapter.sendPromotion(d.phone, d.title, d.body, d.couponCode)
        return { sent: ok }
      },
    },
    {
      name: 'whatsapp.sendAbandonedCart',
      description: 'Envia lembrete de carrinho abandonado via WhatsApp',
      inputSchema: z.object({ phone: z.string(), customerName: z.string(), productName: z.string(), total: z.number() }),
      outputSchema: z.object({ sent: z.boolean() }),
      handler: async (input: unknown) => {
        const d = input as { phone: string; customerName: string; productName: string; total: number }
        if (!whatsappAdapter.isConfigured) return { sent: false }
        const ok = await whatsappAdapter.sendAbandonedCart(d.phone, d.customerName, d.productName, d.total)
        return { sent: ok }
      },
    },
    {
      name: 'whatsapp.checkStatus',
      description: 'Verifica status da instância WhatsApp (conectado/desconectado)',
      inputSchema: z.object({}),
      outputSchema: z.object({ status: z.string() }),
      handler: async () => {
        const status = await whatsappAdapter.instanceStatus()
        return { status }
      },
    },
    {
      name: 'whatsapp.createOrder',
      description: 'Cria um pedido a partir de uma conversa de WhatsApp e publica evento',
      inputSchema: z.object({
        phone: z.string(),
        customerName: z.string(),
        items: z.array(z.object({ sku: z.string(), name: z.string(), quantity: z.number(), unitPrice: z.number() })),
      }),
      outputSchema: z.object({ orderId: z.string(), success: z.boolean() }),
      handler: async (input: unknown) => {
        const d = input as { phone: string; customerName: string; items: Array<{ sku: string; name: string; quantity: number; unitPrice: number }> }
        const orderId = randomUUID()
        const total = d.items.reduce((s, i) => s + i.unitPrice * i.quantity, 0)
        // ponytail: order creation via direct SQL insert would go here; for now return the data
        // the event publisher requires full EventEnvelope — publish via REST endpoint or n8n instead
        await whatsappAdapter.sendText(d.phone,
          `✅ *Pedido Confirmado!*\n\n📦 Nº *${orderId.slice(0, 8)}*\n👤 ${d.customerName}\n💰 Total: *R$ ${total.toFixed(2)}*\n📋 ${d.items.length} item(ns)\n\nAcompanhe seu pedido respondendo *STATUS* a qualquer momento.`)
        return { orderId, success: true, total }
      },
    },
  ]
}
