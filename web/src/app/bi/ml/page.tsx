"use client";

import { useEffect, useState } from "react";
import type { AnomalyResult, CustomerSegment, MLRecommendation } from "../types";
import { ANOMALIAS, SEGMENTOS, RECOMENDACOES } from "../data/ml";
import { formatCurrency } from "../types";
import PageHeader from "@/app/_components/PageHeader";
import AnomalyCard from "../_components/AnomalyCard";

export default function MLPage() {
  const [anomalias, setAnomalias] = useState<AnomalyResult[]>([]);
  const [segmentos, setSegmentos] = useState<CustomerSegment[]>([]);
  const [recomendacoes, setRecomendacoes] = useState<MLRecommendation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("/api/bi/ml/anomalias").then(r => r.ok ? r.json() : null),
      fetch("/api/bi/ml/segmentos").then(r => r.ok ? r.json() : null),
      fetch("/api/bi/ml/recomendacoes").then(r => r.ok ? r.json() : null),
    ]).then(([a, s, r]) => {
      setAnomalias((a as AnomalyResult[]) ?? ANOMALIAS);
      setSegmentos((s as CustomerSegment[]) ?? SEGMENTOS);
      setRecomendacoes((r as MLRecommendation[]) ?? RECOMENDACOES);
    }).catch(() => {
      setAnomalias(ANOMALIAS);
      setSegmentos(SEGMENTOS);
      setRecomendacoes(RECOMENDACOES);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-neutral-400">Carregando...</div>;
  return (
    <div className="p-6 space-y-6">
      <PageHeader title="Machine Learning" subtitle="Detecção de anomalias, segmentação de clientes e recomendações inteligentes" />

      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Anomalias Detectadas</h2>
        <div className="space-y-3">
          {anomalias.map(a => <AnomalyCard key={a.id} anomalia={a} />)}
        </div>
      </section>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">Segmentação de Clientes</h2>
          <div className="space-y-3">
            {segmentos.map(seg => (
              <div key={seg.segmento} className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-medium text-neutral-200">{seg.segmento}</h3>
                  <span className="text-xs text-neutral-500">{seg.percentual}% da base</span>
                </div>
                <p className="text-xs text-neutral-500 mb-2">{seg.descricao}</p>
                <div className="flex items-center gap-4 text-xs">
                  <div>
                    <span className="text-neutral-500">Receita Média:</span>
                    <span className="text-neutral-300 ml-1 font-mono">{formatCurrency(seg.receitaMedia)}</span>
                  </div>
                  <div>
                    <span className="text-neutral-500">Churn:</span>
                    <span className={`ml-1 font-mono ${seg.churn > 30 ? "text-red-400" : seg.churn > 15 ? "text-amber-400" : "text-emerald-400"}`}>
                      {seg.churn}%
                    </span>
                  </div>
                </div>
                {/* Bar chart for segment size */}
                <div className="w-full h-1.5 bg-neutral-700 rounded-full mt-2">
                  <div
                    className="h-full bg-indigo-500 rounded-full"
                    style={{ width: `${seg.percentual}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">Recomendações Inteligentes</h2>
          <div className="space-y-3">
            {recomendacoes.map(rec => (
              <div key={rec.id} className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className={`text-[10px] uppercase px-2 py-0.5 rounded ${
                    rec.tipo === "cross-sell" ? "bg-blue-900/30 text-blue-400" :
                    rec.tipo === "upsell" ? "bg-emerald-900/30 text-emerald-400" :
                    "bg-amber-900/30 text-amber-400"
                  }`}>{rec.tipo}</span>
                  <span className="text-[10px] text-neutral-500">Confiança: {rec.confianca}%</span>
                </div>
                <p className="text-sm text-neutral-200">{rec.descricao}</p>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-neutral-500">Receita estimada: <span className="text-emerald-400 font-mono">{formatCurrency(rec.receitaEstimada)}</span></span>
                </div>
                <p className="text-xs text-indigo-400">
                  <span className="text-neutral-500">Ação:</span> {rec.acao}
                </p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
