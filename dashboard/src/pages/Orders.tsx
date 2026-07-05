import { useState } from 'react'
import { useQuery, useSubscription } from '@apollo/client/react'
import { ORDERS, ORDER_DETAIL } from '../graphql/queries'
import { ORDER_UPDATED } from '../graphql/subscriptions'
import { OrderTable } from '../components/OrderTable'
import { StatusBadge } from '../components/StatusBadge'
import { X } from 'lucide-react'

export function Orders() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [channelFilter, setChannelFilter] = useState('')

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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-100">Pedidos</h2>
        <span className="text-xs text-slate-400">{orders.length} pedidos</span>
      </div>

      <div className="flex gap-2 flex-wrap">
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="bg-slate-800 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-slate-300"
        >
          <option value="">Todos os status</option>
          {['draft', 'confirmed', 'in_production', 'shipped', 'delivered', 'cancelled'].map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={channelFilter}
          onChange={e => setChannelFilter(e.target.value)}
          className="bg-slate-800 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-slate-300"
        >
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
              <button onClick={() => setSelectedId(null)} className="text-slate-400 hover:text-slate-200">
                <X size={20} />
              </button>
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

                <div>
                  <h4 className="text-slate-400 text-xs uppercase tracking-wider mb-2">Cliente</h4>
                  <div className="text-sm text-slate-200 space-y-1">
                    <p className="font-medium">{detail.order.customer?.name}</p>
                    <p className="text-slate-400">{detail.order.customer?.email}</p>
                    <p className="text-slate-400">Tier: {detail.order.customer?.tier}</p>
                  </div>
                </div>

                <div>
                  <h4 className="text-slate-400 text-xs uppercase tracking-wider mb-2">Itens</h4>
                  <div className="space-y-2">
                    {detail.order.items?.map((item: any, i: number) => (
                      <div key={i} className="flex justify-between text-sm bg-slate-800 rounded p-2">
                        <span className="text-slate-200 font-mono">{item.sku}</span>
                        <span className="text-slate-400">{item.quantity}x</span>
                        <span className="text-slate-200">{(item.unitPrice * item.quantity).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 className="text-slate-400 text-xs uppercase tracking-wider mb-2">Totais</h4>
                  <div className="text-sm text-slate-300 space-y-1 bg-slate-800 rounded p-3">
                    <div className="flex justify-between"><span>Subtotal</span><span>{detail.order.totals?.subtotal?.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</span></div>
                    <div className="flex justify-between"><span>Frete</span><span>{detail.order.totals?.shipping?.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</span></div>
                    <div className="flex justify-between"><span>Desconto</span><span>{detail.order.totals?.discount?.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</span></div>
                    <div className="flex justify-between font-bold text-slate-100 border-t border-slate-700 pt-1 mt-1"><span>Total</span><span>{detail.order.totals?.grandTotal?.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</span></div>
                  </div>
                </div>

                {detail.order.fulfillment && (
                  <div>
                    <h4 className="text-slate-400 text-xs uppercase tracking-wider mb-2">Fulfillment</h4>
                    <div className="text-sm text-slate-300 space-y-1 bg-slate-800 rounded p-3">
                      <div className="flex justify-between"><span>Status</span><StatusBadge status={detail.order.fulfillment.status} /></div>
                      <div className="flex justify-between"><span>Transportadora</span><span>{detail.order.fulfillment.carrierId ?? '—'}</span></div>
                      <div className="flex justify-between"><span>Rastreio</span><span className="font-mono text-sky-400">{detail.order.fulfillment.trackingCode ?? '—'}</span></div>
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
