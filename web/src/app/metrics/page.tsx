"use client";

import { useState, useEffect } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { api } from "@/lib/api";

type Loja = { id: number; tipo: string; nome: string; receita: number; pedidos: number; ticket_medio: number };

const fmtBRL = (v: number) =>
  v >= 1000 ? `R$ ${(v / 1000).toFixed(1)}k` : `R$ ${v.toFixed(0)}`;

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2 text-xs shadow-lg">
      <div className="text-neutral-400 mb-1">{label}</div>
      <div className="text-neutral-100 numeric">R$ {Number(payload[0].value).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</div>
    </div>
  );
}

export default function MetricsPage() {
  const [lojas, setLojas] = useState<Loja[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.lojas(30)])
      .then(([l]) => setLojas(l as Loja[]))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao carregar métricas"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-neutral-500">Carregando...</div>;

  const fisicas = lojas.filter((l) => l.tipo === "fisica");
  const digitais = lojas.filter((l) => l.tipo === "digital");
  const chartData = [...lojas].sort((a, b) => b.receita - a.receita);

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h1 className="text-lg font-light text-neutral-300">Métricas</h1>

      {error && (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {chartData.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">Receita por Loja</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData} margin={{ top: 4, right: 4, left: 8, bottom: 4 }}>
                <XAxis
                  dataKey="nome"
                  tick={{ fill: "#737373", fontSize: 11 }}
                  axisLine={{ stroke: "#262626" }}
                  tickLine={false}
                />
                <YAxis
                  tickFormatter={fmtBRL}
                  tick={{ fill: "#737373", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={64}
                />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                <Bar dataKey="receita" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={entry.tipo === "fisica" ? "#4f46e5" : "#7c3aed"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div className="flex items-center gap-4 mt-2 justify-end text-[10px] text-neutral-500">
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-2.5 h-2.5 rounded-sm bg-indigo-600" /> Loja física
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-2.5 h-2.5 rounded-sm bg-violet-600" /> Marketplace
              </span>
            </div>
          </div>
        </section>
      )}

      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Lojas Físicas</h2>
        {fisicas.length === 0 ? (
          <div className="text-neutral-500 text-sm">Nenhuma loja física encontrada.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {fisicas.map((loja) => (
              <div key={loja.id} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
                <h3 className="text-sm font-medium text-neutral-200">{loja.nome}</h3>
                <div className="mt-3 space-y-1 text-xs text-neutral-400">
                  <div className="flex justify-between">
                    <span>Receita</span>
                    <span className="text-neutral-200 numeric">R$ {Number(loja.receita).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Pedidos</span>
                    <span className="text-neutral-200 numeric">{String(loja.pedidos)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Ticket médio</span>
                    <span className="text-neutral-200 numeric">R$ {Number(loja.ticket_medio).toFixed(2)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Marketplaces</h2>
        {digitais.length === 0 ? (
          <div className="text-neutral-500 text-sm">Nenhum marketplace encontrado.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {digitais.map((mp) => (
              <div key={mp.id} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
                <h3 className="text-sm font-medium text-neutral-200 capitalize">{mp.nome}</h3>
                <div className="mt-3 space-y-1 text-xs text-neutral-400">
                  <div className="flex justify-between">
                    <span>Receita</span>
                    <span className="text-neutral-200 numeric">R$ {Number(mp.receita).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Pedidos</span>
                    <span className="text-neutral-200 numeric">{String(mp.pedidos)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Ticket médio</span>
                    <span className="text-neutral-200 numeric">R$ {Number(mp.ticket_medio).toFixed(2)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
