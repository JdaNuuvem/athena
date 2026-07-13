"use client";

import { useEffect, useState } from "react";
import Spinner from "./shared/Spinner";
import Alert from "./shared/Alert";
import { resumoVendasBling, BlingResumoVendas } from "@/lib/api";

export default function BlingVendasTab() {
  const [resumo, setResumo] = useState<BlingResumoVendas | null>(null);
  const [dias, setDias] = useState(30);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    async function carregar() {
      try {
        setLoading(true);
        setErro(null);
        const r = await resumoVendasBling(dias);
        setResumo(r);
      } catch (e) {
        setErro(e instanceof Error ? e.message : "Erro ao carregar analytics");
      } finally {
        setLoading(false);
      }
    }
    carregar();
  }, [dias]);

  if (loading) return <Spinner />;
  if (erro) return <Alert message={erro} type="error" />;
  if (!resumo || resumo.vendas_diarias.length === 0) {
    return <Alert message="Sem dados de vendas no período" type="info" />;
  }

  const valores = resumo.vendas_diarias.map(([, v]) => v);
  const maxValor = Math.max(...valores, 1);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <label className="text-xs text-neutral-400">Período:</label>
        {[7, 15, 30, 60, 90].map((d) => (
          <button key={d} onClick={() => setDias(d)}
            className={`px-3 py-1 text-xs rounded-lg transition-colors ${dias === d ? "bg-indigo-600 text-white" : "bg-neutral-700 text-neutral-300 hover:bg-neutral-600"}`}>
            {d}d
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3">
          <p className="text-[10px] text-neutral-500">Receita Total</p>
          <p className="text-sm font-semibold text-emerald-400">R$ {resumo.total_receita.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3">
          <p className="text-[10px] text-neutral-500">Pedidos</p>
          <p className="text-sm font-semibold text-neutral-100">{resumo.total_pedidos}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3">
          <p className="text-[10px] text-neutral-500">Média Diária</p>
          <p className="text-sm font-semibold text-neutral-100">R$ {(resumo.total_receita / Math.max(resumo.dias_analisados, 1)).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3">
          <p className="text-[10px] text-neutral-500">Ticket Médio</p>
          <p className="text-sm font-semibold text-neutral-100">R$ {(resumo.total_pedidos > 0 ? resumo.total_receita / resumo.total_pedidos : 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</p>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-neutral-200 mb-3">Vendas Diárias ({resumo.dias_analisados} dias)</h3>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <div className="flex items-end gap-[2px] h-40">
            {resumo.vendas_diarias.map(([data, valor]) => {
              const altura = Math.max((valor / maxValor) * 100, 2);
              return (
                <div key={data} className="flex-1 min-w-[4px] group relative" title={`${data}: R$ ${valor.toFixed(2)}`}>
                  <div className="w-full bg-indigo-500 rounded-t-sm hover:bg-indigo-400 transition-colors" style={{ height: `${altura}%` }} />
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-10">
                    <div className="bg-neutral-900 border border-neutral-600 rounded px-2 py-1 text-[10px] whitespace-nowrap">
                      <p className="text-neutral-200">{data}</p>
                      <p className="text-emerald-400">R$ {valor.toFixed(2)}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex justify-between mt-2 text-[10px] text-neutral-500">
            <span>{resumo.vendas_diarias[0]?.[0]}</span>
            <span>{resumo.vendas_diarias[Math.floor(resumo.vendas_diarias.length / 2)]?.[0]}</span>
            <span>{resumo.vendas_diarias[resumo.vendas_diarias.length - 1]?.[0]}</span>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-neutral-200 mb-2">Top SKUs</h3>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400">
                <th className="text-left p-2">#</th>
                <th className="text-left p-2">SKU</th>
                <th className="text-right p-2">Qtd</th>
                <th className="text-right p-2">Receita</th>
              </tr>
            </thead>
            <tbody>
              {resumo.top_skus.slice(0, 10).map((item, i) => (
                <tr key={item.sku} className="border-b border-neutral-700/50">
                  <td className="p-2 text-neutral-500">{i + 1}</td>
                  <td className="p-2 text-neutral-200 font-mono">{item.sku}</td>
                  <td className="p-2 text-right text-neutral-300">{item.quantidade}</td>
                  <td className="p-2 text-right text-emerald-400">R$ {item.receita.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
