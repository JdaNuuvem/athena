"use client";

import type { KpiMetric, SubmenuItem } from "@/lib/types/ui";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import SubmenuCard from "@/app/_components/SubmenuCard";
import { fmtBRL } from "@/lib/format";

const KPIS: KpiMetric[] = [
  { label: "Valor em Estoque", value: fmtBRL(1847500), color: "text-emerald-400" },
  { label: "SKUs Ativos", value: "1.247", color: "text-blue-400" },
  { label: "Giro Médio (30d)", value: "3.2x", color: "text-indigo-400" },
  { label: "Acuracidade Média", value: "96.8%", color: "text-emerald-400" },
  { label: "Itens em Ruptura", value: "8", color: "text-red-400", sub: "▼ 3 vs semana anterior" },
  { label: "Cobertura Média", value: "28 dias", color: "text-amber-400" },
  { label: "Depósitos Ativos", value: "6", color: "text-neutral-300" },
  { label: "Movimentações Hoje", value: "143", color: "text-blue-400" },
];

const SUBMENU: SubmenuItem[] = [
  { href: "/estoque/movimentacoes", label: "Movimentações", color: "bg-blue-600" },
  { href: "/estoque/depositos", label: "Depósitos & Multilojas", color: "bg-emerald-600" },
  { href: "/estoque/inventario", label: "Inventário", color: "bg-purple-600" },
  { href: "/estoque/custos", label: "Custos & Curva ABC", color: "bg-amber-600" },
  { href: "/estoque/analise", label: "Análise (Giro/Ruptura/Cobertura)", color: "bg-indigo-600" },
];

export default function EstoquePage() {
  return (
    <div className="p-6 space-y-6">
      <PageHeader title="Estoque" subtitle="Controle de inventário, movimentações, depósitos e custos" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {KPIS.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
      </div>

      <div>
        <h2 className="text-sm font-semibold text-neutral-300 mb-3">Módulos</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {SUBMENU.map(item => <SubmenuCard key={item.href} item={item} />)}
        </div>
      </div>
    </div>
  );
}
