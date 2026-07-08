import { useState, useEffect, useMemo } from 'react'
import { useApi } from '../hooks/useAuth'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

export default function Metrics() {
  const api = useApi()
  const [health, setHealth] = useState<Record<string, unknown> | null>(null)
  const [history, setHistory] = useState<Array<{ time: string; running: number; errored: number }>>([])

  useEffect(() => {
    api<Record<string, unknown>>('/api/health').then(d => {
      if (!d) return
      setHealth(d)
      const agents = d['agents'] as Record<string, number> | undefined
      if (agents) setHistory(p => [...p.slice(-30), { time: new Date().toLocaleTimeString(), running: agents['running'] || 0, errored: agents['errored'] || 0 }])
    })
    const t = setInterval(() => api<Record<string, unknown>>('/api/health').then(d => {
      if (!d) return
      setHealth(d)
      const agents = d['agents'] as Record<string, number> | undefined
      if (agents) setHistory(p => [...p.slice(-30), { time: new Date().toLocaleTimeString(), running: agents['running'] || 0, errored: agents['errored'] || 0 }])
    }), 5000)
    return () => clearInterval(t)
  }, [api])

  const infra = (health?.['infrastructure'] as Record<string, { connected: boolean }>) || {}

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white">Metrics</h2>
        <p className="text-athena-600 text-sm">System observability</p>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {Object.entries(infra).map(([k, v]) => (
          <div key={k} className="bg-athena-800 rounded-lg border border-athena-700 p-4 text-center">
            <p className="text-athena-600 text-xs uppercase mb-1">{k}</p>
            <p className={`text-2xl font-bold ${v?.['connected'] ? 'text-athena-success' : 'text-athena-error'}`}>{v?.['connected'] ? '●' : '○'}</p>
            <p className="text-athena-600 text-xs">{String((v as Record<string, unknown>)?.['status'] || '')}</p>
          </div>
        ))}
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-4">
        <h3 className="text-sm font-semibold text-athena-400 mb-4">Agents Over Time</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={history}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="time" stroke="#64748b" fontSize={12} />
            <YAxis stroke="#64748b" fontSize={12} />
            <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }} />
            <Legend />
            <Line type="monotone" dataKey="running" stroke="#22c55e" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="errored" stroke="#ef4444" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-4">
        <h3 className="text-sm font-semibold text-athena-400 mb-3">System Info</h3>
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div className="bg-athena-900 p-3 rounded"><p className="text-athena-600 text-xs">Status</p><p className="text-white text-lg">{String(health?.['status'] || '...')}</p></div>
          <div className="bg-athena-900 p-3 rounded"><p className="text-athena-600 text-xs">Version</p><p className="text-white text-lg">{String(health?.['version'] || '...')}</p></div>
          <div className="bg-athena-900 p-3 rounded"><p className="text-athena-600 text-xs">Memory</p><p className="text-white text-lg">{String((health?.['memory'] as Record<string, number>)?.['heapUsedMB'] || 0)} MB</p></div>
        </div>
      </div>
    </div>
  )
}
