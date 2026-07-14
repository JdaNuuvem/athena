"use client";

import { useEffect, useState } from "react";
import type { IndicadorFinanceiro } from "../types";
import { INDICADORES, STATUS_TEXTO, STATUS_COR } from "../data/indicadores";
import PageHeader from "@/app/_components/PageHeader";
import TrendIndicator from "../_components/TrendIndicator";

export default function IndicadoresPage() {
  const [indicadores, setIndicadores] = useState<IndicadorFinanceiro[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/bi/indicadores")
      .then(r => r.ok ? r.json() : null)
      .then((data: IndicadorFinanceiro[] | null) => setIndicadores(data ?? INDICADORES))
      .catch(() => setIndicadores(INDICADORES))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-neutral-400">Carregando...</div>;
  return (
    <div className="p-6 space-y-6">
      <PageHeader title="Indicadores Financeiros" subtitle="Liquidez, rentabilidade, endividamento e eficiência operacional" />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {indicadores.map(ind => (
          <div key={ind.id} className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-neutral-300">{ind.nome}</h3>
              <span className={`text-[10px] uppercase px-2 py-0.5 rounded ${
                ind.status === "good" ? "bg-emerald-900/30 text-emerald-400" :
                ind.status === "warning" ? "bg-amber-900/30 text-amber-400" :
                "bg-red-900/30 text-red-400"
              }`}>{STATUS_TEXTO[ind.status]}</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className={`text-2xl font-bold ${STATUS_COR[ind.status]}`}>
                {ind.unidade === "x" ? ind.valor.toFixed(2) : ind.valor.toFixed(1)}
                <span className="text-sm font-normal ml-1">{ind.unidade}</span>
              </span>
              <TrendIndicator tendencia={ind.tendencia} valor={ind.tendenciaValor} />
            </div>
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-neutral-500">Referência: {ind.referencia}</span>
            </div>
            {/* Progress bar */}
            <div className="w-full h-1.5 bg-neutral-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  ind.status === "good" ? "bg-emerald-500" :
                  ind.status === "warning" ? "bg-amber-500" : "bg-red-500"
                }`}
                style={{ width: `${Math.min(ind.valor / 2, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
