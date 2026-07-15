"use client";

import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from "recharts";
import { api, type KPIOverview, type Agent } from "@/lib/api";

const fmtBRL = (v: number) => "R$ " + v.toLocaleString("pt-BR", { minimumFractionDigits: 2 });

const margemColor = (m: number) => m >= 25 ? "#22c55e" : m >= 15 ? "#f59e0b" : "#ef4444";

const alertaStyles: Record<string, { border: string; badge: string; icon: string }> = {
  critico: { border: "border-l-red-500", badge: "bg-red-500/10 text-red-400 border border-red-500/30", icon: "!" },
  atencao: { border: "border-l-amber-500", badge: "bg-amber-500/10 text-amber-400 border border-amber-500/30", icon: "!" },
  info: { border: "border-l-blue-500", badge: "bg-blue-500/10 text-blue-400 border border-blue-500/30", icon: "i" },
};

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return <div className="bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2 text-xs shadow-lg"><div className="text-neutral-400">{label}</div><div className="text-neutral-100 numeric">{fmtBRL(payload[0].value)}</div></div>;
}

function KpiCard({ label, value, valueClassName }: { label: string; value: string; valueClassName?: string; subtitle?: string }) {
  return <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-3"><div className="text-[10px] text-neutral-500 uppercase tracking-wider">{label}</div><div className={"text-sm mt-1 font-medium " + (valueClassName || "text-neutral-200")}>{value}</div></div>;
}

interface DashboardData {
  vendasDia: number; vendasMes: number; vendasMesChart: { dia: string; valor: number }[];
  estoqueCritico: number; estoqueTotal: number;
  fluxoCaixa: number; clientesNovos: number; clientesTotal: number;
  vendasHoje: number; vendasQtd: number;
  topProdutos: { nome: string; valor: number; margem: number }[];
  alertas: { tipo: string; mensagem: string; data: string }[];
}

export default function DashboardPage() {
  const [kpi, setKpi] = useState<KPIOverview | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [dash, setDash] = useState<DashboardData>({ vendasDia:0, vendasMes:0, vendasMesChart:[], estoqueCritico:0, estoqueTotal:0, fluxoCaixa:0, clientesNovos:0, clientesTotal:0, vendasHoje:0, vendasQtd:0, topProdutos:[], alertas:[] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.kpiOverview(), api.agentsList(),
      fetch("/api/relatorios/vendas?dias=1").then(r => r.json()).catch(() => ({})),
      fetch("/api/relatorios/vendas?dias=30").then(r => r.json()).catch(() => ({})),
      fetch("/api/relatorios/estoque").then(r => r.json()).catch(() => ({})),
      fetch("/api/relatorios/fluxo-caixa?dias=30").then(r => r.json()).catch(() => ({})),
      fetch("/api/relatorios/clientes?dias=30").then(r => r.json()).catch(() => ({})),
    ]).then(([k, a, r1, r30, est, fc, cli]) => {
      setKpi(k as unknown as KPIOverview);
      setAgents(a.agents);
      const diarias = (r30.diarias || []).map((d: any) => ({ dia: (d.dia || "").slice(8, 10), valor: d.valor || 0 }));
      setDash({
        vendasDia: r1.total || 0,
        vendasMes: r30.total || 0,
        vendasMesChart: diarias,
        estoqueCritico: est.baixo_estoque || 0,
        estoqueTotal: est.total_itens || 0,
        fluxoCaixa: fc.saldo || 0,
        clientesNovos: cli.novos || 0,
        clientesTotal: cli.total || 0,
        vendasHoje: r1.total || 0,
        vendasQtd: r1.quantidade || 0,
        topProdutos: (k as any)?.top_produtos || [],
        alertas: [],
      });
    }).catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-neutral-500">Carregando...</div>;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-light text-neutral-300">Dashboard</h1>
      {error && <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{error}</div>}

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-3">
        <KpiCard label="Vendas do dia" value={fmtBRL(dash.vendasDia)} valueClassName="text-green-400" />
        <KpiCard label="Vendas do mes" value={fmtBRL(dash.vendasMes)} valueClassName="text-blue-400" />
        <KpiCard label="Ticket medio" value={kpi ? "R$ " + Number(kpi.ticket_medio).toFixed(2) : "—"} />
        <KpiCard label="Receita (30d)" value={kpi ? fmtBRL(kpi.receita_total) : "—"} valueClassName="text-green-400" />
        <KpiCard label="Estoque critico" value={String(dash.estoqueCritico)} valueClassName="text-red-400" />
        <KpiCard label="Total itens" value={String(dash.estoqueTotal)} />
        <KpiCard label="Fluxo de caixa" value={fmtBRL(dash.fluxoCaixa)} valueClassName={dash.fluxoCaixa >= 0 ? "text-green-400" : "text-red-400"} />
        <KpiCard label="Clientes novos" value={String(dash.clientesNovos)} />
        <KpiCard label="Clientes total" value={String(dash.clientesTotal)} />
        <KpiCard label="Pedidos hoje" value={String(dash.vendasQtd)} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">Vendas do Mes</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            {dash.vendasMesChart.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={dash.vendasMesChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                  <XAxis dataKey="dia" stroke="#525252" tick={{ fontSize: 10 }} />
                  <YAxis stroke="#525252" tick={{ fontSize: 10 }} tickFormatter={v => "R$ " + v} />
                  <Tooltip content={<ChartTooltip />} />
                  <Line type="monotone" dataKey="valor" stroke="#6366f1" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : <div className="text-neutral-600 text-sm text-center py-20">Sem dados de vendas no periodo</div>}
          </div>
        </section>

        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">Agentes</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-3 space-y-1">
            {agents.slice(0, 8).map(a => (
              <div key={a.id} className="flex items-center justify-between px-2 py-1.5 rounded hover:bg-neutral-800/50">
                <span className="text-xs text-neutral-300">{a.name}</span>
                <span className={"inline-block w-2 h-2 rounded-full " + (a.status === "running" ? "bg-green-500" : "bg-yellow-500")} />
              </div>
            ))}
          </div>
        </section>
      </div>

      {dash.topProdutos.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">Top Produtos</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-3">
            <BarChart width={600} height={200} data={dash.topProdutos.slice(0, 8)} layout="vertical" margin={{ left: 120 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis type="number" stroke="#525252" tick={{ fontSize: 10 }} tickFormatter={v => fmtBRL(v)} />
              <YAxis type="category" dataKey="nome" stroke="#525252" tick={{ fontSize: 10 }} width={120} />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="valor" radius={[0, 4, 4, 0]}>{dash.topProdutos.map((e, i) => <Cell key={i} fill={margemColor(e.margem)} />)}</Bar>
            </BarChart>
          </div>
        </section>
      )}

      {dash.alertas.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">Alertas</h2>
          <div className="space-y-2">{dash.alertas.map((a, i) => (
            <div key={i} className={"bg-neutral-900 border border-neutral-800 border-l-4 rounded-lg px-4 py-2 flex items-center gap-3 " + (alertaStyles[a.tipo]?.border || "border-l-neutral-600")}>
              <span className={alertaStyles[a.tipo]?.badge || "bg-neutral-700 text-neutral-400"} style={{ padding: "2px 8px", borderRadius: "4px", fontSize: "10px" }}>{a.tipo}</span>
              <span className="text-xs text-neutral-300 flex-1">{a.mensagem}</span>
              <span className="text-[10px] text-neutral-500">{a.data}</span>
            </div>
          ))}</div>
        </section>
      )}
    </div>
  );
}
