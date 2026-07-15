"use client";

import { useEffect, useState, useCallback } from "react";
import { vendasDashboard, vendasList, vendasSyncBling, vendasDetalhePedido, vendasAtualizarStatus } from "@/lib/api";
import DateFilter, { type DateFilterValue } from "@/app/_components/DateFilter";
import { fmtBRL } from "@/lib/format";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import { Can } from "@/lib/auth";

interface PedidoRow {
  id: number;
  numero: string;
  cliente: string;
  total: number;
  status: string;
  data: string;
  marketplace: string;
  vendedor: string;
}

interface DashboardData {
  total_vendas: number;
  quantidade: number;
  ticket_medio: number;
  pedidos_abertos: number;
  faturados: number;
  cancelados: number;
  diarias: Array<{ dia: string; qtd: number; valor: number }>;
  por_canal: Array<{ canal: string; qtd: number; valor: number }>;
  recentes: PedidoRow[];
}

const STATUS_VARIANT: Record<string, "success" | "danger" | "warning" | "neutral"> = {
  aberto: "warning", em_andamento: "warning", faturado: "success",
  concluido: "success", cancelado: "danger", devolvido: "neutral",
};

const TABS = [
  { key: "", label: "Todos" },
  { key: "aberto", label: "Abertos" },
  { key: "em_andamento", label: "Andamento" },
  { key: "faturado", label: "Faturados" },
  { key: "concluido", label: "Concluídos" },
  { key: "cancelado", label: "Cancelados" },
];

