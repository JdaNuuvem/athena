import { AgentRuntime } from '../core/agent-runtime'
import { AgentContext } from '../core/agent-context'
import { DefaultMemoryManager } from '../memory/memory-manager'
import { DefaultToolRegistry, type ToolDefinition } from '../tools/tool-registry'
import { ToolExecutor } from '../tools/tool-executor'
import { catalogTools, marketplaceTools, retailTools, telegramTools } from './commercial-tools'
import type { AgentDefinition } from '../core/agent-types'

type AgentRole = 'observer' | 'analyst' | 'decision-maker' | 'executor'

function make(id: string, name: string, role: AgentRole, context: string, prompt: string, tools: ToolDefinition[]): AgentRuntime {
  const memory = new DefaultMemoryManager()
  const registry = new DefaultToolRegistry()
  for (const t of tools) registry.register(t)
  const def: AgentDefinition = { id, name, role, context, systemPrompt: prompt, capabilities: tools.map(t => ({ name: t.name, description: t.description, inputSchema: {}, outputSchema: {} })), config: { modelProvider: 'openai', modelName: 'gpt-4o-mini', temperature: 0.2, maxTokens: 1024, retryPolicy: { maxRetries: 1, backoffMs: 500 }, timeout: 15000 } }
  return new (class extends AgentRuntime { private exec = new ToolExecutor(registry); constructor() { super(id, def, new AgentContext(id, memory, registry)) } override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> { await super.handleTask(task); const tool = tools[0]; if (tool) { const r = await this.exec.execute(tool.name, task); return { ...task, result: r } } return super.handleTask(task) } })()
}

const ct = catalogTools(); const mt = marketplaceTools(); const rt = retailTools(); const tt = telegramTools()

export const createCatalogEnricher = () => make('ag-019', 'catalog-enricher', 'executor', 'catalog', 'Enriquece fichas de produto: descrições, bullets, atributos.', [ct[0]!])
export const createMediaOrganizer = () => make('ag-020', 'media-organizer', 'executor', 'catalog', 'Organiza e taggeia mídia de produto.', [ct[1]!])
export const createSEOOptimizer = () => make('ag-021', 'seo-optimizer', 'analyst', 'catalog', 'Analisa e otimiza títulos e keywords para SEO.', [ct[0]!])
export const createListingSync = () => make('ag-022', 'listing-synchronizer', 'executor', 'marketplace-integration', 'Mantém listings sincronizados entre canais.', [mt[0]!])
export const createCompetitorMonitor = () => make('ag-023', 'competitor-monitor', 'observer', 'marketplace-integration', 'Monitora preços de concorrentes.', [mt[1]!])
export const createChannelHealth = () => make('ag-024', 'channel-health-checker', 'observer', 'marketplace-integration', 'Monitora saúde das contas nos marketplaces.', [mt[2]!])
export const createRepricingAgent = () => make('ag-025', 'repricing-agent', 'decision-maker', 'marketplace-integration', 'Ajusta preços dinamicamente.', [mt[3]!])
export const createStoreInventoryAuditor = () => make('ag-026', 'store-inventory-auditor', 'observer', 'retail-operations', 'Reconcilia inventário físico vs sistema.', [rt[0]!])
export const createSalesPatternAnalyzer = () => make('ag-027', 'sales-pattern-analyzer', 'analyst', 'retail-operations', 'Analisa padrões de venda por loja.', [rt[1]!])
export const createConversationalSeller = () => make('ag-028', 'conversational-seller', 'executor', 'telegram-commerce', 'Conduz conversa de venda no Telegram.', [tt[0]!])
export const createOrderAssistant = () => make('ag-029', 'order-assistant', 'executor', 'telegram-commerce', 'Auxilia cliente com status de pedido.', [tt[1]!])
export const createProductRecommender = () => make('ag-030', 'product-recommender', 'analyst', 'telegram-commerce', 'Recomenda produtos baseado no histórico.', [tt[2]!])
