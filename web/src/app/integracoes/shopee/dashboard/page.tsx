"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "@/lib/api";
import type { ShopeeDashboardLoja, ShopeeSerieDiariaPonto, ShopeeTopProdutoHoje, ShopeeEstoqueRisco, ShopeeShopPerformance } from "@/lib/api";
import Icon from "@/app/_components/Icon";
import RankingProdutosModal from "@/app/_components/RankingProdutosModal";

const fmtBRL = (v: number) => "R$ " + Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const RATING_META: Record<number, { label: string; className: string }> = {
  1: { label: "Ruim", className: "bg-red-950/40 border-red-900/50 text-red-400" },
  2: { label: "Precisa melhorar", className: "bg-amber-950/40 border-amber-900/50 text-amber-400" },
  3: { label: "Boa", className: "bg-emerald-950/40 border-emerald-900/50 text-emerald-400" },
  4: { label: "Excelente", className: "bg-emerald-950/40 border-emerald-900/50 text-emerald-300" },
};

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number; name: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2 text-xs shadow-lg">
      <div className="text-neutral-500">{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="numeric text-neutral-200 mt-0.5">{p.name === "receita" ? fmtBRL(p.value) : p.value}</div>
      ))}
    </div>
  );
}

interface SaudeState {
  [lojaId: number]: { loading: boolean; performance?: ShopeeShopPerformance; erro?: string };
}

