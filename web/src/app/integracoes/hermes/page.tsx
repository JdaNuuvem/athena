"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export default function HermesIntegrationPage() {
  const [agents, setAgents] = useState<Record<string, unknown>[]>([]);
  const [executions, setExecutions] = useState<Record<string, unknown>[]>([]);

  useEffect(() => {
    Promise.all([api.hermesAgents(), api.hermesExecutions()])
      .then(([a, e]) => {
        setAgents(a as Record<string, unknown>[]);
        setExecutions(e as Record<string, unknown>[]);
      })
      .catch(() => {});
  }, []);

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div>
        <a href="/integracoes" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors">← Integrações</a>
        <h1 className="text-lg font-light text-neutral-300 mt-1">Hermes Agents</h1>
      </div>

      <section>
        <h2 className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Agentes Cadastrados ({agents.length})</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {agents.map((a, i) => (
            <div key={i} className="bg-neutral-900 border border-neutral-800 rounded-lg p-3">
              <div className="text-xs font-mono text-indigo-400">{a.agente_id as string || a.id as string}</div>
              <div className="text-sm text-neutral-200 mt-1">{a.nome as string}</div>
              <div className="text-[10px] text-neutral-500">{a.categoria as string || a.descricao as string}</div>
            </div>
          ))}
        </div>
      </section>

      {executions.length > 0 && (
        <section>
          <h2 className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Últimas Execuções</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
            <table className="w-full text-sm min-w-[480px]">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                  <th className="text-left p-3 font-medium">Agente</th>
                  <th className="text-left p-3 font-medium">Ação</th>
                  <th className="text-left p-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {executions.slice(0, 10).map((e, i) => (
                  <tr key={i} className="border-b border-neutral-800/50 last:border-0">
                    <td className="p-3 font-mono text-xs text-neutral-300 numeric">{e.agente_id as string}</td>
                    <td className="p-3 text-neutral-400">{e.action as string}</td>
                    <td className="p-3">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${e.status === "sucesso" ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"}`}>
                        {e.status as string}
                      </span>
                    </td>
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
