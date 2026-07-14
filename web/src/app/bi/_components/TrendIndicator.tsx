interface TrendIndicatorProps {
  tendencia: "up" | "down" | "stable";
  valor: number;
}

export default function TrendIndicator({ tendencia, valor }: TrendIndicatorProps) {
  const color = tendencia === "up" ? "text-emerald-400" : tendencia === "down" ? "text-red-400" : "text-neutral-400";
  const icon = tendencia === "up" ? "▲" : tendencia === "down" ? "▼" : "—";
  return (
    <span className={`text-[10px] font-medium ${color}`}>
      {icon} {Math.abs(valor).toFixed(1)}%
    </span>
  );
}
