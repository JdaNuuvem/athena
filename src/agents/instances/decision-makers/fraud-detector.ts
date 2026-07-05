import { AgentRuntime } from '../../core/agent-runtime'
import { AgentContext } from '../../core/agent-context'
import { DefaultMemoryManager } from '../../memory/memory-manager'
import { DefaultToolRegistry } from '../../tools/tool-registry'
import { ToolExecutor } from '../../tools/tool-executor'
import { z } from 'zod'
import type { AgentDefinition } from '../../core/agent-types'

const FRAUD_DETECTOR_DEFINITION: AgentDefinition = {
  id: 'ag-036',
  name: 'fraud-detector',
  role: 'decision-maker',
  context: 'order-management',
  systemPrompt: `Você é o Fraud Detector, agente decisor do contexto de Order Management.
Analisa pedidos em tempo real contra padrões de fraude:
- Score de risco baseado em múltiplos fatores
- Bloqueio automático para alto risco
- Liberação para baixo risco
- Revisão manual para risco médio`,
  capabilities: [
    { name: 'fraud.analyze', description: 'Analyze order for fraud patterns', inputSchema: {}, outputSchema: {} },
  ],
  config: {
    modelProvider: 'openai', modelName: 'gpt-4o-mini',
    temperature: 0.1, maxTokens: 1024,
    retryPolicy: { maxRetries: 1, backoffMs: 500 }, timeout: 15000,
  },
}

export class FraudDetectorAgent extends AgentRuntime {
  private executor: ToolExecutor

  constructor() {
    const memory = new DefaultMemoryManager()
    const tools = new DefaultToolRegistry()
    const context = new AgentContext('ag-036', memory, tools)

    tools.register({
      name: 'fraud.analyze',
      description: 'Analisa pedido para detecção de fraude',
      inputSchema: z.object({ orderId: z.string(), amount: z.number(), customerId: z.string() }),
      outputSchema: z.object({ orderId: z.string(), riskScore: z.number(), recommendation: z.enum(['approve', 'review', 'block']), flags: z.array(z.string()) }),
      handler: async (input: unknown) => {
        const data = input as { orderId: string; amount: number; customerId: string }
        const score = Math.random()
        const recommendation = score > 0.8 ? 'block' as const : score > 0.4 ? 'review' as const : 'approve' as const
        const flags: string[] = []
        if (data.amount > 5000) flags.push('high_value')
        if (score > 0.6) flags.push('unusual_pattern')
        return { orderId: data.orderId, riskScore: Math.round(score * 100) / 100, recommendation, flags }
      },
    })

    super('ag-036', FRAUD_DETECTOR_DEFINITION, context)
    this.executor = new ToolExecutor(tools)
  }

  override async handleTask(task: Record<string, unknown>): Promise<Record<string, unknown>> {
    await super.handleTask(task)
    if (task['type'] === 'check_fraud') {
      const result = await this.executor.execute('fraud.analyze', task)
      this.context.memory.episodic.record({
        type: 'fraud.checked', agentId: this.id,
        data: { orderId: task['orderId'] as string, result },
      })
      return { ...task, result }
    }
    return super.handleTask(task)
  }
}
