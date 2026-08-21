interface StatCardProps {
  icon: string;
  label: string;
  value: string | number;
  trend?: string;
  trendUp?: boolean;
}

export default function StatCard({ icon, label, value, trend, trendUp }: StatCardProps) {
  return (
    <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-lg">{icon}</span>
        {trend && (
          <span className={`text-xs ${trendUp ? "text-emerald-400" : "text-red-400"}`}>
            {trendUp ? "↑" : "↓"} {trend}
          </span>
        )}
      </div>
      <p className="text-xs text-neutral-400">{label}</p>
      <p className="text-sm font-semibold text-neutral-100 mt-0.5">{value}</p>
    </div>
  );
}
