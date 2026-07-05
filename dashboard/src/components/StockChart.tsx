import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface StockChartProps {
  data: { name: string; quantity: number; available: number }[]
  loading?: boolean
}

export function StockChart({ data, loading }: StockChartProps) {
  if (loading) {
    return <div className="h-64 bg-slate-800 rounded-lg animate-pulse" />
  }
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
      <h3 className="text-slate-400 text-xs uppercase tracking-wider mb-3">Estoque por Produto</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} />
          <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
          <Tooltip
            contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '6px', fontSize: 12 }}
            labelStyle={{ color: '#e2e8f0' }}
          />
          <Bar dataKey="quantity" fill="#38bdf8" radius={[4, 4, 0, 0]} name="Quantidade" />
          <Bar dataKey="available" fill="#22c55e" radius={[4, 4, 0, 0]} name="Disponível" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
