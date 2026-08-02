"use client";

import { useEffect, useState, useMemo } from "react";
import PageHeader from "@/app/_components/PageHeader";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import { fmtBRL } from "@/lib/format";
import { fiscalApuracao, fiscalApuracaoFechar, fiscalApuracaoReabrir } from "@/lib/api";
import { Can } from "@/lib/auth";

interface ResumoApuracao {
  total_notas: number; valor_total: number; valor_produtos: number;
  base_icms: number; total_icms: number; total_ipi: number;
  total_pis: number; total_cofins: number; total_iss: number; total_tributos: number;
}

interface MensalRow {
  ano: number; mes: number; total_notas: number;
  valor_total: number; icms: number; pis: number; cofins: number; ipi: number; total_tributos: number;
}

interface Fechamento {
  fechado: boolean;
  fechado_por?: string;
  fechado_em?: string;
  divergente?: boolean;
  total_tributos_no_fechamento?: number;
}

const MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

export default function ApuracaoPage() {
  const [resumo, setResumo] = useState<ResumoApuracao | null>(null);
  const [mensal, setMensal] = useState<MensalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [dias, setDias] = useState(365);

  const [mesSelecionado, setMesSelecionado] = useState<MensalRow | null>(null);
  const [fechamento, setFechamento] = useState<Fechamento | null>(null);
  const [carregandoFechamento, setCarregandoFechamento] = useState(false);
  const [processando, setProcessando] = useState(false);
  const [erroFechamento, setErroFechamento] = useState<string | null>(null);

  const carregar = async (d: number) => {
    setLoading(true); setErro(null);
    try {
      const data = await fiscalApuracao({ dias: d });
      if (data.error) { setErro(data.error); return; }
      setResumo((data.resumo as unknown as ResumoApuracao) || null);
      setMensal((data.mensal as unknown as MensalRow[]) || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar");
    } finally { setLoading(false); }
  };

  const abrirMes = async (m: MensalRow) => {
    setMesSelecionado(m);
    setFechamento(null);
    setErroFechamento(null);
    setCarregandoFechamento(true);
    try {
      const data = await fiscalApuracao({ ano: m.ano, mes: m.mes });
      if (data.error) { setErroFechamento(data.error); return; }
      setFechamento(data.fechamento || { fechado: false });
    } catch (e) {
      setErroFechamento(e instanceof Error ? e.message : "Erro ao carregar fechamento");
    } finally {
      setCarregandoFechamento(false);
    }
  };

  const fecharMes = async () => {
    if (!mesSelecionado) return;
    setProcessando(true); setErroFechamento(null);
    try {
      const r = await fiscalApuracaoFechar(mesSelecionado.ano, mesSelecionado.mes);
      if (r.error) { setErroFechamento(String(r.error)); return; }
      await abrirMes(mesSelecionado);
    } catch (e) {
      setErroFechamento(e instanceof Error ? e.message : "Erro ao fechar apuração");
    } finally {
      setProcessando(false);
    }
  };

  const reabrirMes = async () => {
    if (!mesSelecionado) return;
    if (!confirm(`Reabrir a apuração de ${MESES[mesSelecionado.mes - 1]}/${mesSelecionado.ano}? O fechamento atual será removido.`)) return;
    setProcessando(true); setErroFechamento(null);
    try {
      const r = await fiscalApuracaoReabrir(mesSelecionado.ano, mesSelecionado.mes);
      if (r.error) { setErroFechamento(String(r.error)); return; }
      await abrirMes(mesSelecionado);
    } catch (e) {
      setErroFechamento(e instanceof Error ? e.message : "Erro ao reabrir apuração");
    } finally {
      setProcessando(false);
    }
  };

  useEffect(() => { carregar(dias); }, [dias]);

  const periodos = useMemo(() => {
    const labels = ["365 dias", "180 dias", "90 dias", "30 dias"];
    return labels.map((l, i) => ({ label: l, dias: [365, 180, 90, 30][i] }));
  }, []);

  const tributosCards = useMemo(() => {
    if (!resumo) return [];
    return [
      { label: "ICMS", valor: Number(resumo.total_icms || 0), color: "text-blue-400" },
      { label: "PIS", valor: Number(resumo.total_pis || 0), color: "text-amber-400" },
      { label: "COFINS", valor: Number(resumo.total_cofins || 0), color: "text-purple-400" },
      { label: "IPI", valor: Number(resumo.total_ipi || 0), color: "text-emerald-400" },
      { label: "ISS", valor: Number(resumo.total_iss || 0), color: "text-rose-400" },
      { label: "Total Tributos", valor: Number(resumo.total_tributos || 0), color: "text-red-400" },
    ];
  }, [resumo]);

  const totalGeral = resumo ? Number(resumo.valor_total || 0) : 0;

  return (
    <div className="p-4 space-y-4">
      <PageHeader title="Apuração de Impostos" subtitle="ICMS, PIS, COFINS, IPI, ISS — totais por período" />

      {/* Period selector */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-neutral-400">Período:</span>
        {periodos.map(p => (
          <button key={p.dias} onClick={() => setDias(p.dias)}
            className={`px-3 py-1 text-xs rounded-lg border transition-colors ${dias === p.dias ? "bg-indigo-600/30 border-indigo-500 text-indigo-300" : "border-neutral-600 text-neutral-500 hover:border-neutral-500"}`}>
            {p.label}
          </button>
        ))}
      </div>

      <ErrorAlert message={erro} />
      {loading ? <LoadingState /> : !resumo ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center">
          <p className="text-neutral-400 text-sm">Nenhum dado de apuração disponível. Sincronize NF-e do Bling.</p>
        </div>
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            <KpiSmall label="Notas" value={String(resumo.total_notas || 0)} color="text-neutral-100" />
            <KpiSmall label="Valor Total" value={fmtBRL(resumo.valor_total)} color="text-emerald-400" />
            <KpiSmall label="Base ICMS" value={fmtBRL(resumo.base_icms)} color="text-neutral-300" />
            {tributosCards.map(t => (
              <KpiSmall key={t.label} label={t.label} value={fmtBRL(t.valor)} color={t.color} />
            ))}
          </div>

          {/* Carga tributária */}
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
            <h3 className="text-xs font-semibold text-neutral-400 mb-2">Carga Tributária</h3>
            <div className="flex items-center gap-2">
              <div className="flex-1 bg-neutral-700 rounded-full h-3 overflow-hidden">
                <div className="bg-red-500 h-full rounded-full" style={{
                  width: `${totalGeral > 0 ? Math.min(100, (Number(resumo.total_tributos || 0) / totalGeral) * 100) : 0}%`
                }} />
              </div>
              <span className="text-xs text-red-400 font-mono whitespace-nowrap">
                {totalGeral > 0 ? ((Number(resumo.total_tributos || 0) / totalGeral) * 100).toFixed(1) : 0}%
              </span>
            </div>
            <div className="flex justify-between mt-1 text-[10px]">
              <span className="text-neutral-500">{fmtBRL(Number(resumo.total_tributos || 0))} tributos</span>
              <span className="text-neutral-500">{fmtBRL(totalGeral)} valor NF</span>
            </div>
          </div>

          {/* Monthly breakdown */}
          {mensal.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-neutral-400 mb-3">Detalhamento Mensal</h3>
              <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                      <th className="text-left p-2">Mês</th>
                      <th className="text-right p-2">Notas</th>
                      <th className="text-right p-2">Valor Total</th>
                      <th className="text-right p-2">ICMS</th>
                      <th className="text-right p-2">PIS</th>
                      <th className="text-right p-2">COFINS</th>
                      <th className="text-right p-2">IPI</th>
                      <th className="text-right p-2 font-bold">Total Tributos</th>
                      <th className="text-right p-2">% Carga</th>
                      <th className="text-right p-2">Fechamento</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mensal.map((m, i) => {
                      const pct = m.valor_total > 0 ? (Number(m.total_tributos || 0) / Number(m.valor_total || 1)) * 100 : 0;
                      return (
                        <tr key={`${m.ano}-${m.mes}`}
                          onClick={() => abrirMes(m)}
                          className={`border-b border-neutral-700/50 cursor-pointer hover:bg-neutral-700/40 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                          <td className="p-2 text-neutral-200">{MESES[m.mes - 1] || m.mes}/{m.ano}</td>
                          <td className="p-2 text-right text-neutral-300">{m.total_notas}</td>
                          <td className="p-2 text-right text-emerald-400 font-mono">{fmtBRL(m.valor_total)}</td>
                          <td className="p-2 text-right text-blue-400 font-mono">{fmtBRL(m.icms)}</td>
                          <td className="p-2 text-right text-amber-400 font-mono">{fmtBRL(m.pis)}</td>
                          <td className="p-2 text-right text-purple-400 font-mono">{fmtBRL(m.cofins)}</td>
                          <td className="p-2 text-right text-emerald-300 font-mono">{fmtBRL(m.ipi)}</td>
                          <td className="p-2 text-right text-red-400 font-bold font-mono">{fmtBRL(m.total_tributos)}</td>
                          <td className="p-2 text-right font-mono">
                            <span className={pct > 15 ? "text-red-400" : pct > 5 ? "text-amber-400" : "text-emerald-400"}>
                              {pct.toFixed(1)}%
                            </span>
                          </td>
                          <td className="p-2 text-right">
                            <span className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2">Detalhes</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {mesSelecionado && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setMesSelecionado(null)}>
          <div className="w-full max-w-[440px] rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
              <h3 className="text-sm font-semibold text-neutral-100">
                Fechamento — {MESES[mesSelecionado.mes - 1]}/{mesSelecionado.ano}
              </h3>
              <button onClick={() => setMesSelecionado(null)} className="text-neutral-500 hover:text-neutral-300 text-xs">✕</button>
            </div>
            <div className="px-5 py-4 space-y-3">
              {carregandoFechamento ? (
                <p className="text-xs text-neutral-500">Carregando...</p>
              ) : (
                <>
                  {erroFechamento && (
                    <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erroFechamento}</div>
                  )}
                  {fechamento?.fechado ? (
                    <div className="space-y-2">
                      <div className="text-xs px-3 py-2 rounded-lg border bg-emerald-950/30 border-emerald-800 text-emerald-400">
                        Fechado {fechamento.fechado_por ? `por ${fechamento.fechado_por}` : ""}
                        {fechamento.fechado_em ? ` em ${new Date(fechamento.fechado_em).toLocaleString("pt-BR")}` : ""}.
                      </div>
                      {fechamento.divergente && (
                        <div className="text-xs px-3 py-2 rounded-lg border bg-amber-950/30 border-amber-800 text-amber-400">
                          ⚠ O total de tributos ao vivo diverge do valor fechado ({fmtBRL(fechamento.total_tributos_no_fechamento || 0)}).
                          Alguma nota deste período foi alterada ou cancelada depois do fechamento.
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-neutral-400">Este período ainda não foi fechado.</p>
                  )}
                </>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-neutral-700/70 px-5 py-4">
              <button onClick={() => setMesSelecionado(null)} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200">
                Fechar janela
              </button>
              {!carregandoFechamento && (fechamento?.fechado ? (
                <Can permission="fiscal.excluir">
                  <button onClick={reabrirMes} disabled={processando}
                    className="rounded-lg bg-amber-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-amber-500 disabled:opacity-50">
                    {processando ? "Reabrindo..." : "Reabrir apuração"}
                  </button>
                </Can>
              ) : (
                <Can permission="fiscal.editar">
                  <button onClick={fecharMes} disabled={processando}
                    className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
                    {processando ? "Fechando..." : "Fechar apuração"}
                  </button>
                </Can>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function KpiSmall({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3">
      <div className="text-[10px] text-neutral-500">{label}</div>
      <div className={`text-xs font-bold ${color} mt-0.5`}>{value}</div>
    </div>
  );
}
