import { useState, useMemo } from 'react'
import { useQuery, useSubscription } from '@apollo/client/react'
import { STOCK_ITEMS, STOCK_MOVEMENTS, SHOPEE_PRODUCTS } from '../graphql/queries'
import { INVENTORY_CHANGED } from '../graphql/subscriptions'
import { StockChart } from '../components/StockChart'
import { StatusBadge } from '../components/StatusBadge'
import { AlertTriangle, Warehouse, PackageOpen, BarChart3, ArrowDownUp } from 'lucide-react'

const WAREHOUSE_ALIASES: Record<string, string> = {
  'wh-main': 'Centro de Distribuição',
  'wh-south': 'Filial Sul',
  'wh-north': 'Filial Norte',
  'wh-express': 'Dark Store Express',
}

function warehouseLabel(id: string) {
  return WAREHOUSE_ALIASES[id] ?? id.slice(0, 8)
}

function warehouseColor(id: string) {
  const map: Record<string, string> = {
    'wh-main': 'bg-sky-500/10 text-sky-400 border-sky-500/30',
    'wh-south': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    'wh-north': 'bg-violet-500/10 text-violet-400 border-violet-500/30',
    'wh-express': 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  }
  return map[id] ?? 'bg-slate-500/10 text-slate-400 border-slate-500/30'
}

