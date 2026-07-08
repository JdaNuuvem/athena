import { useState, useEffect } from 'react'
import { useApi } from '../hooks/useAuth'

interface AdsCampaign {
  id: number
  campaign_id: string
  shop_id: string
  name: string
  type: 'search' | 'discovery' | 'affiliate' | 'top_display'
  status: 'active' | 'paused' | 'ended'
  daily_budget: number
  start_date: string
  end_date: string
  created_at: string
}

interface AdsPerformance {
  id: number
  campaign_id: string
  date: string
  impressions: number
  clicks: number
  cost: number
  orders: number
  revenue: number
  ctr: number
  cpc: number
  conversion_rate: number
  roas: number
}

interface AdsInsight {
  id: number
  campaign_id: string
  insight_type: string
  message: string
  severity: 'info' | 'suggestion' | 'warning' | 'critical'
  confidence: number
  action_taken: boolean
  created_at: string
}

interface ABTest {
  id: number
  test_id: string
  campaign_id: string
  name: string
  variant: 'control' | 'test'
  status: 'running' | 'paused' | 'completed'
  start_date: string
  winner: string
  confidence: number
  created_at: string
}

export default function ShopeeAdsIntegration() {
  const api = useApi()
  const [campaigns, setCampaigns] = useState<AdsCampaign[]>([])
  const [performance, setPerformance] = useState<AdsPerformance[]>([])
  const [insights, setInsights] = useState<AdsInsight[]>([])
  const [abTests, setAbTests] = useState<ABTest[]>([])
  const [selectedCampaign, setSelectedCampaign] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000) // Atualizar a cada 30s
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const [campaignsData, perfData, insightsData, testsData] = await Promise.all([
        api<AdsCampaign[]>('/api/shopee-ads/campaigns'),
        api<AdsPerformance[]>('/api/shopee-ads/performance'),
        api<AdsInsight[]>('/api/shopee-ads/insights'),
        api<ABTest[]>('/api/shopee-ads/abtests')
      ])
      
      if (campaignsData) setCampaigns(campaignsData)
      if (perfData) setPerformance(perfData)
      if (insightsData) setInsights(insightsData)
      if (testsData) setAbTests(testsData)
    } catch (e) {
      console.error('Failed to load ads data:', e)
    } finally {
      setLoading(false)
    }
  }

  const createCampaign = async () => {
    setLoading(true)
    setResult(null)
    try {
      const name = prompt('Nome da campanha:')
      if (!name) return

      const budget = parseFloat(prompt('Orçamento diário (R$):') || '100')
      if (isNaN(budget) || budget < 10) {
        alert('Orçamento mínimo: R$ 10')
        return
      }

      const res = await api('/api/shopee-ads/campaigns', {
        method: 'POST',
        body: JSON.stringify({
          shopId: 'your-shop-id',
          name,
          dailyBudget: budget,
          startDate: new Date().toISOString().split('T')[0],
          keywords: [
            { keyword: 'organizador cozinha', matchType: 'phrase', bid: 1.5 },
            { keyword: 'cozinha organização', matchType: 'broad', bid: 1.0 },
            { keyword: 'potes plásticos', matchType: 'exact', bid: 2.0 }
          ]
        })
      })
      
      setResult(res)
      await loadData()
    } catch (e) {
      setResult({ error: String(e) })
    } finally {
      setLoading(false)
    }
  }

  const analyzeCampaign = async (campaignId: string) => {
    setLoading(true)
    setResult(null)
    setSelectedCampaign(campaignId)
    try {
      const res = await api(`/api/shopee-ads/campaigns/${campaignId}/analyze?days=30`)
      setResult(res)
    } catch (e) {
      setResult({ error: String(e) })
    } finally {
      setLoading(false)
    }
  }

  const autoAdjustBids = async (campaignId: string) => {
    setLoading(true)
    setResult(null)
    try {
      const targetRoas = parseFloat(prompt('ROAS alvo (padrão: 3.0):') || '3.0')
      const res = await api(`/api/shopee-ads/campaigns/${campaignId}/adjust-bids`, {
        method: 'POST',
        body: JSON.stringify({ targetRoas })
      })
      setResult(res)
      await loadData()
    } catch (e) {
      setResult({ error: String(e) })
    } finally {
      setLoading(false)
    }
  }

  const predictPerformance = async (campaignId: string) => {
    setLoading(true)
    setResult(null)
    setSelectedCampaign(campaignId)
    try {
      const res = await api(`/api/shopee-ads/campaigns/${campaignId}/predict?days=30`)
      setResult(res)
    } catch (e) {
      setResult({ error: String(e) })
    } finally {
      setLoading(false)
    }
  }

  const suggestBudget = async (campaignId: string) => {
    setLoading(true)
    setResult(null)
    setSelectedCampaign(campaignId)
    try {
      const targetRoas = parseFloat(prompt('ROAS alvo (padrão: 3.0):') || '3.0')
      const res = await api(`/api/shopee-ads/campaigns/${campaignId}/suggest-budget?targetRoas=${targetRoas}`)
      setResult(res)
    } catch (e) {
      setResult({ error: String(e) })
    } finally {
      setLoading(false)
    }
  }

  const resolveInsight = async (insightId: number) => {
    try {
      await api(`/api/shopee-ads/insights/${insightId}/resolve`, { method: 'POST' })
      await loadData()
    } catch (e) {
      console.error('Failed to resolve insight:', e)
    }
  }

  const getSeverityColor = (severity: string) => {
    const colors = {
      info: 'bg-blue-500/20 text-blue-400',
      suggestion: 'bg-athena-accent/20 text-athena-accent',
      warning: 'bg-yellow-500/20 text-yellow-400',
      critical: 'bg-red-500/20 text-red-400'
    }
    return colors[severity] || colors.info
  }

  const getStatusColor = (status: string) => {
    const colors = {
      active: 'bg-green-500/20 text-green-400',
      paused: 'bg-yellow-500/20 text-yellow-400',
      ended: 'bg-gray-500/20 text-gray-400'
    }
    return colors[status] || colors.active
  }

  const getROASColor = (roas: number) => {
    if (roas >= 4.0) return 'text-green-400'
    if (roas >= 2.5) return 'text-athena-accent'
    if (roas >= 1.5) return 'text-yellow-400'
    return 'text-red-400'
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-1">Shopee Ads Manager</h2>
        <p className="text-athena-600 text-sm">AG-ADS: Agente Inteligente de Publicidade Shopee</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4 text-center">
          <div className="text-3xl mb-2">📢</div>
          <p className="text-athena-600 text-xs uppercase mb-1">Campanhas</p>
          <p className="text-2xl font-bold text-white">{campaigns.filter(c => c.status === 'active').length}</p>
          <p className="text-athena-600 text-xs mt-1">Total: {campaigns.length}</p>
        </div>
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4 text-center">
          <div className="text-3xl mb-2">👀</div>
          <p className="text-athena-600 text-xs uppercase mb-1">Impressões Hoje</p>
          <p className="text-2xl font-bold text-white">{performance.filter(p => p.date === new Date().toISOString().split('T')[0]).reduce((sum, p) => sum + p.impressions, 0).toLocaleString()}</p>
        </div>
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4 text-center">
          <div className="text-3xl mb-2">🔗</div>
          <p className="text-athena-600 text-xs uppercase mb-1">Cliques Hoje</p>
          <p className="text-2xl font-bold text-white">{performance.filter(p => p.date === new Date().toISOString().split('T')[0]).reduce((sum, p) => sum + p.clicks, 0).toLocaleString()}</p>
        </div>
        <div className="bg-athena-800 rounded-lg border border-athena-700 p-4 text-center">
          <div className="text-3xl mb-2">💰</div>
          <p className="text-athena-600 text-xs uppercase mb-1">ROAS Médio</p>
          <p className={`text-2xl font-bold ${getROASColor(performance.length > 0 ? performance.reduce((sum, p) => sum + p.roas, 0) / performance.length : 0)}`}>
            {performance.length > 0 ? (performance.reduce((sum, p) => sum + p.roas, 0) / performance.length).toFixed(2) : '0.00'}
          </p>
        </div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={createCampaign}
          disabled={loading}
          className="bg-athena-accent hover:bg-athena-accent/80 text-white font-medium rounded-lg px-4 py-2 transition disabled:opacity-50 text-sm"
        >
          + Nova Campanha
        </button>
        <button
          onClick={() => loadData()}
          disabled={loading}
          className="bg-athena-800 hover:bg-athena-700 text-white font-medium rounded-lg px-4 py-2 border border-athena-700 transition disabled:opacity-50 text-sm"
        >
          🔄 Atualizar
        </button>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Campanhas Ads</h3>

        <div className="space-y-3">
          {campaigns.length === 0 ? (
            <div className="text-center py-8 text-athena-600">
              Nenhuma campanha criada. Clique em "+ Nova Campanha" para começar.
            </div>
          ) : (
            campaigns.map(campaign => (
              <div key={campaign.id} className="flex items-center justify-between p-4 bg-athena-900/50 rounded-lg hover:bg-athena-900 transition">
                <div>
                  <p className="text-white font-medium">{campaign.name}</p>
                  <p className="text-athena-600 text-sm">{campaign.type} • R$ {campaign.daily_budget}/dia</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-1 rounded text-xs ${getStatusColor(campaign.status)}`}>
                    {campaign.status}
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => analyzeCampaign(campaign.campaign_id)}
                      disabled={loading}
                      className="bg-athena-700 hover:bg-athena-600 text-white text-sm font-medium px-3 py-1.5 rounded transition disabled:opacity-50"
                    >
                      📊
                    </button>
                    <button
                      onClick={() => autoAdjustBids(campaign.campaign_id)}
                      disabled={loading}
                      className="bg-athena-700 hover:bg-athena-600 text-white text-sm font-medium px-3 py-1.5 rounded transition disabled:opacity-50"
                    >
                      ⚙️
                    </button>
                    <button
                      onClick={() => predictPerformance(campaign.campaign_id)}
                      disabled={loading}
                      className="bg-athena-700 hover:bg-athena-600 text-white text-sm font-medium px-3 py-1.5 rounded transition disabled:opacity-50"
                    >
                      🔮
                    </button>
                    <button
                      onClick={() => suggestBudget(campaign.campaign_id)}
                      disabled={loading}
                      className="bg-athena-700 hover:bg-athena-600 text-white text-sm font-medium px-3 py-1.5 rounded transition disabled:opacity-50"
                    >
                      💰
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {result && (
        <div className={`p-4 rounded-lg ${result.error ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}`}>
          <p className="font-medium mb-2">{result.error ? 'Erro' : 'Sucesso'}</p>
          <pre className="text-sm overflow-x-auto">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-athena-800 rounded-lg border border-athena-700">
          <div className="border-b border-athena-700">
            <nav className="flex">
              <button className="flex items-center gap-2 px-4 py-3 text-sm font-medium bg-athena-700 text-white border-b-2 border-athena-accent">
                <span>⚡</span>
                <span>Insights</span>
                <span className="bg-athena-700 text-xs px-2 py-0.5 rounded-full">{insights.filter(i => !i.action_taken).length}</span>
              </button>
            </nav>
          </div>

          <div className="p-4">
            {insights.length === 0 ? (
              <div className="text-center py-8 text-athena-600">
                Nenhum insight. Sistema funcionando perfeitamente.
              </div>
            ) : (
              <div className="space-y-2">
                {insights.slice(0, 10).map(insight => (
                  <div key={insight.id} className="p-3 bg-athena-900/50 rounded-lg border-l-2 border-athena-700">
                    <div className="flex items-center justify-between">
                      <span className={`px-2 py-1 rounded text-xs ${getSeverityColor(insight.severity)}`}>
                        {insight.insight_type}
                      </span>
                      <span className="text-athena-600 text-xs">
                        {new Date(insight.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <p className="text-white text-sm mt-2">{insight.message}</p>
                    {insight.confidence && (
                      <p className="text-athena-600 text-xs mt-1">
                        Confiança: {insight.confidence}%
                      </p>
                    )}
                    {!insight.action_taken && (
                      <button
                        onClick={() => resolveInsight(insight.id)}
                        className="text-athena-accent text-sm hover:underline mt-2"
                      >
                        Marcar como resolvido
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="bg-athena-800 rounded-lg border border-athena-700">
          <div className="border-b border-athena-700">
            <nav className="flex">
              <button className="flex items-center gap-2 px-4 py-3 text-sm font-medium bg-athena-700 text-white border-b-2 border-athena-accent">
                <span>🧪</span>
                <span>A/B Tests</span>
                <span className="bg-athena-700 text-xs px-2 py-0.5 rounded-full">{abTests.filter(t => t.status === 'running').length}</span>
              </button>
            </nav>
          </div>

          <div className="p-4">
            {abTests.length === 0 ? (
              <div className="text-center py-8 text-athena-600">
                Nenhum A/B Test em andamento.
              </div>
            ) : (
              <div className="space-y-2">
                {abTests.slice(0, 10).map(test => (
                  <div key={test.id} className="p-3 bg-athena-900/50 rounded-lg">
                    <div className="flex items-center justify-between">
                      <p className="text-white font-medium">{test.name}</p>
                      <span className={`px-2 py-1 rounded text-xs ${
                        test.status === 'running' ? 'bg-green-500/20 text-green-400' :
                        test.status === 'completed' ? 'bg-blue-500/20 text-blue-400' :
                        'bg-gray-500/20 text-gray-400'
                      }`}>
                        {test.status}
                      </span>
                    </div>
                    <p className="text-athena-600 text-sm mt-1">
                      {test.variant === 'control' ? '🎯 Controle' : '🧪 Teste'}
                    </p>
                    {test.winner && (
                      <p className="text-athena-accent text-sm mt-1">
                        Vencedor: {test.winner} ({test.confidence}% confiança)
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Performance Recente</h3>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-athena-700">
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Data</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Impressões</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Cliques</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">CTR</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Custo</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Pedidos</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Receita</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">ROAS</th>
              </tr>
            </thead>
            <tbody>
              {performance.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-center py-8 text-athena-600">
                    Nenhum dado de performance. Sincronize campanhas primeiro.
                  </td>
                </tr>
              ) : (
                performance.slice(0, 30).map(p => (
                  <tr key={p.id} className="border-b border-athena-700/50">
                    <td className="py-2 px-3 text-white">{new Date(p.date).toLocaleDateString()}</td>
                    <td className="py-2 px-3 text-white">{p.impressions.toLocaleString()}</td>
                    <td className="py-2 px-3 text-white">{p.clicks.toLocaleString()}</td>
                    <td className="py-2 px-3 text-athena-300">{p.ctr.toFixed(2)}%</td>
                    <td className="py-2 px-3 text-white">R$ {p.cost.toFixed(2)}</td>
                    <td className="py-2 px-3 text-white">{p.orders}</td>
                    <td className="py-2 px-3 text-white">R$ {p.revenue.toFixed(2)}</td>
                    <td className={`py-2 px-3 font-medium ${getROASColor(p.roas)}`}>
                      {p.roas.toFixed(2)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span>📚</span> Documentação AG-ADS
        </h3>

        <div className="space-y-2 text-sm">
          <a
            href="/docs/tutorial-shopee-ads.md"
            target="_blank"
            rel="noopener noreferrer"
            className="block text-athena-accent hover:text-athena-accent/80 underline"
          >
            📘 Tutorial completo Shopee Ads
          </a>
          <a
            href="https://open.shopee.com/documents?module=63"
            target="_blank"
            rel="noopener noreferrer"
            className="block text-athena-accent hover:text-athena-accent/80 underline"
          >
            🔗 API Shopee Ads Oficial
          </a>
          <a
            href="/docs/documentacao-tecnica-ads.md"
            target="_blank"
            rel="noopener noreferrer"
            className="block text-athena-accent hover:text-athena-accent/80 underline"
          >
            📋 Documentação técnica AG-ADS
          </a>
        </div>
      </div>
    </div>
  )
}