import { useState, useEffect } from 'react'
import { useApi } from '../hooks/useAuth'

interface HermesAgent {
  id: number
  agente_id: string
  nome: string
  descricao: string
  categoria: string
  modelo: string
  provider: string
  status: string
  intervalo_minutos: number
  ultima_execucao: string
  proxima_execucao: string
  estatisticas: Record<string, unknown>
}

interface HermesOpportunity {
  id: number
  nome: string
  marketplace_origem: string
  url: string
  data_descoberta: string
  preco_medio: number
  volume_vendas_estimado: number
  concorrentes_diretos: number
  nivel_concorrencia: string
  fabricavel: boolean
  complexidade_molde: number
  custo_molde_estimado: number
  custo_producao_unitario: number
  margem_estimada_pct: number
  tempo_lancamento_dias: number
  tendencia: string
  score_final: number
  status: string
  tags: string[]
  created_at: string
  updated_at: string
}

interface HermesAlert {
  id: number
  agente_origem: string
  tipo: string
  sku: string
  marketplace: string
  mensagem: string
  gravidade: string
  resolvido: boolean
  data_ocorrencia: string
  data_resolucao: string
  acao_tomada: string
  created_at: string
  updated_at: string
}

interface HermesExecution {
  id: number
  agente_id: string
  action: string
  params: Record<string, unknown>
  status: string
  resultado: Record<string, unknown> | null
  erro: string | null
  inicio_execucao: string
  fim_execucao: string
  duracao_segundos: number
  created_at: string
}

