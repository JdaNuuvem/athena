"use client";

import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from "recharts";
import { api, type KPIOverview, type Agent } from "@/lib/api";
import { useStore } from "@/lib/store-context";
import RankingProdutosModal from "@/app/_components/RankingProdutosModal";
import TabBar from "@/app/_components/TabBar";

type Aba = "geral" | "virtuais";
const ABAS_DASHBOARD = [
  { key: "geral", label: "Geral" },
  { key: "virtuais", label: "Virtuais" },
];

const fmtBRL = (v: number) => "R$ " + v.toLocaleString("pt-BR", { minimumFractionDigits: 2 });

const STATUS_COLOR = { ok: "var(--status-ok)", warn: "var(--status-warn)", crit: "var(--status-crit)" } as const;
type Status = keyof typeof STATUS_COLOR;

const margemColor = (m: number) => (m >= 25 ? STATUS_COLOR.ok : m >= 15 ? STATUS_COLOR.warn : STATUS_COLOR.crit);

const alertaMeta: Record<string, { status: Status; label: string }> = {
  critico: { status: "crit", label: "Crítico" },
  atencao: { status: "warn", label: "Atenção" },
  info: { status: "ok", label: "Info" },
};

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="instrument px-3 py-2 text-xs" style={{ boxShadow: "0 8px 24px -8px rgba(0,0,0,0.6)" }}>
      <div style={{ color: "var(--ink-500)" }}>{label}</div>
      <div className="numeric mt-0.5" style={{ color: "var(--ink-100)" }}>{fmtBRL(payload[0].value)}</div>
    </div>
  );
}

/** Primary instrument — the panel's largest readouts, one number owning the face. */
function PrimaryInstrument({ label, value, status, trend, hero }: { label: string; value: string; status?: Status; trend?: string; hero?: boolean }) {
  const color = hero ? "#ffffff" : status ? STATUS_COLOR[status] : "var(--ink-100)";
  return (
    <div className={hero ? "hero-gradient rounded-hero px-5 py-4 flex-1 min-w-[200px]" : "instrument instrument-lit px-5 py-4 flex-1 min-w-[200px]"}>
      <div className="flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-[0.12em]" style={{ color: hero ? "rgba(255,255,255,0.85)" : "var(--ink-500)" }}>{label}</div>
        {status && !hero && <span aria-hidden className="w-1.5 h-1.5 rounded-full" style={{ background: color, boxShadow: `0 0 6px ${color}` }} />}
      </div>
      <div className="numeric text-[28px] leading-tight font-medium mt-1.5" style={{ color }}>{value}</div>
      {trend && <div className="text-[11px] mt-1" style={{ color: hero ? "rgba(255,255,255,0.75)" : "var(--ink-700)" }}>{trend}</div>}
    </div>
  );
}

/** Secondary instrument — smaller readout for a supporting figure. */
function SecondaryInstrument({ label, value, status }: { label: string; value: string; status?: Status }) {
  const color = status ? STATUS_COLOR[status] : "var(--ink-300)";
  return (
    <div className="instrument px-3.5 py-3">
      <div className="text-[9px] uppercase tracking-[0.1em]" style={{ color: "var(--ink-700)" }}>{label}</div>
      <div className="numeric text-base font-medium mt-1" style={{ color }}>{value}</div>
    </div>
  );
}

interface DashboardData {
  vendasDia: number; vendasMes: number; vendasMesChart: { dia: string; valor: number }[];
  estoqueCritico: number; estoqueTotal: number;
  fluxoCaixa: number; clientesNovos: number; clientesTotal: number;
  vendasHoje: number; vendasQtd: number;
  topProdutos: { nome: string; valor: number; margem: number; atributo?: string | null; produto_pai?: string | null }[];
  alertas: { tipo: string; mensagem: string; data: string }[];
}

