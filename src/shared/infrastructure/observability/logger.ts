import pino from 'pino'

const level = process.env['LOG_LEVEL'] ?? 'info'

export const logger = pino({ level, serializers: { err: pino.stdSerializers.err, req: pino.stdSerializers.req, res: pino.stdSerializers.res } })

export function createContextLogger(context: string, extra?: Record<string, string>) {
  return logger.child({ context, ...extra })
}

export function logAgentEvent(agentId: string, event: string, data?: Record<string, unknown>) {
  logger.info({ agentId, event, ...data }, `[${agentId}] ${event}`)
}

export function logWorkflowEvent(workflowId: string, stepId: string, event: string, data?: Record<string, unknown>) {
  logger.info({ workflowId, stepId, event, ...data }, `[wf:${workflowId}] ${stepId} — ${event}`)
}

export function logError(context: string, err: unknown, extra?: Record<string, unknown>) {
  logger.error({ context, err, ...extra }, `[${context}] ${String(err)}`)
}
