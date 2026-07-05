import { AgentRuntime } from '../../core/agent-runtime'
import { AgentContext } from '../../core/agent-context'
import { DefaultMemoryManager } from '../../memory/memory-manager'
import { DefaultToolRegistry } from '../../tools/tool-registry'
import { ToolExecutor } from '../../tools/tool-executor'
import { createDefectDetectorTools } from './defect-detector-tools'
import type { AgentDefinition } from '../../core/agent-types'

const DEFECT_DETECTOR_DEFINITION: AgentDefinition = {
  id: 'ag-011',
  name: 'defect-detector',
  role: 'observer',
  context: 'injection-molding',
  systemPrompt: `Você é o Defect Detector, agente observador do contexto de Injection Molding.
Sua responsabilidade é identificar padrões de defeito (rebarba, rechupo, queima) correlacionando
com parâmetros de máquina. Você pode decidir parar uma máquina se a taxa de defeito exceder o threshold.`,
  capabilities: [
    { name: 'quality.analyzeDefect', description: 'Analyze cycle for defects', inputSchema: {}, outputSchema: {} },
    { name: 'quality.stopMachine', description: 'Stop injection machine', inputSchema: {}, outputSchema: {} },
  ],
  config: {
    modelProvider: 'openai',
    modelName: 'gpt-4o-mini',
    temperature: 0.2,
    maxTokens: 1024,
    retryPolicy: { maxRetries: 1, backoffMs: 500 },
    timeout: 30000,
  },
}

export class DefectDetectorAgent extends AgentRuntime {
  private executor: ToolExecutor

  constructor() {
    const memory = new DefaultMemoryManager({ stMaxSize: 500 })
    const tools = new DefaultToolRegistry()
    const context = new AgentContext('ag-011', memory, tools)

    for (const tool of createDefectDetectorTools(memory)) tools.register(tool)

    super('ag-011', DEFECT_DETECTOR_DEFINITION, context)

    this.executor = new ToolExecutor(tools)
  }

  override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> {
    await super.handleTask(task)

    if (task['type'] === 'analyze_cycle') {
      const result = await this.executor.execute('quality.analyzeDefect', task)
      if (result.success && result.data) {
        const data = result.data as Record<string, unknown>
        const defects = data['defects'] as Array<Record<string, unknown>>
        const criticalCount = defects.filter(d => d['severity'] === 'critical').length
        if (criticalCount > 0) {
          await this.executor.execute('quality.stopMachine', {
            machineId: task['machineId'],
            reason: `${criticalCount} critical defects detected`,
            defectRate: 0.85,
          })
        }
      }
      return { ...task, result }
    }

    return super.handleTask(task)
  }
}

export function createDefectDetector(): DefectDetectorAgent {
  return new DefectDetectorAgent()
}
