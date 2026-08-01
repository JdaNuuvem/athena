interface TrendIndicatorProps {
  tendencia: "up" | "down" | "stable";
  valor: number;
}

function TrendIcon({ tendencia }: { tendencia: "up" | "down" | "stable" }) {
  const d =
    tendencia === "up" ? "M12 19V5M5 12l7-7 7 7" :
    tendencia === "down" ? "M12 5v14M19 12l-7 7-7-7" :
    "M5 12h14";
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

export default function TrendIndicator({ tendencia, valor }: TrendIndicatorProps) {
  const color = tendencia === "up" ? "text-emerald-400" : tendencia === "down" ? "text-red-400" : "text-neutral-400";
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-medium ${color}`}>
      <TrendIcon tendencia={tendencia} /> {Math.abs(valor).toFixed(1)}%
    </span>
  );
}
