"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "@/lib/api";
import { useTheme, chartAxisColors } from "@/lib/theme-context";
import { useStore } from "@/lib/store-context";
import type {
  ShopeeDashboardLoja, ShopeeSerieDiariaPonto, ShopeeTopProdutoHoje, ShopeeEstoqueRisco,
  ShopeeShopPerformance, ShopeeFunilFulfillment, ShopeeAdsPerformanceRow, ShopeeAdsInsight, ShopeeSyncLogEntry,
  ShopeePeriodoAnterior, ShopeeVendidoOntem, ShopeeCancelamentos, ShopeeRankingPeriodoItem, ShopeeProdutoParado,
} from "@/lib/api";
import Icon from "@/app/_components/Icon";
import RankingProdutosModal from "@/app/_components/RankingProdutosModal";
import DateRangePicker from "@/app/_components/DateRangePicker";

function fmtDataIso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

const fmtBRL = (v: number) => "R$ " + Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function fmtTempoAtras(data: Date | null): string {
  if (!data) return "";
  const segundos = Math.floor((Date.now() - data.getTime()) / 1000);
  if (segundos < 60) return "agora";
  const minutos = Math.floor(segundos / 60);
  if (minutos < 60) return `há ${minutos}min`;
  const horas = Math.floor(minutos / 60);
  return `há ${horas}h`;
}

