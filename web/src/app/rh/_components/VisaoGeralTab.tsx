"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL, fmtDataBR } from "@/lib/format";

export default function VisaoGeralTab() {
  const [dash, setDash] = useState<Awaited<ReturnType<typeof api.rhDashboard>> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.rhDashboard().then(setDash).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-xs text-neutral-500">Carregando...</p>;

  const cards = [
    { label: "Funcionários", value: String(dash?.total_funcionarios ?? 0), cor: "text-blue-400" },
    { label: "Ativos", value: String(dash?.ativos ?? 0), cor: "text-emerald-400" },
    { label: "Em Férias", value: String(dash?.ferias ?? 0), cor: "text-amber-400" },
    { label: "Folha do Mês", value: fmtBRL(dash?.folha_mes ?? 0), cor: "text-purple-400" },
    { label: "Ponto Hoje", value: String(dash?.ponto_hoje ?? 0), cor: "text-cyan-400" },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {cards.map(c => (
          <div key={c.label} className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
            <p className="text-[10px] text-neutral-500">{c.label}</p>
            <p className={`mt-0.5 text-lg font-semibold ${c.cor}`}>{c.value}</p>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
        <p className="mb-3 text-xs font-semibold text-neutral-300">Próximas Férias</p>
        {!dash?.ferias_proximas || dash.ferias_proximas.length === 0 ? (
          <p className="text-xs text-neutral-500">Nenhuma férias agendada</p>
        ) : (
          <div className="space-y-1.5">
            {dash.ferias_proximas.map((f, i) => (
              <div key={i} className="flex items-center justify-between text-xs text-neutral-300">
                <span>{f.nome}</span>
                <span className="text-neutral-500">{fmtDataBR(f.inicio)} → {fmtDataBR(f.fim)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
