import { useQuery } from '@apollo/client/react'
import { CUSTOMERS } from '../graphql/queries'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'

const TIER_COLORS: Record<string, string> = {
  bronze: '#cd7f32',
  prata: '#c0c0c0',
  silver: '#c0c0c0',
  ouro: '#ffd700',
  gold: '#ffd700',
  diamante: '#b9f2ff',
  diamond: '#b9f2ff',
}

export function Customers() {
  const { data, loading } = useQuery<{ customers: any[] }>(CUSTOMERS, { pollInterval: 60000 })

  const customers = data?.customers ?? []

  const tierCounts: Record<string, number> = {}
  customers.forEach((c: any) => {
    tierCounts[c.tier] = (tierCounts[c.tier] ?? 0) + 1
  })
  const tierData = Object.entries(tierCounts).map(([name, value]) => ({
    name,
    value,
    color: TIER_COLORS[name] ?? '#64748b',
  }))

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-100">Clientes</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <h3 className="text-slate-400 text-xs uppercase tracking-wider mb-3">Tiers</h3>
          {loading ? (
            <div className="h-48 animate-pulse bg-slate-700 rounded" />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={tierData} cx="50%" cy="50%" innerRadius={40} outerRadius={70} paddingAngle={3} dataKey="value">
                    {tierData.map((entry: any, i: number) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '6px', fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap gap-2 mt-2">
                {tierData.map(d => (
                  <div key={d.name} className="flex items-center gap-1 text-xs text-slate-400">
                    <span className="w-2 h-2 rounded-full" style={{ background: d.color }} />
                    {d.name} ({d.value})
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="lg:col-span-2 bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
          <div className="p-3 border-b border-slate-700">
            <h3 className="text-slate-400 text-xs uppercase tracking-wider">Todos os Clientes</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
                  <th className="text-left p-3">Nome</th>
                  <th className="text-left p-3">Email</th>
                  <th className="text-left p-3">Telefone</th>
                  <th className="text-left p-3">Tier</th>
                  <th className="text-left p-3">Origem</th>
                  <th className="text-right p-3">Pedidos</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={6} className="p-4 text-center text-slate-500">Carregando...</td></tr>
                ) : customers.map((c: any) => (
                  <tr key={c.id} className="border-b border-slate-700/50">
                    <td className="p-3 text-slate-200 font-medium">{c.name}</td>
                    <td className="p-3 text-slate-400 text-xs">{c.email}</td>
                    <td className="p-3 text-slate-400 text-xs">{c.phone ?? '—'}</td>
                    <td className="p-3">
                      <span className="text-xs capitalize" style={{ color: TIER_COLORS[c.tier] ?? '#94a3b8' }}>
                        {c.tier}
                      </span>
                    </td>
                    <td className="p-3 text-slate-400 text-xs capitalize">{c.channelOrigin}</td>
                    <td className="p-3 text-right text-slate-200">{c.totalOrders}</td>
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
