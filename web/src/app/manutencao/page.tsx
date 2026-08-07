"use client";
import { useState, useEffect } from "react";
import { fmtDataBR } from "@/lib/format";

export default function ManutencaoPage() {
  const [dash, setDash] = useState<any>(null);
  const [pendentes, setPendentes] = useState<any[]>([]);
  const [alertas, setAlertas] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("/api/manutencao/kpi").then(r => r.json()).catch(() => ({})),
      fetch("/api/manutencao/pendentes").then(r => r.json()).catch(() => ({ manutencoes: [] })),
      fetch("/api/manutencao/alertas").then(r => r.json()).catch(() => ({ alertas: [] })),
    ]).then(([d, p, a]) => {
      setDash(d);
      setPendentes(p.manutencoes || []);
      setAlertas(a.alertas || []);
    }).finally(() => setLoading(false));
  }, []);

  const pendentesPorPrioridade = (p: number) => pendentes.filter((m: any) => m.prioridade === p).length;

  if (loading) return <div className="p-6 text-neutral-500">Carregando...</div>;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Manutencao</h1>
        <p className="text-xs text-neutral-500 mt-1">Agendamento, pendentes, KPIs e MTBF de equipamentos</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Pendentes</p>
          <p className="text-xl font-bold text-amber-400">{dash?.pendentes ?? pendentes.length}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Concluidas (30d)</p>
          <p className="text-xl font-bold text-emerald-400">{dash?.concluidas_periodo ?? 0}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">MTBF Medio (h)</p>
          <p className="text-xl font-bold text-blue-400">{dash?.mtbf_medio_horas ?? "—"}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Alertas Ativos</p>
          <p className="text-xl font-bold text-red-400">{alertas.length}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Priorid. Alta</p>
          <p className="text-xl font-bold text-red-400">{pendentesPorPrioridade(1)}</p>
        </div>
      </div>

      {pendentes.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-neutral-300 mb-3">Pendentes</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead><tr className="border-b border-neutral-800 text-neutral-500">
                <th className="text-left p-2">OS</th><th className="text-left p-2">Equipamento</th><th className="text-left p-2">Tipo</th><th className="text-left p-2">Prioridade</th><th className="text-left p-2">Data</th>
              </tr></thead>
              <tbody>
                {pendentes.map((m: any, i: number) => (
                  <tr key={i} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                    <td className="p-2 text-neutral-300">{m.numero || m.id}</td>
                    <td className="p-2 text-neutral-400">{m.equipamento_tipo} #{m.equipamento_id}</td>
                    <td className="p-2"><span className="px-1.5 py-0.5 rounded text-[10px] bg-neutral-700 text-neutral-400">{m.tipo}</span></td>
                    <td className="p-2">
                      <span className={m.prioridade <= 2 ? "text-red-400" : m.prioridade === 3 ? "text-amber-400" : "text-neutral-500"}>
                        {m.prioridade === 1 ? "Critica" : m.prioridade === 2 ? "Alta" : m.prioridade === 3 ? "Media" : "Baixa"}
                      </span>
                    </td>
                    <td className="p-2 text-neutral-500">{m.data_agendada ? fmtDataBR(m.data_agendada) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {alertas.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-neutral-300 mb-3">Alertas</h2>
          <div className="space-y-2">
            {alertas.map((a: any, i: number) => (
              <div key={i} className="bg-neutral-900 border border-neutral-800 rounded-lg px-4 py-2 flex items-center gap-3">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" />
                <span className="bg-red-500/10 text-red-400 border border-red-500/30 px-2 py-0.5 rounded text-[10px]">{a.tipo || "alerta"}</span>
                <span className="text-xs text-neutral-300 flex-1">{a.mensagem}</span>
                <span className="text-[10px] text-neutral-500">{a.data ? fmtDataBR(a.data) : ""}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