export default function HermesIntegration() {
  const api = useApi()
  const [agents, setAgents] = useState<HermesAgent[]>([])
  const [opportunities, setOpportunities] = useState<HermesOpportunity[]>([])
  const [alerts, setAlerts] = useState<HermesAlert[]>([])
  const [executions, setExecutions] = useState<HermesExecution[]>([])
  const [loading, setLoading] = useState(false)
  const [syncResult, setSyncResult] = useState<{ synced: number; errors: string[] } | null>(null)
  const [executing, setExecuting] = useState<string | null>(null)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 60000) // Atualizar a cada minuto
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const [agentsData, oppsData, alertsData, execsData] = await Promise.all([
        api<HermesAgent[]>('/api/hermes/agents'),
        api<HermesOpportunity[]>('/api/hermes/opportunities'),
        api<HermesAlert[]>('/api/hermes/alerts'),
        api<HermesExecution[]>('/api/hermes/executions')
      ])
      
      if (agentsData) setAgents(agentsData)
      if (oppsData) setOpportunities(oppsData)
      if (alertsData) setAlerts(alertsData)
      if (execsData) setExecutions(execsData)
    } catch (e) {
      console.error('Failed to load Hermes data:', e)
    } finally {
      setLoading(false)
    }
  }

  const executeAgent = async (agentId: string, action: string, params: Record<string, unknown> = {}) => {
    setExecuting(agentId)
    setSyncResult(null)
    try {
      const result = await api<{ success: boolean; data?: unknown; error?: string }>('/api/hermes/execute', {
        method: 'POST',
        body: JSON.stringify({ agent_id: agentId, action, params })
      })
      
      if (result?.success) {
        await loadData()
        setSyncResult({
          synced: 1,
          errors: result.error ? [result.error] : []
        })
      } else {
        setSyncResult({
          synced: 0,
          errors: [result?.error || 'Erro desconhecido']
        })
      }
    } catch (e) {
      setSyncResult({
        synced: 0,
        errors: [String(e)]
      })
    } finally {
      setExecuting(null)
    }
  }

  const syncAllHermesToAthena = async () => {
    setLoading(true)
    setSyncResult(null)
    try {
      const result = await api<{ synced: number; errors: string[] }>('/api/hermes/sync-all', {
        method: 'POST'
      })
      setSyncResult(result)
      await loadData()
    } catch (e) {
      setSyncResult({
        synced: 0,
        errors: [String(e)]
      })
    } finally {
      setLoading(false)
    }
  }

  const resolveAlert = async (alertId: number) => {
    try {
      await api(`/api/hermes/alerts/${alertId}/resolve`, { method: 'POST' })
      await loadData()
    } catch (e) {
      console.error('Failed to resolve alert:', e)
    }
  }

  const getAgentIcon = (categoria: string) => {
    const icons: Record<string, string> = {
      memoria: '🧠',
      cacador: '🔍',
      lucratividade: '💰',
      marketplaces: '🏪',
      planejador: '📊',
      industrial: '🏭',
      telegram: '💬',
      laboratorio: '🔬',
      lojas: '🏬',
      diretor: '🎯',
      finance: '💵'
    }
    return icons[categoria] || '🤖'
  }

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      'ativo': 'bg-green-500/20 text-green-400',
      'inativo': 'bg-gray-500/20 text-gray-400',
      'manutencao': 'bg-yellow-500/20 text-yellow-400',
      'erro': 'bg-red-500/20 text-red-400'
    }
    return colors[status] || colors['ativo']
  }

  const getExecutionStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      'em_execucao': 'bg-blue-500/20 text-blue-400',
      'sucesso': 'bg-green-500/20 text-green-400',
      'erro': 'bg-red-500/20 text-red-400',
      'timeout': 'bg-yellow-500/20 text-yellow-400'
    }
    return colors[status] || colors['em_execuacao']
  }

  const getAlertColor = (gravidade: string) => {
    const colors: Record<string, string> = {
      'info': 'bg-blue-500/20 text-blue-400',
      'alerta': 'bg-yellow-500/20 text-yellow-400',
      'critico': 'bg-red-500/20 text-red-400'
    }
    return colors[gravidade] || colors['info']
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-400'
    if (score >= 60) return 'text-athena-accent'
    if (score >= 40) return 'text-yellow-400'
    return 'text-red-400'
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-1">Integração Hermes Agents</h2>
        <p className="text-athena-600 text-sm">Sistema multi-agente inteligente para fábrica Jorge Charme e Leon</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4 text-center">
          <div className="text-3xl mb-2">🤖</div>
          <p className="text-athena-600 text-xs uppercase mb-1">Agents Ativos</p>
          <p className="text-2xl font-bold text-white">{agents.filter(a => a.status === 'ativo').length}</p>
          <p className="text-athena-600 text-xs mt-1">Total: {agents.length}</p>
        </div>
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4 text-center">
          <div className="text-3xl mb-2">🔍</div>
          <p className="text-athena-600 text-xs uppercase mb-1">Oportunidades</p>
          <p className="text-2xl font-bold text-white">{opportunities.filter(o => o.status === 'analisar').length}</p>
          <p className="text-athena-600 text-xs mt-1">Total: {opportunities.length}</p>
        </div>
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4 text-center">
          <div className="text-3xl mb-2">⚠️</div>
          <p className="text-athena-600 text-xs uppercase mb-1">Alertas</p>
          <p className="text-2xl font-bold text-white">{alerts.filter(a => !a.resolvido).length}</p>
          <p className="text-athena-600 text-xs mt-1">Total: {alerts.length}</p>
        </div>
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4 text-center">
          <div className="text-3xl mb-2">⚡</div>
          <p className="text-athena-600 text-xs uppercase mb-1">Execuções</p>
          <p className="text-2xl font-bold text-white">{executions.length}</p>
          <p className="text-athena-600 text-xs mt-1">Hoje</p>
        </div>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <span>🤖</span> Agents Hermes
          </h3>
          <button
            onClick={syncAllHermesToAthena}
            disabled={loading}
            className="bg-athena-accent hover:bg-athena-accent/80 text-white font-medium rounded-lg px-4 py-2 transition disabled:opacity-50 text-sm"
          >
            {loading ? 'Sincronizando...' : 'Sincronizar Todos com Athena'}
          </button>
        </div>

        <div className="space-y-3">
          {agents.length === 0 ? (
            <div className="text-center py-8 text-athena-600">
              Nenhum agente registrado. Use os comandos Python Hermes.
            </div>
          ) : (
            agents.map(agent => (
              <div key={agent.id} className="flex items-center justify-between p-4 bg-athena-900/50 rounded-lg hover:bg-athena-900 transition">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{getAgentIcon(agent.categoria)}</span>
                  <div>
                    <p className="text-white font-medium">{agent.nome}</p>
                    <p className="text-athena-600 text-xs">{agent.agente_id}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-1 rounded text-xs ${getStatusColor(agent.status)}`}>
                    {agent.status}
                  </span>
                  <span className="text-athena-600 text-xs">
                    {agent.intervalo_minutos}min
                  </span>
                </div>
                <div className="flex gap-2">
                  {agent.categoria === 'cacador' && (
                    <button
                      onClick={() => executeAgent(agent.agente_id, 'executar_cacada')}
                      disabled={executing === agent.agente_id}
                      className="bg-athena-accent hover:bg-athena-accent/80 text-white text-sm font-medium px-3 py-1.5 rounded transition disabled:opacity-50"
                    >
                      {executing === agent.agente_id ? 'Executando...' : '🔍 Caçar'}
                    </button>
                  )}
                  {agent.categoria === 'lucratividade' && (
                    <button
                      onClick={() => executeAgent(agent.agente_id, 'verificar_alertas')}
                      disabled={executing === agent.agente_id}
                      className="bg-athena-accent hover:bg-athena-accent/80 text-white text-sm font-medium px-3 py-1.5 rounded transition disabled:opacity-50"
                    >
                      {executing === agent.agente_id ? 'Executando...' : '💰 Lucro'}
                    </button>
                  )}
                  {agent.categoria === 'memoria' && (
                    <button
                      onClick={() => executeAgent(agent.agente_id, 'stats')}
                      disabled={executing === agent.agente_id}
                      className="bg-athena-accent hover:bg-athena-accent/80 text-white text-sm font-medium px-3 py-1.5 rounded transition disabled:opacity-50"
                    >
                      {executing === agent.agente_id ? 'Executando...' : '📚 Memória'}
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-athena-800 rounded-lg border border-athena-700">
          <div className="border-b border-athena-700">
            <nav className="flex">
              <button className="flex items-center gap-2 px-4 py-3 text-sm font-medium bg-athena-700 text-white border-b-2 border-athena-accent">
                <span>🔍</span>
                <span>Oportunidades</span>
                <span className="bg-athena-700 text-xs px-2 py-0.5 rounded-full">{opportunities.length}</span>
              </button>
            </nav>
          </div>

          <div className="p-4">
            {syncResult && (
              <div className={`p-3 rounded-lg mb-4 ${syncResult.errors.length === 0 ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                ✓ Sincronizados: {syncResult.synced} itens
                {syncResult.errors.length > 0 && (
                  <div className="mt-2 text-xs">
                    Erros: {syncResult.errors.join(', ')}
                  </div>
                )}
              </div>
            )}

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-athena-700">
                    <th className="text-left py-2 px-3 text-athena-400 font-medium">Produto</th>
                    <th className="text-left py-2 px-3 text-athena-400 font-medium">Score</th>
                    <th className="text-left py-2 px-3 text-athena-400 font-medium">Margem</th>
                    <th className="text-left py-2 px-3 text-athena-400 font-medium">Fabricável</th>
                    <th className="text-left py-2 px-3 text-athena-400 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {opportunities.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="text-center py-8 text-athena-600">
                        Nenhuma oportunidade encontrada. Execute o AG-01 Caçador.
                      </td>
                    </tr>
                  ) : (
                    opportunities.slice(0, 10).map(op => (
                      <tr key={op.id} className="border-b border-athena-700/50">
                        <td className="py-2 px-3 text-white">{op.nome}</td>
                        <td className={`py-2 px-3 font-medium ${getScoreColor(op.score_final)}`}>
                          {op.score_final}/100
                        </td>
                        <td className="py-2 px-3 text-white">{op.margem_estimada_pct}%</td>
                        <td className="py-2 px-3">
                          <span className={`px-2 py-1 rounded text-xs ${op.fabricavel ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                            {op.fabricavel ? '✓' : '✗'}
                          </span>
                        </td>
                        <td className="py-2 px-3">
                          <span className={`px-2 py-1 rounded text-xs ${
                            op.status === 'analisar' ? 'bg-athena-warn/20 text-athena-warn' :
                            op.status === 'aprovado' ? 'bg-green-500/20 text-green-400' :
                            op.status === 'sincronizado_athena' ? 'bg-athena-accent/20 text-athena-accent' :
                            'bg-gray-500/20 text-gray-400'
                          }`}>
                            {op.status}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="bg-athena-800 rounded-lg border border-athena-700">
          <div className="border-b border-athena-700">
            <nav className="flex">
              <button className="flex items-center gap-2 px-4 py-3 text-sm font-medium bg-athena-700 text-white border-b-2 border-athena-accent">
                <span>⚠️</span>
                <span>Alertas</span>
                <span className="bg-athena-700 text-xs px-2 py-0.5 rounded-full">{alerts.filter(a => !a.resolvido).length}</span>
              </button>
            </nav>
          </div>

          <div className="p-4">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-athena-700">
                    <th className="text-left py-2 px-3 text-athena-400 font-medium">Agente</th>
                    <th className="text-left py-2 px-3 text-athena-400 font-medium">Tipo</th>
                    <th className="text-left py-2 px-3 text-athena-400 font-medium">SKU</th>
                    <th className="text-left py-2 px-3 text-athena-400 font-medium">Mensagem</th>
                    <th className="text-left py-2 px-3 text-athena-400 font-medium">Gravidade</th>
                    <th className="text-left py-2 px-3 text-athena-400 font-medium">Ação</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="text-center py-8 text-athena-600">
                        Nenhum alerta. Sistema funcionando normalmente.
                      </td>
                    </tr>
                  ) : (
                    alerts.slice(0, 10).map(alert => (
                      <tr key={alert.id} className="border-b border-athena-700/50">
                        <td className="py-2 px-3 text-athena-300 text-xs">{alert.agente_origem}</td>
                        <td className="py-2 px-3 text-white text-sm">{alert.tipo}</td>
                        <td className="py-2 px-3 text-athena-accent font-mono text-xs">{alert.sku || '-'}</td>
                        <td className="py-2 px-3 text-white">{alert.mensagem}</td>
                        <td className="py-2 px-3">
                          <span className={`px-2 py-1 rounded text-xs ${getAlertColor(alert.gravidade)}`}>
                            {alert.gravidade}
                          </span>
                        </td>
                        <td className="py-2 px-3">
                          {alert.resolvido ? (
                            <span className="text-green-400 text-xs">✓ Resolvido</span>
                          ) : (
                            <button
                              onClick={() => resolveAlert(alert.id)}
                              className="text-athena-accent text-sm hover:underline"
                            >
                              Resolver
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span>⚡</span> Execuções Recentes
        </h3>

        <div className="space-y-2">
          {executions.length === 0 ? (
            <div className="text-center py-8 text-athena-600">
              Nenhuma execução registrada hoje.
            </div>
          ) : (
            executions.slice(0, 10).map(exec => (
              <div key={exec.id} className="flex items-center justify-between p-3 bg-athena-900/50 rounded-lg border-l-2 border-athena-700">
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-1 rounded text-xs ${getExecutionStatusColor(exec.status)}`}>
                    {exec.status}
                  </span>
                  <div>
                    <p className="text-white text-sm">{exec.agente_id}</p>
                    <p className="text-athena-600 text-xs">{exec.action}</p>
                  </div>
                </div>
                <div className="text-right">
                  {exec.duracao_segundos && (
                    <p className="text-athena-300 text-xs">{exec.duracao_segundos}s</p>
                  )}
                  {exec.status === 'erro' && exec.erro && (
                    <p className="text-athena-error text-xs">{exec.erro.slice(0, 50)}...</p>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span>📖</span> Documentação e Suporte
        </h3>

        <div className="space-y-2 text-sm">
          <a
            href="/docs/hermes-agents-tutorial.md"
            target="_blank"
            rel="noopener noreferrer"
            className="block text-athena-accent hover:text-athena-accent/80 underline"
          >
            📚 Tutorial completo Hermes Agents
          </a>
          <a
            href="https://github.com/anthropics/anthropic"
            target="_blank"
            rel="noopener noreferrer"
            className="block text-athena-accent hover:text-athena-accent/80 underline"
          >
            🐍 Documentação Claude
          </a>
          <a
            href="https://docs.hermes-agents.com"
            target="_blank"
            rel="noopener noreferrer"
            className="block text-athena-accent hover:text-athena-accent/80 underline"
          >
            📋 Documentação Hermes
          </a>
        </div>
      </div>
    </div>
  )
}