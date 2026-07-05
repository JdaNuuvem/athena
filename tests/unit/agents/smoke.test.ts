import { describe, it, expect } from '@jest/globals'
import { createProductDesignAssistant } from '../../../src/agents/instances/observers/product-design-assistant'

describe('ProductDesignAssistant - Smoke', () => {
  it('should load and create instance', async () => {
    const agent = createProductDesignAssistant()
    expect(agent).toBeDefined()
    expect(agent.id).toBe('AG-001')
    expect(agent.status).toBe('idle')
    await agent.stop()
  })
})
