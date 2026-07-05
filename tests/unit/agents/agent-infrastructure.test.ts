import { describe, it, expect, beforeEach, afterEach } from '@jest/globals'
import { DefaultAgentRegistry } from '../../../src/agents/registry/agent-registry'
import { DefaultCapabilityRegistry } from '../../../src/agents/registry/capability-registry'
import { DefaultHealthCheck } from '../../../src/agents/registry/health-check'
import { DAGOrchestrationEngine } from '../../../src/agents/orchestration/orchestration-engine'
import { defineWorkflow } from '../../../src/agents/orchestration/workflow-definitions'
import { DefaultSagaCoordinator } from '../../../src/agents/orchestration/saga-coordinator'
import { DefaultConflictResolver } from '../../../src/agents/orchestration/conflict-resolver'
import { createProductDesignAssistant } from '../../../src/agents/instances/observers/product-design-assistant'
import type { AgentDefinition } from '../../../src/agents/core/agent-types'

const agentDef: AgentDefinition = {
  id: 'AG-001', name: 'product-design-assistant', role: 'observer', context: 'product-engineering',
  systemPrompt: 'You are a product design assistant.',
  config: { modelProvider: 'openai', modelName: 'gpt-4o-mini', temperature: 0.3, maxTokens: 4096, retryPolicy: { maxRetries: 3, backoffMs: 1000 }, timeout: 60000 },
  capabilities: [
    { name: 'validate-specification', description: 'Validates product specs', inputSchema: {}, outputSchema: {} },
    { name: 'check-bom-completeness', description: 'Checks BOM', inputSchema: {}, outputSchema: {} },
  ],
}

describe('Agent Registry', () => {
  let registry: DefaultAgentRegistry

  beforeEach(() => { registry = new DefaultAgentRegistry() })

  it('should register and retrieve an agent process', async () => {
    const agent = createProductDesignAssistant()
    await agent.start()
    registry.register(agent)
    const reg = registry.get('AG-001')
    expect(reg).toBeDefined()
    expect(reg!.definition.name).toBe('product-design-assistant')
    expect(registry.list().length).toBe(1)
    await agent.stop()
  })

  it('should filter by role', async () => {
    const agent = createProductDesignAssistant()
    await agent.start()
    registry.register(agent)
    expect(registry.list({ role: 'observer' }).length).toBe(1)
    expect(registry.list({ role: 'executor' }).length).toBe(0)
    await agent.stop()
  })

  it('should find by capability', async () => {
    const agent = createProductDesignAssistant()
    await agent.start()
    registry.register(agent)
    expect(registry.findByCapability('validate-specification').length).toBe(1)
    expect(registry.findByCapability('nonexistent').length).toBe(0)
    await agent.stop()
  })

  it('should update status and emit event', async () => {
    const events: Array<{ id: string; current: string }> = []
    registry.events.on('agent-status-changed', (e: { id: string; current: string }) => events.push(e))
    const agent = createProductDesignAssistant()
    await agent.start()
    registry.register(agent)
    registry.updateStatus('AG-001', 'paused')
    expect(registry.get('AG-001')?.status).toBe('paused')
    expect(events.length).toBe(1)
    await agent.stop()
  })

  it('should report health check', async () => {
    const agent = createProductDesignAssistant()
    await agent.start()
    registry.register(agent)
    const health = registry.healthCheck()
    expect(health.length).toBe(1)
    expect(health[0]!.agentId).toBe('AG-001')
    expect(health[0]!.healthy).toBe(true)
    await agent.stop()
  })
})

