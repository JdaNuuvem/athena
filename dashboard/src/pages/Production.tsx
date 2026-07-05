import { useQuery, useSubscription } from '@apollo/client/react'
import { PRODUCTION_RUNS } from '../graphql/queries'
import { PRODUCTION_PROGRESS } from '../graphql/subscriptions'
import { OEEGauge } from '../components/OEEGauge'
import { StatusBadge } from '../components/StatusBadge'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

export function Production() {
  const { data, loading } = useQuery<{ productionRuns: any[] }>(PRODUCTION_RUNS, { pollInterval: 15000 })
  useSubscription(PRODUCTION_PROGRESS)

  const runs = data?.productionRuns ?? []
  const avgOee = runs.length ? runs.reduce((sum: number, r: any) => sum + (r.oee ?? 0), 0) / runs.length : 0
  const avgDefect = runs.length ? runs.reduce((sum: number, r: any) => sum + (r.totalDefectives / Math.max(r.totalPartsProduced, 1)) * 100, 0) / runs.length : 0

  const defectData = runs.map((r: any) => ({
    name: r.id?.slice(0, 6),
    produzido: r.totalPartsProduced,
    defeitos: r.totalDefectives,
  }))

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-100">Produção</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <OEEGauge value={avgOee} loading={loading} />
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 flex flex-col justify-center">
          <span className="text-slate-400 text-xs uppercase tracking-wider">Runs Ativos</span>
          <span className="text-3xl font-bold text-slate-100 mt-1">
            {loading ? '—' : runs.filter((r: any) => r.status !== 'completed').length}
          </span>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 flex flex-col justify-center">
          <span className="text-slate-400 text-xs uppercase tracking-wider">Taxa de Defeitos</span>
          <span className={`text-3xl font-bold mt-1 ${avgDefect > 5 ? 'text-red-400' : 'text-emerald-400'}`}>
            {loading ? '—' : `${avgDefect.toFixed(1)}%`}
          </span>
        </div>
      </div>

      <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
        <h3 className="text-slate-400 text-xs uppercase tracking-wider mb-3">Produção vs Defeitos</h3>
        {loading ? (
          <div className="h-48 animate-pulse bg-slate-700 rounded" />
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={defectData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '6px', fontSize: 12 }} />
              <Bar dataKey="produzido" fill="#38bdf8" radius={[4, 4, 0, 0]} name="Produzido" />
              <Bar dataKey="defeitos" fill="#ef4444" radius={[4, 4, 0, 0]} name="Defeitos" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
        <div className="p-3 border-b border-slate-700">
          <h3 className="text-slate-400 text-xs uppercase tracking-wider">Production Runs</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
                <th className="text-left p-3">Run ID</th>
                <th className="text-left p-3">Máquina</th>
                <th className="text-left p-3">Produto</th>
                <th className="text-left p-3">Status</th>
                <th className="text-right p-3">Produzido</th>
                <th className="text-right p-3">Defeitos</th>
                <th className="text-right p-3">OEE</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="p-4 text-center text-slate-500">Carregando...</td></tr>
              ) : runs.map((r: any) => (
                <tr key={r.id} className="border-b border-slate-700/50">
                  <td className="p-3 font-mono text-xs text-sky-400">{r.id?.slice(0, 8)}</td>
                  <td className="p-3 text-slate-300 font-mono text-xs">{r.machineId?.slice(0, 8)}</td>
                  <td className="p-3 text-slate-300 font-mono text-xs">{r.productId?.slice(0, 8)}</td>
                  <td className="p-3"><StatusBadge status={r.status} /></td>
                  <td className="p-3 text-right text-slate-200">{r.totalPartsProduced}</td>
                  <td className="p-3 text-right text-red-400">{r.totalDefectives}</td>
                  <td className="p-3 text-right text-slate-200">{(r.oee ?? 0).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
