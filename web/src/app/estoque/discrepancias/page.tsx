"use client";

import { useState, useEffect, useCallback } from "react";
import { api, type EstoqueDiscrepanciaLoja, type EstoqueDiscrepanciaOperador } from "@/lib/api";
import DivergenciaSaldo from "./_components/DivergenciaSaldo";
import DateRangePicker from "@/app/_components/DateRangePicker";

function fmtDataIso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export default function DiscrepanciasEstoquePage() {
  const [dataFim, setDataFim] = useState(() => fmtDataIso(new Date()));
  const [dataInicio, setDataInicio] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return fmtDataIso(d);
  });
  const dias = Math.max(1, Math.round((new Date(dataFim).getTime() - new Date(dataInicio).getTime()) / 86400000) + 1);
  const [porLoja, setPorLoja] = useState<EstoqueDiscrepanciaLoja[]>([]);
  const [porOperador, setPorOperador] = useState<EstoqueDiscrepanciaOperador[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.estoqueRelatorioDiscrepancias(dias);
      setPorLoja(r.por_loja || []);
      setPorOperador(r.por_operador || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar relatorio");
    } finally {
      setLoading(false);
    }
  }, [dias]);

  useEffect(() => { carregar(); }, [carregar]);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-lg font-light text-neutral-300">Discrepâncias — Por Loja e Operador</h1>
          <p className="text-xs text-neutral-500 mt-0.5">
            Agrega saídas grandes aprovadas, transferências com discrepância e faltas em contagem cíclica — não substitui investigação, aponta onde olhar.
          </p>
        </div>
        <DateRangePicker
          dataInicio={dataInicio}
          dataFim={dataFim}
          onChange={(inicio, fim) => {
            setDataInicio(inicio);
            setDataFim(fim);
          }}
        />
      </div>

      {erro && <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>}

      {loading ? (
        <div className="text-neutral-500 text-sm">Carregando...</div>
      ) : (
        <>
          <section>
            <h2 className="text-sm font-medium text-neutral-400 mb-2">Por loja</h2>
            {porLoja.length === 0 ? (
              <div className="text-neutral-500 text-xs">Nenhuma discrepância no período.</div>
            ) : (
              <div className="overflow-x-auto border border-neutral-800 rounded-lg">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-neutral-900 text-neutral-400 text-left">
                      <th className="px-3 py-2 font-medium">Loja</th>
                      <th className="px-3 py-2 font-medium text-right">Saídas grandes aprovadas</th>
                      <th className="px-3 py-2 font-medium text-right">Eventos</th>
                      <th className="px-3 py-2 font-medium text-right">Transferências c/ discrepância</th>
                      <th className="px-3 py-2 font-medium text-right">Contagens com falta</th>
                      <th className="px-3 py-2 font-medium text-right">Unidades faltantes (contagem)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {porLoja.map(l => (
                      <tr key={l.loja} className="border-t border-neutral-800 text-neutral-300">
                        <td className="px-3 py-2 font-medium text-neutral-200">{l.loja}</td>
                        <td className="px-3 py-2 text-right numeric text-amber-400">{l.saidas_aprovadas_qtd}</td>
                        <td className="px-3 py-2 text-right numeric">{l.saidas_aprovadas_eventos}</td>
                        <td className="px-3 py-2 text-right numeric text-orange-400">{l.transferencias_com_discrepancia}</td>
                        <td className="px-3 py-2 text-right numeric">{l.contagens_com_falta}</td>
                        <td className="px-3 py-2 text-right numeric text-red-400">{l.unidades_falta_contagem}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section>
            <h2 className="text-sm font-medium text-neutral-400 mb-2">Por operador</h2>
            {porOperador.length === 0 ? (
              <div className="text-neutral-500 text-xs">Nenhuma discrepância no período.</div>
            ) : (
              <div className="overflow-x-auto border border-neutral-800 rounded-lg">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-neutral-900 text-neutral-400 text-left">
                      <th className="px-3 py-2 font-medium">Operador</th>
                      <th className="px-3 py-2 font-medium text-right">Saídas grandes solicitadas</th>
                      <th className="px-3 py-2 font-medium text-right">Aprovadas (un)</th>
                      <th className="px-3 py-2 font-medium text-right">Rejeitadas</th>
                      <th className="px-3 py-2 font-medium text-right">Contagens com falta</th>
                      <th className="px-3 py-2 font-medium text-right">Unidades faltantes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {porOperador.map(o => (
                      <tr key={o.operador} className="border-t border-neutral-800 text-neutral-300">
                        <td className="px-3 py-2 font-medium text-neutral-200">{o.operador}</td>
                        <td className="px-3 py-2 text-right numeric">{o.saidas_grandes_solicitadas}</td>
                        <td className="px-3 py-2 text-right numeric text-amber-400">{o.saidas_grandes_aprovadas_qtd}</td>
                        <td className="px-3 py-2 text-right numeric text-red-400">{o.saidas_grandes_rejeitadas}</td>
                        <td className="px-3 py-2 text-right numeric">{o.contagens_com_falta}</td>
                        <td className="px-3 py-2 text-right numeric text-red-400">{o.unidades_falta_contagem}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section>
            <DivergenciaSaldo />
          </section>
        </>
      )}
    </div>
  );
}
