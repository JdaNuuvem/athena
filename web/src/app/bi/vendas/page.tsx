"use client";

import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell
} from "recharts";
import type { KpiMetric, VendaDiaria, CategoriaVenda } from "../types";
import { formatCurrency } from "../types";
import { gerarVendasDiarias, gerarCategorias } from "../data/vendas";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import DrillDownTable from "../_components/DrillDownTable";

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2 text-xs shadow-lg">
      <div className="text-neutral-400">Dia {label}</div>
      <div className="text-neutral-100 font-mono">{formatCurrency(payload[0].value)}</div>
    </div>
  );
}

const margemColor = (m: number) => m >= 25 ? "#22c55e" : m >= 15 ? "#f59e0b" : "#ef4444";

export default function VendasPage() {
  const [diarias, setDiarias] = useState<VendaDiaria[]>([]);
  const [categorias, setCategorias] = useState<CategoriaVenda[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("/api/bi/vendas/diarias").then(r => r.ok ? r.json() : null),
      fetch("/api/bi/vendas/categorias").then(r => r.ok ? r.json() : null),
    ]).then(([d, c]) => {
      setDiarias(d ?? gerarVendasDiarias());
      setCategorias(c ?? gerarCategorias());
    }).catch(() => {
      setDiarias(gerarVendasDiarias());
      setCategorias(gerarCategorias());
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-neutral-400">Carregando...</div>;

  const receitaTotal = diarias.reduce((s, d) => s + d.valor, 0);
  const mediaDiaria = Math.round(receitaTotal / (diarias.length || 1));

  const kpis: KpiMetric[] = [
    { label: "Receita Total (30d)", value: formatCurrency(receitaTotal), color: "text-emerald-400" },
    { label: "Média Diária", value: formatCurrency(mediaDiaria), color: "text-blue-400" },
    { label: "Dias Analisados", value: String(diarias.length), color: "text-neutral-100" },
    { label: "Categorias", value: String(categorias.length), color: "text-purple-400" },
  ];

  return (
    <div className="p-6 space-y-6">
      <PageHeader title="Vendas & Drill-down" subtitle="Receita diária, categorias e produtos detalhados" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {kpis.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
      </div>

      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Vendas Diárias (30 dias)</h2>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={diarias}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis dataKey="dia" tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} interval={4} />
              <YAxis tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} width={48} />
              <Tooltip content={<ChartTooltip />} />
              <Line type="monotone" dataKey="valor" stroke="#818cf8" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: "#818cf8" }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Drill-down: Categorias → Produtos</h2>
        <DrillDownTable categorias={categorias} />
      </section>

      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Receita por Categoria</h2>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={categorias} layout="vertical" margin={{ top: 0, right: 8, left: 8, bottom: 0 }}>
              <XAxis type="number" tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="categoria" tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} width={120} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
              <Bar dataKey="valor" radius={[0, 4, 4, 0]} barSize={20}>
                {categorias.map((entry, i) => (
                  <Cell key={i} fill={margemColor(entry.produtos.reduce((s, p) => s + p.margem, 0) / entry.produtos.length)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
