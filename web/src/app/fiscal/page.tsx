"use client";

import { useEffect, useState } from "react";
import type { KpiMetric, SubmenuItem } from "./types";
import { fiscalDashboard } from "@/lib/api";
import { fmtBRL } from "@/lib/format";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import SubmenuCard from "@/app/_components/SubmenuCard";
import LoadingState from "@/app/_components/LoadingState";

const SUBMENU: SubmenuItem[] = [
  { href: "/fiscal/notas", label: "Notas Fiscais", color: "bg-blue-600" },
  { href: "/fiscal/apuracao", label: "Apuração", color: "bg-red-600" },
  { href: "/fiscal/tributos", label: "Tributos", color: "bg-amber-600" },
  { href: "/fiscal/obrigacoes", label: "Obrigações", color: "bg-purple-600" },
  { href: "/fiscal/tabelas", label: "Tabelas Fiscais", color: "bg-emerald-600" },
];

export default function FiscalPage() {
  const [kpis, setKpis] = useState<KpiMetric[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fiscalDashboard()
      .then(d => setKpis([
        { label: "Notas emitidas (mês)", value: String(d.nfs_mes), color: "text-blue-400" },
        { label: "Valor emitido (mês)", value: fmtBRL(d.valor_mes), color: "text-emerald-400" },
        { label: "Obrigações pendentes", value: String(d.obrigacoes_pendentes), color: "text-red-400" },
        { label: "Obrigações atrasadas", value: String(d.obrigacoes_atrasadas), color: "text-orange-400" },
        { label: "Tributos ativos", value: String(d.tributos_ativos), color: "text-amber-400" },
        { label: "Contas a receber", value: fmtBRL(d.contas_receber_pendentes), color: "text-green-400" },
      ]))
      .catch(() => setKpis([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-6">
      <PageHeader title="Fiscal" subtitle="Notas fiscais e tributos" />

      {loading ? (
        <LoadingState />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {kpis.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
        </div>
      )}

      <div>
        <h2 className="text-sm font-semibold text-neutral-300 mb-3">Módulos</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {SUBMENU.map(item => <SubmenuCard key={item.href} item={item} />)}
        </div>
      </div>
    </div>
  );
}
