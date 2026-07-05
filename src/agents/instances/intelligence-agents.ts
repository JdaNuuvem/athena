import { AgentRuntime } from '../core/agent-runtime'
import { AgentContext } from '../core/agent-context'
import { DefaultMemoryManager } from '../memory/memory-manager'
import { DefaultToolRegistry, type ToolDefinition } from '../tools/tool-registry'
import { ToolExecutor } from '../tools/tool-executor'
import { analyticsTools, coordinationTools } from './intelligence-tools'
import type { AgentDefinition } from '../core/agent-types'

type AgentRole = 'observer' | 'analyst' | 'decision-maker' | 'executor' | 'coordinator'

function make(id: string, name: string, role: AgentRole, context: string, prompt: string, tools: ToolDefinition[]): AgentRuntime {
  const memory = new DefaultMemoryManager(); const registry = new DefaultToolRegistry()
  for (const t of tools) registry.register(t)
  const def: AgentDefinition = { id, name, role, context, systemPrompt: prompt, capabilities: tools.map(t => ({ name: t.name, description: t.description, inputSchema: {}, outputSchema: {} })), config: { modelProvider: 'openai', modelName: 'gpt-4o-mini', temperature: 0.2, maxTokens: 2048, retryPolicy: { maxRetries: 1, backoffMs: 500 }, timeout: 30000 } }
  return new (class extends AgentRuntime { private exec = new ToolExecutor(registry); constructor() { super(id, def, new AgentContext(id, memory, registry)) } override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> { await super.handleTask(task); const tool = tools[0]; if (tool) { const r = await this.exec.execute(tool.name, task); return { ...task, result: r } } return super.handleTask(task) } })()
}

const at = analyticsTools(); const ct = coordinationTools()

export const createBusinessAnalyst = () => make('ag-045', 'business-analyst', 'analyst', 'analytics', 'Gera relatórios executivos automáticos.', at['report']!)
export const createAnomalyDetector = () => make('ag-046', 'anomaly-detector', 'observer', 'analytics', 'Detecta anomalias estatísticas e dispara alertas.', at['anomaly']!)
export const createTrendForecaster = () => make('ag-047', 'trend-forecaster', 'analyst', 'analytics', 'Prevê tendências de mercado e vendas.', at['trend']!)
export const createExecutiveDigest = () => make('ag-048', 'executive-digest', 'executor', 'analytics', 'Gera resumo executivo e envia por canal.', at['digest']!)
export const createCrossContextCorrelator = () => make('ag-049', 'cross-context-correlator', 'analyst', 'analytics', 'Correlaciona eventos entre contextos.', at['correlate']!)
export const createMarginWatchdog = () => make('ag-050', 'margin-watchdog', 'decision-maker', 'analytics', 'Monitora margem e alerta abaixo do threshold.', at['margin']!)
export const createWorkflowOrchestrator = () => make('ag-051', 'workflow-orchestrator', 'coordinator', 'agents', 'Orquestra workflows multi-agente.', ct['orchestrate']!)
export const createSystemHealthMonitor = () => make('ag-052', 'system-health-monitor', 'observer', 'agents', 'Monitora saúde de todos os agentes.', ct['health']!)
