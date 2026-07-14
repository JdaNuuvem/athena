"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtBRL } from "@/lib/format";
import SubmenuCard from "@/app/_components/SubmenuCard";
import KpiCard from "@/app/_components/KpiCard";
import LoadingState from "@/app/_components/LoadingState";

const SUBMENU = [
  { href: "/rh/funcionarios", label: "Funcionários", color: "bg-blue-600" },
  { href: "/rh/ponto", label: "Ponto Eletrônico", color: "bg-emerald-600" },
  { href: "/rh/ferias", label: "Férias", color: "bg-amber-600" },
  { href: "/rh/folha", label: "Folha de Pagamento", color: "bg-purple-600" },
  { href: "/rh/beneficios", label: "Benefícios", color: "bg-rose-600" },
];

export default function RHPage() {
  const [dash, setDash] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/rh/dashboard")
      .then(r => r.json())
      .then(d => setDash(d))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6"><LoadingState /></div>;

  return (
    <div className="p-6 space-y-6">
      <div><h1 className="text-lg font-bold text-neutral-100">RH</h1><p className="text-xs text-neutral-500 mt-1">Funcionários, folha e ponto</p></div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard metric={{ label: "Funcionários", value: String(dash?.total_funcionarios ?? 0), color: "text-blue-400" }} />
        <KpiCard metric={{ label: "Ativos", value: String(dash?.ativos ?? 0), color: "text-emerald-400" }} />
        <KpiCard metric={{ label: "Em férias", value: String(dash?.ferias ?? 0), color: "text-amber-400" }} />
        <KpiCard metric={{ label: "Afastados", value: String(dash?.afastados ?? 0), color: "text-red-400" }} />
        <KpiCard metric={{ label: "Folha do mês", value: fmtBRL(Number(dash?.folha_mes ?? 0)), color: "text-purple-400" }} />
        <KpiCard metric={{ label: "Ponto hoje", value: String(dash?.ponto_hoje ?? 0), color: "text-cyan-400" }} />
      </div>

      {(dash?.ferias_proximas as unknown[])?.length > 0 && (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <h3 className="text-xs font-semibold text-neutral-400 mb-2">Próximas férias</h3>
          <div className="space-y-1">
            {(dash?.ferias_proximas as Array<{ nome: string; inicio: string; fim: string }>)?.map((f, i) => (
              <div key={i} className="flex justify-between text-xs text-neutral-300">
                <span>{f.nome}</span>
                <span className="text-neutral-500">{f.inicio?.slice(0, 10)} → {f.fim?.slice(0, 10)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <h2 className="text-sm font-semibold text-neutral-300 mb-3">Módulos</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {SUBMENU.map(item => <SubmenuCard key={item.href} item={item} />)}
        </div>
      </div>
    </div>
  );
}
