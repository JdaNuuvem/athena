import { describe, it, expect } from '@jest/globals'
import { PromptManager } from '../../../src/agents/prompt/prompt-manager'
import { InMemoryTaskQueue } from '../../../src/agents/tasks/task-queue'
import { InMemoryAgentLogger, AuditTrail } from '../../../src/agents/logging/agent-logger'
import { createProductDesignTools } from '../../../src/agents/instances/observers/product-design-tools'
import { InMemoryShortTerm } from '../../../src/agents/memory/short-term'
import { InMemoryLongTerm } from '../../../src/agents/memory/long-term'
import { InMemoryEpisodic } from '../../../src/agents/memory/episodic'
import type { DefaultMemoryManager } from '../../../src/agents/memory/memory-manager'

describe('Prompt Manager', () => {
  it('should resolve template variables', () => {
    const manager = new PromptManager()
    manager.register({ name: 'test', version: '1.0', system: 'Hello {{name}}', context: 'Ctx {{ctx}}', tools: '', format: '' })
    const result = manager.resolve(manager.get('test')!, { name: 'World', ctx: 'Test' })
    expect(result).toContain('Hello World')
    expect(result).toContain('Ctx Test')
  })
})

describe('Task Queue', () => {
  it('should dequeue by priority', () => {
    const q = new InMemoryTaskQueue()
    q.enqueue({ id: '1', type: 'low', priority: 'low', input: {}, status: 'pending', createdAt: new Date(), retryCount: 0 })
    q.enqueue({ id: '2', type: 'high', priority: 'high', input: {}, status: 'pending', createdAt: new Date(), retryCount: 0 })
    expect(q.dequeue()?.id).toBe('2')
  })
})

describe('Logger', () => {
  it('should log entries', () => {
    const logger = new InMemoryAgentLogger()
    logger.info('AG-001', 'test', { k: 'v' })
    expect(logger.getLogs('AG-001').length).toBe(1)
  })

  it('should create audit trail', () => {
    const audit = new AuditTrail()
    audit.record({ agentId: 'AG-001', action: 'test', decision: 'pass', rationale: 'r' })
    expect(audit.replay('AG-001').length).toBe(1)
  })
})

describe('Product Design Tools', () => {
  const mem = { shortTerm: new InMemoryShortTerm(), longTerm: new InMemoryLongTerm(), episodic: new InMemoryEpisodic(), hybridSearch: async () => [] } as unknown as DefaultMemoryManager
  const tools = createProductDesignTools(mem)

  it('should validate specification', async () => {
    const tool = tools.find(t => t.name === 'validate-specification')!
    const result = await tool.handler({
      productId: 'P1', sku: 'PT-0001-A', name: 'Test Product', category: 'test',
      materials: [{ materialId: 'M1', name: 'PP', type: 'termoplastico' }],
      dimensions: { lengthMm: 10, widthMm: 10, heightMm: 10, weightG: 10 },
    })
    const r = result as Record<string, unknown>
    expect(r['valid']).toBe(true)
    expect(r['score']).toBe(100)
  })

  it('should check BOM', async () => {
    const tool = tools.find(t => t.name === 'check-bom-completeness')!
    const result = await tool.handler({
      bomId: 'B1', productId: 'P1',
      components: [{ componentId: 'C1', name: 'Comp', quantity: 1, materialSpec: 'PP' }],
    })
    const r = result as Record<string, unknown>
    expect(r['complete']).toBe(true)
  })
})
