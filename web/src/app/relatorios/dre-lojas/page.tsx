"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { DreLoja } from "@/lib/api";

function fmtBRL(v: number) {
  return "R$ " + Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function DreLojasPage() {
  const [data, setData] = useState<DreLoja[]>([]);
  const [dias, setDias] = useState(30);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async (d: number) => {
    setLoading(true);
    setErro(null);
    try {
      const r = await api.relatorioDrePorLoja(d);
      setData(r.data || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar DRE por loja");
      setData([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { carregar(dias); }, [dias, carregar]);

  const total = data.reduce((s, l) => ({
    receita: s.receita + l.receita,
    lucro: s.lucro + l.lucro,
    comissao: s.comissao + l.comissao_valor,
    frete: s.frete + l.frete,
  }), { receita: 0, lucro: 0, comissao: 0, frete: 0 });

  const temCustoAlocado = data.some(l => l.custos_producao_alocado && l.custos_producao > 0);

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">DRE por Loja</h1>
          <p className="text-xs text-neutral-500 mt-1">Receita, custos e lucro real de cada canal</p>
        </div>
        <select value={dias} onChange={e => setDias(Number(e.target.value))}
          className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200">
          {[7, 15, 30, 60, 90].map(d => <option key={d} value={d}>Últimos {d} dias</option>)}
        </select>
      </div>

      {erro && (
        <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erro}</div>
      )}

      {!loading && !erro && data.length > 0 && (
        <div className="instrument-enter grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="instrument-hover bg-neutral-800 border border-neutral-700 rounded-lg p-4">
            <p className="text-xs text-neutral-500">Receita Total</p>
            <p className="text-xl font-bold text-emerald-400 numeric">{fmtBRL(total.receita)}</p>
          </div>
          <div className="instrument-hover bg-neutral-800 border border-neutral-700 rounded-lg p-4">
            <p className="text-xs text-neutral-500">Comissão Shopee</p>
            <p className="text-xl font-bold text-amber-400 numeric">{fmtBRL(total.comissao)}</p>
          </div>
          <div className="instrument-hover bg-neutral-800 border border-neutral-700 rounded-lg p-4">
            <p className="text-xs text-neutral-500">Frete Total</p>
            <p className="text-xl font-bold text-blue-400 numeric">{fmtBRL(total.frete)}</p>
          </div>
          <div className="instrument-hover bg-neutral-800 border border-neutral-700 rounded-lg p-4">
            <p className="text-xs text-neutral-500">Lucro Líquido</p>
            <p className={`text-xl font-bold numeric ${total.lucro >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {fmtBRL(total.lucro)}
            </p>
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-neutral-500 text-sm">Carregando...</p>
      ) : erro ? null : data.length === 0 ? (
        <p className="text-neutral-500 text-sm">Nenhuma loja com dados no período.</p>
      ) : (
        <>
          <div className="instrument-enter bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-xs">
                  <th className="text-left p-3">Loja</th>
                  <th className="text-right p-3">Vendas</th>
                  <th className="text-right p-3">Receita</th>
                  <th className="text-right p-3" title="Só incide sobre a parte da receita que é Shopee — vendas Bling/loja física não pagam comissão de marketplace">Comissão</th>
                  <th className="text-right p-3">Frete</th>
                  <th className="text-right p-3" title="Sem rastreio de custo de produção por loja (fábrica única) — valor alocado proporcionalmente pela participação de cada loja na receita do período">Custos*</th>
                  <th className="text-right p-3">Lucro</th>
                  <th className="text-right p-3">Margem</th>
                </tr>
              </thead>
              <tbody>
                {data.map(l => (
                  <tr key={l.loja_id} className="instrument-hover border-b border-neutral-800/50">
                    <td className="p-3 text-neutral-200 font-medium">{l.loja_nome}</td>
                    <td className="p-3 text-right text-neutral-400 numeric">{l.qtd_vendas}</td>
                    <td className="p-3 text-right text-emerald-400 numeric">{fmtBRL(l.receita)}</td>
                    <td className="p-3 text-right text-amber-400 numeric">{fmtBRL(l.comissao_valor)}</td>
                    <td className="p-3 text-right text-blue-400 numeric">{fmtBRL(l.frete)}</td>
                    <td className="p-3 text-right text-neutral-400 numeric">{fmtBRL(l.custos_producao)}</td>
                    <td className={`p-3 text-right font-bold numeric ${l.lucro >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {fmtBRL(l.lucro)}
                    </td>
                    <td className="p-3 text-right">
                      <span className={`px-2 py-0.5 rounded text-xs ${l.margem_pct >= 20 ? "bg-emerald-900/30 text-emerald-400" : l.margem_pct >= 0 ? "bg-amber-900/30 text-amber-400" : "bg-red-900/30 text-red-400"}`}>
                        {l.margem_pct}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {temCustoAlocado && (
            <p className="text-[11px] text-neutral-600">* Custo de produção não é rastreado por loja (fábrica única) — valor alocado proporcionalmente pela participação de cada loja na receita do período, não é medição direta.</p>
          )}
        </>
      )}
    </div>
  );
}
