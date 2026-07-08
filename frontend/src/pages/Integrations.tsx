import { useState, useEffect } from 'react'
import { useApi } from '../hooks/useAuth'

interface Integration {
  id: string
  name: string
  description: string
  category: 'ecommerce' | 'erp' | 'payment' | 'logistics' | 'communication' | 'analytics' | 'ai' | 'automation' | 'database' | 'messaging' | 'ads' | 'infra'
  status: 'connected' | 'disconnected' | 'error' | 'pending'
  icon: string
  features: string[]
  lastSync?: string
  config?: Record<string, unknown>
}

const AVAILABLE_INTEGRATIONS: Omit<Integration, 'status' | 'lastSync' | 'config'>[] = [
  {
    id: 'bling',
    name: 'Bling ERP',
    description: 'ERP completo para gestão de vendas, estoque e financeiro',
    category: 'erp',
    icon: '💎',
    features: ['Gestão de produtos', 'Controle de estoque', 'Emissão de NF-e', 'Integração contábil', 'Gestão de vendas']
  },
  {
    id: 'shopee',
    name: 'Shopee',
    description: 'Sincronização de produtos, estoque e pedidos com marketplace',
    category: 'ecommerce',
    icon: '🛒',
    features: ['Sincronização de produtos', 'Gestão de estoque', 'Importação de pedidos', 'Atualização de preços']
  },
  {
    id: 'shopee-ads',
    name: 'Shopee Ads (AG-ADS)',
    description: 'Agente inteligente de publicidade Shopee com otimização automática',
    category: 'ai',
    icon: '📢',
    features: ['Criação de campanhas', 'Ajuste de bids automático', 'A/B testing', 'Previsão de performance', 'Insights automáticos']
  },
  {
    id: 'mercadolivre',
    name: 'Mercado Livre',
    description: 'Integração com maior marketplace da América Latina',
    category: 'ecommerce',
    icon: '📦',
    features: ['Sincronização de produtos', 'Gestão de pedidos', 'Atualização de estoque', 'Perguntas e respostas']
  },
  {
    id: 'nuvemshop',
    name: 'Nuvemshop',
    description: 'Plataforma de e-commerce para lojas virtuais',
    category: 'ecommerce',
    icon: '☁️',
    features: ['Catálogo de produtos', 'Gestão de pedidos', 'Sincronização de estoque', 'Integração com gateways']
  },
  {
    id: 'shopify',
    name: 'Shopify',
    description: 'Plataforma global de comércio eletrônico',
    category: 'ecommerce',
    icon: '🏪',
    features: ['Produtos e variantes', 'Gestão de pedidos', 'Sincronização de estoque', 'Analytics']
  },
  {
    id: 'pagseguro',
    name: 'PagSeguro',
    description: 'Gateway de pagamento líder no Brasil',
    category: 'payment',
    icon: '💳',
    features: ['Processamento de pagamentos', 'Gestão de transações', 'Webhooks', 'Reembolsos']
  },
  {
    id: 'mercado_pago',
    name: 'Mercado Pago',
    description: 'Solução de pagamentos digital',
    category: 'payment',
    icon: '💰',
    features: ['Pagamentos online', 'PIX', 'Cartões', 'Boletos']
  },
  {
    id: 'correios',
    name: 'Correios',
    description: 'Sistema de logística e envios',
    category: 'logistics',
    icon: '📮',
    features: ['Cálculo de frete', 'Rastreamento', 'Etiquetas', 'Coletas programadas']
  },
  {
    id: 'jadlog',
    name: 'Jadlog',
    description: 'Transportadora para e-commerce',
    category: 'logistics',
    icon: '🚚',
    features: ['Cotação de frete', 'Rastreamento', 'Integração automática']
  },
  {
    id: 'whatsapp',
    name: 'WhatsApp Business',
    description: 'Comunicação com clientes via WhatsApp',
    category: 'communication',
    icon: '💬',
    features: ['Envio de mensagens', 'Webhooks', 'Chatbots', 'Mídias']
  },
  {
    id: 'google_analytics',
    name: 'Google Analytics',
    description: 'Análise de dados e métricas',
    category: 'analytics',
    icon: '📊',
    features: ['Métricas de vendas', 'Comportamento do usuário', 'Conversões', 'Relatórios']
  },
  {
    id: 'meta',
    name: 'Meta (Facebook/Instagram)',
    description: 'Integração com redes sociais',
    category: 'ecommerce',
    icon: '📱',
    features: ['Facebook Shop', 'Instagram Shopping', 'Ads', 'Messenger']
  },
  {
    id: 'hermes',
    name: 'Hermes Agents',
    description: 'Sistema multi-agente inteligente para indústria e manufatura',
    category: 'ai',
    icon: '🤖',
    features: ['Caçador de Produtos', 'Analista de Lucratividade', 'Gerente de Marketplaces', 'Memória Corporativa', 'Planejador de Produção', 'Telegram Bot']
  }
]

