import { useState } from 'react'
import { useApi } from '../hooks/useAuth'

export default function Business() {
  const api = useApi()
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)

  const checkStock = async () => { setLoading(true); const d = await api<Record<string, unknown>>('/api/business/inventory/PT-0001-A'); setResult(d); setLoading(false) }
  const analyzeQuality = async () => { setLoading(true); const d = await api<Record<string, unknown>>('/api/business/quality/analyze-cycle', { method: 'POST', body: JSON.stringify({ cycleId: `CYC-${Date.now()}`, machineId: 'INJ-03', temp: 225, pressure: 850, cycleTime: 32 }) }); setResult(d); setLoading(false) }
  const createOrder = async () => { setLoading(true); const d = await api<Record<string, unknown>>('/api/business/orders', { method: 'POST', body: JSON.stringify({ orderId: `ORD-${Date.now()}`, customerId: 'CUST-001', skus: ['PT-0001-A', 'PT-0002-B'], amount: 250 }) }); setResult(d); setLoading(false) }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-xl font-bold text-white">Business Operations</h2>
        <p className="text-athena-600 text-sm">Execute business flows via agents</p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <button onClick={checkStock} disabled={loading} className="bg-athena-800 hover:bg-athena-700 border border-athena-700 rounded-lg p-4 text-left transition">
          <p className="text-athena-accent text-lg mb-1">📦</p>
          <p className="text-white font-medium text-sm">Check Stock</p>
          <p className="text-athena-600 text-xs mt-1">PT-0001-A via ag-031</p>
        </button>
        <button onClick={analyzeQuality} disabled={loading} className="bg-athena-800 hover:bg-athena-700 border border-athena-700 rounded-lg p-4 text-left transition">
          <p className="text-athena-accent text-lg mb-1">🔬</p>
          <p className="text-white font-medium text-sm">Quality Analysis</p>
          <p className="text-athena-600 text-xs mt-1">Cycle via ag-011</p>
        </button>
        <button onClick={createOrder} disabled={loading} className="bg-athena-800 hover:bg-athena-700 border border-athena-700 rounded-lg p-4 text-left transition">
          <p className="text-athena-accent text-lg mb-1">🛒</p>
          <p className="text-white font-medium text-sm">Create Order</p>
          <p className="text-athena-600 text-xs mt-1">Route→Fraud→Carrier</p>
        </button>
      </div>

      {loading && <p className="text-athena-accent text-sm">Processing...</p>}

      {result && (
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4">
          <h3 className="text-sm font-semibold text-athena-400 mb-3">Result</h3>
          <pre className="text-xs text-athena-300 font-mono whitespace-pre-wrap max-h-96 overflow-auto">{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}
