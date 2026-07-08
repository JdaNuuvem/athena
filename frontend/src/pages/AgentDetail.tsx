import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useApi } from '../hooks/useAuth'

type Agent = { id: string; name: string; role: string; status: string; context: string; taskCount: number; startedAt: string; capabilities: Array<{ name: string; description: string }>; config: Record<string, unknown> }
type Memory = { shortTerm: unknown[]; episodic: Array<{ type: string; data: Record<string, unknown>; timestamp: string }> }

export default function AgentDetail() {
  const { id } = useParams()
  const api = useApi()
  const [agent, setAgent] = useState<Agent | null>(null)
  const [mem, setMem] = useState<Memory | null>(null)

  useEffect(() => { api<Agent>(`/api/agents/${id}`).then(d => d && setAgent(d)); api<Memory>(`/api/agents/${id}/memory`).then(d => d && setMem(d)) }, [id, api])

  if (!agent) return <div className="text-athena-600">Loading...</div>

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-xl font-bold text-white">{agent.name}</h2>
        <p className="text-athena-600 text-sm">{agent.id} · {agent.context}</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4"><p className="text-athena-600 text-xs">Status</p><p className="text-lg font-bold text-athena-success">{agent.status}</p></div>
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4"><p className="text-athena-600 text-xs">Tasks</p><p className="text-lg font-bold text-white">{agent.taskCount}</p></div>
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4"><p className="text-athena-600 text-xs">Started</p><p className="text-lg font-bold text-white">{agent.startedAt ? new Date(agent.startedAt).toLocaleString() : 'N/A'}</p></div>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-4">
        <h3 className="text-sm font-semibold text-athena-400 mb-3">Capabilities</h3>
        <div className="space-y-1">
          {agent.capabilities.map((c, i) => <div key={i} className="flex gap-3 text-sm py-1"><span className="text-athena-accent font-mono">{c.name}</span><span className="text-athena-600">{c.description}</span></div>)}
        </div>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-4">
        <h3 className="text-sm font-semibold text-athena-400 mb-3">LLM Config</h3>
        <div className="grid grid-cols-4 gap-2 text-sm">
          {Object.entries(agent.config || {}).map(([k, v]) => <div key={k} className="bg-athena-900 p-2 rounded"><p className="text-athena-600 text-xs">{k}</p><p className="text-athena-200">{String(v)}</p></div>)}
        </div>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-4">
        <h3 className="text-sm font-semibold text-athena-400 mb-3">Episodic Memory (last 20)</h3>
        <div className="space-y-1 max-h-64 overflow-auto">
          {mem?.episodic.map((e, i) => <div key={i} className="flex gap-3 text-xs py-1.5 border-b border-athena-700/50"><span className="text-athena-600">{new Date(e.timestamp).toLocaleTimeString()}</span><span className="text-athena-accent">{e.type}</span><span className="text-athena-400 truncate">{JSON.stringify(e.data).slice(0, 100)}</span></div>)}
          {(!mem || mem.episodic.length === 0) && <p className="text-athena-600 text-sm">No events recorded</p>}
        </div>
      </div>
    </div>
  )
}
