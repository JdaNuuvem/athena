import { useState } from 'react'
import { useQuery, useSubscription } from '@apollo/client/react'
import { ORDERS, ORDER_DETAIL, SHOPEE_ORDERS } from '../graphql/queries'
import { ORDER_UPDATED } from '../graphql/subscriptions'
import { OrderTable } from '../components/OrderTable'
import { StatusBadge } from '../components/StatusBadge'
import { X, RefreshCw } from 'lucide-react'

export function Orders() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [channelFilter, setChannelFilter] = useState('')
  const [tab, setTab] = useState<'athena' | 'shopee'>('athena')

  const { data, loading } = useQuery<{ orders: any[] }>(ORDERS, {
    variables: { status: statusFilter || undefined, channel: channelFilter || undefined },
    pollInterval: 15000,
  })

  useSubscription(ORDER_UPDATED)

  const { data: detail, loading: detailLoading } = useQuery<{ order: any }>(ORDER_DETAIL, {
    variables: { id: selectedId! },
    skip: !selectedId,
  })

  const orders = data?.orders ?? []
  const channels = [...new Set<string>(orders.map((o: any) => o.channel))]

  const { data: shopeeData, loading: shopeeLoading } = useQuery<{ shopeeOrders: any[] }>(SHOPEE_ORDERS, { pollInterval: 30000 })

  const shopeeOrders = shopeeData?.shopeeOrders ?? []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-100">Pedidos</h2>
        <div className="flex items-center gap-2">
          {tab === 'shopee' && (
            <button
              onClick={() => { fetch('/api/shopee/orders/sync', { method: 'POST' }).then(r => r.json()).then(d => console.log(d)) }}
              className="flex items-center gap-1 text-xs text-sky-400 border border-sky-500/30 px-2 py-1 rounded hover:bg-sky-500/10"
            >
              <RefreshCw size={12} /> Sincronizar
            </button>
          )}
          <span className="text-xs text-slate-400">{tab === 'athena' ? orders.length : shopeeOrders.length} pedidos</span>
        </div>
      </div>

      <div className="flex gap-1 border-b border-slate-700">
        <button onClick={() => setTab('athena')} className={`px-3 py-1.5 text-sm rounded-t-md transition-colors ${tab === 'athena' ? 'bg-slate-800 text-sky-400 border border-b-0 border-slate-700' : 'text-slate-400 hover:text-slate-200'}`}>ATHENA</button>
        <button onClick={() => setTab('shopee')} className={`px-3 py-1.5 text-sm rounded-t-md transition-colors ${tab === 'shopee' ? 'bg-slate-800 text-sky-400 border border-b-0 border-slate-700' : 'text-slate-400 hover:text-slate-200'}`}>Shopee</button>
      </div>

      {tab === 'athena' ? (
        <div className="space-y-4">
          <div className="flex gap-2 flex-wrap">
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="bg-slate-800 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-slate-300">
              <option value="">Todos os status</option>
              {['draft', 'confirmed', 'in_production', 'shipped', 'delivered', 'cancelled'].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <select value={channelFilter} onChange={e => setChannelFilter(e.target.value)} className="bg-slate-800 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-slate-300">
              <option value="">Todos os canais</option>
              {channels.map((c: string) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          <OrderTable orders={orders} loading={loading} onSelect={o => setSelectedId(o.id)} />

          {selectedId && (
            <div className="fixed inset-0 z-50 flex justify-end">
              <div className="absolute inset-0 bg-black/50" onClick={() => setSelectedId(null)} />
              <div className="relative w-full max-w-lg bg-slate-900 border-l border-slate-700 h-full overflow-y-auto">
                <div className="sticky top-0 bg-slate-900 border-b border-slate-700 p-4 flex items-center justify-between">
                  <h3 className="text-slate-100 font-medium">Pedido {selectedId.slice(0, 8)}</h3>
                  <button onClick={() => setSelectedId(null)} className="text-slate-400 hover:text-slate-200"><X size={20} /></button>
                </div>
                {detailLoading ? (
                  <div className="p-4 space-y-3 animate-pulse">
                    <div className="h-4 bg-slate-700 rounded w-3/4" />
                    <div className="h-4 bg-slate-700 rounded w-1/2" />
                    <div className="h-20 bg-slate-700 rounded" />
                  </div>
                ) : detail?.order ? (
                  <div className="p-4 space-y-4">
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div><span className="text-slate-400">Status:</span> <StatusBadge status={detail.order.status} /></div>
                      <div><span className="text-slate-400">Canal:</span> <span className="text-slate-200 capitalize">{detail.order.channel}</span></div>
                    </div>
                    {detail.order.customer && (
                      <div><h4 className="text-slate-400 text-xs uppercase tracking-wider mb-2">Cliente</h4>
                        <div className="text-sm text-slate-200 space-y-1">
                          <p className="font-medium">{detail.order.customer.name}</p>
                          <p className="text-slate-400">{detail.order.customer.email}</p>
                        </div>
                      </div>
                    )}
                    <div><h4 className="text-slate-400 text-xs uppercase tracking-wider mb-2">Itens</h4>
                      <div className="space-y-2">{detail.order.items?.map((item: any, i: number) => (
                        <div key={i} className="flex justify-between text-sm bg-slate-800 rounded p-2">
                          <span className="text-slate-200 font-mono">{item.sku}</span>
                          <span className="text-slate-400">{item.quantity}x</span>
                          <span className="text-slate-200">{(item.unitPrice * item.quantity).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</span>
                        </div>
                      ))}</div>
                    </div>
                    {detail.order.totals && (
                      <div><h4 className="text-slate-400 text-xs uppercase tracking-wider mb-2">Totais</h4>
                        <div className="text-sm text-slate-300 space-y-1 bg-slate-800 rounded p-3">
                          <div className="flex justify-between"><span>Subtotal</span><span>{detail.order.totals.subtotal?.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</span></div>
                          <div className="flex justify-between"><span>Frete</span><span>{detail.order.totals.shipping?.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</span></div>
                          <div className="flex justify-between font-bold text-slate-100 border-t border-slate-700 pt-1 mt-1"><span>Total</span><span>{detail.order.totals.grandTotal?.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</span></div>
                        </div>
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
          {shopeeLoading ? (
            <div className="animate-pulse p-4 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-10 bg-slate-700 rounded" />)}
            </div>
          ) : shopeeOrders.length === 0 ? (
            <div className="p-8 text-center text-slate-500">Nenhum pedido Shopee importado. Configure as credenciais e clique em "Sincronizar".</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
                    <th className="text-left p-3">Order SN</th>
                    <th className="text-left p-3">Comprador</th>
                    <th className="text-left p-3">Status</th>
                    <th className="text-left p-3">Transportadora</th>
                    <th className="text-right p-3">Total</th>
                    <th className="text-right p-3">Itens</th>
                    <th className="text-right p-3">Data</th>
                  </tr>
                </thead>
                <tbody>
                  {shopeeOrders.map((o: any) => (
                    <tr key={o.orderSn} className="border-b border-slate-700/50">
                      <td className="p-3 font-mono text-xs text-sky-400">{o.orderSn}</td>
                      <td className="p-3 text-slate-200">{o.buyer}</td>
                      <td className="p-3"><StatusBadge status={o.orderStatus} /></td>
                      <td className="p-3 text-slate-400 text-xs">{o.shippingCarrier || '—'}</td>
                      <td className="p-3 text-right text-slate-200">{o.totalAmount.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</td>
                      <td className="p-3 text-right text-slate-400">{(o.items || []).length}</td>
                      <td className="p-3 text-right text-slate-400 text-xs">{o.orderedAt ? new Date(o.orderedAt).toLocaleDateString('pt-BR') : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
