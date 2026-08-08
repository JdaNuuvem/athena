"use client";

import { useEffect, useState, useCallback } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import type { KpiMetric, LojaDre } from "../types";
import { formatCurrency } from "../types";
import { useTheme, chartAxisColors } from "@/lib/theme-context";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import ErroCarregamento from "../_components/ErroCarregamento";
import ExportButtons from "@/app/_components/ExportButtons";

const margemColor = (m: number) => m >= 25 ? "#22c55e" : m >= 15 ? "#f59e0b" : "#ef4444";

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2 text-xs shadow-lg">
      <div className="text-neutral-400">{label}</div>
      <div className="text-neutral-100 font-mono">{formatCurrency(payload[0].value)}</div>
    </div>
  );
}

export default function LojasPage() {
  const { theme } = useTheme();
  const { grid: gridColor, axis: axisColor } = chartAxisColors(theme);
  const [dias, setDias] = useState(30);
  const [lojas, setLojas] = useState<LojaDre[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(false);

  const load = useCallback(() => {
    setLoading(true); setErro(false);
    fetch(`/api/bi/lojas?dias=${dias}`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((data: LojaDre[]) => setLojas(data))
      .catch(() => setErro(true))
      .finally(() => setLoading(false));
  }, [dias]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="p-6 text-neutral-400">Carregando...</div>;
  if (erro) return <ErroCarregamento onRetry={load} />;

  const receitaTotal = lojas.reduce((s, l) => s + l.receita, 0);
  const lucroTotal = lojas.reduce((s, l) => s + l.lucro, 0);
  const melhor = lojas[0];
  const pior = lojas[lojas.length - 1];

  const kpis: KpiMetric[] = [
    { label: "Receita Total", value: formatCurrency(receitaTotal), color: "text-emerald-400" },
    { label: "Lucro Total", value: formatCurrency(lucroTotal), color: lucroTotal >= 0 ? "text-blue-400" : "text-red-400" },
    { label: "Melhor Loja (lucro)", value: melhor ? melhor.loja_nome : "—", color: "text-purple-400" },
    { label: "Loja em Atenção", value: pior ? pior.loja_nome : "—", color: pior && pior.lucro < 0 ? "text-red-400" : "text-neutral-100" },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between gap-3">
        <PageHeader title="Lojas" subtitle="Ranking de lojas por receita, custos e margem — ordenado por lucro" />
        <div className="flex items-center gap-2">
          <select value={dias} onChange={e => setDias(Number(e.target.value))}
            className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200">
            {[7, 30, 60, 90].map(d => <option key={d} value={d}>{d} dias</option>)}
          </select>
          <ExportButtons
            columns={["Loja", "Receita", "Vendas", "Ticket Médio", "Comissão", "Frete", "Custos Produção", "Lucro", "Margem %"]}
            rows={lojas.map(l => [l.loja_nome, formatCurrency(l.receita), l.qtd_vendas, formatCurrency(l.ticket_medio), formatCurrency(l.comissao_valor), formatCurrency(l.frete), formatCurrency(l.custos_producao), formatCurrency(l.lucro), `${l.margem_pct}%`])}
            filename="bi-lojas" title="Ranking de Lojas"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {kpis.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
      </div>

      {lojas.length === 0 ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center text-sm text-neutral-500">
          Nenhuma venda no período selecionado.
        </div>
      ) : (
        <>
          <section>
            <h2 className="text-sm font-medium text-neutral-400 mb-3">Lucro por Loja</h2>
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
              <ResponsiveContainer width="100%" height={Math.max(160, lojas.length * 36)}>
                <BarChart data={lojas} layout="vertical" margin={{ top: 0, right: 8, left: 8, bottom: 0 }}>
                  <XAxis type="number" tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} tick={{ fill: axisColor, fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="loja_nome" tick={{ fill: axisColor, fontSize: 10 }} axisLine={false} tickLine={false} width={120} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: theme === "dark" ? "rgba(255,255,255,0.04)" : "rgba(15,23,32,0.04)" }} />
                  <Bar dataKey="lucro" radius={[0, 4, 4, 0]} barSize={20}>
                    {lojas.map((l, i) => <Cell key={i} fill={margemColor(l.margem_pct)} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-medium text-neutral-400 mb-3">Detalhe por Loja</h2>
            <div className="overflow-x-auto rounded-lg border border-neutral-700">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-neutral-700 bg-neutral-900/60 text-left text-neutral-400">
                    <th className="px-3 py-2 font-medium">Loja</th>
                    <th className="px-3 py-2 font-medium text-right">Receita</th>
                    <th className="px-3 py-2 font-medium text-right">Vendas</th>
                    <th className="px-3 py-2 font-medium text-right">Ticket Médio</th>
                    <th className="px-3 py-2 font-medium text-right">Comissão</th>
                    <th className="px-3 py-2 font-medium text-right">Frete</th>
                    <th className="px-3 py-2 font-medium text-right">Custos Produção</th>
                    <th className="px-3 py-2 font-medium text-right">Lucro</th>
                    <th className="px-3 py-2 font-medium text-right">Margem</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/70">
                  {lojas.map(l => (
                    <tr key={l.loja_id} className="text-neutral-300">
                      <td className="whitespace-nowrap px-3 py-2 font-medium text-neutral-200">{l.loja_nome}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right">{formatCurrency(l.receita)}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right">{l.qtd_vendas}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right">{formatCurrency(l.ticket_medio)}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right">{formatCurrency(l.comissao_valor)}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right">{formatCurrency(l.frete)}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right">{formatCurrency(l.custos_producao)}</td>
                      <td className={`whitespace-nowrap px-3 py-2 text-right font-medium ${l.lucro >= 0 ? "text-emerald-400" : "text-red-400"}`}>{formatCurrency(l.lucro)}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right" style={{ color: margemColor(l.margem_pct) }}>{l.margem_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
