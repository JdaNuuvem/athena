"use client";

import { useState, useEffect } from "react";
import { api, type Agent } from "@/lib/api";

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.agentsList()
      .then((r) => setAgents(r.agents))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-neutral-500">Carregando...</div>;

  const running = agents.filter((a) => a.status === "running");
  const idle = agents.filter((a) => a.status === "idle");
  const errored = agents.filter((a) => a.status === "errored");

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-light text-neutral-300">Agentes</h1>

      <div className="flex gap-4 text-sm text-neutral-400">
        <span>🟢 {running.length} em execução</span>
        <span>🟡 {idle.length} ociosos</span>
        {errored.length > 0 && <span>🔴 {errored.length} com erro</span>}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {agents.map((a) => (
          <a
            key={a.id}
            href={`/agents/${a.id}`}
            className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 hover:border-neutral-700 transition-colors block"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span
                  aria-label={`status: ${a.status}`}
                  className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                    a.status === "running" ? "bg-green-500" : a.status === "idle" ? "bg-yellow-500" : "bg-red-500"
                  }`}
                />
                <span className="text-xs font-mono text-neutral-500">{a.id}</span>
              </div>
              <span className="text-[10px] text-neutral-500 uppercase">{a.context}</span>
            </div>
            <h3 className="text-base font-medium text-neutral-200">{a.name}</h3>
            <p className="text-xs text-neutral-500 mt-1">{a.role} · {a.taskCount} tarefas</p>
          </a>
        ))}
      </div>
    </div>
  );
}
