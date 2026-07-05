import type { AgentRegistry } from '../registry/agent-registry'
import type { AgentProcess } from '../core/agent-runtime'

export interface CronJob {
  readonly id: string
  readonly agentId: string
  readonly taskType: string
  readonly taskInput: Record<string, unknown>
  readonly intervalMs: number
  enabled: boolean
}

export class TaskScheduler {
  private jobs = new Map<string, { config: CronJob; timer: ReturnType<typeof setInterval> | null }>()
  private running = false

  constructor(private registry: AgentRegistry) {}

  register(job: Omit<CronJob, 'enabled'>): void {
    this.jobs.set(job.id, { config: { ...job, enabled: true }, timer: null })
  }

  start(): void {
    if (this.running) return
    this.running = true
    for (const [, entry] of this.jobs) {
      this.startJob(entry)
    }
    console.log(`[Scheduler] ${this.jobs.size} cron jobs started`)
  }

  stop(): void {
    this.running = false
    for (const [, entry] of this.jobs) {
      if (entry.timer) {
        clearInterval(entry.timer)
        entry.timer = null
      }
    }
  }

  private startJob(entry: { config: CronJob; timer: ReturnType<typeof setInterval> | null }): void {
    if (!entry.config.enabled) return
    entry.timer = setInterval(async () => {
      const agent = this.registry.get(entry.config.agentId)
      if (!agent || agent.status !== 'running') return
      try {
        await agent.handleTask({
          type: entry.config.taskType,
          scheduled: true,
          timestamp: new Date().toISOString(),
          ...entry.config.taskInput,
        })
      } catch { /* agent error — already logged by runtime */ }
    }, entry.config.intervalMs)
  }

  list(): CronJob[] {
    return [...this.jobs.values()].map(e => e.config)
  }

  enable(id: string): void {
    const entry = this.jobs.get(id)
    if (entry) {
      entry.config.enabled = true
      if (this.running) this.startJob(entry)
    }
  }

  disable(id: string): void {
    const entry = this.jobs.get(id)
    if (entry) {
      entry.config.enabled = false
      if (entry.timer) { clearInterval(entry.timer); entry.timer = null }
    }
  }

  getStats(): { total: number; running: number; lastRuns: Array<{ jobId: string; agentId: string; lastRun: string | null }> } {
    return {
      total: this.jobs.size,
      running: [...this.jobs.values()].filter(e => e.config.enabled).length,
      lastRuns: [...this.jobs.entries()].map(([id, e]) => ({ jobId: id, agentId: e.config.agentId, lastRun: null })),
    }
  }
}

export function createDefaultCronJobs(): Array<Omit<CronJob, 'enabled'>> {
  return [
    { id: 'sched-stock-check', agentId: 'ag-031', taskType: 'check_stock', taskInput: { warehouseId: 'WH-001' }, intervalMs: 60 * 60 * 1000 },
    { id: 'sched-health-check', agentId: 'ag-052', taskType: 'health_check', taskInput: {}, intervalMs: 5 * 60 * 1000 },
    { id: 'sched-demand-forecast', agentId: 'ag-032', taskType: 'forecast_demand', taskInput: { horizon: 7 }, intervalMs: 24 * 60 * 60 * 1000 },
    { id: 'sched-dead-stock', agentId: 'ag-034', taskType: 'detect_dead', taskInput: { daysWithoutMovement: 90 }, intervalMs: 12 * 60 * 60 * 1000 },
    { id: 'sched-competitor', agentId: 'ag-023', taskType: 'monitor_competitors', taskInput: {}, intervalMs: 6 * 60 * 60 * 1000 },
    { id: 'sched-margin', agentId: 'ag-050', taskType: 'watch_margin', taskInput: {}, intervalMs: 24 * 60 * 60 * 1000 },
    { id: 'sched-tool-wear', agentId: 'ag-008', taskType: 'monitor_tool_wear', taskInput: {}, intervalMs: 2 * 60 * 60 * 1000 },
    { id: 'sched-maintenance', agentId: 'ag-005', taskType: 'predict_maintenance', taskInput: {}, intervalMs: 24 * 60 * 60 * 1000 },
    { id: 'sched-customer-segment', agentId: 'ag-039', taskType: 'segment_customers', taskInput: {}, intervalMs: 7 * 24 * 60 * 60 * 1000 },
  ]
}
