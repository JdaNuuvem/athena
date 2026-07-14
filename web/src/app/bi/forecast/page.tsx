"use client";

import { useEffect, useState } from "react";
import type { KpiMetric, ForecastDataPoint } from "../types";
import { formatCurrency } from "../types";
import { gerarForecast, FORECAST_RESUMO } from "../data/forecast";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import ForecastChart from "../_components/ForecastChart";

interface ForecastResumo { receitaProjetada: number; crescimentoEsperado: number; confianca: number; cenarios: { otimista: number; esperado: number; pessimista: number }; fatores: Array<{ nome: string; impacto: string; valor: string }> }

export default function ForecastPage() {
  const [forecastData, setForecastData] = useState<ForecastDataPoint[]>([]);
  const [resumo, setResumo] = useState<ForecastResumo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/bi/forecast")
      .then(r => r.ok ? r.json() : null)
      .then((data: { pontos: ForecastDataPoint[]; resumo: ForecastResumo } | null) => {
        if (data) { setForecastData(data.pontos); setResumo(data.resumo); }
        else { setForecastData(gerarForecast()); setResumo(FORECAST_RESUMO); }
      })
      .catch(() => { setForecastData(gerarForecast()); setResumo(FORECAST_RESUMO); })
      .finally(() => setLoading(false));
  }, []);

  if (loading || !resumo) return <div className="p-6 text-neutral-400">Carregando...</div>;

  const kpis: KpiMetric[] = [
    { label: "Receita Projetada", value: formatCurrency(resumo.receitaProjetada), color: "text-indigo-400" },
    { label: "Crescimento Esperado", value: `+${resumo.crescimentoEsperado}%`, color: "text-emerald-400" },
    { label: "Confiança do Modelo", value: `${resumo.confianca}%`, color: "text-blue-400" },
    { label: "Cenário Pessimista", value: formatCurrency(resumo.cenarios.pessimista), color: "text-amber-400" },
  ];

  return (
    <div className="p-6 space-y-6">
      <PageHeader title="Forecast" subtitle="Previsão de vendas com séries temporais e análise de cenários" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {kpis.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
      </div>

      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Projeção de Receita (60d histórico + 30d forecast)</h2>
        <ForecastChart data={forecastData} />
      </section>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">Cenários</h2>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-neutral-400">Otimista</span>
                <span className="text-emerald-400 font-mono">{formatCurrency(resumo.cenarios.otimista)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-neutral-400">Esperado</span>
                <span className="text-indigo-400 font-mono">{formatCurrency(resumo.cenarios.esperado)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-neutral-400">Pessimista</span>
                <span className="text-amber-400 font-mono">{formatCurrency(resumo.cenarios.pessimista)}</span>
            </div>
          </div>
        </section>

        <section className="md:col-span-2">
          <h2 className="text-sm font-medium text-neutral-400 mb-3">Fatores de Influência</h2>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-neutral-700 text-neutral-400">
                  <th className="text-left p-2">Fator</th>
                  <th className="text-center p-2">Impacto</th>
                  <th className="text-right p-2">Variação Est.</th>
                </tr>
              </thead>
              <tbody>
                {resumo.fatores.map(f => (
                  <tr key={f.nome} className="border-b border-neutral-700/50">
                    <td className="p-2 text-neutral-300">{f.nome}</td>
                    <td className="p-2 text-center">
                      <span className={`text-[10px] px-2 py-0.5 rounded ${
                        f.impacto === "positivo" ? "bg-emerald-900/30 text-emerald-400" :
                        f.impacto === "negativo" ? "bg-red-900/30 text-red-400" :
                        "bg-neutral-700 text-neutral-400"
                      }`}>{f.impacto}</span>
                    </td>
                    <td className="p-2 text-right font-mono text-neutral-300">{f.valor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
