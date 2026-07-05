import { AgentRuntime } from '../core/agent-runtime'
import { AgentContext } from '../core/agent-context'
import { DefaultMemoryManager } from '../memory/memory-manager'
import { DefaultToolRegistry, type ToolDefinition } from '../tools/tool-registry'
import { ToolExecutor } from '../tools/tool-executor'
import { createCycleOptimizerTools, createProductionForecasterTools, createQualityGatekeeperTools, createFormulationOptimizerTools, createCuringMonitorTools, createCoatingQCTools, createMoldMaterialMatcherTools, createSetupSheetGeneratorTools } from './production-tools'
import type { AgentDefinition } from '../core/agent-types'

type AgentRole = 'observer' | 'analyst' | 'decision-maker' | 'executor'

function makeAgent(id: string, name: string, role: AgentRole, context: string, prompt: string, toolFactory: () => ToolDefinition[]): AgentRuntime {
  const memory = new DefaultMemoryManager()
  const registry = new DefaultToolRegistry()
  const tools = toolFactory()
  for (const t of tools) registry.register(t)
  const def: AgentDefinition = { id, name, role, context, systemPrompt: prompt, capabilities: tools.map(t => ({ name: t.name, description: t.description, inputSchema: {}, outputSchema: {} })), config: { modelProvider: 'openai', modelName: 'gpt-4o-mini', temperature: 0.2, maxTokens: 1024, retryPolicy: { maxRetries: 1, backoffMs: 500 }, timeout: 15000 } }
  return new (class extends AgentRuntime { private exec = new ToolExecutor(registry); constructor() { super(id, def, new AgentContext(id, memory, registry)) } override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> { await super.handleTask(task); const tool = tools[0]; if (tool) { const r = await this.exec.execute(tool.name, task); return { ...task, result: r } } return super.handleTask(task) } })()
}

export const createCycleOptimizer = () => makeAgent('ag-010', 'cycle-optimizer', 'analyst', 'injection-molding', 'Analisa dados de ciclo e recomenda ajustes de parâmetros.', createCycleOptimizerTools)
export const createProductionForecaster = () => makeAgent('ag-012', 'production-forecaster', 'analyst', 'injection-molding', 'Prevê capacidade produtiva baseado em histórico e manutenções.', createProductionForecasterTools)
export const createQualityGatekeeper = () => makeAgent('ag-013', 'quality-gatekeeper', 'decision-maker', 'injection-molding', 'Monitora qualidade em tempo real, decide parada de máquina.', createQualityGatekeeperTools)
export const createFormulationOptimizer = () => makeAgent('ag-014', 'formulation-optimizer', 'analyst', 'plastisol-processing', 'Analisa formulações e sugere ajustes.', createFormulationOptimizerTools)
export const createCuringMonitor = () => makeAgent('ag-015', 'curing-monitor', 'observer', 'plastisol-processing', 'Monitora ciclos de cura e alerta desvios.', createCuringMonitorTools)
export const createCoatingQC = () => makeAgent('ag-016', 'coating-qc', 'decision-maker', 'plastisol-processing', 'Controle de qualidade de revestimento.', createCoatingQCTools)
export const createMoldMaterialMatcher = () => makeAgent('ag-017', 'mold-material-matcher', 'decision-maker', 'mold-making', 'Recomenda aço para molde.', createMoldMaterialMatcherTools)
export const createSetupSheetGenerator = () => makeAgent('ag-018', 'setup-sheet-generator', 'executor', 'cnc-machining', 'Gera setup sheets automaticamente.', createSetupSheetGeneratorTools)
