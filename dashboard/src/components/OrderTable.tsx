interface OrderTableProps {
  orders: any[]
  onSelect?: (order: any) => void
  loading?: boolean
}

export function OrderTable({ orders, onSelect, loading }: OrderTableProps) {
  if (loading) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
        <div className="animate-pulse p-4 space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-10 bg-slate-700 rounded" />
          ))}
        </div>
      </div>
    )
  }

  const statusColors: Record<string, string> = {
    draft: 'text-slate-400',
    confirmed: 'text-sky-400',
    in_production: 'text-violet-400',
    shipped: 'text-cyan-400',
    delivered: 'text-emerald-400',
    cancelled: 'text-red-400',
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
              <th className="text-left p-3">Pedido</th>
              <th className="text-left p-3">Cliente</th>
              <th className="text-left p-3">Canal</th>
              <th className="text-left p-3">Status</th>
              <th className="text-right p-3">Total</th>
              <th className="text-right p-3">Data</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order: any) => (
              <tr
                key={order.id}
                className="border-b border-slate-700/50 hover:bg-slate-700/30 cursor-pointer transition-colors"
                onClick={() => onSelect?.(order)}
              >
                <td className="p-3 font-mono text-sky-400">{order.id?.slice(0, 8)}</td>
                <td className="p-3 text-slate-200">{order.customer?.name ?? '—'}</td>
                <td className="p-3 text-slate-400 capitalize">{order.channel}</td>
                <td className="p-3">
                  <span className={`text-xs font-medium ${statusColors[order.status] ?? 'text-slate-400'}`}>
                    {order.status}
                  </span>
                </td>
                <td className="p-3 text-right text-slate-200">
                  {order.totals?.grandTotal?.toLocaleString('pt-BR', { style: 'currency', currency: order.totals?.currency ?? 'BRL' })}
                </td>
                <td className="p-3 text-right text-slate-400 text-xs">
                  {new Date(order.createdAt).toLocaleDateString('pt-BR')}
                </td>
              </tr>
            ))}
            {orders.length === 0 && (
              <tr>
                <td colSpan={6} className="p-8 text-center text-slate-500">Nenhum pedido encontrado</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
