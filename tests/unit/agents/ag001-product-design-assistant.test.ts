import { describe, it, expect, beforeEach, afterEach } from '@jest/globals'
import { createProductDesignAssistant } from '../../../src/agents/instances/observers/product-design-assistant'
import type { ProductDesignAssistantAgent } from '../../../src/agents/instances/observers/product-design-assistant'

describe('ProductDesignAssistant (AG-001)', () => {
  let agent: ProductDesignAssistantAgent

  beforeEach(() => { agent = createProductDesignAssistant() })
  afterEach(async () => { await agent.stop() })

  it('should start and stop successfully', async () => {
    await agent.start()
    expect(agent.status).toBe('running')
    expect(agent.startedAt).toBeInstanceOf(Date)
    await agent.stop()
    expect(agent.status).toBe('stopped')
  })

  it('should validate a complete specification (tool)', async () => {
    await agent.start()
    const result = await agent.handleTask({
      type: 'validate-specification',
      productId: 'PROD-001', sku: 'PT-0001-A', name: 'Tampa Plastica Universal',
      category: 'utensilios-domesticos',
      materials: [{ materialId: 'MAT-001', name: 'Polipropileno (PP)', type: 'termoplastico' }],
      dimensions: { lengthMm: 120, widthMm: 80, heightMm: 15, weightG: 45 },
    })
    expect(result).toHaveProperty('result')
    const r = result['result'] as Record<string, unknown>
    expect(r['valid']).toBe(true)
    expect(r['score']).toBe(100)
  })

  it('should detect invalid SKU format', async () => {
    await agent.start()
    const result = await agent.handleTask({
      type: 'validate-specification',
      productId: 'PROD-002', sku: 'invalido', name: 'Produto Teste', category: 'test',
      materials: [{ materialId: 'M1', name: 'ABS', type: 'termoplastico' }],
      dimensions: { lengthMm: 100, widthMm: 50, heightMm: 10, weightG: 30 },
    })
    const r = result['result'] as Record<string, unknown>
    expect(r['valid']).toBe(true)
    expect(r['score']).toBe(70)
    const issues = r['issues'] as Array<{ field: string }>
    expect(issues.some(i => i.field === 'sku')).toBe(true)
  })

  it('should pass a complete BOM', async () => {
    await agent.start()
    const result = await agent.handleTask({
      type: 'check-bom-completeness',
      bomId: 'BOM-001', productId: 'PROD-001',
      components: [
        { componentId: 'CMP-001', name: 'Corpo', quantity: 1, materialSpec: 'PP Virgem' },
        { componentId: 'CMP-002', name: 'Tampa', quantity: 1, materialSpec: 'PEAD' },
      ],
    })
    const r = result['result'] as Record<string, unknown>
    expect(r['complete']).toBe(true)
    expect(r['componentCount']).toBe(2)
  })

  it('should detect duplicate components', async () => {
    await agent.start()
    const result = await agent.handleTask({
      type: 'check-bom-completeness',
      bomId: 'BOM-002', productId: 'PROD-002',
      components: [
        { componentId: 'CMP-001', name: 'P1', quantity: 1, materialSpec: 'Aco' },
        { componentId: 'CMP-001', name: 'P1 Dup', quantity: 1, materialSpec: 'Aco' },
      ],
    })
    const r = result['result'] as Record<string, unknown>
    expect(r['complete']).toBe(false)
    expect(r['duplicateCount']).toBeGreaterThan(0)
  })

  it('should have tools registered', () => {
    const tools = agent.getToolRegistry()
    expect(tools.get('validate-specification')).toBeDefined()
    expect(tools.get('check-bom-completeness')).toBeDefined()
  })

  it('should handle generic task gracefully', async () => {
    await agent.start()
    const result = await agent.handleTask({ type: 'unknown_task', data: 'test' })
    expect(result).toHaveProperty('status', 'completed')
    expect(result).toHaveProperty('agentId', 'AG-001')
  })
})
