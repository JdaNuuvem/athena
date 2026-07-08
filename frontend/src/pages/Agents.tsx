import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../hooks/useAuth'

type Agent = {
  id: string
  name: string
  role: string
  status: 'running' | 'idle' | 'error' | 'stopped'
  context: string
  taskCount: number
  lastActivity?: string
  uptime?: number
  errorRate?: number
}

type AgentStats = {
  total: number
  running: number
  idle: number
  error: number
  stopped: number
}

export default function Agents() {
  const api = useApi()
  const [agents, setAgents] = useState<Agent[]>([])
  const [filter, setFilter] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sortBy, setSortBy] = useState<'name' | 'status' | 'tasks' | 'uptime'>('name')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const data = await api<{ agents: Agent[] }>('/api/agents')
        if (data) {
          setAgents(data.agents || [])
        }
      } catch (error) {
        console.error('Failed to fetch agents:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchAgents()
    const interval = setInterval(fetchAgents, 15000)
    return () => clearInterval(interval)
  }, [api])

  const roles = useMemo(() => [...new Set(agents.map(a => a.role))], [agents])
  const statuses = useMemo(() => [...new Set(agents.map(a => a.status))], [agents])

  const filteredAndSortedAgents = useMemo(() => {
    let result = agents.filter(agent => {
      const matchesFilter = !filter || 
        agent.name.toLowerCase().includes(filter.toLowerCase()) ||
        agent.id.toLowerCase().includes(filter.toLowerCase())
      
      const matchesRole = !roleFilter || agent.role === roleFilter
      const matchesStatus = !statusFilter || agent.status === statusFilter

      return matchesFilter && matchesRole && matchesStatus
    })

    result.sort((a, b) => {
      let comparison = 0
      switch (sortBy) {
        case 'name':
          comparison = a.name.localeCompare(b.name)
          break
        case 'status':
          comparison = a.status.localeCompare(b.status)
          break
        case 'tasks':
          comparison = a.taskCount - b.taskCount
          break
        case 'uptime':
          comparison = (a.uptime || 0) - (b.uptime || 0)
          break
      }
      return sortOrder === 'asc' ? comparison : -comparison
    })

    return result
  }, [agents, filter, roleFilter, statusFilter, sortBy, sortOrder])

  const stats = useMemo((): AgentStats => {
    return agents.reduce((acc, agent) => {
      acc[agent.status] = (acc[agent.status] || 0) + 1
      acc.total++
      return acc
    }, { total: 0, running: 0, idle: 0, error: 0, stopped: 0 })
  }, [agents])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'bg-athena-success/20 text-athena-success border-athena-success/30'
      case 'idle': return 'bg-athena-warn/20 text-athena-warn border-athena-warn/30'
      case 'error': return 'bg-athena-error/20 text-athena-error border-athena-error/30'
      case 'stopped': return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running': return '🟢'
      case 'idle': return '🟡'
      case 'error': return '🔴'
      case 'stopped': return '⚫'
      default: return '⚪'
    }
  }

  const formatUptime = (seconds?: number) => {
    if (!seconds) return '-'
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    if (hours > 0) return `${hours}h ${minutes}m`
    return `${minutes}m`
  }

  const handleSort = (field: 'name' | 'status' | 'tasks' | 'uptime') => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortOrder('asc')
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
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">Gerenciamento de Agents</h1>
          <p className="text-athena-600 text-sm">Monitorar e gerenciar todos os agentes do sistema</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="bg-athena-accent hover:bg-athena-accent/80 text-white font-medium px-4 py-2 rounded-lg transition text-sm">
            + Novo Agent
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-athena-600 text-sm uppercase tracking-wide">Total</span>
            <span className="text-2xl">🤖</span>
          </div>
          <p className="text-3xl font-bold text-white">{stats.total}</p>
          <p className="text-athena-600 text-xs mt-1">Agents registrados</p>
        </div>
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-athena-600 text-sm uppercase tracking-wide">Ativos</span>
            <span className="text-2xl">🟢</span>
          </div>
          <p className="text-3xl font-bold text-athena-success">{stats.running}</p>
          <p className="text-athena-600 text-xs mt-1">{((stats.running / stats.total) * 100).toFixed(0)}% do total</p>
        </div>
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-athena-600 text-sm uppercase tracking-wide">Ociosos</span>
            <span className="text-2xl">🟡</span>
          </div>
          <p className="text-3xl font-bold text-athena-warn">{stats.idle}</p>
          <p className="text-athena-600 text-xs mt-1">Aguardando tarefas</p>
        </div>
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-athena-600 text-sm uppercase tracking-wide">Erros</span>
            <span className="text-2xl">🔴</span>
          </div>
          <p className="text-3xl font-bold text-athena-error">{stats.error}</p>
          <p className="text-athena-600 text-xs mt-1">Requer atenção</p>
        </div>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
        <div className="flex flex-col lg:flex-row gap-4 mb-6">
          <div className="flex-1">
            <input
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Buscar por nome ou ID..."
              className="w-full bg-athena-900 border border-athena-700 rounded-lg px-4 py-2.5 text-sm text-athena-200 focus:border-athena-accent focus:outline-none"
            />
          </div>
          <div className="flex gap-3">
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="bg-athena-900 border border-athena-700 rounded-lg px-4 py-2.5 text-sm text-athena-200 focus:border-athena-accent focus:outline-none"
            >
              <option value="">Todos os Roles</option>
              {roles.map(role => (
                <option key={role} value={role}>{role}</option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-athena-900 border border-athena-700 rounded-lg px-4 py-2.5 text-sm text-athena-200 focus:border-athena-accent focus:outline-none"
            >
              <option value="">Todos os Status</option>
              {statuses.map(status => (
                <option key={status} value={status}>{status}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-athena-700">
                <th className="text-left py-3 px-4 text-athena-400 text-sm font-medium uppercase tracking-wider cursor-pointer hover:text-white" onClick={() => handleSort('name')}>
                  Agent {sortBy === 'name' && <span>{sortOrder === 'asc' ? '↑' : '↓'}</span>}
                </th>
                <th className="text-left py-3 px-4 text-athena-400 text-sm font-medium uppercase tracking-wider">
                  ID
                </th>
                <th className="text-left py-3 px-4 text-athena-400 text-sm font-medium uppercase tracking-wider cursor-pointer hover:text-white" onClick={() => handleSort('status')}>
                  Status {sortBy === 'status' && <span>{sortOrder === 'asc' ? '↑' : '↓'}</span>}
                </th>
                <th className="text-left py-3 px-4 text-athena-400 text-sm font-medium uppercase tracking-wider">
                  Role
                </th>
                <th className="text-left py-3 px-4 text-athena-400 text-sm font-medium uppercase tracking-wider">
                  Contexto
                </th>
                <th className="text-left py-3 px-4 text-athena-400 text-sm font-medium uppercase tracking-wider cursor-pointer hover:text-white" onClick={() => handleSort('tasks')}>
                  Tarefas {sortBy === 'tasks' && <span>{sortOrder === 'asc' ? '↑' : '↓'}</span>}
                </th>
                <th className="text-left py-3 px-4 text-athena-400 text-sm font-medium uppercase tracking-wider cursor-pointer hover:text-white" onClick={() => handleSort('uptime')}>
                  Uptime {sortBy === 'uptime' && <span>{sortOrder === 'asc' ? '↑' : '↓'}</span>}
                </th>
                <th className="text-left py-3 px-4 text-athena-400 text-sm font-medium uppercase tracking-wider">
                  Ações
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredAndSortedAgents.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-athena-600">
                    <div className="flex flex-col items-center gap-2">
                      <span className="text-4xl">🔍</span>
                      <p>Nenhum agent encontrado com os filtros atuais</p>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredAndSortedAgents.map(agent => (
                  <tr key={agent.id} className="border-b border-athena-700/50 hover:bg-athena-900/30 transition">
                    <td className="py-4 px-4">
                      <div className="flex items-center gap-3">
                        <span className="text-xl">{getStatusIcon(agent.status)}</span>
                        <div>
                          <p className="text-white font-medium">{agent.name}</p>
                          {agent.lastActivity && (
                            <p className="text-athena-600 text-xs">
                              Última atividade: {new Date(agent.lastActivity).toLocaleString('pt-BR')}
                            </p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="py-4 px-4">
                      <span className="text-athena-accent font-mono text-sm">{agent.id}</span>
                    </td>
                    <td className="py-4 px-4">
                      <span className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(agent.status)}`}>
                        {agent.status}
                      </span>
                    </td>
                    <td className="py-4 px-4">
                      <span className="text-athena-300 text-sm">{agent.role}</span>
                    </td>
                    <td className="py-4 px-4">
                      <span className="text-athena-300 text-sm">{agent.context}</span>
                    </td>
                    <td className="py-4 px-4">
                      <span className="text-white font-medium">{agent.taskCount}</span>
                    </td>
                    <td className="py-4 px-4">
                      <span className="text-athena-300 text-sm">{formatUptime(agent.uptime)}</span>
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex items-center gap-2">
                        <Link
                          to={`/agents/${agent.id}`}
                          className="text-athena-accent hover:text-athena-accent/80 text-sm font-medium"
                        >
                          Detalhes
                        </Link>
                        <button className="text-athena-600 hover:text-athena-400 text-sm">
                          Configurar
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {filteredAndSortedAgents.length > 0 && (
          <div className="mt-4 flex items-center justify-between text-sm text-athena-600">
            <p>
              Mostrando {filteredAndSortedAgents.length} de {agents.length} agents
            </p>
            <div className="flex gap-2">
              <button className="px-3 py-1 bg-athena-900 rounded hover:bg-athena-800 transition">
                Anterior
              </button>
              <button className="px-3 py-1 bg-athena-900 rounded hover:bg-athena-800 transition">
                Próximo
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}