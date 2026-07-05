interface KPICardProps {
  title: string
  value: string
  delta?: { value: string; positive: boolean }
  icon: React.ReactNode
}

export function KPICard({ title, value, delta, icon }: KPICardProps) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-slate-400 text-xs uppercase tracking-wider">{title}</span>
        <span className="text-sky-400">{icon}</span>
      </div>
      <span className="text-2xl font-bold text-slate-100">{value}</span>
      {delta && (
        <span className={`text-xs ${delta.positive ? 'text-emerald-400' : 'text-red-400'}`}>
          {delta.positive ? '↑' : '↓'} {delta.value}
        </span>
      )}
    </div>
  )
}