describe('Capability Registry', () => {
  let agentRegistry: DefaultAgentRegistry
  let capRegistry: DefaultCapabilityRegistry

  beforeEach(() => {
    agentRegistry = new DefaultAgentRegistry()
    capRegistry = new DefaultCapabilityRegistry(agentRegistry)
  })

  it('should register and find capabilities', () => {
    capRegistry.registerCapability('AG-001', { name: 'validate', description: 'Validates data', inputSchema: {}, outputSchema: {} })
    expect(capRegistry.findByCapability('validate')?.agents).toContain('AG-001')
  })

  it('should search capabilities by description', () => {
    capRegistry.registerCapability('AG-001', { name: 'spec-validator', description: 'product specifications domain rules', inputSchema: {}, outputSchema: {} })
    expect(capRegistry.searchCapabilities('specification').length).toBe(1)
  })
})

describe('Health Check', () => {
  let agentRegistry: DefaultAgentRegistry
  let healthCheck: DefaultHealthCheck

  beforeEach(() => {
    agentRegistry = new DefaultAgentRegistry()
    healthCheck = new DefaultHealthCheck(agentRegistry, { heartbeatIntervalMs: 100, heartbeatTimeoutMs: 5000, maxMissedHeartbeats: 3, autoRestart: false })
  })

  afterEach(() => { healthCheck.stop() })

  it('should report healthy agent', async () => {
    const agent = createProductDesignAssistant()
    await agent.start()
    agentRegistry.register(agent)
    agentRegistry.heartbeat('AG-001')
    healthCheck.start()
    const hs = healthCheck.check('AG-001')
    expect(hs?.healthy).toBe(true)
    await agent.stop()
  })
})

describe('Orchestration Engine', () => {
  it('should execute a linear workflow', async () => {
    const engine = new DAGOrchestrationEngine()
    const executed: string[] = []
    engine.registerAgent('AG-TEST', {
      handleTask: async (task: Record<string, unknown>) => { executed.push(task['workflowStep'] as string); return { ok: true } },
    })

    const wf = defineWorkflow({
      name: 'linear-test', description: '', trigger: { manual: true },
      steps: [
        { id: 'step1', label: 'S1', targetAgentId: 'AG-TEST', config: {} },
        { id: 'step2', label: 'S2', targetAgentId: 'AG-TEST', dependsOn: ['step1'], config: {} },
      ],
    })
    engine.deploy(wf)
    const instance = await engine.trigger('linear-test', {})
    expect(instance.status).toBe('completed')
    expect(executed).toEqual(['step1', 'step2'])
  })
})

describe('Saga Coordinator', () => {
  it('should compensate on failure', async () => {
    const saga = new DefaultSagaCoordinator()
    let compensated = false
    const instance = await saga.execute({
      name: 'comp-saga', steps: [
        { id: 's1', action: async () => ({ ok: true }), compensation: async () => { compensated = true } },
        { id: 's2', action: async () => { throw new Error('fail') }, compensation: async () => {} },
      ],
    }, {})
    expect(instance.status).toBe('compensated')
    expect(compensated).toBe(true)
  })
})

describe('Conflict Resolver', () => {
  it('should pick winner by confidence', () => {
    const resolver = new DefaultConflictResolver()
    const r = resolver.resolve(['A1', 'A2'], 'price', [
      { agentId: 'A1', proposal: { p: 100 }, confidence: 0.9 },
      { agentId: 'A2', proposal: { p: 110 }, confidence: 0.4 },
    ])
    expect(r.resolution).toBe('agent-a-wins')
    expect(r.resolvedBy).toBe('A1')
  })
})

describe('Full Stack Integration', () => {
  it('should wire registry + orchestration + agent', async () => {
    const registry = new DefaultAgentRegistry()
    const engine = new DAGOrchestrationEngine()
    const agent = createProductDesignAssistant()

    await agent.start()
    registry.register(agent)
    engine.registerAgent('AG-001', agent)

    const wf = defineWorkflow({
      name: 'int-test', description: '', trigger: { manual: true },
      steps: [{ id: 'check', label: 'Check', targetAgentId: 'AG-001', config: {} }],
    })
    engine.deploy(wf)
    const instance = await engine.trigger('int-test', {})
    await agent.stop()

    expect(instance.status).toBe('completed')
    expect(registry.healthCheck().length).toBe(1)
  })
})
