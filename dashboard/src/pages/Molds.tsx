import { useQuery, useSubscription } from '@apollo/client/react'
import { MOLDS } from '../graphql/queries'
import { MOLD_STATUS_CHANGED } from '../graphql/subscriptions'
import { StatusBadge } from '../components/StatusBadge'
import { Drill, RotateCw } from 'lucide-react'

export function Molds() {
  const { data, loading } = useQuery<{ molds: any[] }>(MOLDS, { pollInterval: 30000 })
  useSubscription(MOLD_STATUS_CHANGED)

  const molds = data?.molds ?? []

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-100">Moldes & CNC</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-40 bg-slate-800 rounded-lg animate-pulse" />
          ))
        ) : molds.map((mold: any) => {
          const usagePct = mold.cycleLife > 0 ? (mold.currentCycles / mold.cycleLife) * 100 : 0
          return (
            <div key={mold.id} className="bg-slate-800 border border-slate-700 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-sky-400">{mold.moldCode}</span>
                <StatusBadge status={mold.status} />
              </div>
              <div className="space-y-1 text-xs text-slate-400">
                <div className="flex items-center gap-2">
                  <Drill size={12} /> {mold.steelType} — {mold.cavityCount} cavidades
                </div>
                <div className="flex items-center gap-2">
                  <RotateCw size={12} /> {mold.currentCycles}/{mold.cycleLife} ciclos
                </div>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-1.5">
                <div
                  className="h-1.5 rounded-full transition-all"
                  style={{
                    width: `${usagePct}%`,
                    background: usagePct > 80 ? '#ef4444' : usagePct > 60 ? '#f59e0b' : '#22c55e',
                  }}
                />
              </div>
              {mold.installedMachineId && (
                <p className="text-[10px] text-slate-500">Máquina: {mold.installedMachineId.slice(0, 8)}</p>
              )}
            </div>
          )
        })}
        {!loading && molds.length === 0 && (
          <p className="text-slate-500 col-span-full text-center py-8">Nenhum molde cadastrado</p>
        )}
      </div>
    </div>
  )
}