export function Inventory() {
  const { data: items, loading: itemsLoading } = useQuery<{ stockItems: any[] }>(STOCK_ITEMS, { pollInterval: 30000 })
  const { data: movements, loading: movLoading } = useQuery<{ stockMovements: any[] }>(STOCK_MOVEMENTS)
  useSubscription(INVENTORY_CHANGED)

  const [selectedWh, setSelectedWh] = useState<string>('all')

  const stockList = items?.stockItems ?? []
  const lowStock = stockList.filter((s: any) => s.quantity <= (s.reorderPoint ?? 10))

  const warehouses = useMemo(() => {
    const whs = new Map<string, { total: number; available: number; low: number; skus: number; items: any[] }>()
    for (const item of stockList) {
      const wid = item.warehouseId ?? 'unknown'
      if (!whs.has(wid)) whs.set(wid, { total: 0, available: 0, low: 0, skus: 0, items: [] })
      const w = whs.get(wid)!
      w.total += item.quantity
      w.available += item.available ?? item.quantity - (item.reserved ?? 0)
      w.skus += 1
      if (item.quantity <= (item.reorderPoint ?? 10)) w.low += 1
      w.items.push(item)
    }
    return whs
  }, [stockList])

  const filtered = selectedWh === 'all' ? stockList : stockList.filter(s => s.warehouseId === selectedWh)

  const chartData = useMemo(() => {
    if (selectedWh === 'all') {
      return Array.from(warehouses.entries()).map(([wh, data]) => ({
        name: warehouseLabel(wh), quantity: data.total, available: data.available,
      }))
    }
    return filtered.map(s => ({ name: s.sku, quantity: s.quantity, available: s.available ?? s.quantity }))
  }, [selectedWh, warehouses, filtered])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-100">Estoque Multiloja</h2>
        <select
          className="bg-slate-800 border border-slate-600 text-slate-200 text-sm rounded px-3 py-1.5"
          value={selectedWh}
          onChange={e => setSelectedWh(e.target.value)}
        >
          <option value="all">Todas as lojas</option>
          {Array.from(warehouses.keys()).map(wh => (
            <option key={wh} value={wh}>{warehouseLabel(wh)}</option>
          ))}
        </select>
      </div>

      {/* Warehouse summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {Array.from(warehouses.entries()).map(([wh, data]) => (
          <button
            key={wh}
            onClick={() => setSelectedWh(wh === selectedWh ? 'all' : wh)}
            className={`text-left border rounded-lg p-3 transition-colors ${wh === selectedWh ? 'ring-2 ring-sky-400' : ''} ${warehouseColor(wh)}`}
          >
            <div className="flex items-center gap-2 mb-2">
              <Warehouse size={14} />
              <span className="text-xs font-medium">{warehouseLabel(wh)}</span>
            </div>
            <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-xs">
              <span>Estoque</span><span className="text-right font-bold">{data.total}</span>
              <span>Disponível</span><span className="text-right">{data.available}</span>
              <span>SKUs</span><span className="text-right">{data.skus}</span>
              <span className={data.low > 0 ? 'text-amber-600 dark:text-amber-400' : ''}>Baixo</span>
              <span className={`text-right ${data.low > 0 ? 'font-bold text-amber-600 dark:text-amber-400' : ''}`}>{data.low}</span>
            </div>
          </button>
        ))}
      </div>

      {/* Low stock alert */}
      {lowStock.length > 0 && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 flex items-start gap-3">
          <AlertTriangle size={18} className="text-amber-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-amber-400 text-sm font-medium">Alerta de Estoque Baixo ({lowStock.length})</p>
            <p className="text-amber-400/70 text-xs mt-0.5">
              {lowStock.map(s => `${s.sku}@${warehouseLabel(s.warehouseId)} (${s.quantity} un.)`).join(' · ')}
            </p>
          </div>
        </div>
      )}

      {/* Chart — warehouse aggregate or per-SKU */}
      <StockChart data={chartData} loading={itemsLoading} />

      {/* Main tables */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Stock items — takes 2/3 width */}
        <div className="lg:col-span-2 bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
          <div className="p-3 border-b border-slate-700 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <PackageOpen size={14} className="text-slate-400" />
              <h3 className="text-slate-400 text-xs uppercase tracking-wider">Itens em Estoque</h3>
            </div>
            <span className="text-xs text-slate-500">{filtered.length} SKUs</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
                  <th className="text-left p-3">SKU</th>
                  <th className="text-left p-3">Loja / Depósito</th>
                  <th className="text-right p-3">Qtd</th>
                  <th className="text-right p-3">Reservado</th>
                  <th className="text-right p-3">Disp.</th>
                  <th className="text-right p-3">Ponto Rep.</th>
                  <th className="text-center p-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {itemsLoading ? (
                  <tr><td colSpan={7} className="p-4 text-center text-slate-500">Carregando...</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={7} className="p-4 text-center text-slate-500">Nenhum item cadastrado</td></tr>
                ) : (
                  filtered.map((item: any) => {
                    const isLow = item.quantity <= (item.reorderPoint ?? 10)
                    const avail = item.available ?? item.quantity - (item.reserved ?? 0)
                    return (
                      <tr key={`${item.id}-${item.warehouseId}`} className={`border-b border-slate-700/50 ${isLow ? 'bg-red-500/5' : ''}`}>
                        <td className="p-3 font-mono text-sky-400">{item.sku}</td>
                        <td className="p-3">
                          <span className={`text-xs px-2 py-0.5 rounded border ${warehouseColor(item.warehouseId)}`}>
                            {warehouseLabel(item.warehouseId)}
                          </span>
                        </td>
                        <td className={`p-3 text-right font-mono ${isLow ? 'text-red-400 font-bold' : 'text-slate-200'}`}>{item.quantity}</td>
                        <td className="p-3 text-right text-slate-400 font-mono">{item.reserved ?? 0}</td>
                        <td className="p-3 text-right font-mono text-slate-200">{avail}</td>
                        <td className="p-3 text-right text-slate-400 font-mono">{item.reorderPoint ?? '—'}</td>
                        <td className="p-3 text-center">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${isLow ? 'bg-red-500/20 text-red-400' : avail === 0 ? 'bg-slate-500/20 text-slate-400' : 'bg-emerald-500/20 text-emerald-400'}`}>
                            {isLow ? 'BAIXO' : avail === 0 ? 'ZERADO' : 'OK'}
                          </span>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Movements sidebar — 1/3 width */}
        <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
          <div className="p-3 border-b border-slate-700 flex items-center gap-2">
            <ArrowDownUp size={14} className="text-slate-400" />
            <h3 className="text-slate-400 text-xs uppercase tracking-wider">Movimentações</h3>
          </div>
          <div className="overflow-y-auto max-h-[500px]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase sticky top-0 bg-slate-800">
                  <th className="text-left p-3">Tipo</th>
                  <th className="text-left p-3">SKU</th>
                  <th className="text-right p-3">Qtd</th>
                </tr>
              </thead>
              <tbody>
                {movLoading ? (
                  <tr><td colSpan={3} className="p-4 text-center text-slate-500">Carregando...</td></tr>
                ) : ((movements?.stockMovements ?? []) as any[]).map((m: any, i: number) => (
                  <tr key={m.id ?? i} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="p-3"><StatusBadge status={m.type} /></td>
                    <td className="p-3 font-mono text-xs text-sky-400">{m.sku}</td>
                    <td className={`p-3 text-right font-mono text-xs ${m.quantity > 0 ? 'text-emerald-400' : 'text-red-400'}`}>{m.quantity > 0 ? '+' : ''}{m.quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Shopee sync section */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
        <div className="p-3 border-b border-slate-700 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 size={14} className="text-slate-400" />
            <h3 className="text-slate-400 text-xs uppercase tracking-wider">Shopee — Produtos Sincronizados</h3>
          </div>
          <button
            onClick={() => {
              fetch('/api/shopee/sync', { method: 'POST' }).finally(() => window.location.reload())
            }}
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
        <div className="px-3 py-2 bg-red-500/10 border-b border-red-500/20 text-xs text-red-400 flex items-center gap-2">
          <AlertTriangle size={12} />
          {lowStock.length} produto(s) com estoque crítico (≤5)
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
                <td className="p-3 text-slate-200 max-w-[200px] truncate">{p.itemName}</td>
                <td className="p-3"><StatusBadge status={p.itemStatus} /></td>
                <td className={`p-3 text-right font-mono font-medium ${p.stock <= 5 ? 'text-red-400' : 'text-slate-200'}`}>{p.stock}</td>
                <td className="p-3 text-right text-slate-400 font-mono">{p.reservedStock}</td>
                <td className="p-3 text-right text-slate-200 font-mono">R$ {Number(p.price).toFixed(2)}</td>
                <td className="p-3 text-center text-slate-400">{p.hasModel ? 'Sim' : '—'}</td>
                <td className="p-3 text-right text-slate-400 text-xs">{new Date(p.lastSyncedAt).toLocaleTimeString('pt-BR')}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
