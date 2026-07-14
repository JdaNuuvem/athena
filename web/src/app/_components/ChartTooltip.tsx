interface ChartTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number; name: string }>;
  label?: string;
  formatter?: (value: number) => string;
}

export function ChartTooltip({ active, payload, label, formatter }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;
  const fmt = formatter ?? ((v: number) => `R$ ${v.toLocaleString("pt-BR")}`);
  return (
    <div className="bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2 text-xs shadow-lg">
      <div className="text-neutral-400 mb-1">{label}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex justify-between gap-4">
          <span className="text-neutral-400">{p.name}:</span>
          <span className="text-neutral-200 font-mono">{fmt(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

export default ChartTooltip;
