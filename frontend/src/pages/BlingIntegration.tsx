import { useState, useEffect } from 'react'
import { useApi } from '../hooks/useAuth'

interface BlingConfig {
  api_key: string
  sandbox: boolean
  auto_sync: boolean
  sync_interval_minutes: number
  sync_products: boolean
  sync_orders: boolean
  sync_invoices: boolean
  sync_receivables: boolean
  sync_stock: boolean
}

interface BlingProduct {
  id: number
  codigo: string
  descricao: string
  preco: number
  estoque_atual: number
  estoque_minimo: number
  situacao: string
  last_synced_at: string
}

interface BlingOrder {
  id: number
  numero: string
  data: string
  total_venda: number
  situacao: string
  contato_nome: string
  imported_at: string
  synced_to_athena: boolean
}

interface BlingInvoice {
  id: number
  numero: string
  serie: string
  data_emissao: string
  valor_nota: number
  situacao: string
  cliente_nome: string
  imported_at: string
}

interface BlingReceivable {
  id: number
  descricao: string
  valor: number
  data_vencimento: string
  situacao: string
}

interface SyncResult {
  count: number
  errors: string[]
}

export default function BlingIntegration() {
  const api = useApi()
  const [config, setConfig] = useState<BlingConfig>({
    api_key: '',
    sandbox: true,
    auto_sync: true,
    sync_interval_minutes: 30,
    sync_products: true,
    sync_orders: true,
    sync_invoices: true,
    sync_receivables: true,
    sync_stock: true
  })
  
  const [products, setProducts] = useState<BlingProduct[]>([])
  const [orders, setOrders] = useState<BlingOrder[]>([])
  const [invoices, setInvoices] = useState<BlingInvoice[]>([])
  const [receivables, setReceivables] = useState<BlingReceivable[]>([])
  
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null)
  const [testing, setTesting] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [activeTab, setActiveTab] = useState<'products' | 'orders' | 'invoices' | 'receivables'>('products')

  useEffect(() => {
    loadConfig()
    loadData()
  }, [])

  const loadConfig = async () => {
    try {
      const data = await api<BlingConfig>('/api/bling/config')
      if (data) setConfig(data)
    } catch (e) {
      console.warn('Failed to load Bling config:', e)
    }
  }

  const loadData = async () => {
    try {
      const [productsData, ordersData, invoicesData, receivablesData] = await Promise.all([
        api<BlingProduct[]>('/api/bling/products'),
        api<BlingOrder[]>('/api/bling/orders'),
        api<BlingInvoice[]>('/api/bling/invoices'),
        api<BlingReceivable[]>('/api/bling/receivables')
      ])
      
      if (productsData) setProducts(productsData)
      if (ordersData) setOrders(ordersData)
      if (invoicesData) setInvoices(invoicesData)
      if (receivablesData) setReceivables(receivablesData)
    } catch (e) {
      console.warn('Failed to load Bling data:', e)
    }
  }

  const saveConfig = async () => {
    try {
      await api('/api/bling/config', { method: 'PUT', body: JSON.stringify(config) })
      setTestResult({ success: true, message: 'Configurações salvas com sucesso!' })
    } catch (e) {
      setTestResult({ success: false, message: 'Erro ao salvar configurações' })
    }
  }

  const testConnection = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const data = await api<{ success: boolean; message: string }>('/api/bling/test', { method: 'POST' })
      setTestResult(data)
    } catch (e) {
      setTestResult({ success: false, message: 'Falha na conexão com Bling' })
    } finally {
      setTesting(false)
    }
  }

  const syncData = async (type: 'products' | 'orders' | 'invoices' | 'receivables') => {
    setSyncing(true)
    setSyncResult(null)
    try {
      const data = await api<SyncResult>(`/api/bling/sync/${type}`, { method: 'POST' })
      setSyncResult(data)
      if (data) await loadData()
    } catch (e) {
      setSyncResult({ count: 0, errors: [`Erro ao sincronizar ${type}`] })
    } finally {
      setSyncing(false)
    }
  }

  const getStockStatus = (stock: number, minStock: number) => {
    if (stock <= 0) return 'text-red-400'
    if (stock <= minStock) return 'text-yellow-400'
    return 'text-green-400'
  }

  const getOrderStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      'Aberto': 'bg-blue-500/20 text-blue-400',
      'Atendido': 'bg-green-500/20 text-green-400',
      'Em andamento': 'bg-yellow-500/20 text-yellow-400',
      'Cancelado': 'bg-red-500/20 text-red-400',
      'Faturado': 'bg-purple-500/20 text-purple-400',
    }
    return colors[status] || 'bg-gray-500/20 text-gray-400'
  }

  const getInvoiceStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      'Em digitação': 'bg-yellow-500/20 text-yellow-400',
      'Autorizada': 'bg-green-500/20 text-green-400',
      'Cancelada': 'bg-red-500/20 text-red-400',
      'Denegada': 'bg-red-500/20 text-red-400',
      'Rejeitada': 'bg-red-500/20 text-red-400',
    }
    return colors[status] || 'bg-gray-500/20 text-gray-400'
  }

  const getReceivableStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      'aberto': 'bg-yellow-500/20 text-yellow-400',
      'pago': 'bg-green-500/20 text-green-400',
      'cancelado': 'bg-red-500/20 text-red-400',
      'atrasado': 'bg-red-500/20 text-red-400',
    }
    return colors[status] || 'bg-gray-500/20 text-gray-400'
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-1">Integração Bling ERP</h2>
        <p className="text-athena-600 text-sm">Gestão completa de vendas, estoque e financeiro</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>💎</span> Configurações da API
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-athena-400 text-sm mb-1">API Key</label>
                <input
                  type="password"
                  value={config.api_key}
                  onChange={(e) => setConfig({ ...config, api_key: e.target.value })}
                  className="w-full bg-athena-900 border border-athena-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-athena-accent"
                  placeholder="Sua API Key do Bling"
                />
                <p className="text-athena-600 text-xs mt-1">Encontre em: Configurações → Integrações → API</p>
              </div>

              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="sandbox"
                  checked={config.sandbox}
                  onChange={(e) => setConfig({ ...config, sandbox: e.target.checked })}
                  className="w-4 h-4 rounded bg-athena-900 border-athena-700"
                />
                <label htmlFor="sandbox" className="text-athena-400 text-sm">Modo Sandbox</label>
              </div>

              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="auto_sync"
                  checked={config.auto_sync}
                  onChange={(e) => setConfig({ ...config, auto_sync: e.target.checked })}
                  className="w-4 h-4 rounded bg-athena-900 border-athena-700"
                />
                <label htmlFor="auto_sync" className="text-athena-400 text-sm">Sincronização Automática</label>
              </div>

              <div>
                <label className="block text-athena-400 text-sm mb-1">Intervalo (minutos)</label>
                <input
                  type="number"
                  value={config.sync_interval_minutes}
                  onChange={(e) => setConfig({ ...config, sync_interval_minutes: parseInt(e.target.value) })}
                  className="w-full bg-athena-900 border border-athena-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-athena-accent"
                  min="5"
                  max="1440"
                />
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={saveConfig}
                  className="flex-1 bg-athena-accent hover:bg-athena-accent/80 text-white font-medium rounded-lg px-4 py-2 transition"
                >
                  Salvar
                </button>
                <button
                  onClick={testConnection}
                  disabled={testing}
                  className="flex-1 bg-athena-success hover:bg-athena-success/80 text-white font-medium rounded-lg px-4 py-2 transition disabled:opacity-50"
                >
                  {testing ? 'Testando...' : 'Testar'}
                </button>
              </div>

              {testResult && (
                <div className={`p-3 rounded-lg ${testResult.success ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                  {testResult.success ? '✓' : '✗'} {testResult.message}
                </div>
              )}
            </div>
          </div>

          <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>⚙️</span> Opções de Sincronização
            </h3>

            <div className="space-y-3">
              {[
                { key: 'sync_products', label: 'Sincronizar Produtos', icon: '📦' },
                { key: 'sync_orders', label: 'Sincronizar Pedidos', icon: '🛒' },
                { key: 'sync_invoices', label: 'Sincronizar Notas Fiscais', icon: '🧾' },
                { key: 'sync_receivables', label: 'Sincronizar Contas a Receber', icon: '💰' },
                { key: 'sync_stock', label: 'Sincronizar Estoque', icon: '📊' }
              ].map(({ key, label, icon }) => (
                <div key={key} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span>{icon}</span>
                    <span className="text-athena-300 text-sm">{label}</span>
                  </div>
                  <input
                    type="checkbox"
                    id={key}
                    checked={(config as any)[key]}
                    onChange={(e) => setConfig({ ...config, [key]: e.target.checked })}
                    className="w-4 h-4 rounded bg-athena-900 border-athena-700"
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>📖</span> Ajuda e Documentação
            </h3>
            <div className="space-y-2 text-sm">
              <a
                href="/docs/tutorial-configuracao-bling.md"
                target="_blank"
                rel="noopener noreferrer"
                className="block text-athena-accent hover:text-athena-accent/80 underline"
              >
                📚 Tutorial de configuração Bling
              </a>
              <a
                href="https://ajuda.bling.com.br/hc/pt-br/articles/360046419513-Como-obter-minha-API-Key"
                target="_blank"
                rel="noopener noreferrer"
                className="block text-athena-accent hover:text-athena-accent/80 underline"
              >
                🔑 Obter API Key Bling
              </a>
              <a
                href="https://developer.bling.com.br/"
                target="_blank"
                rel="noopener noreferrer"
                className="block text-athena-accent hover:text-athena-accent/80 underline"
              >
                📄 Documentação API Bling
              </a>
              <a
                href="https://ajuda.bling.com.br"
                target="_blank"
                rel="noopener noreferrer"
                className="block text-athena-accent hover:text-athena-accent/80 underline"
              >
                💬 Suporte Bling
              </a>
            </div>
          </div>
        </div>

        <div className="lg:col-span-2 space-y-6">
          {syncResult && (
            <div className={`p-4 rounded-lg ${syncResult.errors.length === 0 ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
              ✓ Sincronizados: {syncResult.count} itens
              {syncResult.errors.length > 0 && (
                <div className="mt-2 text-xs">
                  Erros: {syncResult.errors.join(', ')}
                </div>
              )}
            </div>
          )}

          <div className="bg-athena-800 rounded-lg border border-athena-700">
            <div className="border-b border-athena-700">
              <nav className="flex">
                {[
                  { id: 'products', label: 'Produtos', icon: '📦', count: products.length },
                  { id: 'orders', label: 'Pedidos', icon: '🛒', count: orders.length },
                  { id: 'invoices', label: 'Notas Fiscais', icon: '🧾', count: invoices.length },
                  { id: 'receivables', label: 'Contas a Receber', icon: '💰', count: receivables.length }
                ].map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors ${
                      activeTab === tab.id
                        ? 'bg-athena-700 text-white border-b-2 border-athena-accent'
                        : 'text-athena-400 hover:text-white'
                    }`}
                  >
                    <span>{tab.icon}</span>
                    <span>{tab.label}</span>
                    <span className="bg-athena-700 text-xs px-2 py-0.5 rounded-full">{tab.count}</span>
                  </button>
                ))}
              </nav>
            </div>

            <div className="p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">
                  {activeTab === 'products' && '📦 Produtos'}
                  {activeTab === 'orders' && '🛒 Pedidos'}
                  {activeTab === 'invoices' && '🧾 Notas Fiscais'}
                  {activeTab === 'receivables' && '💰 Contas a Receber'}
                </h3>
                <button
                  onClick={() => syncData(activeTab)}
                  disabled={syncing}
                  className="bg-athena-accent hover:bg-athena-accent/80 text-white font-medium rounded-lg px-4 py-2 transition disabled:opacity-50 text-sm"
                >
                  {syncing ? 'Sincronizando...' : 'Sincronizar Agora'}
                </button>
              </div>

              {activeTab === 'products' && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-athena-700">
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Código</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Descrição</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Situação</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Estoque</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Preço</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Última Sync</th>
                      </tr>
                    </thead>
                    <tbody>
                      {products.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="text-center py-8 text-athena-600">
                            Nenhum produto sincronizado. Clique em "Sincronizar Agora".
                          </td>
                        </tr>
                      ) : (
                        products.slice(0, 10).map(product => (
                          <tr key={product.id} className="border-b border-athena-700/50">
                            <td className="py-2 px-3 text-athena-accent font-mono">{product.codigo}</td>
                            <td className="py-2 px-3 text-white">{product.descricao}</td>
                            <td className="py-2 px-3">
                              <span className={`px-2 py-1 rounded text-xs ${
                                product.situacao === 'A' 
                                  ? 'bg-green-500/20 text-green-400' 
                                  : 'bg-red-500/20 text-red-400'
                              }`}>
                                {product.situacao === 'A' ? 'Ativo' : 'Inativo'}
                              </span>
                            </td>
                            <td className={`py-2 px-3 font-medium ${getStockStatus(product.estoque_atual, product.estoque_minimo)}`}>
                              {product.estoque_atual}
                            </td>
                            <td className="py-2 px-3 text-white">R$ {product.preco.toFixed(2)}</td>
                            <td className="py-2 px-3 text-athena-600 text-xs">
                              {new Date(product.last_synced_at).toLocaleString('pt-BR')}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}

              {activeTab === 'orders' && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-athena-700">
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Número</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Data</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Cliente</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Status</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Total</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Sincronizado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orders.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="text-center py-8 text-athena-600">
                            Nenhum pedido sincronizado. Clique em "Sincronizar Agora".
                          </td>
                        </tr>
                      ) : (
                        orders.slice(0, 10).map(order => (
                          <tr key={order.id} className="border-b border-athena-700/50">
                            <td className="py-2 px-3 text-athena-accent font-mono">{order.numero}</td>
                            <td className="py-2 px-3 text-athena-300 text-xs">
                              {new Date(order.data).toLocaleDateString('pt-BR')}
                            </td>
                            <td className="py-2 px-3 text-white">{order.contato_nome}</td>
                            <td className="py-2 px-3">
                              <span className={`px-2 py-1 rounded text-xs ${getOrderStatusColor(order.situacao)}`}>
                                {order.situacao}
                              </span>
                            </td>
                            <td className="py-2 px-3 text-white">R$ {order.total_venda.toFixed(2)}</td>
                            <td className="py-2 px-3">
                              {order.synced_to_athena ? (
                                <span className="text-green-400">✓ Sim</span>
                              ) : (
                                <span className="text-yellow-400">⏳ Pendente</span>
                              )}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}

              {activeTab === 'invoices' && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-athena-700">
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Número</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Série</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Cliente</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Status</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Valor</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Data</th>
                      </tr>
                    </thead>
                    <tbody>
                      {invoices.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="text-center py-8 text-athena-600">
                            Nenhuma nota fiscal sincronizada. Clique em "Sincronizar Agora".
                          </td>
                        </tr>
                      ) : (
                        invoices.slice(0, 10).map(invoice => (
                          <tr key={invoice.id} className="border-b border-athena-700/50">
                            <td className="py-2 px-3 text-athena-accent font-mono">{invoice.numero}</td>
                            <td className="py-2 px-3 text-athena-300 text-sm">{invoice.serie}</td>
                            <td className="py-2 px-3 text-white">{invoice.cliente_nome}</td>
                            <td className="py-2 px-3">
                              <span className={`px-2 py-1 rounded text-xs ${getInvoiceStatusColor(invoice.situacao)}`}>
                                {invoice.situacao}
                              </span>
                            </td>
                            <td className="py-2 px-3 text-white">R$ {invoice.valor_nota.toFixed(2)}</td>
                            <td className="py-2 px-3 text-athena-300 text-xs">
                              {new Date(invoice.data_emissao).toLocaleDateString('pt-BR')}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}

              {activeTab === 'receivables' && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-athena-700">
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Descrição</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Valor</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Vencimento</th>
                        <th className="text-left py-2 px-3 text-athena-400 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {receivables.length === 0 ? (
                        <tr>
                          <td colSpan={4} className="text-center py-8 text-athena-600">
                            Nenhuma conta a receber sincronizada. Clique em "Sincronizar Agora".
                          </td>
                        </tr>
                      ) : (
                        receivables.slice(0, 10).map(receivable => (
                          <tr key={receivable.id} className="border-b border-athena-700/50">
                            <td className="py-2 px-3 text-white">{receivable.descricao}</td>
                            <td className="py-2 px-3 text-white">R$ {receivable.valor.toFixed(2)}</td>
                            <td className="py-2 px-3 text-athena-300 text-xs">
                              {new Date(receivable.data_vencimento).toLocaleDateString('pt-BR')}
                            </td>
                            <td className="py-2 px-3">
                              <span className={`px-2 py-1 rounded text-xs ${getReceivableStatusColor(receivable.situacao)}`}>
                                {receivable.situacao}
                              </span>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}