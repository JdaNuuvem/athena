import { useState, useEffect } from 'react'

function App() {
  const [config, setConfig] = useState({
    telegramToken: '',
    telegramWebhookUrl: '',
    blingApiKey: '',
    blingApiUrl: '',
    shopeePartnerId: '',
    shopeeShopId: '',
    shopeeApiKey: ''
  })
  const [stats, setStats] = useState(null)
  const [production, setProduction] = useState(null)
  const [quality, setQuality] = useState(null)
  const [maintenance, setMaintenance] = useState(null)
  const [mlStatus, setMlStatus] = useState(null)
  const [configStatus, setConfigStatus] = useState(null)

  const API_BASE = 'https://177.7.45.242:8000/api'

  const saveConfig = async () => {
    try {
      if (config.telegramToken) {
        await fetch(`${API_BASE}/config/telegram`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            token: config.telegramToken,
            webhookUrl: config.telegramWebhookUrl || 'https://177.7.45.242:8000/telegram/webhook'
          })
        })
      }
      if (config.blingApiKey) {
        await fetch(`${API_BASE}/config/bling`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            apiKey: config.blingApiKey,
            apiUrl: config.blingApiUrl
          })
        })
      }
      if (config.shopeePartnerId && config.shopeeShopId && config.shopeeApiKey) {
        await fetch(`${API_BASE}/config/shopee`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            partnerId: config.shopeePartnerId,
            shopId: config.shopeeShopId,
            apiKey: config.shopeeApiKey
          })
        })
      }
      alert('✅ Configurações salvas!')
      fetchConfigStatus()
    } catch (e) {
      console.error('Erro:', e)
      alert('❌ Erro ao salvar configurações')
    }
  }

  const fetchConfigStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/config/status`)
      const data = await res.json()
      setConfigStatus(data)
    } catch (e) {
      console.error('Erro:', e)
    }
  }

  useEffect(() => {
    fetchStats()
    fetchProduction()
    fetchQuality()
    fetchMaintenance()
    fetchMlStatus()
    fetchConfigStatus()
  }, [])

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/agent/ag_06_telegram/stats`)
      const data = await res.json()
      setStats(data)
    } catch (e) {
      console.error('Erro ao carregar stats:', e)
    }
  }

  const fetchProduction = async () => {
    try {
      const res = await fetch(`${API_BASE}/moldes/dashboard`)
      const data = await res.json()
      setProduction(data)
    } catch (e) {
      console.error('Erro ao carregar produção:', e)
    }
  }

  const fetchQuality = async () => {
    try {
      const res = await fetch(`${API_BASE}/qualidade/taxa_defeitos?periodo=30`)
      const data = await res.json()
      setQuality(data)
    } catch (e) {
      console.error('Erro ao carregar qualidade:', e)
    }
  }

  const fetchMaintenance = async () => {
    try {
      const res = await fetch(`${API_BASE}/manutencao/pendentes`)
      const data = await res.json()
      setMaintenance(data)
    } catch (e) {
      console.error('Erro ao carregar manutenção:', e)
    }
  }

  const fetchMlStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/ml/status`)
      const data = await res.json()
      setMlStatus(data)
    } catch (e) {
      console.error('Erro ao carregar ML:', e)
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-4">
      <header className="mb-8">
        <h1 className="text-3xl font-bold mb-2">🏛️ Hermes Dashboard</h1>
        <p className="text-gray-400">Fase 2-3: Produção + Cadeia de Manufatura | Servidor: 177.7.45.242:8000</p>
      </header>

      {/* Configuração */}
      <div className="bg-gray-800 rounded-lg p-6 mb-6">
        <h2 className="text-xl font-bold mb-4">⚙️ Configurações</h2>
        
        {/* Telegram */}
        <div className="mb-4 p-4 bg-gray-700 rounded">
          <h3 className="font-bold mb-2">📱 Telegram</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block mb-2 text-sm">Bot Token</label>
              <input
                type="password"
                value={config.telegramToken}
                onChange={(e) => setConfig({...config, telegramToken: e.target.value})}
                className="w-full p-2 bg-gray-600 rounded text-white"
                placeholder="Token do @BotFather"
              />
            </div>
            <div>
              <label className="block mb-2 text-sm">Webhook URL (opcional)</label>
              <input
                type="text"
                value={config.telegramWebhookUrl}
                onChange={(e) => setConfig({...config, telegramWebhookUrl: e.target.value})}
                className="w-full p-2 bg-gray-600 rounded text-white"
                placeholder="https://177.7.45.242:8000/telegram/webhook"
              />
            </div>
          </div>
        </div>
        
        {/* Bling */}
        <div className="mb-4 p-4 bg-gray-700 rounded">
          <h3 className="font-bold mb-2">💼 Bling ERP</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block mb-2 text-sm">API Key</label>
              <input
                type="password"
                value={config.blingApiKey}
                onChange={(e) => setConfig({...config, blingApiKey: e.target.value})}
                className="w-full p-2 bg-gray-600 rounded text-white"
                placeholder="API Key do Bling"
              />
            </div>
            <div>
              <label className="block mb-2 text-sm">API URL (opcional)</label>
              <input
                type="text"
                value={config.blingApiUrl}
                onChange={(e) => setConfig({...config, blingApiUrl: e.target.value})}
                className="w-full p-2 bg-gray-600 rounded text-white"
                placeholder="https://bling.com.br/Api/v3"
              />
            </div>
          </div>
        </div>
        
        {/* Shopee */}
        <div className="mb-4 p-4 bg-gray-700 rounded">
          <h3 className="font-bold mb-2">🛒 Shopee Marketplace</h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block mb-2 text-sm">Partner ID</label>
              <input
                type="text"
                value={config.shopeePartnerId}
                onChange={(e) => setConfig({...config, shopeePartnerId: e.target.value})}
                className="w-full p-2 bg-gray-600 rounded text-white"
                placeholder="ID do parceiro"
              />
            </div>
            <div>
              <label className="block mb-2 text-sm">Shop ID</label>
              <input
                type="text"
                value={config.shopeeShopId}
                onChange={(e) => setConfig({...config, shopeeShopId: e.target.value})}
                className="w-full p-2 bg-gray-600 rounded text-white"
                placeholder="ID da loja"
              />
            </div>
            <div>
              <label className="block mb-2 text-sm">API Key</label>
              <input
                type="password"
                value={config.shopeeApiKey}
                onChange={(e) => setConfig({...config, shopeeApiKey: e.target.value})}
                className="w-full p-2 bg-gray-600 rounded text-white"
                placeholder="Chave da API"
              />
            </div>
          </div>
        </div>
        
        <div className="mt-4">
          <button
            onClick={saveConfig}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded"
          >
            💾 Salvar Todas as Configurações
          </button>
        </div>
        {configStatus && (
          <div className="mt-4 text-sm text-gray-400">
            Telegram: {configStatus.telegram_configurado ? '✅' : '❌'} | 
            Bling: {configStatus.bling_configurado ? '✅' : '❌'} |
            Shopee: {configStatus.shopee_configurado ? '✅' : '❌'}
          </div>
        )}
      </div>

      {/* Stats Telegram */}
      <div className="bg-gray-800 rounded-lg p-6 mb-6">
        <h2 className="text-xl font-bold mb-4">📊 Estatísticas Telegram</h2>
        {stats ? (
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-gray-700 p-4 rounded">
              <div className="text-2xl font-bold">{stats.total_clientes || 0}</div>
              <div className="text-sm text-gray-400">Clientes</div>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <div className="text-2xl font-bold">{stats.total_pedidos || 0}</div>
              <div className="text-sm text-gray-400">Pedidos</div>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <div className="text-2xl font-bold">R$ {(stats.faturamento_total || 0).toFixed(2)}</div>
              <div className="text-sm text-gray-400">Faturamento</div>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <div className="text-2xl font-bold">R$ {(stats.ticket_medio_geral || 0).toFixed(2)}</div>
              <div className="text-sm text-gray-400">Ticket Médio</div>
            </div>
          </div>
        ) : (
          <div className="text-gray-400">Carregando...</div>
        )}
      </div>

      {/* Produção */}
      <div className="bg-gray-800 rounded-lg p-6 mb-6">
        <h2 className="text-xl font-bold mb-4">🏭 Produção</h2>
        {production ? (
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-gray-700 p-4 rounded">
              <div className="text-2xl font-bold">{production.moldes_criticos || 0}</div>
              <div className="text-sm text-gray-400">Moldes Críticos</div>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <div className="text-2xl font-bold">{production.jobs_cnc_ativos || 0}</div>
              <div className="text-sm text-gray-400">Jobs CNC Ativos</div>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <div className="text-2xl font-bold">{production.eventos_recentes?.length || 0}</div>
              <div className="text-sm text-gray-400">Eventos Recentes</div>
            </div>
          </div>
        ) : (
          <div className="text-gray-400">Carregando...</div>
        )}
      </div>

      {/* Qualidade */}
      <div className="bg-gray-800 rounded-lg p-6 mb-6">
        <h2 className="text-xl font-bold mb-4">✅ Controle de Qualidade</h2>
        {quality ? (
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-gray-700 p-4 rounded">
              <div className="text-2xl font-bold">{quality.lotes_inspecionados || 0}</div>
              <div className="text-sm text-gray-400">Lotes Inspecionados</div>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <div className="text-2xl font-bold">{quality.taxa_reprovacao_pct || 0}%</div>
              <div className="text-sm text-gray-400">Taxa Reprovação</div>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <div className="text-2xl font-bold">{quality.por_sku?.length || 0}</div>
              <div className="text-sm text-gray-400">SKUs com Defeitos</div>
            </div>
          </div>
        ) : (
          <div className="text-gray-400">Carregando...</div>
        )}
      </div>

      {/* Manutenção */}
      <div className="bg-gray-800 rounded-lg p-6 mb-6">
        <h2 className="text-xl font-bold mb-4">🔧 Gestão de Manutenção</h2>
        {maintenance ? (
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-gray-700 p-4 rounded">
              <div className="text-2xl font-bold">{maintenance.total || 0}</div>
              <div className="text-sm text-gray-400">Manutenções Pendentes</div>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <div className="text-2xl font-bold">{maintenance.alertas?.length || 0}</div>
              <div className="text-sm text-gray-400">Alertas Ativos</div>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <div className="text-2xl font-bold">KPIs</div>
              <div className="text-sm text-gray-400">Últimos 30 dias</div>
            </div>
          </div>
        ) : (
          <div className="text-gray-400">Carregando...</div>
        )}
      </div>

      {/* Machine Learning */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">🤖 Machine Learning</h2>
        {mlStatus ? (
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-gray-700 p-4 rounded">
              <div className="text-2xl font-bold">
                {mlStatus.modelo_treinado ? '✅' : '❌'}
              </div>
              <div className="text-sm text-gray-400">Modelo Treinado</div>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <div className="text-2xl font-bold">
                {mlStatus.scikit_learn_instalado ? '✅' : '❌'}
              </div>
              <div className="text-sm text-gray-400">scikit-learn Instalado</div>
            </div>
          </div>
        ) : (
          <div className="text-gray-400">Carregando...</div>
        )}
      </div>

      {/* Links Úteis */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">🔗 Links Rápidos</h2>
        <div className="grid grid-cols-2 gap-4">
          <a href={`${API_BASE}/agent/ag_11_qualidade/pareto?periodo=30`} target="_blank" className="text-blue-400 hover:text-blue-300">
            📊 Análise Pareto de Defeitos
          </a>
          <a href={`${API_BASE}/manutencao/kpi?periodo=30`} target="_blank" className="text-blue-400 hover:text-blue-300">
            🔧 KPIs de Manutenção
          </a>
          <a href={`${API_BASE}/ml/treinar`} target="_blank" className="text-green-400 hover:text-green-300">
            🤖 Treinar Modelo ML
          </a>
          <a href="https://bling.com.br" target="_blank" className="text-purple-400 hover:text-purple-300">
            💼 Acessar Bling ERP
          </a>
          <a href="https://seller.shopee.com.br" target="_blank" className="text-orange-400 hover:text-orange-300">
            🛒 Acessar Shopee Seller
          </a>
          <a href="https://t.me/botfather" target="_blank" className="text-blue-400 hover:text-blue-300">
            📱 Criar Bot Telegram
          </a>
        </div>
      </div>
    </div>
  )
}

export default App