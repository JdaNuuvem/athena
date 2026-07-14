import type { AnomalyResult } from "../types";
import { formatCurrency } from "../types";

interface AnomalyCardProps {
  anomalia: AnomalyResult;
}

const SEVERIDADE_STYLE: Record<string, { border: string; bg: string; text: string; label: string }> = {
  critico: { border: "border-l-red-500", bg: "bg-red-500/10", text: "text-red-400", label: "Crítico" },
  moderado: { border: "border-l-amber-500", bg: "bg-amber-500/10", text: "text-amber-400", label: "Moderado" },
  baixo: { border: "border-l-blue-500", bg: "bg-blue-500/10", text: "text-blue-400", label: "Baixo" },
};

export default function AnomalyCard({ anomalia }: AnomalyCardProps) {
  const s = SEVERIDADE_STYLE[anomalia.severidade];
  return (
    <div className={`bg-neutral-800 border border-neutral-700 ${s.border} border-l-4 rounded-lg p-4 space-y-2`}>
      <div className="flex items-center justify-between">
        <span className={`text-[10px] uppercase px-2 py-0.5 rounded ${s.bg} ${s.text} border border-current/30`}>
          {s.label}
        </span>
        <span className="text-[10px] text-neutral-600">{anomalia.data}</span>
      </div>
      <p className="text-sm text-neutral-200">{anomalia.descricao}</p>
      <div className="flex items-center gap-4 text-xs">
        <span className="text-neutral-500">Impacto: <span className="text-neutral-300">{anomalia.impacto}</span></span>
        <span className="text-neutral-500">Valor: <span className="font-mono text-amber-400">{formatCurrency(anomalia.valor)}</span></span>
      </div>
      <p className="text-xs text-indigo-400">
        <span className="text-neutral-500">Recomendação:</span> {anomalia.recomendacao}
      </p>
    </div>
  );
}