export default function DashboardPage() {
  const { lojaId } = useStore();
  const [aba, setAba] = useState<Aba>("geral");
  const [kpi, setKpi] = useState<KPIOverview | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [dash, setDash] = useState<DashboardData>({ vendasDia: 0, vendasMes: 0, vendasMesChart: [], estoqueCritico: 0, estoqueTotal: 0, fluxoCaixa: 0, clientesNovos: 0, clientesTotal: 0, vendasHoje: 0, vendasQtd: 0, topProdutos: [], alertas: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Aba "Geral" respeita o seletor global de loja (lojaId — especifica ou
  // "todas") normalmente. Aba "Virtuais" ignora lojaId e agrega todas as
  // lojas do tipo "virtual" (Shopee) de uma vez via tipo_loja — mesmos
  // componentes/secoes da pagina, so' com o conjunto de lojas trocado.
  const tipoLojaFiltro = aba === "virtuais" ? "virtual" : undefined;
  const lojaIdFiltro = aba === "virtuais" ? undefined : lojaId;

  useEffect(() => {
    Promise.all([
      api.kpiOverview(30, lojaIdFiltro, tipoLojaFiltro),
      api.agentsList(),
      api.relatorioVendas(1, lojaIdFiltro, undefined, undefined, tipoLojaFiltro),
      api.relatorioVendas(30, lojaIdFiltro, undefined, undefined, tipoLojaFiltro),
      api.relatorioEstoque(lojaIdFiltro, tipoLojaFiltro),
      api.relatorioFluxoCaixa(30, lojaIdFiltro, undefined, undefined, tipoLojaFiltro),
      api.relatorioClientes(30, lojaIdFiltro, undefined, undefined, tipoLojaFiltro),
    ]).then(([k, a, r1, r30, est, fc, cli]: [
      Record<string, unknown>, { agents: Agent[] }, Record<string, unknown>, Record<string, unknown>,
      Record<string, unknown>, Record<string, unknown>, Record<string, unknown>,
    ]) => {
      setKpi(k as unknown as KPIOverview);
      setAgents(a.agents);
      const diarias = ((r30.diarias as any[]) || []).map((d: any) => ({ dia: (d.dia || "").slice(8, 10), valor: d.valor || 0 }));
      setDash({
        vendasDia: Number(r1.total) || 0,
        vendasMes: Number(r30.total) || 0,
        vendasMesChart: diarias,
        estoqueCritico: Number(est.baixo_estoque) || 0,
        estoqueTotal: Number(est.total_itens) || 0,
        fluxoCaixa: Number(fc.saldo) || 0,
        clientesNovos: Number(cli.novos) || 0,
        clientesTotal: Number(cli.total) || 0,
        vendasHoje: Number(r1.total) || 0,
        vendasQtd: Number(r1.quantidade) || 0,
        topProdutos: (k as any)?.top_skus || [],
        alertas: [],
      });
    }).catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, [lojaId, aba]);

  if (loading) {
    return (
      <div className="p-6 flex items-center gap-2 text-sm" style={{ color: "var(--ink-500)" }}>
        <span aria-hidden className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: "var(--accent-400)" }} />
        Calibrando instrumentos…
      </div>
    );
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em]" style={{ color: "var(--ink-500)" }}>Painel de Operação</h1>
          {aba === "virtuais" && (
            <p className="text-[11px] mt-0.5" style={{ color: "var(--ink-700)" }}>Todas as lojas virtuais</p>
          )}
        </div>
        <div className="flex items-center gap-1.5 text-[11px]" style={{ color: "var(--ink-700)" }}>
          <span aria-hidden className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--status-ok)" }} />
          Sistema operando
        </div>
      </div>

      <TabBar tabs={ABAS_DASHBOARD} active={aba} onChange={(k) => setAba(k as Aba)} />

      {error && (
        <div className="instrument px-4 py-3 text-sm" style={{ borderColor: "var(--status-crit)", color: "var(--status-crit)" }}>
          {error}
        </div>
      )}

      {/* Primary instruments — the panel's biggest readouts */}
      <div className="flex flex-wrap gap-3">
        <PrimaryInstrument label="Vendas hoje" value={fmtBRL(dash.vendasDia)} trend={`${dash.vendasQtd} pedido${dash.vendasQtd === 1 ? "" : "s"}`} hero />
        <PrimaryInstrument label="Vendas do mês" value={fmtBRL(dash.vendasMes)} />
        <PrimaryInstrument
          label="Fluxo de caixa (30d)"
          value={fmtBRL(dash.fluxoCaixa)}
          status={dash.fluxoCaixa >= 0 ? "ok" : "crit"}
        />
      </div>

      {/* Secondary instruments — supporting figures */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
        <SecondaryInstrument label="Ticket médio" value={kpi ? fmtBRL(Number(kpi.ticket_medio)) : "—"} />
        <SecondaryInstrument label="Receita (30d)" value={kpi ? fmtBRL(kpi.receita_total) : "—"} status="ok" />
        <SecondaryInstrument label="Estoque crítico" value={String(dash.estoqueCritico)} status={dash.estoqueCritico > 0 ? "crit" : "ok"} />
        <SecondaryInstrument label="Total de itens" value={String(dash.estoqueTotal)} />
        <SecondaryInstrument label="Clientes novos" value={String(dash.clientesNovos)} status="ok" />
        <SecondaryInstrument label="Clientes total" value={String(dash.clientesTotal)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <section className="lg:col-span-2 instrument p-4">
          <h2 className="text-[10px] uppercase tracking-[0.12em] mb-3" style={{ color: "var(--ink-500)" }}>Vendas do mês</h2>
          {dash.vendasMesChart.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={dash.vendasMesChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--panel-border)" />
                <XAxis dataKey="dia" stroke="var(--ink-700)" tick={{ fontSize: 10, fill: "var(--ink-700)" }} />
                <YAxis stroke="var(--ink-700)" tick={{ fontSize: 10, fill: "var(--ink-700)" }} tickFormatter={(v) => "R$ " + v} />
                <Tooltip content={<ChartTooltip />} />
                <Line type="monotone" dataKey="valor" stroke="var(--accent-400)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-sm text-center py-20" style={{ color: "var(--ink-700)" }}>Sem dados de vendas no período</div>
          )}
        </section>

        <section className="instrument p-4">
          <h2 className="text-[10px] uppercase tracking-[0.12em] mb-3" style={{ color: "var(--ink-500)" }}>Agentes</h2>
          <div className="space-y-0.5">
            {agents.slice(0, 8).map((a) => (
              <div key={a.id} className="flex items-center justify-between px-2 py-1.5 rounded transition-colors hover-surface">
                <span className="text-xs" style={{ color: "var(--ink-300)" }}>{a.name}</span>
                <span
                  aria-hidden
                  className="inline-block w-1.5 h-1.5 rounded-full"
                  style={{
                    background: a.status === "running" ? "var(--status-ok)" : "var(--status-warn)",
                    boxShadow: `0 0 5px ${a.status === "running" ? "var(--status-ok)" : "var(--status-warn)"}`,
                  }}
                />
              </div>
            ))}
            {agents.length === 0 && <div className="text-xs px-2 py-4 text-center" style={{ color: "var(--ink-700)" }}>Nenhum agente ativo</div>}
          </div>
        </section>
      </div>

      {dash.topProdutos.length > 0 && (() => {
        // produto_pai/atributo vem da hierarquia Bling (ver
        // core/relatorios.py::ranking_produtos) — "nome" sozinho as vezes e'
        // so' a descricao completa do SKU (ex: "Camiseta - Tamanho P"), dificil
        // de comparar visualmente com as outras variacoes do mesmo produto.
        // Quando a hierarquia existe, mostra "Produto base · Variação".
        const dadosGrafico = dash.topProdutos.slice(0, 8).map((p) => ({
          ...p,
          rotulo: p.produto_pai && p.atributo ? `${p.produto_pai} · ${p.atributo}` : p.nome,
        }));
        return (
          <section className="instrument p-4">
            <h2 className="text-[10px] uppercase tracking-[0.12em] mb-3" style={{ color: "var(--ink-500)" }}>Top produtos</h2>
            <ResponsiveContainer width="100%" height={dadosGrafico.length * 36 + 20}>
              <BarChart data={dadosGrafico} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--panel-border)" horizontal={false} />
                <XAxis type="number" stroke="var(--ink-700)" tick={{ fontSize: 10, fill: "var(--ink-700)" }} tickFormatter={(v) => fmtBRL(v)} />
                <YAxis
                  type="category"
                  dataKey="rotulo"
                  stroke="var(--ink-700)"
                  tick={{ fontSize: 10, fill: "var(--ink-700)" }}
                  width={160}
                  tickFormatter={(rotulo) => (rotulo.length > 22 ? `${rotulo.slice(0, 21)}…` : rotulo)}
                />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="valor" radius={[0, 3, 3, 0]} barSize={18}>
                  {dadosGrafico.map((e, i) => <Cell key={i} fill={margemColor(e.margem)} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </section>
        );
      })()}

      <RankingProdutosModal lojaId={lojaIdFiltro} tipoLoja={tipoLojaFiltro} inline />

      {dash.alertas.length > 0 && (
        <section>
          <h2 className="text-[10px] uppercase tracking-[0.12em] mb-2" style={{ color: "var(--ink-500)" }}>Alertas</h2>
          <div className="space-y-1.5">
            {dash.alertas.map((a, i) => {
              const meta = alertaMeta[a.tipo] || { status: "ok" as Status, label: a.tipo };
              const color = STATUS_COLOR[meta.status];
              return (
                <div key={i} className="instrument px-3.5 py-2.5 flex items-center gap-3">
                  <span aria-hidden className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: color, boxShadow: `0 0 5px ${color}` }} />
                  <span
                    className="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded shrink-0"
                    style={{ background: `${color}22`, color }}
                  >
                    {meta.label}
                  </span>
                  <span className="text-xs flex-1" style={{ color: "var(--ink-300)" }}>{a.mensagem}</span>
                  <span className="text-[10px] numeric shrink-0" style={{ color: "var(--ink-700)" }}>{a.data}</span>
                </div>
              );
            })}
          </div>
        </section>
      )}

    </div>
  );
}
