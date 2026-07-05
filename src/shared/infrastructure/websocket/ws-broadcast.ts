import { wsBus } from './ws-bus'

export function setupWSBroadcast(registry: { events: { on: (e: string, cb: (...args: unknown[]) => void) => void }; list: () => Array<{ id: string; status: string }> }): void {
  registry.events.on('agent-registered', (data: unknown) => {
    const d = data as { id: string }
    wsBus.broadcast('agent.registered', { agentId: d.id })
  })

  registry.events.on('agent-status-changed', (data: unknown) => {
    const d = data as { id: string; current: string }
    wsBus.broadcast('agent.status', { agentId: d.id, status: d.current })
  })

  setInterval(() => {
    const agents = registry.list()
    wsBus.broadcast('agent.snapshot', {
      total: agents.length,
      running: agents.filter(a => a.status === 'running').length,
      errored: agents.filter(a => a.status === 'error').length,
      idle: agents.filter(a => a.status === 'idle').length,
    })
  }, 10000).unref()
}

export function broadcastAgentTask(agentId: string, event: string, data?: Record<string, unknown>): void {
  wsBus.broadcast(`agent.task.${event}`, { agentId, ...(data ?? {}) })
}

export function broadcastWorkflowStatus(workflowName: string, stepId: string, status: string, data?: Record<string, unknown>): void {
  wsBus.broadcast('workflow.status', { name: workflowName, stepId, status, ...(data ?? {}) })
}
