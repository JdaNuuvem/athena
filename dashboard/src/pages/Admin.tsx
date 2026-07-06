import { useState, useEffect } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import { Activity, Clock, ShieldCheck, Server, Database } from 'lucide-react'

interface Agent {
  id: string
  name: string
  role: string
  status: string
  context: string
  startedAt: string | null
  taskCount: number
}

interface Health {
  status: string
  timestamp: string
  env: string
  uptime: number
}

export function Admin() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchData() {
      try {
        const [agentsRes, healthRes] = await Promise.all([
          fetch('/api/agents'),
          fetch('/api/health'),
        ])
        const agentsData = await agentsRes.json()
        const healthData = await healthRes.json()
        setAgents(agentsData.agents ?? [])
        setHealth(healthData)
      } catch {
        // API may require auth — show empty state
      } finally {
        setLoading(false)
      }
    }
    fetchData()
    const interval = setInterval(fetchData, 15000)
    return () => clearInterval(interval)
  }, [])

  const statusCounts = agents.reduce((acc: Record<string, number>, a) => {
    acc[a.status] = (acc[a.status] ?? 0) + 1
    return acc
  }, {})

  const uptimeHrs = health?.uptime ? Math.floor(health.uptime / 3600) : 0
  const uptimeMin = health?.uptime ? Math.floor((health.uptime % 3600) / 60) : 0

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-100">Admin</h2>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs uppercase tracking-wider mb-1">
            <Activity size={14} /> Agentes
          </div>
          <span className="text-2xl font-bold text-slate-100">{loading ? '—' : agents.length}</span>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs uppercase tracking-wider mb-1">
            <ShieldCheck size={14} /> Running
          </div>
          <span className="text-2xl font-bold text-emerald-400">{loading ? '—' : (statusCounts.running ?? 0)}</span>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs uppercase tracking-wider mb-1">
            <Clock size={14} /> Uptime
          </div>
          <span className="text-2xl font-bold text-slate-100">{loading ? '—' : `${uptimeHrs}h ${uptimeMin}m`}</span>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs uppercase tracking-wider mb-1">
            <Server size={14} /> Env
          </div>
          <span className="text-2xl font-bold text-sky-400">{loading ? '—' : health?.env ?? '—'}</span>
        </div>
      </div>

      <div className="flex items-center gap-2 p-3 bg-slate-800 border border-slate-700 rounded-lg">
        <Database size={16} className="text-slate-400 shrink-0" />
        <span className="text-sm text-slate-400 flex-1">Banco vazio? Clique para popular com dados de exemplo (produtos, clientes, pedidos).</span>
        <button
          onClick={async () => {
            if (!confirm('Popular banco com dados de exemplo? Isso vai criar produtos, clientes, pedidos e moldes.')) return
            try {
              const token = localStorage.getItem('athena_token')
              const resp = await fetch('/api/system/seed', { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {} })
              const data = await resp.json()
              if (resp.ok) {
                const tables = data.tables?.map((t: string) => `- ${t}: ${data.counts?.[t] ?? 'ok'}`).join('\n')
                alert(`✅ Seed concluido!\n\n${tables}\n\nRecarregue a pagina para ver os dados.`)
                window.location.reload()
              } else {
                alert(`Erro: ${data.error || resp.statusText}`)
              }
            } catch (err: any) { alert('Erro de conexao: ' + (err.message || 'servidor offline')) }
          }}
          className="text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-3 py-1.5 rounded hover:bg-emerald-500/20 transition-colors"
        >
          Rodar Seed
        </button>
      </div>

      <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
        <div className="p-3 border-b border-slate-700">
          <h3 className="text-slate-400 text-xs uppercase tracking-wider">Agentes ({agents.length})</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
                <th className="text-left p-3">ID</th>
                <th className="text-left p-3">Nome</th>
                <th className="text-left p-3">Role</th>
                <th className="text-left p-3">Status</th>
                <th className="text-left p-3">Contexto</th>
                <th className="text-right p-3">Tarefas</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} className="p-4 text-center text-slate-500">Carregando...</td></tr>
              ) : agents.length === 0 ? (
                <tr><td colSpan={6} className="p-4 text-center text-slate-500">Nenhum agente encontrado (API pode exigir autenticação)</td></tr>
              ) : (
                agents.map(a => (
                  <tr key={a.id} className="border-b border-slate-700/50">
                    <td className="p-3 font-mono text-xs text-sky-400">{a.id}</td>
                    <td className="p-3 text-slate-200">{a.name}</td>
                    <td className="p-3 text-slate-400 text-xs">{a.role}</td>
                    <td className="p-3"><StatusBadge status={a.status} /></td>
                    <td className="p-3 text-slate-400 text-xs capitalize">{a.context}</td>
                    <td className="p-3 text-right text-slate-200">{a.taskCount}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
