import { AgentRuntime } from '../../core/agent-runtime'
import { AgentContext } from '../../core/agent-context'
import { DefaultMemoryManager } from '../../memory/memory-manager'
import { DefaultToolRegistry, type ToolDefinition } from '../../tools/tool-registry'
import { ToolExecutor } from '../../tools/tool-executor'
import { createWhatsAppTools } from '../../tools/whatsapp-tools'
import type { AgentDefinition } from '../../core/agent-types'

const DEFINITION: AgentDefinition = {
  id: 'ag-052',
  name: 'whatsapp-seller',
  role: 'executor',
  context: 'whatsapp-commerce',
  systemPrompt: `Você é o WhatsApp Seller da ATHENA OS. Você conduz vendas completas via WhatsApp:
- Envia catálogo de produtos com preços reais
- Responde dúvidas sobre produtos, preços e prazos
- Cria pedidos diretamente na conversa
- Envia status de pedidos (confirmado, produção, enviado, entregue)
- Dispara promoções e recuperação de carrinho abandonado
- Transfere para atendente humano quando necessário`,
  capabilities: [
    { name: 'whatsapp.sendText', description: 'Enviar texto', inputSchema: {}, outputSchema: {} },
    { name: 'whatsapp.sendProductCard', description: 'Enviar card de produto', inputSchema: {}, outputSchema: {} },
    { name: 'whatsapp.sendCatalog', description: 'Enviar catálogo', inputSchema: {}, outputSchema: {} },
    { name: 'whatsapp.sendOrderStatus', description: 'Atualizar status de pedido', inputSchema: {}, outputSchema: {} },
    { name: 'whatsapp.createOrder', description: 'Criar pedido', inputSchema: {}, outputSchema: {} },
    { name: 'whatsapp.sendPromotion', description: 'Enviar promoção', inputSchema: {}, outputSchema: {} },
    { name: 'whatsapp.sendAbandonedCart', description: 'Recuperar carrinho', inputSchema: {}, outputSchema: {} },
    { name: 'whatsapp.checkStatus', description: 'Verificar conexão', inputSchema: {}, outputSchema: {} },
  ],
  config: {
    modelProvider: 'openai',
    modelName: 'gpt-4o-mini',
    temperature: 0.3,
    maxTokens: 1024,
    retryPolicy: { maxRetries: 2, backoffMs: 500 },
    timeout: 15000,
  },
}

const tools: ToolDefinition[] = createWhatsAppTools()

export class WhatsAppSellerAgent extends AgentRuntime {
  private exec: ToolExecutor

  constructor() {
    const memory = new DefaultMemoryManager()
    const registry = new DefaultToolRegistry()
    for (const t of tools) registry.register(t)
    super('ag-052', DEFINITION, new AgentContext('ag-052', memory, registry))
    this.exec = new ToolExecutor(registry)
  }

  override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> {
    await super.handleTask(task)

    const type = task['type'] as string
    const phone = task['phone'] as string

    switch (type) {
      case 'send_catalog': {
        const products = task['products'] as Array<{ name: string; price: number; sku: string; description: string }> | undefined
        const r = await this.exec.execute('whatsapp.sendCatalog', { phone, products: products ?? [] })
        return { ...task, result: r }
      }
      case 'send_product_card': {
        const r = await this.exec.execute('whatsapp.sendProductCard', task)
        return { ...task, result: r }
      }
      case 'send_order_status': {
        const r = await this.exec.execute('whatsapp.sendOrderStatus', task)
        return { ...task, result: r }
      }
      case 'create_order': {
        const r = await this.exec.execute('whatsapp.createOrder', task)
        return { ...task, result: r }
      }
      case 'send_promotion': {
        const r = await this.exec.execute('whatsapp.sendPromotion', task)
        return { ...task, result: r }
      }
      case 'abandoned_cart': {
        const r = await this.exec.execute('whatsapp.sendAbandonedCart', task)
        return { ...task, result: r }
      }
      case 'check_status': {
        const r = await this.exec.execute('whatsapp.checkStatus', {})
        return { ...task, result: r }
      }
      case 'handle_message': {
        const text = (task['text'] as string ?? '').toLowerCase()
        const r = await this.handleIncomingMessage(phone, text)
        return { ...task, result: r }
      }
      default:
        return { ...task, result: { handled: false, reason: `Unknown task type: ${type}` } }
    }
  }

