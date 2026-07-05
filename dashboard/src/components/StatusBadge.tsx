const statusColors: Record<string, string> = {
  active: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  running: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  completed: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
  delivered: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
  pending: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  scheduled: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  draft: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
  cancelled: 'bg-red-500/20 text-red-400 border-red-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  error: 'bg-red-500/20 text-red-400 border-red-500/30',
  low_stock: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  in_production: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
  maintenance: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  shipped: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  idle: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
}

interface StatusBadgeProps {
  status: string
  label?: string
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const color = statusColors[status] ?? 'bg-slate-500/20 text-slate-400 border-slate-500/30'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${color}`}>
      {label ?? status}
    </span>
  )
}
