import { trace, Span, SpanStatusCode, Tracer, context, propagation } from '@opentelemetry/api'
import type { FastifyRequest } from 'fastify'

let _tracer: Tracer | null = null

function getTracer(): Tracer {
  if (!_tracer) _tracer = trace.getTracer('athena')
  return _tracer
}

export function startSpan(name: string, attributes?: Record<string, string>): Span {
  return getTracer().startSpan(name, { attributes })
}

export function startAgentSpan(agentId: string, taskType: string): Span {
  return getTracer().startSpan(`agent.${agentId}.${taskType}`, {
    attributes: { 'agent.id': agentId, 'task.type': taskType },
  })
}

export function startWorkflowSpan(workflowName: string, stepId: string): Span {
  return getTracer().startSpan(`workflow.${workflowName}.${stepId}`, {
    attributes: { 'workflow.name': workflowName, 'step.id': stepId },
  })
}

export function endSpan(span: Span, error?: Error) {
  if (error) {
    span.setStatus({ code: SpanStatusCode.ERROR, message: error.message })
    span.recordException(error)
  }
  span.end()
}

export function extractTraceContext(req: FastifyRequest): void {
  const ctx = propagation.extract(context.active(), req.headers)
  if (ctx) {
    try { context.active(); /* use ctx for propagation */ } catch { /* ignore */ }
  }
}

export function injectTraceContext(span: Span, headers: Record<string, string>): void {
  const ctx = trace.setSpan(context.active(), span)
  propagation.inject(ctx, headers)
}
