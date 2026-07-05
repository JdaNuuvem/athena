import { AgentRuntime } from '../core/agent-runtime'
import { AgentContext } from '../core/agent-context'
import { DefaultMemoryManager } from '../memory/memory-manager'
import { DefaultToolRegistry, type ToolDefinition } from '../tools/tool-registry'
import { ToolExecutor } from '../tools/tool-executor'
import { opsTools } from './operations-tools'
import type { AgentDefinition } from '../core/agent-types'

type AgentRole = 'observer' | 'analyst' | 'decision-maker' | 'executor'

function make(id: string, name: string, role: AgentRole, context: string, prompt: string, tools: ToolDefinition[]): AgentRuntime {
  const memory = new DefaultMemoryManager(); const registry = new DefaultToolRegistry()
  for (const t of tools) registry.register(t)
  const def: AgentDefinition = { id, name, role, context, systemPrompt: prompt, capabilities: tools.map(t => ({ name: t.name, description: t.description, inputSchema: {}, outputSchema: {} })), config: { modelProvider: 'openai', modelName: 'gpt-4o-mini', temperature: 0.2, maxTokens: 1024, retryPolicy: { maxRetries: 1, backoffMs: 500 }, timeout: 15000 } }
  return new (class extends AgentRuntime { private exec = new ToolExecutor(registry); constructor() { super(id, def, new AgentContext(id, memory, registry)) } override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> { await super.handleTask(task); const tool = tools[0]; if (tool) { const r = await this.exec.execute(tool.name, task); return { ...task, result: r } } return super.handleTask(task) } })()
}

const t = opsTools()
export const createDemandForecaster = () => make('ag-032', 'demand-forecaster', 'analyst', 'inventory', 'Prevê demanda por SKU/canal usando séries temporais.', t['demand']!)
export const createInventoryOptimizer = () => make('ag-033', 'inventory-optimizer', 'decision-maker', 'inventory', 'Otimiza distribuição de estoque entre depósitos.', t['optimize']!)
export const createDeadStockDetector = () => make('ag-034', 'dead-stock-detector', 'analyst', 'inventory', 'Identifica estoque parado e sugere liquidação.', t['dead']!)
export const createFulfillmentMonitor = () => make('ag-037', 'fulfillment-monitor', 'observer', 'order-management', 'Monitora SLAs de fulfillment, alerta sobre atrasos.', t['fulfillment']!)
export const createReturnAnalyzer = () => make('ag-038', 'return-analyzer', 'analyst', 'order-management', 'Analisa padrões de devolução.', t['returns']!)
export const createCustomerSegmenter = () => make('ag-039', 'customer-segmenter', 'analyst', 'customer', 'Segmenta clientes por comportamento RFM.', t['segment']!)
export const createChurnPredictor = () => make('ag-040', 'churn-predictor', 'decision-maker', 'customer', 'Prediz risco de churn e sugere retenção.', t['churn']!)
export const createLifetimeValueEstimator = () => make('ag-041', 'lifetime-value-estimator', 'analyst', 'customer', 'Estima LTV por segmento e coorte.', t['ltv']!)
export const createShippingCostOptimizer = () => make('ag-043', 'shipping-cost-optimizer', 'analyst', 'shipping', 'Sugere otimizações de embalagem e frete.', t['shipOptimize']!)
export const createDeliveryTracker = () => make('ag-044', 'delivery-tracker', 'observer', 'shipping', 'Monitora entregas em tempo real.', t['track']!)