function Variacao({ atual, anterior }: { atual: number; anterior: number }) {
  if (anterior <= 0) return null;
  const pct = ((atual - anterior) / anterior) * 100;
  const positivo = pct >= 0;
  return (
    <span className={`text-xs numeric ml-1.5 ${positivo ? "text-emerald-400" : "text-red-400"}`}>
      {positivo ? "↑" : "↓"} {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

const RATING_META: Record<number, { label: string; className: string }> = {
  1: { label: "Ruim", className: "bg-red-950/40 border-red-900/50 text-red-400" },
  2: { label: "Precisa melhorar", className: "bg-amber-950/40 border-amber-900/50 text-amber-400" },
  3: { label: "Boa", className: "bg-emerald-950/40 border-emerald-900/50 text-emerald-400" },
  4: { label: "Excelente", className: "bg-emerald-950/40 border-emerald-900/50 text-emerald-300" },
};

const SEVERITY_META: Record<string, { label: string; className: string }> = {
  alta: { label: "Alta", className: "bg-red-950/40 border-red-900/50 text-red-400" },
  high: { label: "Alta", className: "bg-red-950/40 border-red-900/50 text-red-400" },
  media: { label: "Média", className: "bg-amber-950/40 border-amber-900/50 text-amber-400" },
  média: { label: "Média", className: "bg-amber-950/40 border-amber-900/50 text-amber-400" },
  medium: { label: "Média", className: "bg-amber-950/40 border-amber-900/50 text-amber-400" },
  baixa: { label: "Baixa", className: "bg-neutral-800 text-neutral-400" },
  low: { label: "Baixa", className: "bg-neutral-800 text-neutral-400" },
};

function metricaForaMeta(m: { current_period: number; target?: { value: number; comparator: string } }): boolean {
  if (!m.target) return false;
  const { value, comparator } = m.target;
  if (comparator === "<=") return m.current_period > value;
  if (comparator === "<") return m.current_period >= value;
  if (comparator === ">=") return m.current_period < value;
  if (comparator === ">") return m.current_period <= value;
  return false;
}

function QuickActionCard({ label, value, tone, href, tooltip }: { label: string; value: number; tone: "red" | "amber"; href?: string; tooltip?: string }) {
  const cls = tone === "red" ? "bg-red-950/40 border-red-900/50 text-red-400" : "bg-amber-950/40 border-amber-900/50 text-amber-400";
  const content = (
    <div className={`instrument-hover border rounded-lg p-3 ${cls}`} title={tooltip}>
      <p className="text-2xl numeric font-semibold">{value}</p>
      <p className="text-xs uppercase tracking-wider mt-0.5">{label}</p>
    </div>
  );
  return href ? <Link href={href} className="block">{content}</Link> : content;
}

function diasAte(iso: string | null): number | null {
  if (!iso) return null;
  const diff = new Date(iso).getTime() - Date.now();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

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

interface SaudeLojaState {
  loading: boolean;
  performance?: ShopeeShopPerformance;
  pontosPenalidade?: number;
  punicoesAtivas?: number;
  anunciosComProblema?: number;
  pedidosAtrasados?: number;
  descontosAtivos?: number;
  vouchersAtivos?: number;
  erro?: string;
}

interface SaudeState {
  [lojaId: number]: SaudeLojaState;
}

function StatCard({ label, value, tone = "neutral", tooltip }: { label: string; value: string | number; tone?: "emerald" | "amber" | "red" | "neutral"; tooltip?: string }) {
  const cor = tone === "emerald" ? "text-emerald-400" : tone === "amber" ? "text-amber-400" : tone === "red" ? "text-red-400" : "text-neutral-200";
  return (
    <div className="instrument-hover bg-neutral-900 border border-neutral-800 rounded-lg p-3" title={tooltip}>
      <p className="text-xs text-neutral-500 uppercase tracking-wider inline-flex items-center gap-1">
        {label}
        {tooltip && <span aria-hidden className="text-neutral-600">ⓘ</span>}
      </p>
      <p className={`text-lg numeric font-medium ${cor}`}>{value}</p>
    </div>
  );
}

export default function ShopeeDashboardPage() {
  const { theme } = useTheme();
  const { grid: gridColor, axis: axisColor } = chartAxisColors(theme);
  const { lojaId } = useStore();
  const [lojas, setLojas] = useState<ShopeeDashboardLoja[]>([]);
  const [serieDiaria, setSerieDiaria] = useState<ShopeeSerieDiariaPonto[]>([]);
  const [topProdutosHoje, setTopProdutosHoje] = useState<ShopeeTopProdutoHoje[]>([]);
  const [estoqueRisco, setEstoqueRisco] = useState<ShopeeEstoqueRisco[]>([]);
  const [funil, setFunil] = useState<ShopeeFunilFulfillment>({ total: 0, sem_bling: 0, sem_nota: 0, nao_despachado: 0 });
  const [lucroPeriodo, setLucroPeriodo] = useState(0);
  const [periodoAnterior, setPeriodoAnterior] = useState<ShopeePeriodoAnterior>({ receita: 0, unidades: 0 });
  const [vendidoOntem, setVendidoOntem] = useState<ShopeeVendidoOntem>({ receita: 0, unidades: 0, pedidos: 0 });
  const [cancelamentos, setCancelamentos] = useState<ShopeeCancelamentos>({ total: 0, cancelados: 0, devolucao: 0, taxa_cancelamento_pct: 0, taxa_devolucao_pct: 0 });
  const [projecaoMes, setProjecaoMes] = useState(0);
  const [rankingPeriodo, setRankingPeriodo] = useState<ShopeeRankingPeriodoItem[]>([]);
  const [produtosParados, setProdutosParados] = useState<ShopeeProdutoParado[]>([]);
  const [dataFim, setDataFim] = useState(() => fmtDataIso(new Date()));
  const [dataInicio, setDataInicio] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return fmtDataIso(d);
  });
  const dias = Math.max(1, Math.round((new Date(dataFim).getTime() - new Date(dataInicio).getTime()) / 86400000) + 1);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [showRanking, setShowRanking] = useState(false);
  const [saude, setSaude] = useState<SaudeState>({});
  const [syncLog, setSyncLog] = useState<ShopeeSyncLogEntry[]>([]);
  const [adsPerf, setAdsPerf] = useState<ShopeeAdsPerformanceRow[]>([]);
  const [adsInsights, setAdsInsights] = useState<ShopeeAdsInsight[]>([]);
  const [atualizadoEm, setAtualizadoEm] = useState<Date | null>(null);
  const [, setTick] = useState(0);

  const carregar = useCallback(async () => {
    if (lojaId === "todas") {
      // Ao contrario de /dashboard (o unico lugar do sistema com visao
      // "todas as lojas"), esta pagina sempre mostra UMA loja Shopee por
      // vez — sem loja selecionada nao chama a API nem mostra agregado.
      setLoading(false);
      setErro(null);
      setLojas([]);
      setSerieDiaria([]);
      setTopProdutosHoje([]);
      setEstoqueRisco([]);
      setFunil({ total: 0, sem_bling: 0, sem_nota: 0, nao_despachado: 0 });
      setLucroPeriodo(0);
      setPeriodoAnterior({ receita: 0, unidades: 0 });
      setVendidoOntem({ receita: 0, unidades: 0, pedidos: 0 });
      setCancelamentos({ total: 0, cancelados: 0, devolucao: 0, taxa_cancelamento_pct: 0, taxa_devolucao_pct: 0 });
      setProjecaoMes(0);
      setRankingPeriodo([]);
      setProdutosParados([]);
      return;
    }
    setLoading(true);
    setErro(null);
    try {
      const r = await api.shopeeDashboard(dias, lojaId);
      if (r.error) setErro(r.error);
      setLojas(r.lojas || []);
      setSerieDiaria(r.serie_diaria || []);
      setTopProdutosHoje(r.top_produtos_hoje || []);
      setEstoqueRisco(r.estoque_risco || []);
      setFunil(r.funil_fulfillment || { total: 0, sem_bling: 0, sem_nota: 0, nao_despachado: 0 });
      setLucroPeriodo(r.lucro_periodo || 0);
      setPeriodoAnterior(r.periodo_anterior || { receita: 0, unidades: 0 });
      setVendidoOntem(r.vendido_ontem || { receita: 0, unidades: 0, pedidos: 0 });
      setCancelamentos(r.cancelamentos || { total: 0, cancelados: 0, devolucao: 0, taxa_cancelamento_pct: 0, taxa_devolucao_pct: 0 });
      setProjecaoMes(r.projecao_mes || 0);
      setRankingPeriodo(r.ranking_periodo || []);
      setProdutosParados(r.produtos_parados || []);
      setAtualizadoEm(new Date());
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar painel");
    } finally {
      setLoading(false);
    }
  }, [dias, dataInicio, dataFim, lojaId]);

  useEffect(() => { carregar(); }, [carregar]);

  useEffect(() => {
    const intervalo = setInterval(() => carregar(), 5 * 60 * 1000);
    return () => clearInterval(intervalo);
  }, [carregar]);

  useEffect(() => {
    const intervalo = setInterval(() => setTick((t) => t + 1), 30 * 1000);
    return () => clearInterval(intervalo);
  }, []);

  useEffect(() => {
    api.shopeeSyncLog().then((r) => setSyncLog(r.log || [])).catch(() => {});
    api.shopeeAdsPerformance().then(setAdsPerf).catch(() => {});
    api.shopeeAdsInsights().then(setAdsInsights).catch(() => {});
  }, []);

  useEffect(() => {
    const lojasAtivas = lojas.filter((l) => l.tem_token);
    if (lojasAtivas.length === 0) return;
    lojasAtivas.forEach((l) => {
      setSaude((s) => ({ ...s, [l.loja_id]: { loading: true } }));
      Promise.allSettled([
        api.shopeeSaudePerformance(l.loja_id),
        api.shopeeSaudePenalidades(l.loja_id),
        api.shopeeSaudePunicoes(l.loja_id, 1),
        api.shopeeSaudeAnunciosComProblema(l.loja_id),
        api.shopeeSaudePedidosAtrasados(l.loja_id),
        api.shopeeListarDescontos(l.loja_id, "ongoing"),
        api.shopeeListarVouchers(l.loja_id, "ongoing"),
      ]).then(([perf, penal, punic, anunc, atraso, desc, vouch]) => {
        const val = <T,>(r: PromiseSettledResult<T>) => (r.status === "fulfilled" ? r.value : null);
        const performance = val(perf) as Awaited<ReturnType<typeof api.shopeeSaudePerformance>> | null;
        const penalidades = val(penal) as Awaited<ReturnType<typeof api.shopeeSaudePenalidades>> | null;
        const punicoes = val(punic) as Awaited<ReturnType<typeof api.shopeeSaudePunicoes>> | null;
        const anuncios = val(anunc) as Awaited<ReturnType<typeof api.shopeeSaudeAnunciosComProblema>> | null;
        const atrasados = val(atraso) as Awaited<ReturnType<typeof api.shopeeSaudePedidosAtrasados>> | null;
        const descontos = val(desc) as Awaited<ReturnType<typeof api.shopeeListarDescontos>> | null;
        const vouchers = val(vouch) as Awaited<ReturnType<typeof api.shopeeListarVouchers>> | null;
        const semNenhumDado = !performance?.response && !penalidades?.response && !punicoes?.response && !anuncios?.response && !atrasados?.response;
        setSaude((s) => ({
          ...s,
          [l.loja_id]: {
            loading: false,
            performance: performance?.response,
            pontosPenalidade: (penalidades?.response?.penalty_point_list || []).reduce((sum, p) => sum + Number(p.latest_point_num || 0), 0),
            punicoesAtivas: punicoes?.response?.total_count ?? punicoes?.response?.punishment_list?.length,
            anunciosComProblema: anuncios?.response?.total_count ?? anuncios?.response?.listing_list?.length,
            pedidosAtrasados: atrasados?.response?.total_count ?? atrasados?.response?.late_order_list?.length,
            descontosAtivos: descontos?.response?.discount_list?.length,
            vouchersAtivos: vouchers?.response?.voucher_list?.length,
            erro: semNenhumDado ? "Indisponível" : undefined,
          },
        }));
      });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lojas.map((l) => l.loja_id).join(",")]);

  const totalReceita = lojas.reduce((s, l) => s + Number(l.receita || 0), 0);
  const totalUnidades = lojas.reduce((s, l) => s + Number(l.unidades_vendidas || 0), 0);
  const totalAnunciosAtivos = lojas.reduce((s, l) => s + Number(l.anuncios_ativos || 0), 0);
  const totalAnunciosPausados = lojas.reduce((s, l) => s + Number(l.anuncios_pausados || 0), 0);
  const totalAnunciosBanidos = lojas.reduce((s, l) => s + Number(l.anuncios_banidos || 0), 0);
  const totalEstoqueBaixo = lojas.reduce((s, l) => s + Number(l.produtos_estoque_baixo || 0), 0);
  const maiorReceita = Math.max(1, ...lojas.map(l => Number(l.receita || 0)));

  const receitaHoje = lojas.reduce((s, l) => s + Number(l.receita_hoje || 0), 0);
  const pedidosHoje = lojas.reduce((s, l) => s + Number(l.pedidos_hoje || 0), 0);
  const unidadesHoje = lojas.reduce((s, l) => s + Number(l.unidades_hoje || 0), 0);
  const ticketMedioHoje = pedidosHoje > 0 ? receitaHoje / pedidosHoje : 0;

  const saudeValores = Object.values(saude);
  const totalPedidosAtrasados = saudeValores.reduce((s, v) => s + Number(v.pedidosAtrasados || 0), 0);
  const totalPontosPenalidade = saudeValores.reduce((s, v) => s + Number(v.pontosPenalidade || 0), 0);
  const totalPunicoesAtivas = saudeValores.reduce((s, v) => s + Number(v.punicoesAtivas || 0), 0);
  const totalAnunciosComProblema = saudeValores.reduce((s, v) => s + Number(v.anunciosComProblema || 0), 0);
  const totalDescontosAtivos = saudeValores.reduce((s, v) => s + Number(v.descontosAtivos || 0), 0);
  const totalVouchersAtivos = saudeValores.reduce((s, v) => s + Number(v.vouchersAtivos || 0), 0);
  const metricasForaMeta = saudeValores.flatMap((v) => (v.performance?.metric_list || []).filter(metricaForaMeta));

  const adsCost = adsPerf.reduce((s, p) => s + Number(p.cost || 0), 0);
  const adsRevenue = adsPerf.reduce((s, p) => s + Number(p.revenue || 0), 0);
  const adsRoas = adsCost > 0 ? adsRevenue / adsCost : 0;
  const adsInsightsPendentes = adsInsights.filter((i) => !i.action_taken);

  const syncUltimo = syncLog[0];
  const syncComErro = !!syncUltimo?.erro || syncUltimo?.status === "erro";
  const syncExecutando = syncUltimo?.status === "executando";

  const lojasComTokenExpirando = lojas.filter((l) => {
    const d = diasAte(l.shopee_token_expira_em);
    return d !== null && d <= 7;
  });

  const chartData = serieDiaria.map((p) => ({ ...p, diaLabel: p.dia.slice(8, 10) + "/" + p.dia.slice(5, 7) }));

  const alertas: Array<{ texto: string; tone: "red" | "amber" }> = [];
  if (totalPedidosAtrasados > 0) alertas.push({ texto: `${totalPedidosAtrasados} pedido${totalPedidosAtrasados === 1 ? "" : "s"} atrasado${totalPedidosAtrasados === 1 ? "" : "s"} pra envio`, tone: "red" });
  if (totalPunicoesAtivas > 0) alertas.push({ texto: `${totalPunicoesAtivas} punição${totalPunicoesAtivas === 1 ? "" : "ões"} ativa${totalPunicoesAtivas === 1 ? "" : "s"} na conta`, tone: "red" });
  if (totalAnunciosBanidos > 0) alertas.push({ texto: `${totalAnunciosBanidos} anúncio${totalAnunciosBanidos === 1 ? "" : "s"} banido${totalAnunciosBanidos === 1 ? "" : "s"}`, tone: "red" });
  if (syncComErro) alertas.push({ texto: `Última sincronização com erro${syncUltimo?.erro ? `: ${syncUltimo.erro}` : ""}`, tone: "red" });
  lojasComTokenExpirando.forEach((l) => {
    const d = diasAte(l.shopee_token_expira_em);
    alertas.push({ texto: `Token de "${l.nome}" ${d !== null && d <= 0 ? "expirado" : `expira em ${d}d`}`, tone: "amber" });
  });
  if (totalAnunciosComProblema > 0) alertas.push({ texto: `${totalAnunciosComProblema} anúncio${totalAnunciosComProblema === 1 ? "" : "s"} sinalizado${totalAnunciosComProblema === 1 ? "" : "s"} pela Shopee`, tone: "amber" });
  if (totalPontosPenalidade > 0) alertas.push({ texto: `${totalPontosPenalidade} ponto${totalPontosPenalidade === 1 ? "" : "s"} de penalidade no trimestre`, tone: "amber" });

  return (
    <div className="p-6 space-y-4">
      <div>
        <Link href="/integracoes/shopee" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors inline-flex items-center gap-1"><Icon name="chevronLeft" size={14} /> Shopee</Link>
        <h1 className="text-lg font-light text-neutral-300 mt-1">Painel Consolidado Shopee</h1>
        <p className="text-xs text-neutral-500 mt-0.5">Visão geral das lojas Shopee conectadas.</p>
      </div>

      {lojaId === "todas" ? (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-8 text-center text-neutral-500 text-sm">
          Selecione uma loja no topo da página para ver o painel Shopee dela.
          <p className="text-xs text-neutral-600 mt-1">
            Este painel mostra dados de uma loja Shopee por vez — o consolidado de todas as lojas fica no{" "}
            <Link href="/dashboard" className="text-indigo-400 hover:text-indigo-300 transition-colors">dashboard principal</Link>.
          </p>
        </div>
      ) : (
        <>
      {!loading && lojas.length === 0 && !erro && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 text-center text-neutral-500 text-sm">
          Nenhuma loja Shopee conectada ainda.
        </div>
      )}

      {lojas.length > 0 && (totalPedidosAtrasados > 0 || cancelamentos.cancelados > 0 || cancelamentos.devolucao > 0 || totalAnunciosBanidos > 0 || metricasForaMeta.length > 0) && (
        <div>
          <p className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Ação rápida</p>
          <div className="instrument-enter grid grid-cols-2 sm:grid-cols-4 gap-3">
            {totalPedidosAtrasados > 0 && (
              <QuickActionCard label={`Pedido${totalPedidosAtrasados === 1 ? "" : "s"} atrasado${totalPedidosAtrasados === 1 ? "" : "s"}`} value={totalPedidosAtrasados} tone="red" href="/integracoes/shopee/pedidos" />
            )}
            {(cancelamentos.cancelados > 0 || cancelamentos.devolucao > 0) && (
              <QuickActionCard label="Cancel. + devoluções" value={cancelamentos.cancelados + cancelamentos.devolucao} tone="amber" tooltip={`${cancelamentos.cancelados} cancelados, ${cancelamentos.devolucao} devoluções no período`} />
            )}
            {totalAnunciosBanidos > 0 && (
              <QuickActionCard label={`Anúncio${totalAnunciosBanidos === 1 ? "" : "s"} banido${totalAnunciosBanidos === 1 ? "" : "s"}`} value={totalAnunciosBanidos} tone="red" />
            )}
            {metricasForaMeta.length > 0 && (
              <QuickActionCard
                label="Métricas fora da meta"
                value={metricasForaMeta.length}
                tone="amber"
                tooltip={metricasForaMeta.map((m) => m.metric_name).join(", ")}
              />
            )}
          </div>
        </div>
      )}

      {lojas.length > 0 && (
        <div className="instrument-enter bg-gradient-to-br from-emerald-950/50 to-neutral-900 border border-emerald-900/40 rounded-xl p-5">
          <p className="text-xs text-emerald-400/80 uppercase tracking-wider mb-1">Vendido hoje</p>
          <p className="text-4xl font-semibold text-emerald-400 numeric flex items-baseline flex-wrap">
            {fmtBRL(receitaHoje)}
            <Variacao atual={receitaHoje} anterior={vendidoOntem.receita} />
          </p>
          {vendidoOntem.receita > 0 && (
            <p className="text-xs text-neutral-500 mt-1">Ontem: {fmtBRL(vendidoOntem.receita)} ({vendidoOntem.pedidos} pedido{vendidoOntem.pedidos === 1 ? "" : "s"})</p>
          )}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-4 border-t border-emerald-900/30">
            <div>
              <p className="text-xs text-neutral-500 uppercase tracking-wider">Pedidos</p>
              <p className="text-xl text-neutral-200 numeric font-medium">{pedidosHoje}</p>
            </div>
            <div>
              <p className="text-xs text-neutral-500 uppercase tracking-wider">Unidades</p>
              <p className="text-xl text-neutral-200 numeric font-medium">{unidadesHoje}</p>
            </div>
            <div>
              <p className="text-xs text-neutral-500 uppercase tracking-wider">Ticket médio</p>
              <p className="text-xl text-neutral-200 numeric font-medium">{fmtBRL(ticketMedioHoje)}</p>
            </div>
            <div>
              <p className="text-xs text-neutral-500 uppercase tracking-wider" title="Receita do mês até hoje, projetada linearmente para os dias restantes">Projeção do mês</p>
              <p className="text-xl text-neutral-200 numeric font-medium">{fmtBRL(projecaoMes)}</p>
            </div>
          </div>
        </div>
      )}

      {erro && (
        <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erro}</div>
      )}

      {lojas.length > 0 && alertas.length > 0 && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-3 space-y-1.5">
          <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1.5">Alertas</p>
          {alertas.map((a, i) => (
            <div key={i} className={`flex items-center gap-2 text-xs ${a.tone === "red" ? "text-red-400" : "text-amber-400"}`}>
              <span aria-hidden className={`w-1.5 h-1.5 rounded-full shrink-0 ${a.tone === "red" ? "bg-red-500" : "bg-amber-500"}`} />
              {a.texto}
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2">
        <DateRangePicker
          dataInicio={dataInicio}
          dataFim={dataFim}
          onChange={(inicio, fim) => {
            setDataInicio(inicio);
            setDataFim(fim);
          }}
        />
        <button
          onClick={carregar}
          disabled={loading}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
        >
          {loading ? "Carregando..." : "Atualizar"}
        </button>
        {atualizadoEm && <span className="text-xs text-neutral-600">Atualizado {fmtTempoAtras(atualizadoEm)}</span>}
        <button
          onClick={() => setShowRanking(true)}
          className="bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-sm px-4 py-2 rounded-lg transition-colors ml-auto"
        >
          Ranking de produtos
        </button>
      </div>

      {lojas.length > 0 && (
        <>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            <p className="text-xs text-neutral-500 uppercase tracking-wider mb-3">Vendas — últimos {dias} dias</p>
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                  <XAxis dataKey="diaLabel" stroke={axisColor} tick={{ fontSize: 10, fill: axisColor }} />
                  <YAxis stroke={axisColor} tick={{ fontSize: 10, fill: axisColor }} tickFormatter={(v) => "R$ " + v} width={70} />
                  <Tooltip content={<ChartTooltip />} />
                  <Line type="monotone" dataKey="receita" name="receita" stroke={theme === "dark" ? "#34d399" : "#059669"} strokeWidth={2} dot={false} />
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

          {rankingPeriodo.length > 0 && (
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
              <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Ranking de produtos — {dias} dias</p>
              <p className="text-xs text-neutral-600 mb-3" title="Custo só é descontado se o produto tiver preço de custo cadastrado no catálogo.">Receita e lucro estimado (após comissão Shopee; custo do produto só entra se cadastrado).</p>
              <div className="space-y-1.5">
                {rankingPeriodo.map((p, i) => (
                  <div key={p.sku} className="flex items-center gap-3 text-sm">
                    <span className="text-xs text-neutral-600 w-4 shrink-0">{i + 1}</span>
                    <span className="flex-1 min-w-0 truncate text-neutral-300" title={p.descricao}>{p.descricao}</span>
                    <span className="text-xs text-neutral-500 numeric shrink-0">{p.quantidade} un</span>
                    <span className="text-emerald-400 numeric shrink-0 w-24 text-right">{fmtBRL(p.receita)}</span>
                    <span className={`numeric shrink-0 w-24 text-right ${p.lucro >= 0 ? "text-neutral-400" : "text-red-400"}`}>{fmtBRL(p.lucro)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <p className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Período selecionado ({dias} dias)</p>
            <div className="instrument-enter grid grid-cols-2 lg:grid-cols-5 gap-3">
              <div className="instrument-hover bg-neutral-900 border border-neutral-800 rounded-lg p-3">
                <p className="text-xs text-neutral-500 uppercase tracking-wider">Receita Total</p>
                <p className="text-lg numeric font-medium text-emerald-400 flex items-baseline flex-wrap">
                  {fmtBRL(totalReceita)}
                  <Variacao atual={totalReceita} anterior={periodoAnterior.receita} />
                </p>
              </div>
              <StatCard
                label="Lucro Estimado"
                value={fmtBRL(lucroPeriodo)}
                tone={lucroPeriodo >= 0 ? "emerald" : "red"}
                tooltip="Receita menos comissão Shopee (12%) menos custo do produto. O custo só é descontado se o SKU tiver preço de custo cadastrado no catálogo — hoje nenhum produto vendido nesse período tem esse campo preenchido, então na prática este valor é só receita líquida de comissão."
              />
              <StatCard label="Unidades Vendidas" value={totalUnidades} />
              <StatCard label="Anúncios Ativos" value={totalAnunciosAtivos} />
              <StatCard
                label="Estoque Baixo"
                value={totalEstoqueBaixo}
                tone={totalEstoqueBaixo > 0 ? "amber" : "neutral"}
                tooltip="Produtos com estoque igual ou abaixo do mínimo cadastrado no catálogo. Depende de dois campos que hoje não estão preenchidos no sistema: estoque físico por loja e estoque mínimo por produto — enquanto isso, este número fica sempre zero."
              />
            </div>
          </div>

          {cancelamentos.total > 0 && (
            <div className="instrument-enter grid grid-cols-2 gap-3">
              <StatCard label="Taxa de cancelamento" value={`${cancelamentos.taxa_cancelamento_pct}% (${cancelamentos.cancelados})`} tone={cancelamentos.taxa_cancelamento_pct > 5 ? "red" : "neutral"} />
              <StatCard label="Taxa de devolução" value={`${cancelamentos.taxa_devolucao_pct}% (${cancelamentos.devolucao})`} tone={cancelamentos.taxa_devolucao_pct > 5 ? "amber" : "neutral"} />
            </div>
          )}

          {(totalAnunciosPausados > 0 || totalAnunciosBanidos > 0) && (
            <div className="instrument-enter grid grid-cols-2 gap-3">
              <StatCard label="Anúncios Pausados" value={totalAnunciosPausados} tone={totalAnunciosPausados > 0 ? "amber" : "neutral"} />
              <StatCard label="Anúncios Banidos" value={totalAnunciosBanidos} tone={totalAnunciosBanidos > 0 ? "red" : "neutral"} />
            </div>
          )}

          {funil.total > 0 && (
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
              <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Funil de fulfillment ({dias} dias)</p>
              <p className="text-xs text-neutral-600 mb-3">Pedidos Shopee do período, do vínculo com o Bling até o despacho.</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard label="Pedidos no período" value={funil.total} />
                <StatCard label="Sem vínculo Bling" value={funil.sem_bling} tone={funil.sem_bling > 0 ? "amber" : "neutral"} />
                <StatCard label="Sem nota emitida" value={funil.sem_nota} tone={funil.sem_nota > 0 ? "amber" : "neutral"} />
                <StatCard label="Não despachados" value={funil.nao_despachado} tone={funil.nao_despachado > 0 ? "amber" : "neutral"} />
              </div>
            </div>
          )}

          {(totalDescontosAtivos > 0 || totalVouchersAtivos > 0) && (
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
              <p className="text-xs text-neutral-500 uppercase tracking-wider mb-3">Promoções ativas</p>
              <div className="grid grid-cols-2 gap-3">
                <StatCard label="Descontos (flash deals)" value={totalDescontosAtivos} />
                <StatCard label="Cupons" value={totalVouchersAtivos} />
              </div>
            </div>
          )}

          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-neutral-500 uppercase tracking-wider">Shopee Ads</p>
              <Link href="/integracoes/shopee-ads" className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">Ver campanhas →</Link>
            </div>
            {adsPerf.length > 0 ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard label="Gasto (90d)" value={fmtBRL(adsCost)} />
                <StatCard label="Receita gerada" value={fmtBRL(adsRevenue)} tone="emerald" />
                <StatCard label="ROAS" value={adsRoas.toFixed(2) + "x"} tone={adsRoas >= 3 ? "emerald" : adsRoas > 0 ? "amber" : "neutral"} />
                <StatCard label="Insights pendentes" value={adsInsightsPendentes.length} tone={adsInsightsPendentes.length > 0 ? "amber" : "neutral"} />
              </div>
            ) : (
              <p className="text-sm text-center py-4 text-neutral-500">Sem campanhas sincronizadas ainda.</p>
            )}
            {adsInsightsPendentes.length > 0 && (
              <div className="space-y-1.5 mt-3 pt-3 border-t border-neutral-800">
                {adsInsightsPendentes.slice(0, 5).map((ins) => {
                  const sev = SEVERITY_META[ins.severity?.toLowerCase()] || { label: ins.severity, className: "bg-neutral-800 text-neutral-400" };
                  return (
                    <div key={ins.id} className="flex items-center gap-2 text-xs">
                      <span className={`px-1.5 py-0.5 rounded-full font-medium shrink-0 ${sev.className}`}>{sev.label}</span>
                      <span className="text-neutral-400 truncate">{ins.message}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            <p className="text-xs text-neutral-500 uppercase tracking-wider mb-3">Sincronização</p>
            {syncUltimo ? (
              <div className="flex items-center gap-3 text-sm">
                <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${syncComErro ? "bg-red-950/40 text-red-400" : syncExecutando ? "bg-amber-950/40 text-amber-400" : "bg-emerald-950/40 text-emerald-400"}`}>
                  {syncComErro ? "Erro" : syncExecutando ? "Sincronizando" : "OK"}
                </span>
                <span className="text-neutral-300 capitalize">{syncUltimo.tipo}</span>
                <span className="text-neutral-500 text-xs">{new Date(syncUltimo.iniciado_em).toLocaleString("pt-BR")}</span>
                {syncUltimo.itens_processados > 0 && <span className="text-neutral-500 text-xs">· {syncUltimo.itens_processados} itens</span>}
              </div>
            ) : (
              <p className="text-sm text-neutral-500">Sem histórico de sincronização.</p>
            )}
          </div>

          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Estoque baixo × vendas</p>
            <p className="text-xs text-neutral-600 mb-3">Produtos vendendo bem no período mas com estoque no limite.</p>
            {estoqueRisco.length > 0 ? (
              <div className="space-y-1.5">
                {estoqueRisco.map((p) => (
                  <div key={p.sku} className="flex items-center gap-3 text-sm">
                    <span className="flex-1 min-w-0 truncate text-neutral-300" title={p.descricao}>{p.descricao}</span>
                    <span className="text-xs text-neutral-500 numeric shrink-0">{p.vendidos} vendidos</span>
                    {p.dias_ate_ruptura !== null && (
                      <span className="text-xs text-red-400 numeric shrink-0" title="Estimativa: estoque atual dividido pela velocidade média de venda do período">~{p.dias_ate_ruptura}d p/ zerar</span>
                    )}
                    <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium numeric shrink-0 ${p.estoque_atual <= 0 ? "bg-red-950/40 text-red-400" : "bg-amber-950/40 text-amber-400"}`}>
                      {p.estoque_atual} / mín. {p.estoque_minimo}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-center py-4 text-neutral-500">
                Nenhum produto com estoque mínimo cadastrado ainda — sem isso não há como calcular risco de ruptura.
              </p>
            )}
          </div>

          {produtosParados.length > 0 && (
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
              <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Produtos parados</p>
              <p className="text-xs text-neutral-600 mb-3">Anunciados e com estoque, mas sem nenhuma venda em {dias} dias — candidatos a promoção ou revisão de preço.</p>
              <div className="space-y-1.5">
                {produtosParados.map((p) => (
                  <div key={p.sku} className="flex items-center gap-3 text-sm">
                    <span className="flex-1 min-w-0 truncate text-neutral-300" title={p.titulo}>{p.titulo}</span>
                    <span className="text-xs text-neutral-500 numeric shrink-0">{fmtBRL(p.preco)}</span>
                    <span className="text-xs px-1.5 py-0.5 rounded-full font-medium numeric shrink-0 bg-neutral-800 text-neutral-400">{p.estoque} em estoque</span>
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
              const tokenDias = diasAte(l.shopee_token_expira_em);
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
                      {!!s?.pedidosAtrasados && (
                        <span className="text-xs px-1.5 py-0.5 rounded-full bg-red-950/40 text-red-400 font-medium">{s.pedidosAtrasados} atrasado{s.pedidosAtrasados === 1 ? "" : "s"}</span>
                      )}
                      {!!s?.punicoesAtivas && (
                        <span className="text-xs px-1.5 py-0.5 rounded-full bg-red-950/40 text-red-400 font-medium">{s.punicoesAtivas} punição{s.punicoesAtivas === 1 ? "" : "ões"}</span>
                      )}
                      {!!s?.anunciosComProblema && (
                        <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-950/40 text-amber-400 font-medium">{s.anunciosComProblema} anúncio{s.anunciosComProblema === 1 ? "" : "s"} c/ problema</span>
                      )}
                      {!!s?.pontosPenalidade && (
                        <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-950/40 text-amber-400 font-medium">{s.pontosPenalidade} pts penalidade</span>
                      )}
                      {tokenDias !== null && tokenDias <= 7 && (
                        <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${tokenDias <= 0 ? "bg-red-950/40 text-red-400" : "bg-amber-950/40 text-amber-400"}`}>
                          {tokenDias <= 0 ? "Token expirado" : `Token expira em ${tokenDias}d`}
                        </span>
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
                  {(!!s?.descontosAtivos || !!s?.vouchersAtivos) && (
                    <div className="flex items-center gap-3 text-xs text-neutral-500 pt-1 border-t border-neutral-800/70">
                      {!!s?.descontosAtivos && <span>{s.descontosAtivos} desconto{s.descontosAtivos === 1 ? "" : "s"} ativo{s.descontosAtivos === 1 ? "" : "s"}</span>}
                      {!!s?.vouchersAtivos && <span>{s.vouchersAtivos} cupom{s.vouchersAtivos === 1 ? "" : "s"} ativo{s.vouchersAtivos === 1 ? "" : "s"}</span>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
        </>
      )}

      {showRanking && <RankingProdutosModal onClose={() => setShowRanking(false)} />}
    </div>
  );
}
