"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export default function BusinessPage() {
  const [alerts, setAlerts] = useState<Record<string, unknown>[]>([]);
  const [opportunities, setOpportunities] = useState<Record<string, unknown>[]>([]);
  const [executions, setExecutions] = useState<Record<string, unknown>[]>([]);
  const [mlStatus, setMlStatus] = useState<{ modelo_treinado: boolean } | null>(null);
  const [mlMessage, setMlMessage] = useState<{ text: string; ok: boolean } | null>(null);
  const [mlLoading, setMlLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.hermesAlerts(),
      api.hermesOpportunities(),
      api.hermesExecutions(),
      api.mlStatus(),
    ])
      .then(([a, o, e, m]) => {
        setAlerts(a as Record<string, unknown>[]);
        setOpportunities(o as Record<string, unknown>[]);
        setExecutions(e as Record<string, unknown>[]);
        setMlStatus(m as { modelo_treinado: boolean });
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao carregar dados"));
  }, []);

  const treinarModelo = async () => {
    setMlLoading(true);
    try {
      await api.mlTreinar();
      setMlMessage({ text: "Treinamento iniciado com sucesso", ok: true });
    } catch {
      setMlMessage({ text: "Erro ao iniciar treinamento", ok: false });
    } finally {
      setMlLoading(false);
      setTimeout(() => setMlMessage(null), 5000);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h1 className="text-lg font-light text-neutral-300">Operações</h1>

      {error && (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-2">Machine Learning</h2>
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm text-neutral-300">Modelo de previsão de defeitos</span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${mlStatus?.modelo_treinado ? "bg-green-900/50 text-green-400" : "bg-yellow-900/50 text-yellow-400"}`}>
              {mlStatus?.modelo_treinado ? "Treinado" : "Não treinado"}
            </span>
            {mlMessage && (
              <span className={`text-xs px-2 py-0.5 rounded-full ${mlMessage.ok ? "bg-green-950/60 text-green-400" : "bg-red-950/60 text-red-400"}`}>
                {mlMessage.text}
              </span>
            )}
          </div>
          <button
            onClick={treinarModelo}
            disabled={mlLoading}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs px-4 py-2 rounded-lg transition-colors shrink-0"
          >
            {mlLoading ? "Iniciando..." : "Treinar modelo"}
          </button>
        </div>
      </section>

      {Array.isArray(opportunities) && opportunities.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-2">Oportunidades de Produto</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
            <table className="w-full text-sm min-w-[560px]">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                  <th className="text-left p-3 font-medium">Produto</th>
                  <th className="text-right p-3 font-medium">Score</th>
                  <th className="text-right p-3 font-medium">Margem</th>
                  <th className="text-right p-3 font-medium">Concorrência</th>
                  <th className="text-center p-3 font-medium">Fabricável</th>
                </tr>
              </thead>
              <tbody>
                {(opportunities as Array<Record<string, unknown>>).slice(0, 10).map((o, i) => (
                  <tr key={i} className="border-b border-neutral-800/50 last:border-0">
                    <td className="p-3 text-neutral-300">{o.nome as string}</td>
                    <td className="p-3 text-right text-indigo-400 font-mono text-xs numeric">{String(o.score_final)}</td>
                    <td className="p-3 text-right text-neutral-400 numeric">{o.margem_estimada_pct != null ? `${o.margem_estimada_pct}%` : "—"}</td>
                    <td className="p-3 text-right text-neutral-400">{o.nivel_concorrencia as string}</td>
                    <td className="p-3 text-center">
                      {o.fabricavel
                        ? <span className="text-green-400" aria-label="sim">✓</span>
                        : <span className="text-red-400" aria-label="não">✗</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {alerts.length > 0 && (
        <section>
          <h2 className="text-xs text-neutral-500 uppercase tracking-wider mb-2">
            Alertas <span className="text-neutral-500 normal-case font-normal">({alerts.length})</span>
          </h2>
          <div className="space-y-2">
            {alerts.slice(0, 10).map((a, i) => (
              <div key={i} className="bg-neutral-900 border border-neutral-800 rounded-lg p-3 text-xs">
                <div className="flex items-center gap-2">
                  <span
                    aria-hidden="true"
                    className={`w-1.5 h-1.5 rounded-full shrink-0 ${(a.gravidade as string) === "critico" || (a.gravidade as string) === "alta" ? "bg-red-500" : "bg-yellow-500"}`}
                  />
                  <span className="text-neutral-500 font-mono">{(a.tipo as string) || (a.type as string)}</span>
                  <span className="text-neutral-300">{a.mensagem as string || a.message as string}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {Array.isArray(executions) && executions.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-2">Execuções Recentes</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
            <table className="w-full text-sm min-w-[480px]">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                  <th className="text-left p-3 font-medium">Agente</th>
                  <th className="text-left p-3 font-medium">Ação</th>
                  <th className="text-left p-3 font-medium">Status</th>
                  <th className="text-right p-3 font-medium">Data</th>
                </tr>
              </thead>
              <tbody>
                {(executions as Array<Record<string, unknown>>).slice(0, 10).map((e, i) => (
                  <tr key={i} className="border-b border-neutral-800/50 last:border-0">
                    <td className="p-3 text-neutral-300 font-mono text-xs">{e.agente_id as string}</td>
                    <td className="p-3 text-neutral-400">{e.action as string}</td>
                    <td className="p-3">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${e.status === "sucesso" ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"}`}>
                        {e.status as string}
                      </span>
                    </td>
                    <td className="p-3 text-right text-neutral-500 text-xs numeric">{e.fim_execucao ? String(e.fim_execucao).slice(0, 10) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
