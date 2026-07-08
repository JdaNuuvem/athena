import { useState, useEffect, useMemo } from 'react'
import { useApi, useWebSocket } from '../hooks/useAuth'

interface Health {
  status: string
  agents: { total: number; running: number; errored: number; idle: number }
  infrastructure: Record<string, { connected: boolean; status: string; latency?: number }>
  uptime: number
  version: string
  memory: { heapUsedMB: number; heapTotalMB: number; rssMB: number }
}

type Agent = {
  id: string
  name: string
  role: string
  status: string
  context: string
  taskCount: number
  lastActivity?: string
}

interface MetricCardProps {
  label: string
  value: string | number
  sub: string
  color: 'accent' | 'success' | 'error' | 'warning'
  trend?: { value: number; positive: boolean }
  icon?: string
}

function MetricCard({ label, value, sub, color, trend, icon }: MetricCardProps) {
  const colors = {
    accent: 'text-athena-accent',
    success: 'text-athena-success',
    error: 'text-athena-error',
    warning: 'text-athena-warn'
  }

  return (
    <div className="bg-athena-800 rounded-lg border border-athena-700 p-5 hover:border-athena-600 transition-all">
      <div className="flex items-start justify-between mb-2">
        <p className="text-athena-600 text-xs uppercase tracking-wide font-medium">{label}</p>
        {icon && <span className="text-athena-accent text-lg">{icon}</span>}
      </div>
      <p className={`text-3xl font-bold ${colors[color]}`}>{value}</p>
      <div className="flex items-center justify-between mt-2">
        <p className="text-athena-600 text-xs">{sub}</p>
        {trend && (
          <span className={`text-xs font-medium ${trend.positive ? 'text-athena-success' : 'text-athena-error'}`}>
            {trend.positive ? '↑' : '↓'} {Math.abs(trend.value)}%
          </span>
        )}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const api = useApi()
  const events = useWebSocket()
  const [health, setHealth] = useState<Health | null>(null)
  const [agents, setAgents] = useState<Agent[]>([])
  const [recentActivity, setRecentActivity] = useState<Array<{ id: string; type: string; message: string; timestamp: string }>>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [healthData, agentsData] = await Promise.all([
          api<Health>('/api/health'),
          api<{ agents: Agent[] }>('/api/agents')
        ])
        if (healthData) setHealth(healthData)
        if (agentsData) setAgents(agentsData.agents || [])
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [api])

  useEffect(() => {
    if (events.length > 0) {
      const newActivity = events.slice(0, 5).map(e => ({
        id: e.id || crypto.randomUUID(),
        type: e.type,
        message: JSON.stringify(e.payload).slice(0, 100),
        timestamp: new Date(e.timestamp).toLocaleTimeString('pt-BR')
      }))
      setRecentActivity(newActivity)
    }
  }, [events])

  const roles = useMemo(() => {
    return agents.reduce((acc, agent) => {
      acc[agent.role] = (acc[agent.role] || 0) + 1
      return acc
    }, {} as Record<string, number>)
  }, [agents])

  const statusCounts = useMemo(() => {
    return agents.reduce((acc, agent) => {
      acc[agent.status] = (acc[agent.status] || 0) + 1
      return acc
    }, {} as Record<string, number>)
  }, [agents])

  const infrastructureHealth = useMemo(() => {
    if (!health?.infrastructure) return { healthy: 0, total: 0, status: 'unknown' }
    const infra = Object.values(health.infrastructure)
    const healthy = infra.filter(i => i.connected).length
    const status = healthy === infra.length ? 'healthy' : healthy > infra.length / 2 ? 'degraded' : 'critical'
    return { healthy, total: infra.length, status }
  }, [health])

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    if (days > 0) return `${days}d ${hours}h`
    if (hours > 0) return `${hours}h ${minutes}m`
    return `${minutes}m`
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'running': return 'bg-athena-success'
      case 'error': return 'bg-athena-error'
      case 'idle': return 'bg-athena-warn'
      default: return 'bg-gray-500'
    }
  }

  const getInfraStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'text-athena-success'
      case 'degraded': return 'text-athena-warn'
      case 'critical': return 'text-athena-error'
      default: return 'text-gray-500'
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-athena-accent"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">Dashboard Athena OS</h1>
          <p className="text-athena-600 text-sm">Visão geral do sistema em tempo real</p>
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${getInfraStatusColor(infrastructureHealth.status)} bg-athena-800 border border-athena-700`}>
            <span className={`w-2 h-2 rounded-full ${getStatusColor(infrastructureHealth.status === 'healthy' ? 'running' : infrastructureHealth.status === 'degraded' ? 'idle' : 'error')}`}></span>
            <span className="capitalize">{infrastructureHealth.status}</span>
          </div>
          <div className="text-right">
            <p className="text-athena-600 text-xs">Uptime</p>
            <p className="text-white text-sm font-medium">{formatUptime(health?.uptime || 0)}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Total de Agents"
          value={agents.length}
          sub={`${statusCounts.running || 0} rodando · ${statusCounts.errored || 0} erro`}
          color="accent"
          icon="⚡"
        />
        <MetricCard
          label="Agents Ativos"
          value={statusCounts.running || 0}
          sub={`${statusCounts.idle || 0} ociosos`}
          color="success"
          icon="🟢"
        />
        <MetricCard
          label="Infraestrutura"
          value={`${infrastructureHealth.healthy}/${infrastructureHealth.total}`}
          sub="serviços conectados"
          color={infrastructureHealth.status === 'healthy' ? 'success' : infrastructureHealth.status === 'degraded' ? 'warning' : 'error'}
          icon="🔧"
        />
        <MetricCard
          label="Memória"
          value={`${health?.memory.heapUsedMB || 0} MB`}
          sub={`Total: ${health?.memory.heapTotalMB || 0} MB`}
          color="accent"
          icon="💾"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <span>🤖</span> Agents Recentes
              </h3>
              <Link to="/agents" className="text-athena-accent text-sm hover:underline">
                Ver todos →
              </Link>
            </div>
            <div className="space-y-2">
              {agents.slice(0, 6).map(agent => (
                <div key={agent.id} className="flex items-center justify-between p-3 bg-athena-900/50 rounded-lg hover:bg-athena-900 transition">
                  <div className="flex items-center gap-3">
                    <span className={`w-2 h-2 rounded-full ${getStatusColor(agent.status)}`}></span>
                    <div>
                      <p className="text-white font-medium text-sm">{agent.name}</p>
                      <p className="text-athena-600 text-xs font-mono">{agent.id}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="text-athena-400 text-xs">{agent.role}</p>
                      <p className="text-athena-600 text-xs">{agent.taskCount} tarefas</p>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      agent.status === 'running' ? 'bg-athena-success/20 text-athena-success' :
                      agent.status === 'error' ? 'bg-athena-error/20 text-athena-error' :
                      'bg-athena-warn/20 text-athena-warn'
                    }`}>
                      {agent.status}
                    </span>
                  </div>
                </div>
              ))}
              {agents.length === 0 && (
                <div className="text-center py-8 text-athena-600">
                  Nenhum agent ativo no momento
                </div>
              )}
            </div>
          </div>

          <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <span>📊</span> Distribuição por Role
              </h3>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {Object.entries(roles).map(([role, count]) => (
                <div key={role} className="bg-athena-900/50 p-4 rounded-lg">
                  <p className="text-athena-400 text-xs mb-1">{role}</p>
                  <p className="text-2xl font-bold text-white">{count}</p>
                  <div className="w-full bg-athena-700 rounded-full h-1.5 mt-2">
                    <div
                      className="bg-athena-accent h-1.5 rounded-full transition-all"
                      style={{ width: `${(count / agents.length) * 100}%` }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>⚡</span> Eventos ao Vivo
            </h3>
            <div className="space-y-2 max-h-96 overflow-auto">
              {recentActivity.length > 0 ? (
                recentActivity.map((event, index) => (
                  <div key={event.id} className="p-3 bg-athena-900/50 rounded-lg border-l-2 border-athena-accent">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-athena-accent text-xs font-mono">{event.type}</span>
                      <span className="text-athena-600 text-xs">{event.timestamp}</span>
                    </div>
                    <p className="text-athena-300 text-xs truncate">{event.message}</p>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-athena-600">
                  Aguardando eventos...
                </div>
              )}
            </div>
          </div>

          <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>🔌</span> Status da Infraestrutura
            </h3>
            <div className="space-y-3">
              {Object.entries(health?.infrastructure || {}).map(([name, status]) => (
                <div key={name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${status.connected ? 'bg-athena-success' : 'bg-athena-error'}`}></span>
                    <span className="text-athena-300 text-sm capitalize">{name}</span>
                  </div>
                  <div className="text-right">
                    <span className={`text-xs ${status.connected ? 'text-athena-success' : 'text-athena-error'}`}>
                      {status.connected ? 'Conectado' : 'Desconectado'}
                    </span>
                    {status.latency && (
                      <span className="text-athena-600 text-xs ml-2">
                        {status.latency}ms
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span>⚙️</span> Ações Rápidas
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Link
            to="/business"
            className="flex items-center gap-3 p-4 bg-athena-900/50 rounded-lg hover:bg-athena-900 transition group"
          >
            <span className="text-2xl group-hover:scale-110 transition">🛒</span>
            <div>
              <p className="text-white font-medium text-sm">Novo Pedido</p>
              <p className="text-athena-600 text-xs">Criar ordem</p>
            </div>
          </Link>
          <Link
            to="/workflows"
            className="flex items-center gap-3 p-4 bg-athena-900/50 rounded-lg hover:bg-athena-900 transition group"
          >
            <span className="text-2xl group-hover:scale-110 transition">🔄</span>
            <div>
              <p className="text-white font-medium text-sm">Workflows</p>
              <p className="text-athena-600 text-xs">Gerenciar fluxos</p>
            </div>
          </Link>
          <Link
            to="/shopee"
            className="flex items-center gap-3 p-4 bg-athena-900/50 rounded-lg hover:bg-athena-900 transition group"
          >
            <span className="text-2xl group-hover:scale-110 transition">🛒</span>
            <div>
              <p className="text-white font-medium text-sm">Shopee</p>
              <p className="text-athena-600 text-xs">Sincronizar</p>
            </div>
          </Link>
          <Link
            to="/metrics"
            className="flex items-center gap-3 p-4 bg-athena-900/50 rounded-lg hover:bg-athena-900 transition group"
          >
            <span className="text-2xl group-hover:scale-110 transition">📈</span>
            <div>
              <p className="text-white font-medium text-sm">Métricas</p>
              <p className="text-athena-600 text-xs">Monitorar</p>
            </div>
          </Link>
        </div>
      </div>
    </div>
  )
}