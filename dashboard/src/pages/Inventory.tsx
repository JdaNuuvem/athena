import { useQuery, useSubscription } from '@apollo/client/react'
import { STOCK_ITEMS, STOCK_MOVEMENTS } from '../graphql/queries'
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
    </div>
  )
}
