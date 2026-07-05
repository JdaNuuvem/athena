import type { AgentRegistry } from '../../agents/registry/agent-registry'
import type { OrchestrationEngine } from '../../agents/orchestration/orchestration-engine'

export interface DashboardConfig {
  readonly port: number
  readonly host: string
}

interface DashboardRequest {
  params: Record<string, string>
  query: Record<string, string>
}

// ponytail: minimal REST API without framework. Import fastify when >5 endpoints.
export function createDashboardRoutes(
  registry: AgentRegistry,
  orchestrator: OrchestrationEngine,
): Array<{ method: string; path: string; handler: (req: DashboardRequest) => Record<string, unknown> }> {
  return [
    {
      method: 'GET', path: '/api/health',
      handler: () => ({ status: 'ok', timestamp: new Date().toISOString() }),
    },
    {
      method: 'GET', path: '/api/agents',
      handler: () => ({
        agents: registry.list().map(a => ({
          id: a.id, name: a.definition.name, role: a.definition.role,
          status: a.status, context: a.definition.context,
        })),
      }),
    },
    {
      method: 'GET', path: '/api/agents/:id',
      handler: (req) => {
        const agent = registry.get(req.params['id'] ?? '')
        if (!agent) return { error: 'Not found' }
        return {
          id: agent.id, name: agent.definition.name, role: agent.definition.role,
          status: agent.status, startedAt: agent.startedAt, config: agent.definition.config,
        }
      },
    },
    {
      method: 'GET', path: '/api/agents/:id/health',
      handler: (req) => {
        const health = registry.healthCheck()
        const agentHealth = health.find(h => h.agentId === req.params['id'])
        return agentHealth ?? { error: 'Agent not found' }
      },
    },
    {
      method: 'GET', path: '/api/memory/:agentId',
      handler: (req) => {
        const agent = registry.get(req.params['agentId'] ?? '')
        if (!agent) return { error: 'Agent not found' }
        return {
          shortTerm: agent.context.memory.shortTerm.recent(20),
          episodic: agent.context.memory.episodic.history(req.params['agentId'] ?? '', 20),
        }
      },
    },
    {
      method: 'GET', path: '/api/workflows/:id',
      handler: (req) => {
        const status = orchestrator.getWorkflowStatus(req.params['id'] ?? '')
        return status ?? { error: 'Workflow not found' }
      },
    },
  ]
}