export default function Integrations() {
  const api = useApi()
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchIntegrations = async () => {
      try {
        const data = await api<Integration[]>('/api/integrations')
        if (data) {
          setIntegrations(data)
        } else {
          setIntegrations(AVAILABLE_INTEGRATIONS.map(int => ({
            ...int,
            status: 'disconnected'
          })))
        }
      } catch (error) {
        console.error('Failed to fetch integrations:', error)
        setIntegrations(AVAILABLE_INTEGRATIONS.map(int => ({
          ...int,
          status: 'disconnected'
        })))
      } finally {
        setLoading(false)
      }
    }

    fetchIntegrations()
  }, [api])

  const categories = [
    { id: 'all', name: 'Todas', icon: '🌐' },
    { id: 'ecommerce', name: 'E-commerce', icon: '🛒' },
    { id: 'erp', name: 'ERP', icon: '💼' },
    { id: 'payment', name: 'Pagamentos', icon: '💳' },
    { id: 'logistics', name: 'Logística', icon: '📦' },
    { id: 'communication', name: 'Comunicação', icon: '💬' },
    { id: 'analytics', name: 'Analytics', icon: '📊' },
    { id: 'ai', name: 'IA & Agents', icon: '🤖' }
  ]

  const filteredIntegrations = integrations.filter(integration => {
    const matchesCategory = selectedCategory === 'all' || integration.category === selectedCategory
    const matchesSearch = !searchQuery || 
      integration.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      integration.description.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesCategory && matchesSearch
  })

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected': return 'bg-athena-success/20 text-athena-success border-athena-success/30'
      case 'disconnected': return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
      case 'error': return 'bg-athena-error/20 text-athena-error border-athena-error/30'
      case 'pending': return 'bg-athena-warn/20 text-athena-warn border-athena-warn/30'
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'connected': return '✓'
      case 'disconnected': return '○'
      case 'error': return '✗'
      case 'pending': return '⏳'
      default: return '○'
    }
  }

  const handleConnect = async (integrationId: string) => {
    try {
      if (integrationId === 'bling') {
        // Redirecionar para página específica do Bling
        window.location.href = '/bling'
        return
      }
      
      const result = await api<{ success: boolean; authUrl?: string }>(`/api/integrations/${integrationId}/connect`, { method: 'POST' })
      if (result?.success && result.authUrl) {
        window.open(result.authUrl, '_blank')
      } else if (result?.success) {
        setIntegrations(prev => prev.map(int => 
          int.id === integrationId ? { ...int, status: 'connected' } : int
        ))
      }
    } catch (error) {
      console.error('Failed to connect integration:', error)
    }
  }

  const handleDisconnect = async (integrationId: string) => {
    try {
      await api(`/api/integrations/${integrationId}/disconnect`, { method: 'POST' })
      setIntegrations(prev => prev.map(int => 
        int.id === integrationId ? { ...int, status: 'disconnected' } : int
      ))
    } catch (error) {
      console.error('Failed to disconnect integration:', error)
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
      <div>
        <h1 className="text-2xl font-bold text-white mb-1">Integrações</h1>
        <p className="text-athena-600 text-sm">Gerencie conexões com plataformas de e-commerce, ERPs e serviços</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {categories.map(category => (
          <button
            key={category.id}
            onClick={() => setSelectedCategory(category.id)}
            className={`p-4 rounded-lg border transition-all ${
              selectedCategory === category.id
                ? 'bg-athena-accent/10 border-athena-accent text-white'
                : 'bg-athena-800 border-athena-700 text-athena-400 hover:border-athena-600'
            }`}
          >
            <div className="flex items-center gap-3">
              <span className="text-2xl">{category.icon}</span>
              <div className="text-left">
                <p className="font-medium">{category.name}</p>
                <p className="text-xs opacity-60">
                  {selectedCategory === category.id
                    ? filteredIntegrations.length
                    : integrations.filter(i => category.id === 'all' || i.category === category.id).length
                  } integrações
                </p>
              </div>
            </div>
          </button>
        ))}
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-4">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Buscar integrações..."
          className="w-full bg-athena-900 border border-athena-700 rounded-lg px-4 py-2.5 text-sm text-athena-200 focus:border-athena-accent focus:outline-none"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredIntegrations.map(integration => (
          <div key={integration.id} className="bg-athena-800 rounded-lg border border-athena-700 p-6 hover:border-athena-600 transition-all">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <span className="text-3xl">{integration.icon}</span>
                <div>
                  <h3 className="text-white font-semibold text-lg">{integration.name}</h3>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium border ${getStatusColor(integration.status)}`}>
                    {getStatusIcon(integration.status)} {integration.status}
                  </span>
                </div>
              </div>
            </div>

            <p className="text-athena-400 text-sm mb-4">{integration.description}</p>

            <div className="mb-4">
              <p className="text-athena-600 text-xs uppercase tracking-wide mb-2">Funcionalidades</p>
              <div className="flex flex-wrap gap-2">
                {integration.features.slice(0, 3).map((feature, index) => (
                  <span key={index} className="bg-athena-900 text-athena-300 text-xs px-2 py-1 rounded">
                    {feature}
                  </span>
                ))}
                {integration.features.length > 3 && (
                  <span className="text-athena-600 text-xs">+{integration.features.length - 3}</span>
                )}
              </div>
            </div>

            {integration.lastSync && (
              <div className="mb-4">
                <p className="text-athena-600 text-xs uppercase tracking-wide mb-1">Última sincronização</p>
                <p className="text-athena-300 text-sm">{new Date(integration.lastSync).toLocaleString('pt-BR')}</p>
              </div>
            )}

            <div className="flex gap-2">
              {integration.status === 'connected' ? (
                <>
                  <button
                    onClick={() => handleDisconnect(integration.id)}
                    className="flex-1 bg-athena-error/20 hover:bg-athena-error/30 text-athena-error font-medium px-4 py-2 rounded-lg transition text-sm"
                  >
                    Desconectar
                  </button>
                  <button
                    className="flex-1 bg-athena-900 hover:bg-athena-700 text-athena-300 font-medium px-4 py-2 rounded-lg transition text-sm"
                  >
                    Configurar
                  </button>
                </>
              ) : (
                <button
                  onClick={() => handleConnect(integration.id)}
                  className="flex-1 bg-athena-accent hover:bg-athena-accent/80 text-athena-900 font-medium px-4 py-2 rounded-lg transition text-sm"
                >
                  Conectar
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {filteredIntegrations.length === 0 && (
        <div className="text-center py-12 text-athena-600">
          <span className="text-4xl mb-4 block">🔍</span>
          <p>Nenhuma integração encontrada com os filtros atuais</p>
        </div>
      )}
    </div>
  )
}