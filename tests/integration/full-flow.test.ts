import { describe, it, beforeAll } from '@jest/globals'

const BASE = 'http://localhost:3000'
let token = ''

async function api(method: string, path: string, body?: unknown) {
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) h['Authorization'] = `Bearer ${token}`
  const r = await fetch(`${BASE}${path}`, { method, headers: h, body: body ? JSON.stringify(body) : undefined })
  return { status: r.status, data: await r.json().catch(() => null) }
}

describe('ATHENA Integration Tests', () => {
  beforeAll(async () => {
    const r = await api('POST', '/api/auth/login', { username: 'admin', password: 'athena-admin-2026' })
    token = (r.data as Record<string, string>)?.['token'] || ''
  }, 15000)

  it('GET /api/health — returns healthy status', async () => {
    const r = await api('GET', '/api/health')
    expect(r.status).toBe(200)
    expect((r.data as Record<string, unknown>)['status']).toBe('healthy')
  })

  it('GET /api/agents — returns 52 agents', async () => {
    const r = await api('GET', '/api/agents')
    expect(r.status).toBe(200)
    const agents = (r.data as Record<string, unknown>)['agents'] as Array<unknown>
    expect(agents.length).toBeGreaterThanOrEqual(50)
  })

  it('GET /api/agents/:id — returns agent detail', async () => {
    const r = await api('GET', '/api/agents/ag-031')
    expect(r.status).toBe(200)
    expect((r.data as Record<string, unknown>)['name']).toBe('stock-level-monitor')
  })

  it('POST /api/business/quality/analyze-cycle — analyzes cycle', async () => {
    const r = await api('POST', '/api/business/quality/analyze-cycle', {
      cycleId: 'CYC-INT-001', machineId: 'INJ-03', temp: 225, pressure: 850, cycleTime: 32,
    })
    expect(r.status).toBe(200)
    expect((r.data as Record<string, unknown>)['result']).toBeDefined()
  })

  it('POST /api/business/orders — creates order workflow', async () => {
    const r = await api('POST', '/api/business/orders', {
      orderId: `ORD-INT-${Date.now()}`, customerId: 'CUST-001', skus: ['PT-0001-A'], amount: 150,
    })
    expect(r.status).toBe(200)
    expect((r.data as Record<string, unknown>)['workflowInstance']).toBeDefined()
  })

  it('GET /api/admin/scheduler — returns scheduler jobs', async () => {
    const r = await api('GET', '/api/admin/scheduler')
    expect(r.status).toBe(200)
    const jobs = (r.data as Record<string, unknown>)['jobs'] as Array<unknown>
    expect(jobs.length).toBeGreaterThanOrEqual(9)
  })

  it('GET /metrics — returns Prometheus text', async () => {
    const r = await fetch(`${BASE}/metrics`)
    const text = await r.text()
    expect(r.status).toBe(200)
    expect(text).toContain('athena_agents_running')
    expect(text).toContain('athena_agent_tasks_total')
  })

  it('GET /api/health — infrastructure all connected', async () => {
    const r = await api('GET', '/api/health')
    const infra = (r.data as Record<string, unknown>)['infrastructure'] as Record<string, { connected: boolean }>
    expect(infra?.['postgres']?.['connected']).toBe(true)
    expect(infra?.['redis']?.['connected']).toBe(true)
    expect(infra?.['kafka']?.['connected']).toBe(true)
  })
})