export default function ShopeeDashboardPage() {
  const [lojas, setLojas] = useState<ShopeeDashboardLoja[]>([]);
  const [serieDiaria, setSerieDiaria] = useState<ShopeeSerieDiariaPonto[]>([]);
  const [topProdutosHoje, setTopProdutosHoje] = useState<ShopeeTopProdutoHoje[]>([]);
  const [estoqueRisco, setEstoqueRisco] = useState<ShopeeEstoqueRisco[]>([]);
  const [dias, setDias] = useState(30);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [showRanking, setShowRanking] = useState(false);
  const [saude, setSaude] = useState<SaudeState>({});

  const carregar = useCallback(async () => {
    setLoading(true);
    setErro(null);
    try {
      const r = await api.shopeeDashboard(dias);
      if (r.error) setErro(r.error);
      setLojas(r.lojas || []);
      setSerieDiaria(r.serie_diaria || []);
      setTopProdutosHoje(r.top_produtos_hoje || []);
      setEstoqueRisco(r.estoque_risco || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar painel");
    } finally {
      setLoading(false);
    }
  }, [dias]);

  useEffect(() => { carregar(); }, [carregar]);

  useEffect(() => {
    const lojasAtivas = lojas.filter((l) => l.tem_token);
    if (lojasAtivas.length === 0) return;
    lojasAtivas.forEach((l) => {
      setSaude((s) => ({ ...s, [l.loja_id]: { loading: true } }));
      api.shopeeSaudePerformance(l.loja_id)
        .then((r) => {
          if (r.error || !r.response) {
            setSaude((s) => ({ ...s, [l.loja_id]: { loading: false, erro: r.error || "Indisponível" } }));
          } else {
            setSaude((s) => ({ ...s, [l.loja_id]: { loading: false, performance: r.response } }));
          }
        })
        .catch((e) => setSaude((s) => ({ ...s, [l.loja_id]: { loading: false, erro: e instanceof Error ? e.message : "Erro" } })));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lojas.map((l) => l.loja_id).join(",")]);

  const totalReceita = lojas.reduce((s, l) => s + Number(l.receita || 0), 0);
  const totalUnidades = lojas.reduce((s, l) => s + Number(l.unidades_vendidas || 0), 0);
  const totalAnunciosAtivos = lojas.reduce((s, l) => s + Number(l.anuncios_ativos || 0), 0);
  const totalEstoqueBaixo = lojas.reduce((s, l) => s + Number(l.produtos_estoque_baixo || 0), 0);
  const maiorReceita = Math.max(1, ...lojas.map(l => Number(l.receita || 0)));

  const receitaHoje = lojas.reduce((s, l) => s + Number(l.receita_hoje || 0), 0);
  const pedidosHoje = lojas.reduce((s, l) => s + Number(l.pedidos_hoje || 0), 0);
  const unidadesHoje = lojas.reduce((s, l) => s + Number(l.unidades_hoje || 0), 0);
  const ticketMedioHoje = pedidosHoje > 0 ? receitaHoje / pedidosHoje : 0;

  const chartData = serieDiaria.map((p) => ({ ...p, diaLabel: p.dia.slice(8, 10) + "/" + p.dia.slice(5, 7) }));

  return (
    <div className="p-6 space-y-4 max-w-5xl">
      <div>
        <Link href="/integracoes/shopee" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors inline-flex items-center gap-1"><Icon name="chevronLeft" size={14} /> Shopee</Link>
        <h1 className="text-lg font-light text-neutral-300 mt-1">Painel Consolidado Shopee</h1>
        <p className="text-xs text-neutral-500 mt-0.5">Visão geral das lojas Shopee conectadas.</p>
      </div>

      <div className="flex items-center gap-2">
        <select
          value={dias}
          onChange={(e) => setDias(Number(e.target.value))}
          className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
        >
          <option value={7}>Últimos 7 dias</option>
          <option value={30}>Últimos 30 dias</option>
          <option value={90}>Últimos 90 dias</option>
        </select>
        <button
          onClick={carregar}
          disabled={loading}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
        >
          {loading ? "Carregando..." : "Atualizar"}
        </button>
        <button
          onClick={() => setShowRanking(true)}
          className="bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-sm px-4 py-2 rounded-lg transition-colors ml-auto"
        >
          Ranking de produtos
        </button>
      </div>

      {erro && (
        <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erro}</div>
      )}

      {!loading && lojas.length === 0 && !erro && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 text-center text-neutral-500 text-sm">
          Nenhuma loja Shopee conectada ainda.
        </div>
      )}

      {lojas.length > 0 && (
        <>
          <div>
            <p className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Hoje</p>
            <div className="instrument-enter grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="instrument-hover bg-neutral-900 border border-neutral-800 rounded-lg p-3">
                <p className="text-xs text-neutral-500 uppercase tracking-wider">Vendido Hoje</p>
                <p className="text-lg text-emerald-400 numeric font-medium">{fmtBRL(receitaHoje)}</p>
              </div>
              <div className="instrument-hover bg-neutral-900 border border-neutral-800 rounded-lg p-3">
                <p className="text-xs text-neutral-500 uppercase tracking-wider">Pedidos Hoje</p>
                <p className="text-lg text-neutral-200 numeric font-medium">{pedidosHoje}</p>
              </div>
              <div className="instrument-hover bg-neutral-900 border border-neutral-800 rounded-lg p-3">
                <p className="text-xs text-neutral-500 uppercase tracking-wider">Unidades Hoje</p>
                <p className="text-lg text-neutral-200 numeric font-medium">{unidadesHoje}</p>
              </div>
              <div className="instrument-hover bg-neutral-900 border border-neutral-800 rounded-lg p-3">
                <p className="text-xs text-neutral-500 uppercase tracking-wider">Ticket Médio Hoje</p>
                <p className="text-lg text-neutral-200 numeric font-medium">{fmtBRL(ticketMedioHoje)}</p>
              </div>
            </div>
          </div>

          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            <p className="text-xs text-neutral-500 uppercase tracking-wider mb-3">Vendas — últimos {dias} dias</p>
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                  <XAxis dataKey="diaLabel" stroke="#737373" tick={{ fontSize: 10, fill: "#737373" }} />
                  <YAxis stroke="#737373" tick={{ fontSize: 10, fill: "#737373" }} tickFormatter={(v) => "R$ " + v} width={70} />
                  <Tooltip content={<ChartTooltip />} />
                  <Line type="monotone" dataKey="receita" name="receita" stroke="#34d399" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-sm text-center py-16 text-neutral-500">Sem dados de vendas no período</div>
            )}
          </div>

          {topProdutosHoje.length > 0 && (
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
              <p className="text-xs text-neutral-500 uppercase tracking-wider mb-3">Produtos mais vendidos hoje</p>
              <div className="space-y-1.5">
                {topProdutosHoje.map((p, i) => (
                  <div key={p.sku} className="flex items-center gap-3 text-sm">
                    <span className="text-xs text-neutral-600 w-4 shrink-0">{i + 1}</span>
                    <span className="flex-1 min-w-0 truncate text-neutral-300" title={p.descricao}>{p.descricao}</span>
                    <span className="text-xs text-neutral-500 numeric shrink-0">{p.quantidade} un</span>
                    <span className="text-emerald-400 numeric shrink-0 w-24 text-right">{fmtBRL(p.receita)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <p className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Período selecionado ({dias} dias)</p>
            <div className="instrument-enter grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="instrument-hover bg-neutral-900 border border-neutral-800 rounded-lg p-3">
                <p className="text-xs text-neutral-500 uppercase tracking-wider">Receita Total</p>
                <p className="text-lg text-emerald-400 numeric font-medium">{fmtBRL(totalReceita)}</p>
              </div>
              <div className="instrument-hover bg-neutral-900 border border-neutral-800 rounded-lg p-3">
                <p className="text-xs text-neutral-500 uppercase tracking-wider">Unidades Vendidas</p>
                <p className="text-lg text-neutral-200 numeric font-medium">{totalUnidades}</p>
              </div>
              <div className="instrument-hover bg-neutral-900 border border-neutral-800 rounded-lg p-3">
                <p className="text-xs text-neutral-500 uppercase tracking-wider">Anúncios Ativos</p>
                <p className="text-lg text-neutral-200 numeric font-medium">{totalAnunciosAtivos}</p>
              </div>
              <div className="instrument-hover bg-neutral-900 border border-neutral-800 rounded-lg p-3">
                <p className="text-xs text-neutral-500 uppercase tracking-wider">Estoque Baixo</p>
                <p className={`text-lg numeric font-medium ${totalEstoqueBaixo > 0 ? "text-amber-400" : "text-neutral-200"}`}>{totalEstoqueBaixo}</p>
              </div>
            </div>
          </div>

          {estoqueRisco.length > 0 && (
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
              <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Estoque baixo × vendas</p>
              <p className="text-xs text-neutral-600 mb-3">Produtos vendendo bem no período mas com estoque no limite.</p>
              <div className="space-y-1.5">
                {estoqueRisco.map((p) => (
                  <div key={p.sku} className="flex items-center gap-3 text-sm">
                    <span className="flex-1 min-w-0 truncate text-neutral-300" title={p.descricao}>{p.descricao}</span>
                    <span className="text-xs text-neutral-500 numeric shrink-0">{p.vendidos} vendidos</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium numeric shrink-0 ${p.estoque_atual <= 0 ? "bg-red-950/40 text-red-400" : "bg-amber-950/40 text-amber-400"}`}>
                      {p.estoque_atual} / mín. {p.estoque_minimo}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="instrument-enter space-y-3">
            {lojas.map((l) => {
              const s = saude[l.loja_id];
              const rating = s?.performance?.overall_performance?.rating;
              const ratingMeta = rating ? RATING_META[rating] : null;
              return (
                <div key={l.loja_id} className="instrument-hover bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm text-neutral-200 font-medium">{l.nome}</p>
                      <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium inline-flex items-center gap-1 ${l.tem_token ? "bg-green-900/40 text-green-400" : "bg-red-900/40 text-red-400"}`}>
                        {l.tem_token ? (
                          <svg xmlns="http://www.w3.org/2000/svg" width={8} height={8} viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10" /></svg>
                        ) : (
                          <Icon name="close" size={10} />
                        )}
                        {l.tem_token ? "Ativa" : "Sem token"}
                      </span>
                      {l.tem_token && s?.loading && (
                        <span className="text-xs px-1.5 py-0.5 rounded-full bg-neutral-800 text-neutral-500">Saúde...</span>
                      )}
                      {l.tem_token && ratingMeta && (
                        <span className={`text-xs px-1.5 py-0.5 rounded-full border font-medium ${ratingMeta.className}`}>
                          Saúde: {ratingMeta.label}
                        </span>
                      )}
                      {l.tem_token && s && !s.loading && s.erro && !ratingMeta && (
                        <span className="text-xs px-1.5 py-0.5 rounded-full bg-neutral-800 text-neutral-600">Saúde indisponível</span>
                      )}
                    </div>
                    <span className="text-sm text-emerald-400 numeric font-medium">{fmtBRL(l.receita)}</span>
                  </div>
                  <div className="w-full bg-neutral-800 rounded-full h-1.5 overflow-hidden">
                    <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${Math.round((Number(l.receita || 0) / maiorReceita) * 100)}%` }} />
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div>
                      <p className="text-xs text-neutral-500">Hoje</p>
                      <p className="text-xs text-emerald-400 numeric">{fmtBRL(l.receita_hoje)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-neutral-500">Pedidos hoje</p>
                      <p className="text-xs text-neutral-300 numeric">{l.pedidos_hoje}</p>
                    </div>
                    <div>
                      <p className="text-xs text-neutral-500">Anúncios ativos</p>
                      <p className="text-xs text-neutral-300 numeric">{l.anuncios_ativos} / {l.anuncios_total}</p>
                    </div>
                    <div>
                      <p className="text-xs text-neutral-500">Estoque baixo</p>
                      <p className={`text-xs numeric ${l.produtos_estoque_baixo > 0 ? "text-amber-400" : "text-neutral-300"}`}>{l.produtos_estoque_baixo}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {showRanking && <RankingProdutosModal onClose={() => setShowRanking(false)} />}
    </div>
  );
}
