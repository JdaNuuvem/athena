import { describe, it, expect } from '@jest/globals'
import { createProductDesignAssistant } from '../../../src/agents/instances/observers/product-design-assistant'

describe('ProductDesignAssistant - Static Import', () => {
  it('should create instance with tools', () => {
    const agent = createProductDesignAssistant()
    expect(agent).toBeDefined()
    expect(agent.getToolRegistry().list().length).toBe(2)
    agent.stop()
  })
})