export default function VendasPage() {
  const [dash, setDash] = useState<DashboardData | null>(null);
  const [pedidos, setPedidos] = useState<PedidoRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [dateFilter, setDateFilter] = useState<DateFilterValue>({});
  const [statusTab, setStatusTab] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detalhe, setDetalhe] = useState<Record<string, unknown> | null>(null);

  const carregarDashboard = useCallback(() => {
    const dias = dateFilter.dias || (dateFilter.data_inicio ? 0 : 30);
    vendasDashboard(dias || undefined)
      .then(d => setDash(d as unknown as DashboardData))
      .catch(() => {});
  }, [dateFilter]);

  const carregarPedidos = useCallback(() => {
    const params: Record<string, string> = {};
    if (dateFilter.data_inicio) params.data_inicio = dateFilter.data_inicio;
    if (dateFilter.data_fim) params.data_fim = dateFilter.data_fim;
    if (dateFilter.dias) params.dias = String(dateFilter.dias);
    if (statusTab) params.status = statusTab;
    vendasList("pedidos", params)
      .then(r => setPedidos((r.data || []) as PedidoRow[]))
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar"));
  }, [dateFilter, statusTab]);

  useEffect(() => {
    setLoading(true);
    setErro(null);
    Promise.all([carregarDashboard(), carregarPedidos()])
      .finally(() => setLoading(false));
  }, [carregarDashboard, carregarPedidos]);

  const sync = async () => {
    setSyncing(true);
    try {
      const r = await vendasSyncBling();
      if (r.error) setErro(r.error);
      carregarPedidos();
      carregarDashboard();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao sincronizar");
    } finally {
      setSyncing(false);
    }
  };

  const toggleDetalhe = async (id: number) => {
    if (expandedId === id) { setExpandedId(null); setDetalhe(null); return; }
    setExpandedId(id);
    const d = await vendasDetalhePedido(id);
    setDetalhe(d as unknown as Record<string, unknown>);
  };

  const mudarStatus = async (id: number, status: string) => {
    await vendasAtualizarStatus(id, status);
    carregarPedidos();
    carregarDashboard();
    setExpandedId(null);
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <PageHeader title="Vendas" subtitle="Pedidos de venda e faturamento" />
        <div className="flex items-center gap-3">
          <DateFilter value={dateFilter} onChange={setDateFilter} />
          <Can permission="orders:edit">
          <button
            onClick={sync}
            disabled={syncing}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs rounded whitespace-nowrap"
          >
            {syncing ? "Sincronizando..." : "Sync Bling"}
          </button>
          </Can>
        </div>
      </div>

      <ErrorAlert message={erro} />

      {loading ? (
        <LoadingState />
      ) : (
        <>
          {/* KPIs */}
          {dash && (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              <KpiCard metric={{ label: "Total vendas", value: fmtBRL(dash.total_vendas), color: "text-emerald-400" }} />
              <KpiCard metric={{ label: "Pedidos", value: String(dash.quantidade), color: "text-blue-400" }} />
              <KpiCard metric={{ label: "Ticket médio", value: fmtBRL(dash.ticket_medio), color: "text-purple-400" }} />
              <KpiCard metric={{ label: "Abertos", value: String(dash.pedidos_abertos), color: "text-amber-400" }} />
              <KpiCard metric={{ label: "Faturados", value: String(dash.faturados), color: "text-emerald-400" }} />
              <KpiCard metric={{ label: "Cancelados", value: String(dash.cancelados), color: "text-red-400" }} />
            </div>
          )}

          {/* Gráfico diário simplificado */}
          {dash?.diarias && dash.diarias.length > 0 && (
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
              <h3 className="text-xs font-semibold text-neutral-400 mb-3">Vendas diárias</h3>
              <div className="flex items-end gap-1 h-24">
                {dash.diarias.map((d, i) => {
                  const maxVal = Math.max(...dash.diarias.map(x => x.valor), 1);
                  const h = Math.max(4, (d.valor / maxVal) * 80);
                  return (
                    <div key={i} className="flex-1 flex flex-col items-center justify-end gap-1 group relative" title={`${d.dia?.slice(5)}: ${fmtBRL(d.valor)}`}>
                      <span className="text-[9px] text-neutral-500 opacity-0 group-hover:opacity-100 transition-opacity">{fmtBRL(d.valor)}</span>
                      <div className="w-full bg-emerald-600/60 hover:bg-emerald-500 rounded-t" style={{ height: `${h}px` }} />
                      <span className="text-[8px] text-neutral-600">{d.dia?.slice(8) || ""}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Canais */}
          {dash?.por_canal && dash.por_canal.length > 0 && (
            <div className="flex gap-2 flex-wrap">
              {dash.por_canal.map(c => (
                <span key={c.canal} className="bg-neutral-800 border border-neutral-700 rounded px-2 py-0.5 text-[10px] text-neutral-400">
                  {c.canal || "manual"}: {fmtBRL(c.valor)} ({c.qtd} pedidos)
                </span>
              ))}
            </div>
          )}

          {/* Tabs de status */}
          <div className="flex gap-1 flex-wrap">
            {TABS.map(t => (
              <button
                key={t.key}
                onClick={() => setStatusTab(t.key)}
                className={`px-3 py-1 text-xs rounded ${statusTab === t.key ? "bg-blue-600 text-white" : "bg-neutral-800 text-neutral-400 hover:bg-neutral-700"}`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Tabela de pedidos */}
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-neutral-700 text-neutral-400">
                  <th className="text-left p-2">#</th>
                  <th className="text-left p-2">Cliente</th>
                  <th className="text-center p-2">Status</th>
                  <th className="text-right p-2">Total</th>
                  <th className="text-center p-2">Data</th>
                  <th className="text-center p-2">Canal</th>
                  <th className="text-center p-2">Vendedor</th>
                </tr>
              </thead>
              <tbody>
                {pedidos.length === 0 ? (
                  <tr><td colSpan={7} className="p-4 text-center text-neutral-500">Nenhum pedido encontrado</td></tr>
                ) : (
                  pedidos.map(p => (
                    <tr key={p.id} className={`border-b border-neutral-700/50 hover:bg-neutral-700/30 cursor-pointer ${expandedId === p.id ? "bg-neutral-700/50" : ""}`} onClick={() => toggleDetalhe(p.id)}>
                      <td className="p-2 text-neutral-300">{p.id}</td>
                      <td className="p-2 text-neutral-200">{p.cliente}</td>
                      <td className="p-2 text-center">
                        <StatusBadge label={p.status} variant={STATUS_VARIANT[p.status] || "neutral"} />
                      </td>
                      <td className="p-2 text-right text-emerald-400">{fmtBRL(p.total)}</td>
                      <td className="p-2 text-center text-neutral-400">{String(p.data || "—").slice(0, 10)}</td>
                      <td className="p-2 text-center text-neutral-500">{p.marketplace || "manual"}</td>
                      <td className="p-2 text-center text-neutral-500">{p.vendedor || "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Detalhe expandido */}
          {expandedId && detalhe && (
            <div className="bg-neutral-800 border border-blue-700 rounded-lg p-4 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-neutral-200">Pedido #{expandedId}</h3>
                <button onClick={() => setExpandedId(null)} className="text-neutral-500 hover:text-neutral-300 text-xs">✕ Fechar</button>
              </div>

              {/* Itens */}
              <div>
                <h4 className="text-xs font-semibold text-neutral-400 mb-2">Itens</h4>
                <div className="overflow-hidden rounded border border-neutral-700">
                  <table className="w-full text-xs">
                    <thead><tr className="border-b border-neutral-700 text-neutral-400"><th className="text-left p-1.5">SKU</th><th className="text-left p-1.5">Descrição</th><th className="text-right p-1.5">Qtd</th><th className="text-right p-1.5">Unit.</th><th className="text-right p-1.5">Total</th></tr></thead>
                    <tbody>
                      {(detalhe.itens as unknown[])?.map((item: unknown, i: number) => {
                        const it = item as Record<string, unknown>;
                        return (
                          <tr key={i} className="border-b border-neutral-700/50">
                            <td className="p-1.5 text-neutral-300">{String(it.sku ?? "")}</td>
                            <td className="p-1.5 text-neutral-400">{String(it.descricao ?? "—")}</td>
                            <td className="p-1.5 text-right text-neutral-300">{String(it.quantidade ?? 0)}</td>
                            <td className="p-1.5 text-right text-neutral-400">{fmtBRL(Number(it.valor_unitario ?? 0))}</td>
                            <td className="p-1.5 text-right text-emerald-400">{fmtBRL(Number(it.valor_total ?? 0))}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Pagamentos */}
              <div>
                <h4 className="text-xs font-semibold text-neutral-400 mb-2">Pagamentos</h4>
                <div className="flex gap-2 flex-wrap">
                  {(detalhe.pagamentos as unknown[])?.map((pg: unknown, i: number) => {
                    const p = pg as Record<string, unknown>;
                    return (
                      <span key={i} className="bg-neutral-700 rounded px-2 py-0.5 text-[10px] text-neutral-300">
                        {String(p.forma ?? "")}: {fmtBRL(Number(p.valor ?? 0))} {Number(p.parcelas ?? 1) > 1 ? `(${p.parcelas}x)` : ""}
                      </span>
                    );
                  })}
                </div>
              </div>

              {/* Ações de status */}
              <Can permission="orders:edit">
              <div className="flex gap-2 flex-wrap">
                {["aberto", "em_andamento", "faturado", "concluido", "cancelado"].map(s => (
                  <button
                    key={s}
                    onClick={() => mudarStatus(expandedId, s)}
                    className={`px-2 py-1 text-[10px] rounded ${s === "cancelado" ? "bg-red-700 hover:bg-red-600" : "bg-neutral-700 hover:bg-neutral-600"} text-white`}
                  >
                    {s === "em_andamento" ? "Em andamento" : s.charAt(0).toUpperCase() + s.slice(1)}
                  </button>
                ))}
              </div>
              </Can>
            </div>
          )}
        </>
      )}
    </div>
  );
}
