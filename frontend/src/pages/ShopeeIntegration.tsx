import { useState, useEffect } from 'react'
import { useApi } from '../hooks/useAuth'

interface ShopeeConfig {
  partner_id: string
  partner_key: string
  shop_id: string
  region: string
  sandbox: boolean
}

interface ShopeeProduct {
  item_id: number
  item_sku: string
  item_name: string
  item_status: string
  stock: number
  reserved_stock: number
  has_model: boolean
  price: number
  last_synced_at: string
}

interface ShopeeOrder {
  order_sn: string
  order_status: string
  buyer: string
  total_amount: number
  items: Array<{ item_name: string; quantity: number }>
  ordered_at: string
  synced_to_athena: boolean
}

interface SyncResult {
  count: number
  errors: string[]
}

export default function ShopeeIntegration() {
  const api = useApi()
  const [config, setConfig] = useState<ShopeeConfig>({ partner_id: '', partner_key: '', shop_id: '', region: 'br', sandbox: true })
  const [products, setProducts] = useState<ShopeeProduct[]>([])
  const [orders, setOrders] = useState<ShopeeOrder[]>([])
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null)
  const [testing, setTesting] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [showOrders, setShowOrders] = useState(false)

  useEffect(() => {
    loadConfig()
    loadProducts()
    loadOrders()
  }, [])

  const loadConfig = async () => {
    try {
      const data = await api<ShopeeConfig>('/api/shopee/config')
      if (data) setConfig(data)
    } catch (e) {
      console.warn('Failed to load Shopee config:', e)
    }
  }

  const loadProducts = async () => {
    try {
      const data = await api<ShopeeProduct[]>('/api/shopee/products')
      if (data) setProducts(data)
    } catch (e) {
      console.warn('Failed to load Shopee products:', e)
    }
  }

  const loadOrders = async () => {
    try {
      const data = await api<ShopeeOrder[]>('/api/shopee/orders')
      if (data) setOrders(data)
    } catch (e) {
      console.warn('Failed to load Shopee orders:', e)
    }
  }

  const saveConfig = async () => {
    try {
      await api('/api/shopee/config', { method: 'PUT', body: JSON.stringify(config) })
      setTestResult({ success: true, message: 'Configurações salvas com sucesso!' })
    } catch (e) {
      setTestResult({ success: false, message: 'Erro ao salvar configurações' })
    }
  }

  const testConnection = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const data = await api<{ success: boolean; message: string }>('/api/shopee/test', { method: 'POST' })
      setTestResult(data)
    } catch (e) {
      setTestResult({ success: false, message: 'Falha na conexão com Shopee' })
    } finally {
      setTesting(false)
    }
  }

  const syncProducts = async () => {
    setSyncing(true)
    setSyncResult(null)
    try {
      const data = await api<SyncResult>('/api/shopee/sync', { method: 'POST' })
      setSyncResult(data)
      if (data) await loadProducts()
    } catch (e) {
      setSyncResult({ count: 0, errors: ['Erro ao sincronizar produtos'] })
    } finally {
      setSyncing(false)
    }
  }

  const syncOrders = async () => {
    setSyncing(true)
    setSyncResult(null)
    try {
      const data = await api<SyncResult>('/api/shopee/sync-orders', { method: 'POST' })
      setSyncResult(data)
      if (data) await loadOrders()
    } catch (e) {
      setSyncResult({ count: 0, errors: ['Erro ao sincronizar pedidos'] })
    } finally {
      setSyncing(false)
    }
  }

  const getStockStatus = (stock: number) => {
    if (stock <= 5) return 'text-red-400'
    if (stock <= 15) return 'text-yellow-400'
    return 'text-green-400'
  }

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      NORMAL: 'bg-green-500/20 text-green-400',
      BANNED: 'bg-red-500/20 text-red-400',
      UNLIST: 'bg-yellow-500/20 text-yellow-400',
      DELETED: 'bg-gray-500/20 text-gray-400',
    }
    return colors[status] || 'bg-gray-500/20 text-gray-400'
  }

  const getOrderStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      READY_TO_SHIP: 'bg-blue-500/20 text-blue-400',
      PROCESSED: 'bg-purple-500/20 text-purple-400',
      SHIPPED: 'bg-yellow-500/20 text-yellow-400',
      COMPLETED: 'bg-green-500/20 text-green-400',
      CANCELLED: 'bg-red-500/20 text-red-400',
    }
    return colors[status] || 'bg-gray-500/20 text-gray-400'
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white mb-1">Integração Shopee</h2>
        <p className="text-athena-600 text-sm">Sincronização de produtos, estoque e pedidos</p>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span>🔧</span> Configurações da API
        </h3>

        <div className="space-y-4">
          <div>
            <label className="block text-athena-400 text-sm mb-1">Partner ID</label>
            <input
              type="text"
              value={config.partner_id}
              onChange={(e) => setConfig({ ...config, partner_id: e.target.value })}
              className="w-full bg-athena-900 border border-athena-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-athena-accent"
              placeholder="Ex: 123456"
            />
          </div>

          <div>
            <label className="block text-athena-400 text-sm mb-1">Partner Key</label>
            <input
              type="password"
              value={config.partner_key}
              onChange={(e) => setConfig({ ...config, partner_key: e.target.value })}
              className="w-full bg-athena-900 border border-athena-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-athena-accent"
              placeholder="Chave secreta da Shopee"
            />
            <p className="text-athena-600 text-xs mt-1">⚠️ Mantenha esta chave segura, nunca compartilhe</p>
          </div>

          <div>
            <label className="block text-athena-400 text-sm mb-1">Shop ID</label>
            <input
              type="text"
              value={config.shop_id}
              onChange={(e) => setConfig({ ...config, shop_id: e.target.value })}
              className="w-full bg-athena-900 border border-athena-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-athena-accent"
              placeholder="ID da sua loja Shopee"
            />
          </div>

          <div>
            <label className="block text-athena-400 text-sm mb-1">Região</label>
            <select
              value={config.region}
              onChange={(e) => setConfig({ ...config, region: e.target.value })}
              className="w-full bg-athena-900 border border-athena-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-athena-accent"
            >
              <option value="br">Brasil</option>
              <option value="global">Global</option>
            </select>
          </div>

          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="sandbox"
              checked={config.sandbox}
              onChange={(e) => setConfig({ ...config, sandbox: e.target.checked })}
              className="w-4 h-4 rounded bg-athena-900 border-athena-700"
            />
            <label htmlFor="sandbox" className="text-athena-400 text-sm">Modo Sandbox (Testes)</label>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              onClick={saveConfig}
              className="flex-1 bg-athena-accent hover:bg-athena-accent/80 text-white font-medium rounded-lg px-4 py-2 transition"
            >
              Salvar Configurações
            </button>
            <button
              onClick={testConnection}
              disabled={testing}
              className="flex-1 bg-athena-success hover:bg-athena-success/80 text-white font-medium rounded-lg px-4 py-2 transition disabled:opacity-50"
            >
              {testing ? 'Testando...' : 'Testar Conexão'}
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
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <span>📦</span> Produtos Sincronizados
          </h3>
          <button
            onClick={syncProducts}
            disabled={syncing}
            className="bg-athena-accent hover:bg-athena-accent/80 text-white font-medium rounded-lg px-4 py-2 transition disabled:opacity-50 text-sm"
          >
            {syncing ? 'Sincronizando...' : 'Sincronizar Agora'}
          </button>
        </div>

        {syncResult && (
          <div className={`p-3 rounded-lg mb-4 ${syncResult.errors.length === 0 ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
            ✓ Sincronizados: {syncResult.count} produtos
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
                <th className="text-left py-2 px-3 text-athena-400 font-medium">SKU</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Produto</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Status</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Estoque</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Reservado</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Preço</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Variações</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Última Sync</th>
              </tr>
            </thead>
            <tbody>
              {products.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-8 text-athena-600">
                    Nenhum produto sincronizado. Clique em "Sincronizar Agora".
                  </td>
                </tr>
              ) : (
                products.map((product) => (
                  <tr key={product.item_id} className="border-b border-athena-700/50">
                    <td className="py-2 px-3 text-athena-accent font-mono">{product.item_sku}</td>
                    <td className="py-2 px-3 text-white">{product.item_name}</td>
                    <td className="py-2 px-3">
                      <span className={`px-2 py-1 rounded text-xs ${getStatusBadge(product.item_status)}`}>
                        {product.item_status}
                      </span>
                    </td>
                    <td className={`py-2 px-3 font-medium ${getStockStatus(product.stock)}`}>
                      {product.stock}
                    </td>
                    <td className="py-2 px-3 text-athena-600">{product.reserved_stock}</td>
                    <td className="py-2 px-3 text-white">R$ {product.price.toFixed(2)}</td>
                    <td className="py-2 px-3 text-athena-400">
                      {product.has_model ? '✓ Sim' : '✗ Não'}
                    </td>
                    <td className="py-2 px-3 text-athena-600 text-xs">
                      {new Date(product.last_synced_at).toLocaleString('pt-BR')}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <span>🛒</span> Pedidos Shopee
          </h3>
          <button
            onClick={syncOrders}
            disabled={syncing}
            className="bg-athena-accent hover:bg-athena-accent/80 text-white font-medium rounded-lg px-4 py-2 transition disabled:opacity-50 text-sm"
          >
            {syncing ? 'Sincronizando...' : 'Sincronizar Pedidos'}
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-athena-700">
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Pedido</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Status</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Comprador</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Total</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Itens</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Data</th>
                <th className="text-left py-2 px-3 text-athena-400 font-medium">Sincronizado</th>
              </tr>
            </thead>
            <tbody>
              {orders.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-athena-600">
                    Nenhum pedido sincronizado. Clique em "Sincronizar Pedidos".
                  </td>
                </tr>
              ) : (
                orders.map((order) => (
                  <tr key={order.order_sn} className="border-b border-athena-700/50">
                    <td className="py-2 px-3 text-athena-accent font-mono">{order.order_sn}</td>
                    <td className="py-2 px-3">
                      <span className={`px-2 py-1 rounded text-xs ${getOrderStatusBadge(order.order_status)}`}>
                        {order.order_status}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-white">{order.buyer}</td>
                    <td className="py-2 px-3 text-white">R$ {order.total_amount.toFixed(2)}</td>
                    <td className="py-2 px-3 text-athena-600 text-xs">
                      {order.items.length} item(s)
                    </td>
                    <td className="py-2 px-3 text-athena-600 text-xs">
                      {new Date(order.ordered_at).toLocaleString('pt-BR')}
                    </td>
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
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span>📖</span> Ajuda e Documentação
        </h3>
        <div className="space-y-2 text-sm">
          <a
            href="/docs/tutorial-configuracao-shopee.md"
            target="_blank"
            rel="noopener noreferrer"
            className="block text-athena-accent hover:text-athena-accent/80 underline"
          >
            📚 Tutorial completo de configuração da API Shopee
          </a>
          <a
            href="https://open.shopee.com.br/documents"
            target="_blank"
            rel="noopener noreferrer"
            className="block text-athena-accent hover:text-athena-accent/80 underline"
          >
            📄 Documentação oficial da API Shopee
          </a>
          <a
            href="https://help.shopee.com.br"
            target="_blank"
            rel="noopener noreferrer"
            className="block text-athena-accent hover:text-athena-accent/80 underline"
          >
            💬 Suporte Shopee
          </a>
        </div>
      </div>
    </div>
  )
}