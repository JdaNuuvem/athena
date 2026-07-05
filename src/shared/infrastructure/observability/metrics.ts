import { Counter, Histogram, Gauge, Registry, collectDefaultMetrics } from 'prom-client'

const registry = new Registry()
collectDefaultMetrics({ register: registry, prefix: 'athena_' })

export const metrics = {
  agentTasksTotal: new Counter({
    name: 'athena_agent_tasks_total',
    help: 'Total agent tasks processed',
    labelNames: ['agent_id', 'status'],
    registers: [registry],
  }),

  agentTaskDuration: new Histogram({
    name: 'athena_agent_task_duration_seconds',
    help: 'Agent task duration in seconds',
    labelNames: ['agent_id'],
    buckets: [0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10, 30],
    registers: [registry],
  }),

  workflowExecutionsTotal: new Counter({
    name: 'athena_workflow_executions_total',
    help: 'Total workflow executions',
    labelNames: ['workflow_name', 'status'],
    registers: [registry],
  }),

  workflowStepDuration: new Histogram({
    name: 'athena_workflow_step_duration_seconds',
    help: 'Workflow step duration',
    labelNames: ['workflow_name', 'step_id'],
    buckets: [0.1, 0.5, 1, 5, 10, 30, 60],
    registers: [registry],
  }),

  httpRequestsTotal: new Counter({
    name: 'athena_http_requests_total',
    help: 'Total HTTP requests',
    labelNames: ['method', 'route', 'status_code'],
    registers: [registry],
  }),

  httpRequestDuration: new Histogram({
    name: 'athena_http_request_duration_seconds',
    help: 'HTTP request duration',
    labelNames: ['method', 'route'],
    buckets: [0.01, 0.05, 0.1, 0.5, 1, 2, 5],
    registers: [registry],
  }),

  agentsRunning: new Gauge({
    name: 'athena_agents_running',
    help: 'Number of running agents',
    registers: [registry],
  }),

  agentsErrored: new Gauge({
    name: 'athena_agents_errored',
    help: 'Number of agents in error state',
    registers: [registry],
  }),

  kafkaMessagesConsumed: new Counter({
    name: 'athena_kafka_messages_consumed_total',
    help: 'Total Kafka messages consumed',
    labelNames: ['event_type'],
    registers: [registry],
  }),

  domainEventsHandled: new Counter({
    name: 'athena_domain_events_handled_total',
    help: 'Total domain events handled',
    labelNames: ['event_type', 'status'],
    registers: [registry],
  }),
}

export async function getMetricsAsText(): Promise<string> {
  return registry.metrics()
}

export function getMetricsRegistry(): Registry {
  return registry
}
