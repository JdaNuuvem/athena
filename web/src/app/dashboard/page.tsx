"use client";

import { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from "recharts";
import { api, type KPIOverview, type Agent } from "@/lib/api";

const kpisMock = {
  vendasDia: 12450.00, vendasMes: 287320.00, pedidosAberto: 23,
  pedidosFaturados: 156, estoqueCritico: 8, produtosSemGiro: 12,
  contasPagar: 45200.00, contasReceber: 89700.00,
  fluxoCaixa: 44500.00, lucratividade: 32.5,
  clientesNovos: 47, clientesRecorrentes: 89,
};

const vendasMesChart = [
  { dia: "01", valor: 8200 }, { dia: "02", valor: 9100 }, { dia: "03", valor: 7800 },
  { dia: "04", valor: 6500 }, { dia: "05", valor: 10500 }, { dia: "06", valor: 11200 },
  { dia: "07", valor: 8900 }, { dia: "08", valor: 9400 }, { dia: "09", valor: 8700 },
  { dia: "10", valor: 10100 }, { dia: "11", valor: 12300 }, { dia: "12", valor: 11800 },
  { dia: "13", valor: 9600 }, { dia: "14", valor: 10800 }, { dia: "15", valor: 13400 },
  { dia: "16", valor: 8600 }, { dia: "17", valor: 9200 }, { dia: "18", valor: 10300 },
  { dia: "19", valor: 9800 }, { dia: "20", valor: 12100 }, { dia: "21", valor: 11500 },
  { dia: "22", valor: 8900 }, { dia: "23", valor: 9500 }, { dia: "24", valor: 10700 },
  { dia: "25", valor: 8400 }, { dia: "26", valor: 10200 }, { dia: "27", valor: 11600 },
  { dia: "28", valor: 9900 }, { dia: "29", valor: 8800 }, { dia: "30", valor: 13200 },
];

const topProdutosChart = [
  { nome: "Organizador MC-001", valor: 45300, margem: 38.5 },
  { nome: "Garrafa Térmica", valor: 38200, margem: 42.1 },
  { nome: "Kit Presente", valor: 29100, margem: 28.3 },
  { nome: "Jogo de Copos", valor: 22400, margem: 18.7 },
  { nome: "Porta Temperos", valor: 18700, margem: 14.2 },
];

const alertasMock = [
  { tipo: "critico", mensagem: 'Estoque de "Organizador MC-001" abaixo do mínimo (Matriz: 8 un)', data: "14/07 14:30" },
  { tipo: "atencao", mensagem: "3 pedidos aguardando faturamento há mais de 48h", data: "14/07 12:15" },
  { tipo: "atencao", mensagem: "Conta a pagar de R$ 12.300,00 vence em 2 dias", data: "14/07 10:00" },
  { tipo: "info", mensagem: "Sincronização Bling concluída — 234 produtos atualizados", data: "14/07 08:45" },
  { tipo: "info", mensagem: "AG-04 produziu novo plano diário com 87% de ocupação", data: "14/07 07:30" },
];

const fmtBRL = (v: number) => `R$ ${v.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;

const alertaStyles: Record<string, { border: string; badge: string; icon: string }> = {
  critico: { border: "border-l-red-500", badge: "bg-red-500/10 text-red-400 border border-red-500/30", icon: "🔴" },
  atencao: { border: "border-l-amber-500", badge: "bg-amber-500/10 text-amber-400 border border-amber-500/30", icon: "🟡" },
  info: { border: "border-l-blue-500", badge: "bg-blue-500/10 text-blue-400 border border-blue-500/30", icon: "🔵" },
};

const margemColor = (m: number) =>
  m >= 25 ? "#22c55e" : m >= 15 ? "#f59e0b" : "#ef4444";

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2 text-xs shadow-lg">
      <div className="text-neutral-400">{label}</div>
      <div className="text-neutral-100 numeric">{fmtBRL(payload[0].value)}</div>
    </div>
  );
}

export default function DashboardPage() {
  const [kpi, setKpi] = useState<KPIOverview | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.kpiOverview(), api.agentsList()])
      .then(([k, a]) => {
        setKpi(k as unknown as KPIOverview);
        setAgents(a.agents);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao carregar dashboard"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-neutral-500">Carregando...</div>;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-light text-neutral-300">Dashboard</h1>

      {error && (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {/* KPIs — 14 cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-3">
        <KpiCard label="Vendas do dia" value={fmtBRL(kpisMock.vendasDia)} />
        <KpiCard label="Vendas do mês" value={fmtBRL(kpisMock.vendasMes)} />
        <KpiCard label="Ticket médio" value={kpi ? `R$ ${Number(kpi.ticket_medio).toFixed(2)}` : "—"} />
        <KpiCard label="Pedidos em aberto" value={String(kpisMock.pedidosAberto)} />
        <KpiCard label="Pedidos faturados" value={String(kpisMock.pedidosFaturados)} />
        <KpiCard label="Receita (30d)" value={kpi ? fmtBRL(kpi.receita_total) : "—"} />
        <KpiCard label="Estoque crítico" value={String(kpisMock.estoqueCritico)} valueClassName="text-red-400" />
        <KpiCard label="Produtos s/ giro" value={String(kpisMock.produtosSemGiro)} valueClassName="text-amber-400" />
        <KpiCard label="Contas a pagar" value={fmtBRL(kpisMock.contasPagar)} />
        <KpiCard label="Contas a receber" value={fmtBRL(kpisMock.contasReceber)} />
        <KpiCard label="Fluxo de caixa" value={fmtBRL(kpisMock.fluxoCaixa)} valueClassName={kpisMock.fluxoCaixa >= 0 ? "text-green-400" : "text-red-400"} />
        <KpiCard label="Lucratividade" value={`${kpisMock.lucratividade}%`} valueClassName="text-green-400" />
        <KpiCard label="Clientes novos" value={String(kpisMock.clientesNovos)} />
        <KpiCard label="Recorrentes" value={String(kpisMock.clientesRecorrentes)} />
      </div>

      {/* Gráficos */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">Vendas do Mês</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={vendasMesChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="dia" tick={{ fill: "#71717a", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis
                  tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)}
                  tick={{ fill: "#71717a", fontSize: 11 }} axisLine={false} tickLine={false} width={48}
                />
                <Tooltip content={<ChartTooltip />} />
                <defs>
                  <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#818cf8" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#818cf8" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Line type="monotone" dataKey="valor" stroke="#818cf8" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: "#818cf8" }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">Top 5 Produtos</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={topProdutosChart} layout="vertical" margin={{ top: 0, right: 8, left: 8, bottom: 0 }}>
                <XAxis type="number" tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)} tick={{ fill: "#71717a", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="nome" tick={{ fill: "#71717a", fontSize: 11 }} axisLine={false} tickLine={false} width={120} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                <Bar dataKey="valor" radius={[0, 4, 4, 0]} barSize={16}>
                  {topProdutosChart.map((entry, i) => (
                    <Cell key={i} fill={margemColor(entry.margem)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      {/* Alertas */}
      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Alertas</h2>
        <div className="space-y-2">
          {alertasMock.map((a, i) => {
            const s = alertaStyles[a.tipo];
            return (
              <div key={i} className={`bg-neutral-900 border border-neutral-800 ${s.border} border-l-4 rounded-lg p-3 flex items-start gap-3`}>
                <span className="text-sm mt-0.5">{s.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded ${s.badge}`}>
                      {a.tipo === "critico" ? "Crítico" : a.tipo === "atencao" ? "Atenção" : "Info"}
                    </span>
                    <span className="text-[10px] text-neutral-600">{a.data}</span>
                  </div>
                  <p className="text-sm text-neutral-300">{a.mensagem}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Agentes (existente) */}
      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Agentes</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {agents.map((a) => (
            <a
              key={a.id}
              href={`/agents/${a.id}`}
              className="bg-neutral-900 border border-neutral-800 rounded-lg p-3 hover:border-neutral-700 transition-colors"
            >
              <div className="flex items-center gap-2 mb-1">
                <span
                  aria-label={`status: ${a.status}`}
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    a.status === "running" ? "bg-green-500" : a.status === "idle" ? "bg-yellow-500" : "bg-red-500"
                  }`}
                />
                <span className="text-xs text-neutral-400 truncate">{a.id}</span>
              </div>
              <div className="text-sm font-medium text-neutral-200 truncate">{a.name}</div>
              <div className="text-[10px] text-neutral-500 uppercase mt-1 truncate">{a.role}</div>
              <div className="text-xs text-neutral-500 mt-1 numeric">{a.taskCount} tarefas</div>
            </a>
          ))}
        </div>
      </section>

      {/* Top SKUs (existente) */}
      {kpi?.top_skus && kpi.top_skus.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">Top SKUs</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
            <table className="w-full text-sm min-w-[560px]">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                  <th className="text-left p-3 font-medium">SKU</th>
                  <th className="text-left p-3 font-medium">Nome</th>
                  <th className="text-right p-3 font-medium">Vendidos</th>
                  <th className="text-right p-3 font-medium">Receita</th>
                  <th className="text-right p-3 font-medium">Margem</th>
                </tr>
              </thead>
              <tbody>
                {kpi.top_skus.map((sku) => (
                  <tr key={sku.sku} className="border-b border-neutral-800/50 last:border-0 hover:bg-neutral-800/30">
                    <td className="p-3 text-indigo-400 font-mono text-xs numeric">{sku.sku}</td>
                    <td className="p-3 text-neutral-300">{sku.nome}</td>
                    <td className="p-3 text-right text-neutral-400 numeric">{sku.qtd}</td>
                    <td className="p-3 text-right text-neutral-300 numeric">R$ {Number(sku.receita).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                    <td className="p-3 text-right">
                      <span className={`numeric ${Number(sku.margem) >= 25 ? "text-green-400" : Number(sku.margem) >= 15 ? "text-yellow-400" : "text-red-400"}`}>
                        {Number(sku.margem).toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function KpiCard({ label, value, valueClassName }: { label: string; value: string; valueClassName?: string }) {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
      <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-2xl font-light numeric ${valueClassName ?? "text-neutral-100"}`}>{value}</div>
    </div>
  );
}
