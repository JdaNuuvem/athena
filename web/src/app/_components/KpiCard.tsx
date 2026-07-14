import type { KpiMetric } from "@/lib/types/ui";

interface KpiCardProps {
  metric: KpiMetric;
}

export default function KpiCard({ metric }: KpiCardProps) {
  return (
    <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
      <p className="text-xs text-neutral-500">{metric.label}</p>
      <p className={`text-xl font-bold ${metric.color ?? "text-neutral-100"}`}>{metric.value}</p>
      {metric.sub && <p className="text-[10px] text-neutral-600 mt-0.5">{metric.sub}</p>}
    </div>
  );
}
