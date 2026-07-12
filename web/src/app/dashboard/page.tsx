"use client";

import { useState, useEffect } from "react";
import { api, type KPIOverview, type Agent } from "@/lib/api";

export default function DashboardPage() {
  const [kpi, setKpi] = useState<KPIOverview | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.kpiOverview(), api.agentsList()])
      .then(([k, a]) => {
        setKpi(k as unknown as KPIOverview);
        setAgents(a.agents);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-neutral-500">Carregando...</div>;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-light text-neutral-300">Dashboard</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Receita (30d)" value={kpi ? `R$ ${(kpi.receita_total as number).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}` : "—"} />
        <KpiCard label="Pedidos" value={kpi ? String(kpi.total_pedidos) : "—"} />
        <KpiCard label="Produtos" value={kpi ? String(kpi.total_produtos) : "—"} />
        <KpiCard label="Ticket Médio" value={kpi ? `R$ ${Number(kpi.ticket_medio).toFixed(2)}` : "—"} />
      </div>

      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Agentes</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {agents.map((a) => (
            <a
              key={a.id}
              href={`/agents/${a.id}`}
              className="bg-neutral-900 border border-neutral-800 rounded-lg p-3 hover:border-neutral-700 transition-colors"
            >
              <div className="flex items-center gap-2 mb-1">
                <span
                  aria-label={`status: ${a.status}`}
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    a.status === "running" ? "bg-green-500" : a.status === "idle" ? "bg-yellow-500" : "bg-red-500"
                  }`}
                />
                <span className="text-xs text-neutral-400 truncate">{a.id}</span>
              </div>
              <div className="text-sm font-medium text-neutral-200 truncate">{a.name}</div>
              <div className="text-[10px] text-neutral-500 uppercase mt-1 truncate">{a.role}</div>
              <div className="text-xs text-neutral-500 mt-1 numeric">{a.taskCount} tarefas</div>
            </a>
          ))}
        </div>
      </section>

      {kpi?.top_skus && kpi.top_skus.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">Top SKUs</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
            <table className="w-full text-sm min-w-[560px]">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                  <th className="text-left p-3 font-medium">SKU</th>
                  <th className="text-left p-3 font-medium">Nome</th>
                  <th className="text-right p-3 font-medium">Vendidos</th>
                  <th className="text-right p-3 font-medium">Receita</th>
                  <th className="text-right p-3 font-medium">Margem</th>
                </tr>
              </thead>
              <tbody>
                {kpi.top_skus.map((sku) => (
                  <tr key={sku.sku} className="border-b border-neutral-800/50 last:border-0 hover:bg-neutral-800/30">
                    <td className="p-3 text-indigo-400 font-mono text-xs numeric">{sku.sku}</td>
                    <td className="p-3 text-neutral-300">{sku.nome}</td>
                    <td className="p-3 text-right text-neutral-400 numeric">{sku.qtd}</td>
                    <td className="p-3 text-right text-neutral-300 numeric">R$ {Number(sku.receita).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                    <td className="p-3 text-right">
                      <span className={`numeric ${Number(sku.margem) >= 25 ? "text-green-400" : Number(sku.margem) >= 15 ? "text-yellow-400" : "text-red-400"}`}>
                        {Number(sku.margem).toFixed(1)}%
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

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
      <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">{label}</div>
      <div className="text-2xl font-light text-neutral-100 numeric">{value}</div>
    </div>
  );
}
