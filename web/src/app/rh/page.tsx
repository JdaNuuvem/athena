"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function RHPage() {
  const [dash, setDash] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    fetch("/api/rh/dashboard").then(r => r.json()).then(setDash).catch(() => {});
  }, []);

  const KPI = ({ label, value, color }: { label: string; value: string; color: string }) => (
    <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3">
      <p className="text-xs text-neutral-500">{label}</p>
      <p className={`text-lg font-bold ${color}`}>{value}</p>
    </div>
  );

  return (
    <div className="p-6 space-y-6">
      <div><h1 className="text-lg font-bold text-neutral-100">RH</h1><p className="text-xs text-neutral-500 mt-1">Funcionarios, ponto, ferias, folha, beneficios, vale e comissoes</p></div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <KPI label="Funcionarios" value={String(dash?.total_funcionarios ?? 0)} color="text-blue-400" />
        <KPI label="Ativos" value={String(dash?.ativos ?? 0)} color="text-emerald-400" />
        <KPI label="Em Ferias" value={String(dash?.ferias ?? 0)} color="text-amber-400" />
        <KPI label="Folha do Mes" value={"R$ " + (Number(dash?.folha_mes ?? 0)).toLocaleString("pt-BR", { minimumFractionDigits: 2 })} color="text-purple-400" />
        <KPI label="Ponto Hoje" value={String(dash?.ponto_hoje ?? 0)} color="text-cyan-400" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { href: "/rh/funcionarios", label: "Funcionarios", color: "bg-blue-600" },
          { href: "/rh/ponto", label: "Ponto Eletronico", color: "bg-emerald-600" },
          { href: "/rh/ferias", label: "Ferias", color: "bg-amber-600" },
          { href: "/rh/folha", label: "Folha Pagamento", color: "bg-purple-600" },
          { href: "/rh/beneficios", label: "Beneficios", color: "bg-rose-600" },
          { href: "/rh/vale", label: "Vale / Adiantamento", color: "bg-teal-600" },
          { href: "/rh/comissoes", label: "Comissoes", color: "bg-orange-600" },
        ].map(m => (
          <Link key={m.href} href={m.href} className={`${m.color} hover:opacity-90 text-white rounded-lg p-4 transition-opacity`}>
            <p className="text-sm font-semibold">{m.label}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
