"use client";

import { useState, useEffect, useCallback } from "react";
import DateRangePicker from "@/app/_components/DateRangePicker";

function fmtDataIso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

interface QuebraCaixa {
  id: number;
  numero: string | null;
  operador_fechamento: string | null;
  loja_id: number | null;
  saldo_inicial: number;
  saldo_final: number;
  diferenca: number;
  data_abertura: string;
  data_fechamento: string;
}

export default function QuebraCaixaPage() {
  const [dataFim, setDataFim] = useState(() => fmtDataIso(new Date()));
  const [dataInicio, setDataInicio] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 90);
    return fmtDataIso(d);
  });
  const dias = Math.max(1, Math.round((new Date(dataFim).getTime() - new Date(dataInicio).getTime()) / 86400000) + 1);
  const [operador, setOperador] = useState("");
  const [quebras, setQuebras] = useState<QuebraCaixa[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const q = new URLSearchParams({ dias: String(dias) });
      if (operador) q.set("operador", operador);
      const r = await fetch(`/api/pdv/quebras-caixa?${q}`).then(res => res.json());
      setQuebras(r.quebras || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }, [dias, operador]);

  useEffect(() => { carregar(); }, [carregar]);

  const porOperador = quebras.reduce((acc: Record<string, { total: number; eventos: number }>, q) => {
    const key = q.operador_fechamento || "—";
    if (!acc[key]) acc[key] = { total: 0, eventos: 0 };
    acc[key].total += q.diferenca;
    acc[key].eventos += 1;
    return acc;
  }, {});

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-lg font-light text-neutral-300">Quebra de Caixa — Histórico</h1>
          <p className="text-xs text-neutral-500 mt-0.5">Diferença entre o saldo esperado e o saldo conferido em cada fechamento de caixa.</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            value={operador} onChange={e => setOperador(e.target.value)}
            placeholder="Filtrar por operador"
            className="bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-1.5 text-xs text-neutral-300"
          />
          <DateRangePicker
            dataInicio={dataInicio}
            dataFim={dataFim}
            onChange={(inicio, fim) => {
              setDataInicio(inicio);
              setDataFim(fim);
            }}
          />
        </div>
      </div>

      {erro && <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>}

      {loading ? (
        <div className="text-neutral-500 text-sm">Carregando...</div>
      ) : (
        <>
          <section>
            <h2 className="text-sm font-medium text-neutral-400 mb-2">Resumo por operador</h2>
            {Object.keys(porOperador).length === 0 ? (
              <div className="text-neutral-500 text-xs">Nenhum fechamento no período.</div>
            ) : (
              <div className="overflow-x-auto border border-neutral-800 rounded-lg">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-neutral-900 text-neutral-400 text-left">
                      <th className="px-3 py-2 font-medium">Operador</th>
                      <th className="px-3 py-2 font-medium text-right">Fechamentos</th>
                      <th className="px-3 py-2 font-medium text-right">Quebra acumulada</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(porOperador).sort((a, b) => Math.abs(b[1].total) - Math.abs(a[1].total)).map(([op, dados]) => (
                      <tr key={op} className="border-t border-neutral-800 text-neutral-300">
                        <td className="px-3 py-2 font-medium text-neutral-200">{op}</td>
                        <td className="px-3 py-2 text-right numeric">{dados.eventos}</td>
                        <td className={`px-3 py-2 text-right numeric ${dados.total < 0 ? "text-red-400" : dados.total > 0 ? "text-emerald-400" : "text-neutral-500"}`}>
                          {dados.total > 0 ? "+" : ""}R$ {dados.total.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section>
            <h2 className="text-sm font-medium text-neutral-400 mb-2">Histórico detalhado</h2>
            {quebras.length === 0 ? (
              <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-8 text-center text-neutral-500 text-xs">Nenhum fechamento encontrado</div>
            ) : (
              <div className="overflow-x-auto border border-neutral-800 rounded-lg">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-neutral-900 text-neutral-400 text-left">
                      <th className="px-3 py-2 font-medium">Caixa</th>
                      <th className="px-3 py-2 font-medium">Operador</th>
                      <th className="px-3 py-2 font-medium text-right">Saldo inicial</th>
                      <th className="px-3 py-2 font-medium text-right">Saldo final</th>
                      <th className="px-3 py-2 font-medium text-right">Diferença</th>
                      <th className="px-3 py-2 font-medium">Fechado em</th>
                    </tr>
                  </thead>
                  <tbody>
                    {quebras.map(q => (
                      <tr key={q.id} className="border-t border-neutral-800 text-neutral-300">
                        <td className="px-3 py-2 font-mono">{q.numero || `#${q.id}`}</td>
                        <td className="px-3 py-2">{q.operador_fechamento || "—"}</td>
                        <td className="px-3 py-2 text-right numeric">R$ {Number(q.saldo_inicial).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                        <td className="px-3 py-2 text-right numeric">R$ {Number(q.saldo_final).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                        <td className={`px-3 py-2 text-right numeric ${q.diferenca < 0 ? "text-red-400" : q.diferenca > 0 ? "text-emerald-400" : "text-neutral-500"}`}>
                          {q.diferenca > 0 ? "+" : ""}R$ {Number(q.diferenca).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                        <td className="px-3 py-2 text-neutral-500">{q.data_fechamento ? new Date(q.data_fechamento).toLocaleString("pt-BR") : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
