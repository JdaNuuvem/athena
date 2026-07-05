import { useQuery, useSubscription } from '@apollo/client/react'
import { STOCK_ITEMS, STOCK_MOVEMENTS, SHOPEE_PRODUCTS } from '../graphql/queries'
import { INVENTORY_CHANGED } from '../graphql/subscriptions'
import { StockChart } from '../components/StockChart'
import { StatusBadge } from '../components/StatusBadge'
import { AlertTriangle } from 'lucide-react'

export function Inventory() {
  const { data: items, loading: itemsLoading } = useQuery<{ stockItems: any[] }>(STOCK_ITEMS, { pollInterval: 30000 })
  const { data: movements, loading: movLoading } = useQuery<{ stockMovements: any[] }>(STOCK_MOVEMENTS)
  useSubscription(INVENTORY_CHANGED)

  const stockList = items?.stockItems ?? []
  const lowStock = stockList.filter((s: any) => s.quantity <= (s.reorderPoint ?? 10))
  const chartData = stockList.map((s: any) => ({ name: s.sku, quantity: s.quantity, available: s.available }))

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-100">Estoque</h2>

      {lowStock.length > 0 && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 flex items-start gap-3">
          <AlertTriangle size={18} className="text-amber-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-amber-400 text-sm font-medium">Alerta de Estoque Baixo</p>
            <p className="text-amber-400/70 text-xs mt-0.5">
              {lowStock.map((s: any) => `${s.sku} (${s.quantity} un.)`).join(', ')}
            </p>
          </div>
        </div>
      )}

      <StockChart data={chartData} loading={itemsLoading} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
          <div className="p-3 border-b border-slate-700">
            <h3 className="text-slate-400 text-xs uppercase tracking-wider">Itens em Estoque</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
                  <th className="text-left p-3">SKU</th>
                  <th className="text-left p-3">Depósito</th>
                  <th className="text-right p-3">Qtd</th>
                  <th className="text-right p-3">Disp.</th>
                  <th className="text-right p-3">Ponto Rep.</th>
                </tr>
              </thead>
              <tbody>
                {itemsLoading ? (
                  <tr><td colSpan={5} className="p-4 text-center text-slate-500">Carregando...</td></tr>
                ) : (
                  stockList.map((item: any) => {
                    const isLow = item.quantity <= (item.reorderPoint ?? 10)
                    return (
                      <tr key={item.id} className={`border-b border-slate-700/50 ${isLow ? 'bg-red-500/5' : ''}`}>
                        <td className="p-3 font-mono text-sky-400">{item.sku}</td>
                        <td className="p-3 text-slate-300 font-mono text-xs">{item.warehouseId?.slice(0, 8)}</td>
                        <td className={`p-3 text-right ${isLow ? 'text-red-400 font-medium' : 'text-slate-200'}`}>{item.quantity}</td>
                        <td className="p-3 text-right text-slate-300">{item.available}</td>
                        <td className="p-3 text-right text-slate-400">{item.reorderPoint}</td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
          <div className="p-3 border-b border-slate-700">
            <h3 className="text-slate-400 text-xs uppercase tracking-wider">Movimentações</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
                  <th className="text-left p-3">Tipo</th>
                  <th className="text-left p-3">SKU</th>
                  <th className="text-right p-3">Qtd</th>
                  <th className="text-right p-3">Data</th>
                </tr>
              </thead>
              <tbody>
                {movLoading ? (
                  <tr><td colSpan={4} className="p-4 text-center text-slate-500">Carregando...</td></tr>
                ) : (movements?.stockMovements ?? []).map((m: any) => (
                  <tr key={m.id} className="border-b border-slate-700/50">
                    <td className="p-3"><StatusBadge status={m.type} /></td>
                    <td className="p-3 font-mono text-xs text-sky-400">{m.sku}</td>
                    <td className={`p-3 text-right ${m.quantity > 0 ? 'text-emerald-400' : 'text-red-400'}`}>{m.quantity > 0 ? '+' : ''}{m.quantity}</td>
                    <td className="p-3 text-right text-slate-400 text-xs">{new Date(m.timestamp).toLocaleDateString('pt-BR')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
        <div className="p-3 border-b border-slate-700 flex items-center justify-between">
          <h3 className="text-slate-400 text-xs uppercase tracking-wider">Shopee — Produtos Sincronizados</h3>
          <button
            onClick={() => { (async () => {
              try {
                await fetch('/api/shopee/sync', { method: 'POST' })
                window.location.reload()
              } catch { /* ignore */ }
            })() }}
            className="text-xs text-sky-400 hover:text-sky-300 border border-sky-500/30 px-2 py-1 rounded"
          >
            Sincronizar Agora
          </button>
        </div>
        <ShopeeProductTable />
      </div>
    </div>
  )
}

function ShopeeProductTable() {
  const { data, loading } = useQuery<{ shopeeProducts: any[] }>(SHOPEE_PRODUCTS, { pollInterval: 60000 })
  const products = data?.shopeeProducts ?? []

  const lowStock = products.filter(p => p.stock <= 5)

  return (
    <div className="overflow-x-auto">
      {lowStock.length > 0 && (
        <div className="px-3 py-2 bg-red-500/10 border-b border-red-500/20 text-xs text-red-400">
          ⚠️ {lowStock.length} produto(s) com estoque crítico (≤5)
        </div>
      )}
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
            <th className="text-left p-3">SKU</th>
            <th className="text-left p-3">Produto</th>
            <th className="text-left p-3">Status</th>
            <th className="text-right p-3">Estoque</th>
            <th className="text-right p-3">Reservado</th>
            <th className="text-right p-3">Preço</th>
            <th className="text-right p-3">Variações</th>
            <th className="text-right p-3">Última Sinc.</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr><td colSpan={8} className="p-4 text-center text-slate-500">Carregando...</td></tr>
          ) : products.length === 0 ? (
            <tr><td colSpan={8} className="p-4 text-center text-slate-500">
              Nenhum produto sincronizado. Configure as credenciais Shopee e clique em "Sincronizar Agora".
            </td></tr>
          ) : (
            products.map((p: any) => (
              <tr key={p.itemId} className={`border-b border-slate-700/50 ${p.stock <= 5 ? 'bg-red-500/5' : ''}`}>
                <td className="p-3 font-mono text-xs text-sky-400">{p.itemSku || p.itemId}</td>
                <td className="p-3 text-slate-200">{p.itemName}</td>
                <td className="p-3"><StatusBadge status={p.itemStatus} /></td>
                <td className={`p-3 text-right font-medium ${p.stock <= 5 ? 'text-red-400' : 'text-slate-200'}`}>{p.stock}</td>
                <td className="p-3 text-right text-slate-400">{p.reservedStock}</td>
                <td className="p-3 text-right text-slate-200">R$ {Number(p.price).toFixed(2)}</td>
                <td className="p-3 text-right text-slate-400">{p.hasModel ? 'Sim' : '—'}</td>
                <td className="p-3 text-right text-slate-400 text-xs">{new Date(p.lastSyncedAt).toLocaleTimeString('pt-BR')}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
