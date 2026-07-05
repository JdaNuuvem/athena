interface OEEGaugeProps {
  value: number
  loading?: boolean
}

export function OEEGauge({ value, loading }: OEEGaugeProps) {
  if (loading) {
    return <div className="h-32 bg-slate-800 rounded-lg animate-pulse" />
  }

  const pct = Math.min(Math.max(value, 0), 100)
  const color = pct >= 85 ? '#22c55e' : pct >= 70 ? '#f59e0b' : '#ef4444'
  const circumference = 2 * Math.PI * 54
  const offset = circumference - (pct / 100) * circumference

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 flex flex-col items-center">
      <h3 className="text-slate-400 text-xs uppercase tracking-wider mb-2">OEE</h3>
      <div className="relative w-32 h-32">
        <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
          <circle cx="60" cy="60" r="54" fill="none" stroke="#1e293b" strokeWidth="10" />
          <circle
            cx="60" cy="60" r="54" fill="none" stroke={color} strokeWidth="10"
            strokeDasharray={circumference} strokeDashoffset={offset}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-bold text-slate-100">{pct.toFixed(1)}%</span>
        </div>
      </div>
    </div>
  )
}
