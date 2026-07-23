"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { KpiMetric, SubmenuItem } from "./types";
import { formatCurrency } from "./types";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";

const DEFAULT_KPIS: KpiMetric[] = [
  { label: "Receita (mês)", value: "--", color: "text-neutral-500" },
  { label: "Ticket Médio", value: "--", color: "text-neutral-500" },
  { label: "Margem Média", value: "--", color: "text-neutral-500" },
  { label: "Previsão (próx. mês)", value: "--", color: "text-neutral-500" },
  { label: "ROI", value: "--", color: "text-neutral-500" },
  { label: "Churn (30d)", value: "--", color: "text-neutral-500" },
];

const DEFAULT_SUBMENU: SubmenuItem[] = [
  { href: "/bi/vendas", label: "Vendas & Drill-down", color: "bg-blue-600" },
  { href: "/bi/indicadores", label: "Indicadores", color: "bg-amber-600" },
  { href: "/bi/forecast", label: "Forecast", color: "bg-purple-600" },
  { href: "/bi/ml", label: "Machine Learning", color: "bg-emerald-600" },
];

export default function BiPage() {
  const [kpis, setKpis] = useState<KpiMetric[]>(DEFAULT_KPIS);
  const [submenu] = useState<SubmenuItem[]>(DEFAULT_SUBMENU);

  useEffect(() => {
    fetch("/api/bi/dashboard")
      .then(r => r.ok ? r.json() : null)
      .then((data: { kpis: KpiMetric[] } | null) => { if (data?.kpis) setKpis(data.kpis); })
      .catch(() => {});
  }, []);
  return (
    <div className="p-6 space-y-6">
      <PageHeader title="BI" subtitle="Business Intelligence, dashboards e análises" />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {kpis.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
      </div>

      <div>
        <h2 className="text-sm font-semibold text-neutral-300 mb-3">Módulos</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {submenu.map(item => (
            <Link
              key={item.href}
              href={item.href}
              className={`${item.color} hover:opacity-90 text-white rounded-lg p-4 transition-opacity`}
            >
              <p className="text-sm font-semibold">{item.label}</p>
              <p className="text-[10px] opacity-80 mt-1">Acessar {item.label.toLowerCase()}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
