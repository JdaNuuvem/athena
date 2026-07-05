const BASE_URL = process.env['ATHENA_URL'] ?? 'http://localhost:3000'

interface FetchResult { status: number; data: unknown }

async function get(path: string): Promise<FetchResult> {
  const res = await fetch(`${BASE_URL}${path}`)
  const data = await res.json()
  return { status: res.status, data }
}

async function post(path: string, body: unknown): Promise<FetchResult> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json()
  return { status: res.status, data }
}

async function main(): Promise<void> {
  console.log('╔══════════════════════════════════════╗')
  console.log('║   ATHENA Demo — Fluxo de Negócio    ║')
  console.log('╚══════════════════════════════════════╝\n')

  console.log('1. Health check...')
  const health = await get('/api/health')
  console.log(`   ${health.status === 200 ? '✅' : '❌'} ${JSON.stringify(health.data)}\n`)

  console.log('2. Agentes ativos...')
  const agents = await get('/api/agents')
  const agentList = (agents.data as { agents?: Array<{ id: string; name: string; status: string }> }).agents ?? []
  for (const a of agentList) console.log(`   [${a.id}] ${a.name} — ${a.status}`)
  console.log()

  console.log('3. Criando pedido omnichannel...')
  const order = await post('/api/business/orders', {
    orderId: `ORD-${Date.now()}`,
    customerId: 'CUST-12345',
    channelOrigin: 'telegram',
    lines: [
      { sku: 'PT-0001-A', quantity: 10, unitPrice: 29.90 },
      { sku: 'PT-0002-B', quantity: 5, unitPrice: 45.00 },
      { sku: 'PT-0003-C', quantity: 20, unitPrice: 12.50 },
    ],
  })
  const orderData = order.data as Record<string, unknown>
  const orderStatus = orderData['order'] as Record<string, unknown>
  const workflowResults = orderData['workflowResults'] as Record<string, Record<string, unknown>>
  console.log(`   Status: ${order.status === 200 ? '✅' : '❌'} ${orderStatus?.['id']} → ${orderStatus?.['status']}`)
  console.log()

  console.log('4. Resultados do workflow:')
  if (workflowResults) {
    for (const [step, result] of Object.entries(workflowResults)) {
      const r = result as Record<string, unknown>
      console.log(`   📋 ${step}:`)
      if (r['result'] && (r['result'] as Record<string, unknown>)['data']) {
        const data = (r['result'] as Record<string, unknown>)['data'] as Record<string, unknown>
        for (const [k, v] of Object.entries(data)) {
          console.log(`      ${k}: ${JSON.stringify(v)}`)
        }
      } else if (r['fulfillmentCenter']) {
        console.log(`      center: ${r['fulfillmentCenter']}, delivery: ${r['estimatedDeliveryDays']}d, cost: R$${r['cost']}`)
      } else if (r['recommendation']) {
        console.log(`      score: ${r['riskScore']}, decision: ${r['recommendation']}, flags: ${JSON.stringify(r['flags'])}`)
      } else if (r['carrier']) {
        console.log(`      carrier: ${r['carrier']} ${r['service']}, R$${r['cost']}, ${r['estimatedDays']}d, score: ${r['score']}`)
      }
    }
  }
  console.log()

  console.log('5. Verificando estoque...')
  const stock = await get('/api/business/inventory/PT-0001-A')
  const stockData = stock.data as Record<string, unknown>
  const stockResult = stockData['result'] as Record<string, unknown> | undefined
  console.log(`   ${stock.status === 200 ? '✅' : '❌'} SKU: PT-0001-A — ${stockResult?.['data'] ? JSON.stringify(stockResult['data']) : 'not available'}`)
  console.log()

  console.log('6. Analisando qualidade (ciclo de injeção)...')
  const quality = await post('/api/business/quality/analyze-cycle', {
    cycleId: 'CYC-999',
    machineId: 'INJ-03',
    temp: 225,
    pressure: 850,
    cycleTime: 32,
  })
  const qualityData = quality.data as Record<string, unknown>
  const qResult = qualityData['result'] as Record<string, unknown> | undefined
  console.log(`   ${quality.status === 200 ? '✅' : '❌'} Cycle CYC-999 — ${qResult?.['data'] ? JSON.stringify(qResult['data']) : 'ok'}`)
  console.log()

  console.log('7. Memória dos agentes (últimas ações)...')
  for (const a of agentList.slice(0, 3)) {
    const mem = await get(`/api/agents/${a.id}/memory`)
    const memData = mem.data as Record<string, unknown>
    const episodic = memData['episodic'] as Array<Record<string, unknown>>
    if (episodic) {
      console.log(`   [${a.id}] ${episodic.length} eventos registrados`)
      for (const e of episodic.slice(-2)) {
        console.log(`      ${e['type']}: ${JSON.stringify(e['data']).substring(0, 100)}`)
      }
    }
  }

  console.log('\n╔══════════════════════════════════════╗')
  console.log('║        Demo concluída!               ║')
  console.log('╚══════════════════════════════════════╝')
}

main().catch(console.error)
