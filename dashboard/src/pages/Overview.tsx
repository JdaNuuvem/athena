import { useQuery } from '@apollo/client/react'
import { KPI_SUMMARY, ORDERS_BY_STATUS, RECENT_ORDERS } from '../graphql/queries'
import { KPICard } from '../components/KPICard'
import { OrderTable } from '../components/OrderTable'
import { Package, DollarSign, Factory, AlertTriangle, Gauge, Truck } from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'

const STATUS_COLORS: Record<string, string> = {
  draft: '#64748b',
  confirmed: '#38bdf8',
  in_production: '#a78bfa',
  shipped: '#22d3ee',
  delivered: '#22c55e',
  cancelled: '#ef4444',
}

export function Overview() {
  const { data: kpi, loading: kpiLoading } = useQuery<{ kpiSummary: any }>(KPI_SUMMARY, { pollInterval: 30000 })
  const { data: status, loading: statusLoading } = useQuery<{ ordersByStatus: any[] }>(ORDERS_BY_STATUS)
  const { data: orders, loading: ordersLoading } = useQuery<{ orders: any[] }>(RECENT_ORDERS)

  const s = kpi?.kpiSummary

  const pieData = (status?.ordersByStatus ?? []).map((o: any) => ({
    name: o.status,
    value: o.count,
    color: STATUS_COLORS[o.status] ?? '#64748b',
  }))

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-100">Overview</h2>

      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
        {kpiLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-24 bg-slate-800 rounded-lg animate-pulse" />
          ))
        ) : (
          <>
            <KPICard title="Pedidos" value={String(s?.totalOrders ?? 0)} icon={<Package size={16} />} />
            <KPICard title="Receita" value={(s?.totalRevenue ?? 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })} icon={<DollarSign size={16} />} />
            <KPICard title="Produção" value={String(s?.totalProduction ?? 0)} icon={<Factory size={16} />} />
            <KPICard title="Defeitos" value={`${(s?.defectRate ?? 0).toFixed(1)}%`} icon={<AlertTriangle size={16} />} />
            <KPICard title="OEE" value={`${(s?.oee ?? 0).toFixed(1)}%`} icon={<Gauge size={16} />} />
            <KPICard title="Entrega" value={`${(s?.shippingOnTimeRate ?? 0).toFixed(1)}%`} icon={<Truck size={16} />} />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <h3 className="text-slate-400 text-xs uppercase tracking-wider mb-3">Pedidos por Status</h3>
          {statusLoading ? (
            <div className="h-48 animate-pulse bg-slate-700 rounded" />
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3} dataKey="value">
                  {pieData.map((entry: any, i: number) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '6px', fontSize: 12 }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
          <div className="flex flex-wrap gap-2 mt-2">
            {pieData.map((d: any) => (
              <div key={d.name} className="flex items-center gap-1 text-xs text-slate-400">
                <span className="w-2 h-2 rounded-full" style={{ background: d.color }} />
                {d.name} ({d.value})
              </div>
            ))}
          </div>
        </div>

        <div className="lg:col-span-2">
          <h3 className="text-slate-400 text-xs uppercase tracking-wider mb-2">Pedidos Recentes</h3>
          <OrderTable orders={orders?.orders ?? []} loading={ordersLoading} />
        </div>
      </div>
    </div>
  )
}