  private async handleIncomingMessage(phone: string, text: string): Promise<Record<string, unknown>> {
    if (/ola|oi|bom dia|boa tarde|boa noite|inicio|start/i.test(text)) {
      await this.exec.execute('whatsapp.sendText', {
        phone,
        text: '👋 Olá! Sou o assistente de vendas da *ATHENA OS*.\n\n📋 Digite *catálogo* para ver produtos\n💰 Digite *preços* para valores\n🛒 Digite *comprar* para fazer pedido\n👤 Digite *atendente* para falar com pessoa',
      })
      return { intent: 'greeting' }
    }

    if (/catalogo|produtos|servicos|lista|tem|vende/i.test(text)) {
      await this.exec.execute('whatsapp.sendCatalog', {
        phone,
        products: [
          { name: 'Balde Plástico 20L', price: 49.90, sku: 'BLD-001', description: 'Balde industrial reforçado, polipropileno virgem, alça metálica' },
          { name: 'Tampa Pressão 20L', price: 19.90, sku: 'TMP-001', description: 'Tampa com vedação para balde 20L, trava de segurança' },
          { name: 'Mangueira Cristal 1/2"', price: 12.90, sku: 'MNG-001', description: 'Mangueira PVC cristal, atóxica, rolo 10m' },
          { name: 'Caixa Plástica 60L', price: 79.90, sku: 'CXA-001', description: 'Caixa organizadora industrial, empilhável, reforçada' },
          { name: 'Combo Limpeza', price: 99.90, sku: 'CMB-001', description: 'Balde 20L + Tampa + Mangueira 10m — 15% de desconto' },
        ],
      })
      return { intent: 'catalog' }
    }

    if (/preco|valor|custa|quanto/i.test(text)) {
      await this.exec.execute('whatsapp.sendText', {
        phone,
        text: '💰 *Tabela de Preços*\n\n1️⃣ Balde 20L — R$ 49,90\n2️⃣ Tampa Pressão — R$ 19,90\n3️⃣ Mangueira Cristal — R$ 12,90\n4️⃣ Caixa 60L — R$ 79,90\n5️⃣ Combo Limpeza — R$ 99,90\n\n🚚 *Frete grátis acima de R$ 150!*\n\nDigite o número para detalhes!',
      })
      return { intent: 'pricing' }
    }

    if (/comprar|quero|pedido|pagar|fechar/i.test(text)) {
      await this.exec.execute('whatsapp.sendText', {
        phone,
        text: '🛒 Para finalizar seu pedido, preciso de:\n\n📝 *Nome completo*\n📍 *Endereço de entrega*\n💳 *Forma de pagamento* (PIX/cartão)\n📦 *Produto desejado* (nome ou SKU)\n\nMe envie essas informações e confirmo na hora! ✅',
      })
      return { intent: 'purchase' }
    }

    if (/atendente|humano|pessoa|falar|ajuda/i.test(text)) {
      await this.exec.execute('whatsapp.sendText', {
        phone,
        text: '⏳ Um momento, vou transferir para um atendente humano...\n\nEnquanto isso, pode adiantar qual é sua dúvida?',
      })
      return { intent: 'human' }
    }

    await this.exec.execute('whatsapp.sendText', {
      phone,
      text: 'Desculpe, não entendi. 😅\n\nTente:\n• *catálogo* — ver produtos\n• *preços* — ver valores\n• *comprar* — fazer pedido\n• *atendente* — falar com pessoa',
    })
    return { intent: 'fallback' }
  }
}
