import http from 'k6/http'
import { check, sleep, group } from 'k6'

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 50 },
    { duration: '30s', target: 100 },
    { duration: '1m', target: 100 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'],
    http_req_failed: ['rate<0.05'],
  },
}

const BASE = 'http://localhost:3000'
let token = ''

export default function () {
  if (!token) {
    const login = http.post(`${BASE}/api/auth/login`, JSON.stringify({ username: 'admin', password: 'athena-admin-2026' }), { headers: { 'Content-Type': 'application/json' } })
    const t = login.json() as Record<string, string>
    token = t['token'] || ''
  }

  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }

  group('Health', () => {
    const r = http.get(`${BASE}/api/health`)
    check(r, { 'health 200': (r) => r.status === 200 })
  })

  group('Agents', () => {
    const r = http.get(`${BASE}/api/agents`, { headers })
    check(r, { 'agents 200': (r) => r.status === 200 })
  })

  group('Quality Analysis', () => {
    const r = http.post(`${BASE}/api/business/quality/analyze-cycle`, JSON.stringify({
      cycleId: `CYC-K6-${Date.now()}`, machineId: 'INJ-03', temp: 225, pressure: 850, cycleTime: 32,
    }), { headers })
    check(r, { 'quality 200': (r) => r.status === 200 })
  })

  group('Inventory Check', () => {
    const r = http.get(`${BASE}/api/business/inventory/PT-0001-A`, { headers })
    check(r, { 'inventory 200': (r) => r.status === 200 })
  })

  group('Order Workflow', () => {
    const r = http.post(`${BASE}/api/business/orders`, JSON.stringify({
      orderId: `ORD-K6-${__VU}-${__ITER}`, customerId: 'CUST-001', skus: ['PT-0001-A'], amount: 150,
    }), { headers })
    check(r, { 'order 200': (r) => r.status === 200 })
  })

  group('Metrics', () => {
    const r = http.get(`${BASE}/metrics`)
    check(r, { 'metrics 200': (r) => r.status === 200 })
  })

  sleep(1)
}
